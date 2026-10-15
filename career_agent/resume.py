"""Local-only résumé (CV) import: read a PDF or DOCX on this device and propose profile values.

Design rules this module follows, and the reasons
-------------------------------------------------
* **Local only.** The selected file is read from disk and parsed in this process. Nothing is sent
  anywhere: no network call, no hosted parser, no LLM, no OCR service. The only third-party code is
  :mod:`pypdf` (BSD-3-Clause) and it is imported lazily, so the application still runs, and DOCX
  import still works, when it is not installed.
* **The document is untrusted input.** It is read with a hard size limit before parsing, DOCX parts
  are decompressed only within a declared-size budget, embedded macros and objects are never opened,
  and a DOCX carrying a DTD is refused rather than handed to an XML parser that expands entities.
* **Nothing is retained.** The extracted text is used to build proposals and then dropped: the
  returned :class:`ResumeParseResult` carries short evidence snippets and a character count, never the
  document text, and no copy of the source file is written anywhere. The caller saves a proposal only
  after the person reviews and confirms it.
* **No invented values.** Every proposal quotes the line it came from, keeps its own confidence, and is
  dropped when the pattern is not matched. Missing information stays missing: it is never inferred
  from a date range, a city, a keyword in the body of the document, or a template assumption.
* **Never a positive eligibility result.** This module writes no eligibility data and computes none.
  Values that feed eligibility checks (country, work authorization) are always marked *needs review*.

Field coverage is limited to what :class:`career_agent.core.CandidateProfile` can actually store. A
name, an email address, a phone number or a link has no column in that profile, so those are reported
as informational items instead of being smuggled into a field: showing them is honest, inventing a
schema for them is not.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence
from xml.etree import ElementTree

try:  # optional: PDF import needs it, everything else works without it
    import pypdf
except Exception:  # pragma: no cover - exercised by the "not installed" behaviour test
    pypdf = None
else:
    # pypdf logs structural complaints about a damaged file (and can quote fragments of it) straight
    # to stderr. This application reports every outcome itself, in its own words, so those records are
    # dropped instead of being printed to a terminal where they would outlive the moment.
    _pypdf_logger = logging.getLogger("pypdf")
    _pypdf_logger.addHandler(logging.NullHandler())
    _pypdf_logger.propagate = False

#: Whether PDF import is available in this installation (DOCX import never depends on it).
PDF_SUPPORT_AVAILABLE = pypdf is not None

#: Largest résumé accepted, checked before the file is read. A résumé is a few pages of text; this
#: leaves room for a heavy scan while refusing a file that is not one, without reading it.
MAX_RESUME_BYTES = 10 * 1024 * 1024

#: Largest total uncompressed size of the DOCX parts this module reads. A ZIP can declare far more
#: than its file size suggests, so the declared sizes are checked before anything is decompressed.
MAX_DOCX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024

#: Largest number of pages read from a PDF (a résumé is one to three). A longer file is refused
#: rather than partially parsed: a document read only in part must never look like a full import.
MAX_PDF_PAGES = 40

#: Largest amount of text a chosen document may produce. Documents over this are refused, not
#: truncated, so no proposal is ever made from a document that was only partly read.
MAX_EXTRACTED_CHARACTERS = 400_000

#: Longest evidence snippet kept for a proposal. Enough to recognise the source line, short enough
#: that the review screen shows a quotation rather than the document.
MAX_EVIDENCE_CHARACTERS = 160

#: Longest informational value (name, email, phone, link) kept for display.
MAX_UNMAPPED_CHARACTERS = 120

_WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCX_DOCUMENT_PART = "word/document.xml"
_DOCX_MACRO_PART = "word/vbaProject.bin"
#: The ZIP general-purpose bit that marks one entry as encrypted (a password-protected re-save).
_ZIP_ENCRYPTED_FLAG = 0x1
#: The ZIP compression methods this build can decompress (the set the ``zipfile`` module supports).
#: A part written with anything else - AES, for instance, which another tool may use - is refused with
#: its own message instead of raising ``NotImplementedError`` from inside the archive reader.
_SUPPORTED_ZIP_METHODS = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA)
_OLE_CONTAINER_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class ResumeImportError(Exception):
    """A résumé could not be imported. The message is written to be shown to the user.

    Messages never contain document text, contact details or file-system locations: only the file
    name, what was wrong with the file, and what the person can do next.
    """


class ResumeTooLarge(ResumeImportError):
    """The file, or the work it would take to read it, exceeds a documented limit."""


class ResumeUnreadable(ResumeImportError):
    """The file is not a document of its type, or is damaged."""


class ResumeEncrypted(ResumeImportError):
    """The document is password-protected (or otherwise encrypted) and cannot be read here."""


class ResumeNoText(ResumeImportError):
    """The document holds no selectable text (for example a scan of a printed résumé)."""


class DocumentFormat(str, Enum):
    """A document type this module can read."""

    PDF = "PDF"
    DOCX = "DOCX"


class ProposalConfidence(str, Enum):
    """How strong the evidence behind a proposed value is.

    ``CONFIDENT`` means the value was read from an explicit statement or a labelled section, so the
    review screen offers it selected. ``NEEDS_REVIEW`` means the value is plausible but the wording or
    the field's consequences (country and work authorization feed eligibility checks) demand a human
    decision, so the review screen shows it unselected.
    """

    CONFIDENT = "confident"
    NEEDS_REVIEW = "needs review"


@dataclass(frozen=True)
class FieldProposal:
    """One profile value suggested by a résumé, with the evidence that produced it.

    ``key`` is an existing profile form key (for example ``"graduation_year"``): the value is saved
    through the same validation pathway as a hand-typed entry. ``value`` is the string that would be
    written into that form field, so nothing here depends on a second vocabulary.
    """

    key: str
    label: str
    value: str
    confidence: ProposalConfidence
    evidence: str


@dataclass(frozen=True)
class UnmappedItem:
    """Something the document states that the stored profile has no field for.

    Reported for information only. Adding a column to the database for it would be a schema change
    nothing here needs, and putting it into an unrelated field would be inventing data.
    """

    label: str
    value: str
    note: str


@dataclass(frozen=True)
class ResumeParseResult:
    """What an import found. Deliberately never holds the extracted text."""

    file_name: str
    source_format: DocumentFormat
    proposals: tuple[FieldProposal, ...] = ()
    unmapped: tuple[UnmappedItem, ...] = ()
    notes: tuple[str, ...] = ()
    text_characters: int = 0

    @property
    def proposed_keys(self) -> tuple[str, ...]:
        return tuple(proposal.key for proposal in self.proposals)


@dataclass(frozen=True)
class ExtractedDocument:
    """Text extracted from one document, plus what the caller must not claim about it."""

    source_format: DocumentFormat
    text: str
    notes: tuple[str, ...] = field(default_factory=tuple)


#: Labels for the profile fields this module can propose, in the order the form shows them. Used to
#: report fields the document did not mention at all, so "not found" is visible instead of silent.
PROFILE_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("country", "Country"),
    ("degree", "Degree / discipline"),
    ("study_status", "Study status"),
    ("graduation_year", "Graduation year"),
    ("experience", "Experience years"),
    ("work_authorization", "Work authorization"),
    ("skills", "Skills"),
    ("locations", "Preferred locations"),
    ("work_modes", "Preferred work modes"),
    ("role_types", "Preferred role types"),
)

#: Fields a résumé can supply; the preference fields are choices, not facts a document can prove.
RESUMABLE_FIELD_KEYS: tuple[str, ...] = (
    "country", "degree", "study_status", "graduation_year", "experience", "work_authorization", "skills",
)

_STUDY_STATUS_CHOICES = ("undergraduate", "graduate", "postgraduate", "doctoral", "graduated", "other")

#: Countries recognised on an explicit location line. A fixed list keeps this deterministic and
#: reviewable: the alternative (guessing from a city or from a template) invents facts, and country
#: feeds eligibility checks.
_KNOWN_COUNTRIES: tuple[tuple[str, str], ...] = (
    ("India", "india"),
    ("United States", "united states", "usa", "u.s.a.", "us"),
    ("United Kingdom", "united kingdom", "uk", "u.k.", "england", "scotland", "wales"),
    ("Canada", "canada"),
    ("Germany", "germany"),
    ("France", "france"),
    ("Netherlands", "netherlands", "the netherlands"),
    ("Ireland", "ireland"),
    ("Switzerland", "switzerland"),
    ("Sweden", "sweden"),
    ("Spain", "spain"),
    ("Italy", "italy"),
    ("Poland", "poland"),
    ("Australia", "australia"),
    ("New Zealand", "new zealand"),
    ("Singapore", "singapore"),
    ("Japan", "japan"),
    ("South Korea", "south korea", "korea"),
    ("China", "china"),
    ("United Arab Emirates", "united arab emirates", "uae", "u.a.e."),
    ("Saudi Arabia", "saudi arabia"),
    ("Brazil", "brazil"),
    ("Mexico", "mexico"),
    ("South Africa", "south africa"),
    ("Nigeria", "nigeria"),
    ("Kenya", "kenya"),
    ("Pakistan", "pakistan"),
    ("Bangladesh", "bangladesh"),
    ("Sri Lanka", "sri lanka"),
    ("Nepal", "nepal"),
)

#: Section headings a résumé may use. Each pattern is anchored at the start of the line and kept
#: deliberately small: a heading is a few words, so these are matched against short lines only, and a
#: word that merely appears in a sentence never opens a section.
_SECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "skills",
        re.compile(
            r"^(?:technical|key|core|professional|relevant|additional|other|computer|software|it|soft|"
            r"hard)\s+skills?\b"
            # A discipline or domain word before "skills" states the same thing: a résumé that writes
            # "LABORATORY SKILLS", "CLINICAL SKILLS" or "ANALYTICAL SKILLS" has a skills heading, and
            # before this the list below was invisible and the import reported no skills heading at all.
            r"|^(?:laboratory|lab|clinical|research|engineering|analytical|quantitative|design|creative|"
            r"business|marketing|sales|finance|financial|accounting|data|hardware|electronics|mechanical|"
            r"civil|medical|scientific|domain|functional|practical|transferable)\s+skills?\b"
            # "Skill Set" must match as a whole before the bare "skill" alternative can claim it and
            # leave "Set" looking like a value.
            r"|^skill\s?sets?\b|^skills?\b"
            r"|^areas?\s+of\s+expertise\b|^(?:technical|core)\s+expertise\b|^expertise\b"
            r"|^(?:core|key)\s+competenc(?:y|ies)\b|^competenc(?:y|ies)\b"
            r"|^(?:technical|core)\s+proficienc(?:y|ies)\b|^proficienc(?:y|ies)\b"
            r"|^technolog(?:y|ies)\b|^tech\s+stack\b|^stack\s+of\s+tools\b"
            r"|^tools?\b|^abilities\b|^strengths\b"
            r"|^(?:programming|query|scripting|markup|database)\s+languages?\b"
            # "Software & Tools", "Tools and Technologies", "Core Competencies & Expertise": a short
            # leading word joined by &/and to one of the words a skills heading is made of.
            r"|^[A-Za-z][A-Za-z /\-]{0,24}(?:&|and)\s*(?:skills?|tools?|technolog(?:y|ies)|techniques"
            r"|competenc(?:y|ies)|expertise|proficienc(?:y|ies)|languages?)\b",
            re.I,
        ),
    ),
    (
        "education",
        re.compile(
            r"^education\b|^academics?\b|^academic\s+(?:qualifications?|background|credentials?)\b"
            r"|^(?:educational\s+)?qualifications?\b",
            re.I,
        ),
    ),
    (
        "experience",
        re.compile(
            r"^(?:work|professional|relevant|industry|employment|career|practical|hands[\s-]on)\s+"
            r"(?:experience|history|background)\b"
            r"|^experience\b|^employment\b",
            re.I,
        ),
    ),
    (
        "summary",
        re.compile(
            r"^(?:professional|career|executive)\s+(?:summary|profile|objective)\b"
            r"|^(?:summary|profile|objective|about(?:\s+me)?|overview|highlights)\b",
            re.I,
        ),
    ),
    # Two headings that name a field this module *proposes* (country and work authorization) have to be
    # headings here as well, or their wording is read as content of whatever section they interrupt -
    # measured: "WORK AUTHORIZATION" put "Authorized to work in India" into the skills proposal as a
    # confident value, "COUNTRY" put the country itself there, and that value then feeds eligibility
    # checks offered as a skill. The vocabulary is the same one ``_LABEL_PATTERNS`` uses, so a document
    # spelling its heading either way is understood the same way.
    (
        "work_authorization",
        re.compile(
            r"^(?:work\s+)?(?:authorization|authorisation)\b|^visa\s+status\b|^immigration\s+status\b"
            r"|^work\s+permit\b",
            re.I,
        ),
    ),
    (
        "location",
        re.compile(
            r"^country\b|^location\b|^address\b|^based\s+in\b|^current\s+location\b|^city\b",
            re.I,
        ),
    ),
    ("other", re.compile(r"^(?:(?:test|safety)\s+)*(?:notes?|notices?|disclaimers?)\b|^(?:projects?|certifications?|certificates?|awards?|achievements?|publications?|internships?|activities|volunteering|interests?|languages?|declaration|references?)\b", re.I)),
)

#: Degree abbreviations, by the discipline they belong to. The engineering/science/commerce set was the
#: first written and it was the whole list, which made the importer blind to design, architecture,
#: medicine, pharmacy, law, education and hospitality qualifications: a line such as "B.Des in Design,
#: 2026" produced neither a degree nor a graduation year, because the year rule needs a degree or an
#: institution on the line. Widened after the Phase 4 cross-industry evaluation measured it. An
#: abbreviation that is also an ordinary English word (``bed``, ``des``, ``arch``, ``pharm``) requires its
#: full stop, so prose cannot be read as a qualification; ``bed``-style words without the stop are left out
#: deliberately.
_DEGREE_PATTERN = re.compile(
    r"\b(?:b\.?\s?tech|b\.?\s?e\.?|b\.?\s?sc|b\.?\s?c\.?a|b\.?\s?com|b\.?\s?ba|bachelor(?:'s)?(?:\s+of)?|"
    r"m\.?\s?tech|m\.?\s?e\.?|m\.?\s?sc|m\.?\s?c\.?a|m\.?\s?com|m\.?\s?ba|master(?:'s)?(?:\s+of)?|"
    r"ph\.?\s?d\.?|doctorate|doctoral|diploma|postgraduate|b\.?\s?s\.?|m\.?\s?s\.?|"
    # arts degrees: "B.B.A." was recognised while "B.A." was not, which is the wrong way round
    r"b\.?\s?a\.?|m\.?\s?a\.?|"
    # design and fine art
    r"b\.\s?des|m\.\s?des|b\.?\s?f\.?\s?a|m\.?\s?f\.?\s?a|bachelor\s+of\s+(?:design|fine\s+arts)|"
    r"master\s+of\s+(?:design|fine\s+arts)|"
    # architecture and planning
    r"b\.\s?arch|m\.\s?arch|b\.\s?plan|m\.\s?plan|"
    # medicine and allied health
    r"mbbs|bds|b\.\s?pharm|m\.\s?pharm|pharm\.?\s?d|b\.?\s?n\.?\s?s\.?|bpt|b\.\s?mlt|b\.\s?o\.\s?t|"
    # law
    r"ll\.\s?b|ll\.\s?m|"
    # education
    r"b\.\s?ed|m\.\s?ed|"
    # hospitality, business and social work
    r"bhm|bhmct|pgdm|pgp|bsw|msw)\b",
    re.I,
)
_INSTITUTION_PATTERN = re.compile(
    r"\b(?:university|college|institute|institution|school|academy|iit|nit|iiit|bits|polytechnic)\b", re.I
)
_EXPLICIT_GRADUATION_PATTERN = re.compile(
    r"\b(?:expected|expecting|graduating|graduation|graduated|class\s+of|batch\s+of|passing|passout|passed\s+out)\b"
    r"[^0-9\n]{0,25}(\d{4})\b",
    re.I,
)
_BARE_YEAR_PATTERN = re.compile(r"\b(19|20)(\d{2})\b")
_EXPERIENCE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?"
    r"(?:relevant\s+|professional\s+|industry\s+|work\s+|full[- ]time\s+)?(?:experience|exp\b)",
    re.I,
)
_LABELLED_EXPERIENCE_PATTERN = re.compile(
    r"\b(?:total\s+)?(?:work\s+)?experience\s*[:\-]\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", re.I
)
_LABEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("country", re.compile(r"^\s*country\s*[:\-]\s*(.+)$", re.I)),
    ("location", re.compile(r"^\s*(?:location|address|based\s+in|current\s+location|city)\s*[:\-]\s*(.+)$", re.I)),
    ("work_authorization", re.compile(
        r"^\s*(?:work\s+authorization|work\s+authorisation|authorization|authorisation|visa\s+status|"
        r"immigration\s+status|work\s+permit)\s*[:\-]\s*(.+)$", re.I)),
)
_EMAIL_PATTERN = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?:(?:\+|00)\d{1,3}[\s\-.]?)?(?:\(?\d{2,5}\)?[\s\-.]?)\d{3,5}[\s\-.]?\d{3,5}\b")
_LINK_PATTERN = re.compile(r"(?:https?://|www\.)\S+|(?:linkedin\.com|github\.com)/\S+", re.I)
_NAME_LINE_PATTERN = re.compile(r"^[A-Z][A-Za-z'`.-]*(?:\s+[A-Z][A-Za-z'`.-]*){1,3}$")
_DEGREE_NOISE = frozenset({
    "and", "of", "the", "in", "with", "for", "from", "at", "to", "a", "an", "my", "expected",
    "graduation", "graduate", "pursuing", "completed", "current", "currently", "student", "final",
    "year", "years", "cgpa", "gpa", "percentage", "score", "marks", "grade",
})
_AUTHORIZATION_PHRASES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bauthoriz(?:ed|ation)\s+to\s+work\b[^.\n]{0,80}", re.I),
    re.compile(r"\b(?:do\s+not\s+require|no\s+need\s+for|without)\s+(?:a\s+|any\s+)?sponsorship\b[^.\n]{0,40}", re.I),
    re.compile(r"\brequire\s+(?:a\s+|work\s+|visa\s+)?sponsorship\b[^.\n]{0,40}", re.I),
    re.compile(r"\b(?:permanent\s+resident|green\s+card|work\s+permit|student\s+visa|dependent\s+visa)\b[^.\n]{0,60}", re.I),
    re.compile(r"\b(?:citizen|national)\s+of\s+[A-Za-z][A-Za-z\s.]{2,40}", re.I),
)


#: Characters that may decorate a heading ("=== SKILLS ===", "* Skills *", "SKILLS ---") and the
#: bullets a text extractor leaves at the start of a list item. Stripped from the ends only.
_HEADING_DECORATION = "*_=#~>»«•·▪◦| \t-–—"

#: What may separate a heading from content that continues on the same line ("Skills: Python").
_HEADING_SEPARATORS = ":|•·/"

#: The separator ``_clean_line`` writes for a column gap or a tab, so it can be named in one place.
_COLUMN_SEPARATOR = " | "


def _clean_line(line: str) -> str:
    """Collapse whitespace in a line of extracted text, keeping column gaps, and strip bullets.

    A run of two or more spaces (or a tab) is how a text extractor reports the gap between two columns
    or between two table cells on one line, so it is kept as an explicit ``|`` separator rather than
    collapsed into a single space: collapsing it merges a heading with its own list and joins
    unrelated columns into one value. The separator matches what the DOCX extractor already emits
    between table cells.
    """
    spaced = re.sub(r"[ \t]{2,}", " | ", line.replace("\t", " | "))
    collapsed = re.sub(r"\s+", " ", spaced).strip()
    return collapsed.lstrip(_HEADING_DECORATION).strip()


def _snippet(line: str) -> str:
    """A short quotation of ``line`` for the review screen: enough to recognise, not the document."""
    clipped = _clean_line(line)[:MAX_EVIDENCE_CHARACTERS]
    return clipped.rstrip() + ("…" if len(_clean_line(line)) > MAX_EVIDENCE_CHARACTERS else "")


def _clipped(value: str, limit: int = MAX_UNMAPPED_CHARACTERS) -> str:
    text = _clean_line(value)
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


# --------------------------------------------------------------------------------------
# Extraction: reading a real document, locally
# --------------------------------------------------------------------------------------


def _read_bounded(path: Path, limit: int) -> bytes:
    """Read at most ``limit`` bytes, refusing a file that is larger instead of loading it.

    The size is checked again here even though the caller already stat()ed the file: a file can grow
    between the check and the read, and reading one byte over the limit is how that is detected
    without ever holding an unbounded amount of data.
    """
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ResumeTooLarge(
            f"{path.name} is larger than the {limit // (1024 * 1024)} MB limit for résumé import. "
            "Nothing was read past the limit; choose the file you meant to import."
        )
    return data


def _existing_file(path: Path) -> Path:
    """Validate the chosen path before anything is read from it."""
    if path.is_dir():
        raise ResumeUnreadable(f"{path.name} is a folder, not a résumé file.")
    if not path.exists():
        raise ResumeUnreadable(f"There is no file at {path.name}. Choose a PDF or DOCX résumé.")
    if not path.is_file():
        raise ResumeUnreadable(f"{path.name} is not a regular file that can be read.")
    size = path.stat().st_size
    if size == 0:
        raise ResumeUnreadable(f"{path.name} is empty (0 bytes), so it holds no résumé text.")
    if size > MAX_RESUME_BYTES:
        raise ResumeTooLarge(
            f"{path.name} is {size // 1024} KB, over the {MAX_RESUME_BYTES // (1024 * 1024)} MB limit "
            "for résumé import. A résumé is a few pages; check that you chose the right file."
        )
    return path


def _check_length(text: str, source: str) -> str:
    """Refuse (never truncate) text beyond the documented limit."""
    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise ResumeTooLarge(
            f"{source} produced more than {MAX_EXTRACTED_CHARACTERS:,} characters of text, far more "
            "than a résumé holds. Nothing was imported; check that you chose the right file."
        )
    return text


def extract_pdf(path: Path) -> ExtractedDocument:
    """Extract the embedded text of a PDF locally with :mod:`pypdf`."""
    if pypdf is None:
        raise ResumeImportError(
            "PDF import needs the optional 'pypdf' package, which is not installed in this Python. "
            "Install it (pip install pypdf) or import a DOCX résumé instead."
        )
    data = _read_bounded(path, MAX_RESUME_BYTES)
    if not data.lstrip()[:5].startswith(b"%PDF-"):
        raise ResumeUnreadable(
            f"{path.name} does not start like a PDF. If it is a different format, save it as PDF or "
            "DOCX and try again."
        )
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # An empty user password is common for files that merely restrict editing; trying it is a
            # local operation and costs nothing. A real password is never guessed at.
            try:
                unlocked = reader.decrypt("")
            except Exception:
                unlocked = 0
            if not unlocked:
                raise ResumeEncrypted(
                    f"{path.name} is password-protected, so its text cannot be read here. Export an "
                    "unprotected copy of the résumé, or type the values into the profile yourself."
                )
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            raise ResumeTooLarge(
                f"{path.name} has {len(pages)} pages, over the {MAX_PDF_PAGES}-page limit for résumé "
                "import. Refusing rather than reading part of the document."
            )
        notes: list[str] = []
        chunks: list[str] = []
        empty_pages = 0
        for page in pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                # One damaged page must not silently vanish: it is counted and reported as a note.
                page_text = ""
            if page_text.strip():
                chunks.append(page_text)
            else:
                empty_pages += 1
        if empty_pages:
            notes.append(
                f"{empty_pages} page(s) held no selectable text and contributed nothing."
            )
    except ResumeImportError:
        raise
    except Exception as exc:  # pypdf raises many unrelated types for damaged files
        raise ResumeUnreadable(
            f"{path.name} could not be read as a PDF ({type(exc).__name__}). The file may be damaged "
            "or only partly downloaded; try opening it in a PDF reader, then import it again."
        ) from exc
    text = _check_length("\n".join(chunks), path.name)
    if not text.strip():
        raise ResumeNoText(
            f"{path.name} holds no selectable text, so nothing could be read from it. This is what a "
            "scanned or photographed résumé looks like: this app does not include OCR. Type the "
            "values into the profile, or import a DOCX or a text-based PDF."
        )
    return ExtractedDocument(source_format=DocumentFormat.PDF, text=text, notes=tuple(notes))


def _docx_paragraph_text(paragraph: ElementTree.Element) -> str:
    """Text of one ``w:p`` element, without touching anything but real text runs."""
    pieces: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_WORD_NAMESPACE}t":
            pieces.append(node.text or "")
        elif node.tag in (f"{_WORD_NAMESPACE}tab",):
            pieces.append(" ")
        elif node.tag in (f"{_WORD_NAMESPACE}br", f"{_WORD_NAMESPACE}cr"):
            pieces.append("\n")
    return "".join(pieces)


def _docx_lines_for(element: ElementTree.Element) -> list[str]:
    """Lines for a paragraph, a table (rendered as rows of cells), or a container of either.

    Recursive on purpose: a résumé is as likely to lay its education or skills out in a table as in
    paragraphs, and a table cell can itself hold paragraphs or a nested table. A table row becomes one
    line whose cells are joined with ``|`` so the text stays readable and attributable.
    """
    if element.tag == f"{_WORD_NAMESPACE}p":
        return [_docx_paragraph_text(element)]
    if element.tag == f"{_WORD_NAMESPACE}tbl":
        lines: list[str] = []
        for row in element.findall(f"{_WORD_NAMESPACE}tr"):
            cells = [
                " ".join(line for line in _docx_lines_for(cell) if line.strip())
                for cell in row.findall(f"{_WORD_NAMESPACE}tc")
            ]
            lines.append(" | ".join(cell for cell in cells if cell.strip()))
        return lines
    lines = []
    for child in element:
        lines.extend(_docx_lines_for(child))
    return lines


def extract_docx(path: Path) -> ExtractedDocument:
    """Extract paragraph and table text from a DOCX locally, using only the standard library.

    The file is a ZIP of XML parts. Only ``word/document.xml`` is read; macros, embedded objects,
    images and external links are never opened or executed.
    """
    data = _read_bounded(path, MAX_RESUME_BYTES)
    if data.startswith(_OLE_CONTAINER_SIGNATURE):
        raise ResumeEncrypted(
            f"{path.name} is an encrypted Office file (or a legacy .doc), which this app cannot read. "
            "Open it in your word processor and save a copy as .docx, then import that."
        )
    if not data.startswith(b"PK"):
        raise ResumeUnreadable(
            f"{path.name} is not a DOCX file (a DOCX is a ZIP archive). Save the résumé as .docx and "
            "try again."
        )
    notes: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if _DOCX_DOCUMENT_PART not in names:
                raise ResumeUnreadable(
                    f"{path.name} has no {_DOCX_DOCUMENT_PART} part, so it is not a readable DOCX "
                    "document. Save it as .docx from your word processor and try again."
                )
            if _DOCX_MACRO_PART in names:
                # Reported so the person knows the macro was seen - and ignored, never run.
                notes.append("The document carries a macro project (vbaProject.bin); it was ignored.")
            document_info = archive.getinfo(_DOCX_DOCUMENT_PART)
            if document_info.flag_bits & _ZIP_ENCRYPTED_FLAG:
                # Word's own "password to open" produces an OLE container, which is handled above, but
                # a DOCX can also arrive as a ZIP whose member is encrypted (some archivers and online
                # converters do this). Reading it raises RuntimeError from the zipfile module, so it is
                # recognised here and refused with the same plain explanation as an encrypted Word file.
                raise ResumeEncrypted(
                    f"{path.name} is password-protected: its document part is stored encrypted. Export "
                    "an unprotected copy from your word processor, or type the values into the profile "
                    "yourself."
                )
            if document_info.compress_type not in _SUPPORTED_ZIP_METHODS:
                raise ResumeUnreadable(
                    f"{path.name} stores its document with a compression method this app cannot read "
                    f"(ZIP method {document_info.compress_type}). Open it in your word processor, save a "
                    "fresh copy as .docx, and import that."
                )
            declared = sum(
                info.file_size for info in archive.infolist()
                if info.filename in (_DOCX_DOCUMENT_PART,)
            )
            if declared > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ResumeTooLarge(
                    f"{path.name} declares {declared // (1024 * 1024)} MB of uncompressed text, over "
                    f"the {MAX_DOCX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB limit for résumé import. "
                    "Refusing rather than decompressing it."
                )
            with archive.open(_DOCX_DOCUMENT_PART) as part:
                raw = part.read(MAX_DOCX_UNCOMPRESSED_BYTES + 1)
    except ResumeImportError:
        raise
    except zipfile.BadZipFile as exc:
        raise ResumeUnreadable(
            f"{path.name} could not be opened as a DOCX archive, so it may be damaged or only partly "
            "downloaded. Open it in your word processor, save a fresh copy as .docx, and import that."
        ) from exc
    except Exception as exc:
        # Anything else the archive reader or the decompressor raises for a file that is not a plain,
        # readable DOCX (a damaged stream, a member this build cannot decompress, an error type that
        # varies by Python version) is reported as a refusal naming the failure type. ``parse_resume``
        # promises every failure here is a ResumeImportError: the desktop review flow catches that one
        # type, so anything else would reach a Tk callback that has no handler for it.
        raise ResumeUnreadable(
            f"{path.name} could not be read as a DOCX document ({type(exc).__name__}). The file may be "
            "password-protected or damaged, or saved by a tool this app cannot read. Open it in your "
            "word processor, save a fresh copy as .docx, and import that."
        ) from exc
    if len(raw) > MAX_DOCX_UNCOMPRESSED_BYTES:
        raise ResumeTooLarge(
            f"{path.name} expands to more than {MAX_DOCX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB, "
            "far more than a résumé holds. Refusing rather than reading it."
        )
    if b"<!doctype" in raw[:4096].lower():
        # Word never writes a DTD into a document part; refusing one keeps entity-expansion tricks
        # away from the XML parser instead of relying on the parser to be careful.
        raise ResumeUnreadable(f"{path.name} contains a document type declaration, so it was refused.")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise ResumeUnreadable(
            f"{path.name} could not be read as a DOCX document (its XML is not well formed). The file "
            "may be damaged; save a fresh copy and import that."
        ) from exc
    body = root.find(f"{_WORD_NAMESPACE}body")
    lines: list[str] = []
    if body is not None:
        lines.extend(_docx_lines_for(body))
    text = _check_length("\n".join(lines), path.name)
    if not text.strip():
        raise ResumeNoText(
            f"{path.name} holds no readable text (no paragraphs or table cells with text), so "
            "nothing could be read from it."
        )
    return ExtractedDocument(source_format=DocumentFormat.DOCX, text=text, notes=tuple(notes))


def extract_text(path: str | Path) -> ExtractedDocument:
    """Extract text from a local PDF or DOCX, choosing by extension and validating the content.

    Every failure raises :class:`ResumeImportError` with an actionable message; no document text,
    contact detail or file-system location is ever included in an error.
    """
    source = Path(path)
    try:
        _existing_file(source)
        suffix = source.suffix.lower()
        if suffix == ".pdf":
            return extract_pdf(source)
        if suffix == ".docx":
            return extract_docx(source)
        if suffix == ".doc":
            raise ResumeUnreadable(
                f"{source.name} is a legacy .doc file, which this app cannot read. Save it as .docx or "
                "PDF and import that."
            )
        raise ResumeUnreadable(
            f"{source.name} is not a supported résumé format. Choose a PDF or DOCX file."
        )
    except OSError as exc:
        # A permission problem or a file that vanished mid-read is reported as its own failure. The
        # message names the file, never the folder it lives in.
        raise ResumeUnreadable(
            f"{source.name} could not be opened (it may be unreadable or in use by another program). "
            "Check that you can open the file, then try again."
        ) from exc


# --------------------------------------------------------------------------------------
# Parsing: deterministic proposals, each with its evidence
# --------------------------------------------------------------------------------------


def _lines(text: str) -> list[str]:
    return [line for line in (_clean_line(raw) for raw in text.splitlines()) if line]


#: How long a heading may be. A paragraph that merely starts with the word "Experience" is not one.
_MAX_HEADING_CHARACTERS = 60

#: How long the content that shares a heading's line may be before it is treated as prose.
_MAX_INLINE_CONTENT_CHARACTERS = 120

#: A conjunction that joins two heading words ("SKILLS & INTERESTS", "SKILLS / TOOLS").
_LEADING_CONJUNCTION = re.compile(r"^(?:&|\+|/|,|;|and|or)\s*", re.I)

#: How ``_clean_line`` reports a run of two or more spaces: the gap between two columns or two table
#: cells on one extracted line. Named here because more than one reader has to interpret it.
_COLUMN_GAP = " | "

#: Names for a category *inside* a skills block ("Languages: Python, C++"). Their values are skills,
#: so such a line stays part of the skills section instead of closing it, and the label is dropped
#: before the values are read (the label is a category, not a skill).
_SKILLS_SUB_LABEL_NAMES = (
    r"(?:programming|query|scripting|markup|computer|spoken)\s+languages?", r"languages?",
    r"frameworks?", r"libraries", r"tools?", r"technolog(?:y|ies)", r"databases?", r"platforms?",
    r"cloud", r"devops", r"version\s+control", r"testing", r"methodolog(?:y|ies)", r"packages?",
    r"ides?", r"stacks?",
)
_SKILLS_SUB_LABEL = re.compile(r"^(?:" + "|".join(_SKILLS_SUB_LABEL_NAMES) + r")\b", re.I)
#: The same name followed by a separator and its values, as it appears on one line.
_LABELLED_SKILLS_LINE = re.compile(
    r"^(?:" + "|".join(_SKILLS_SUB_LABEL_NAMES) + r")\s*[:\-–—]\s*(.+)$", re.I
)


def _undecorated(text: str) -> str:
    """Remove heading decoration and bullets from both ends of ``text``."""
    return text.strip().strip(_HEADING_DECORATION).strip()


def _despaced(text: str) -> str:
    """Join a letter-spaced heading back together ("S K I L L S" is the heading "SKILLS").

    Only applied to a run whose words are all single letters, which is what a tracked heading looks
    like after a PDF text extractor has finished with it; ordinary prose is returned unchanged. A
    column gap inside the line is preserved, so "T E C H N I C A L | S K I L L S" becomes
    "TECHNICAL | SKILLS" rather than one run-together word.
    """
    segments = text.split(_COLUMN_SEPARATOR)
    joined = []
    for segment in segments:
        parts = segment.split()
        joined.append("".join(parts) if len(parts) >= 2 and all(len(part) == 1 for part in parts) else segment)
    return _COLUMN_SEPARATOR.join(joined)


def _heading_name(candidate: str) -> str | None:
    """The section a candidate heading names, or ``None``."""
    for name, pattern in _SECTION_PATTERNS:
        if pattern.match(candidate):
            return name
    return None


def _looks_like_inline_content(remainder: str) -> bool:
    """Whether text that follows a heading on the same line is a value list rather than a sentence.

    "SKILLS Python, SQL" and "SKILLS Python" carry a value; "Skills are the reason I applied" is prose
    and is left out. A list separator decides it, and a single word counts because that is how a
    one-entry list looks; anything with spaces and no separator is treated as a sentence.
    """
    if len(remainder) > _MAX_INLINE_CONTENT_CHARACTERS:
        return False
    if re.search(r"[,;|•·/]", remainder):
        return True
    return " " not in remainder


def _heading_match(line: str) -> tuple[str, str] | None:
    """The section ``line`` opens and any content that shares the line, or ``None``.

    Returning the content matters because a text extractor frequently puts a heading and its list on
    one line - a sidebar layout or a table cell produces "SKILLS Python, SQL", and "SKILLS: Python, SQL"
    is written that way on purpose. Treating such a line as a heading only would silently discard the
    list, which is exactly the "no skills section was found" report this handles.
    """
    if len(line) > _MAX_HEADING_CHARACTERS:
        return None
    candidate = _despaced(_undecorated(line.rstrip(":")))
    if not candidate:
        return None
    # A column gap can sit inside the heading itself ("TECHNICAL | SKILLS"). Matching the flattened
    # form as a fallback covers that without touching a gap that belongs to the content, which is
    # what keeps the two columns of a content line splittable further down.
    match_candidates = [candidate]
    if _COLUMN_SEPARATOR in candidate:
        match_candidates.append(candidate.replace(_COLUMN_SEPARATOR, " "))
    for match_candidate in match_candidates:
        for name, pattern in _SECTION_PATTERNS:
            match = pattern.match(match_candidate)
            if not match:
                continue
            remainder = _undecorated(match_candidate[match.end():])
            if not remainder:
                return name, ""
            tail = _undecorated(_LEADING_CONJUNCTION.sub("", remainder))
            # Two columns' headings can arrive on one line ("SKILLS EXPERIENCE"), and a heading can be
            # joined to another by a conjunction ("SKILLS & INTERESTS"). The tail is a heading word,
            # not a value: keeping it would propose "EXPERIENCE" or "INTERESTS" as a skill.
            if _despaced(tail) and _heading_name(_despaced(tail)) is not None:
                return name, ""
            if remainder[0] in _HEADING_SEPARATORS:
                return name, _undecorated(remainder.lstrip(_HEADING_SEPARATORS)).strip()
            if not remainder[0].isalnum():
                return name, ""
            if _looks_like_inline_content(remainder):
                return name, remainder
            return name, ""
    return None


def _section_of(line: str) -> str | None:
    """The section a heading line opens, or ``None`` when the line is not a heading."""
    opened = _heading_match(line)
    return opened[0] if opened else None


def _sections(lines: Sequence[str]) -> dict[str, list[str]]:
    """Split cleaned lines into sections keyed by heading; preamble text lands under ``"header"``.

    Content that shares a heading's line is kept as that section's first content line, and a *labelled*
    category line inside a skills block ("Languages: Python, C++") stays in the skills block: its
    values are skills. A bare word on its own line ("Languages") is left to open its own section,
    because a list under it may well be spoken languages rather than skills.
    """
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in lines:
        opened = _heading_match(line)
        merge_into_skills = (
            opened is not None and bool(opened[1]) and current == "skills" and opened[0] == "other"
            and _SKILLS_SUB_LABEL.match(_undecorated(line))
        )
        if opened is not None and not merge_into_skills:
            current, remainder = opened
            sections.setdefault(current, [])
            if remainder:
                sections[current].append(remainder)
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _skills_proposal(section: Iterable[str]) -> FieldProposal | None:
    """Skills are read from an explicit skills section only.

    A skill word appearing in the body of the document (in a project description, say) is not proof
    that the person lists it as a skill, so nothing is harvested from other sections.

    A category name is a label, not a skill, whether the person separates it with a colon or with the
    column gap the extractors report as ``|``: "Languages: Python, SQL" and "Languages | Python, SQL"
    say the same thing and must not produce different values.

    A line that carries a column gap *without* such a label merges two columns or two table cells that
    the extractor joined, and which column holds the skills is then not knowable from the text alone
    ("Python, SQL, Django    Built ETL pipelines" and "Python, SQL    Built ETL pipelines at scale"
    cannot both be decided by counting words). The values are still offered exactly as read, but the
    proposal is marked for review instead of pre-ticked, so nothing that was guessed at is one click
    from being saved.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    evidence = ""
    merged_column = False
    for line in section:
        if not evidence:
            evidence = line
        # "Languages: Python, SQL" lists skills under a category name, so the values are read without
        # the label. The evidence shown to the person is always the whole original line.
        labelled = _LABELLED_SKILLS_LINE.match(line)
        if not labelled and _COLUMN_GAP in line:
            # The same category name before a column gap ("Languages | Python, SQL") is the same
            # statement, so it is read the same way. Anything else before a gap is left to the
            # reviewer (see the docstring).
            first, rest = line.split(_COLUMN_GAP, 1)
            match = _SKILLS_SUB_LABEL.match(_undecorated(first))
            if match and match.group(0).strip().casefold() == first.strip().casefold():
                labelled = _LABELLED_SKILLS_LINE.match(f"{match.group(0)}: {rest}")
            else:
                # Remembered for the whole proposal, never cleared: a later labelled line must not
                # erase the fact that values were also read out of a merged column.
                merged_column = True
        content = labelled.group(1) if labelled else line
        # Column gaps and tabs already arrive as the "|" separator (see ``_clean_line``), so this
        # splits on the separators a person actually writes between skills.
        for part in re.split(r"[,;•·/]| - | – |\|", content):
            token = _clean_line(part)
            token = re.sub(r"^(?:and|&)\s+", "", token, flags=re.I).strip(" .")
            if not token or len(token) < 2 or len(token) > 40:
                continue
            if token.casefold() in _DEGREE_NOISE or token.casefold() in seen:
                continue
            # ``&`` belongs inside a skill name (GD&T, M&A, P&L): the filter exists to keep punctuation
            # noise out, and a dropped skill is worse than a noisy one, because the person reviews what
            # is proposed and never sees what was discarded.
            if not re.match(r"^[A-Za-z0-9][A-Za-z0-9+#&.()/\- ]*$", token):
                continue
            if len(token.split()) > 4:
                continue
            tokens.append(token)
            seen.add(token.casefold())
            if len(tokens) >= 40:
                break
        if len(tokens) >= 40:
            break
    if not tokens:
        return None
    return FieldProposal(
        key="skills", label="Skills", value=", ".join(tokens),
        confidence=ProposalConfidence.NEEDS_REVIEW if merged_column else ProposalConfidence.CONFIDENT,
        evidence=_snippet(evidence or ", ".join(tokens)),
    )


def _degree_proposal(education_lines: Sequence[str], all_lines: Sequence[str]) -> FieldProposal | None:
    """Degree and discipline, read from an education section or an explicit degree line."""
    candidates = list(education_lines)
    for line in all_lines:
        if line not in candidates and (_DEGREE_PATTERN.search(line) and _INSTITUTION_PATTERN.search(line)):
            candidates.append(line)
    for line in candidates:
        match = _DEGREE_PATTERN.search(line)
        if not match:
            continue
        # An abbreviation can carry its own full stop, and the pattern may leave it behind: "B.Sc. in
        # Biotechnology" matches "B.Sc" and leaves ". in Biotechnology". That stop is part of the
        # abbreviation, not the separator after it, so it is dropped here - otherwise the discipline is
        # never read and the same qualification produces a worse proposal than without the stop.
        remainder = re.sub(r"^[\s.]*", "", line[match.end():])
        discipline_match = re.search(
            r"^\s*(?:in|of|,|:|\()\s*([A-Za-z][A-Za-z&,\- ]{2,60}?)\s*(?:\)|,|\.|$|\||\()", remainder
        )
        if discipline_match:
            discipline = _clean_line(discipline_match.group(1)).strip(" .,-")
            discipline = re.sub(r"\s+(?:at|from)\s+.*$", "", discipline, flags=re.I).strip(" .,-")
            if discipline and not all(part.casefold() in _DEGREE_NOISE for part in discipline.split()):
                return FieldProposal(
                    key="degree", label="Degree / discipline", value=discipline,
                    confidence=ProposalConfidence.CONFIDENT, evidence=_snippet(line),
                )
        degree = _clean_line(match.group(0)).strip(" .,")
        if degree:
            # Only the level was written down, without the subject. It is still exactly what the
            # document says, so it is offered - unselected, because the field asks for both parts.
            return FieldProposal(
                key="degree", label="Degree / discipline", value=degree,
                confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
            )
    return None


def _graduation_year_proposal(lines: Sequence[str]) -> FieldProposal | None:
    """Graduation year, only when the document states it (explicitly, or on an education line)."""
    for line in lines:
        explicit = _EXPLICIT_GRADUATION_PATTERN.search(line)
        if explicit:
            year = int(explicit.group(1))
            if 1950 <= year <= 2100:
                return FieldProposal(
                    key="graduation_year", label="Graduation year", value=str(year),
                    confidence=ProposalConfidence.CONFIDENT, evidence=_snippet(line),
                )
    for line in lines:
        if not (_DEGREE_PATTERN.search(line) or _INSTITUTION_PATTERN.search(line)):
            continue
        bare = _BARE_YEAR_PATTERN.search(line)
        if bare:
            year = int(bare.group(0))
            if 1950 <= year <= 2100:
                return FieldProposal(
                    key="graduation_year", label="Graduation year", value=str(year),
                    confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
                )
    return None


def _experience_proposal(lines: Sequence[str]) -> FieldProposal | None:
    """Years of experience, only from an explicit statement.

    Employment dates are deliberately not used: turning "Aug 2021 - Jul 2023" into a number means
    computing a duration the document never states, which is how a guess becomes a fact.
    """
    for line in lines:
        for pattern in (_EXPERIENCE_PATTERN, _LABELLED_EXPERIENCE_PATTERN):
            match = pattern.search(line)
            if match:
                value = match.group(1).rstrip("0").rstrip(".") if "." in match.group(1) else match.group(1)
                uncertain = bool(re.search(r"\b(?:about|approx|approximately|around|over|more than|nearly)\b", line, re.I)) \
                    or "+" in match.group(0)
                return FieldProposal(
                    key="experience", label="Experience years", value=value,
                    confidence=(ProposalConfidence.NEEDS_REVIEW if uncertain else ProposalConfidence.CONFIDENT),
                    evidence=_snippet(line),
                )
    return None


def _study_status_proposal(lines: Sequence[str]) -> FieldProposal | None:
    """Study status, only when the document states it in words.

    Always offered unselected: mapping "currently pursuing a bachelor's degree" onto one of the
    profile's fixed values is a human decision, and this value is used by eligibility checks.
    """
    phrases: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bph\.?\s?d\.?\s+(?:candidate|student|scholar)\b|\bdoctoral\s+(?:candidate|student|researcher)\b|\bpursuing\s+(?:a\s+)?ph\.?\s?d\b", re.I), "doctoral"),
        (re.compile(r"\bpursuing\s+(?:a\s+)?(?:masters?|m\.?\s?tech|m\.?\s?sc|mba)\b|\bmasters?\s+(?:student|candidate)\b", re.I), "graduate"),
        (re.compile(r"\bpursuing\s+(?:a\s+)?(?:bachelors?|b\.?\s?tech|b\.?\s?e\b|b\.?\s?sc|undergraduate)\b|\bundergraduate\s+(?:student|candidate)\b|\bfinal[\s-]year\s+student\b", re.I), "undergraduate"),
        (re.compile(r"\b(?:graduated|completed\s+(?:my|the|a)\s+(?:bachelors?|masters?|degree|graduation)|alumnus|alumna)\b", re.I), "graduated"),
        (re.compile(r"\bpostgraduate\s+(?:student|candidate)\b", re.I), "postgraduate"),
    )
    for line in lines:
        for pattern, mapped in phrases:
            if pattern.search(line):
                return FieldProposal(
                    key="study_status", label="Study status", value=mapped,
                    confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
                )
    return None


def _country_from_label(value: str) -> str | None:
    """A country on an explicit location line, matched against the documented country list."""
    parts = [part.strip(" .") for part in re.split(r"[,|]", value) if part.strip(" .")]
    for part in reversed(parts):
        folded = part.casefold()
        for canonical, *aliases in _KNOWN_COUNTRIES:
            if folded == canonical.casefold() or folded in aliases:
                return canonical
    return None


def _country_proposal(lines: Sequence[str]) -> FieldProposal | None:
    """Country, only from a labelled country/location line.

    Never inferred from a city, a phone prefix or an institution, and always offered unselected
    because this value decides whether eligibility can pass.
    """
    for line in lines:
        country_label = _LABEL_PATTERNS[0][1].search(line)
        if country_label:
            country = _country_from_label(country_label.group(1)) or _clipped(country_label.group(1), 60)
            return FieldProposal(
                key="country", label="Country", value=country,
                confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
            )
    for line in lines:
        location_label = _LABEL_PATTERNS[1][1].search(line)
        if location_label:
            country = _country_from_label(location_label.group(1))
            if country:
                return FieldProposal(
                    key="country", label="Country", value=country,
                    confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
                )
    return None


def _work_authorization_proposal(lines: Sequence[str]) -> FieldProposal | None:
    """Work authorization, quoted from the document rather than paraphrased.

    The profile field is free text and this app has no controlled vocabulary for it, so the exact
    wording is proposed - unselected, because eligibility checks read this value.
    """
    for line in lines:
        labelled = _LABEL_PATTERNS[2][1].search(line)
        if labelled:
            return FieldProposal(
                key="work_authorization", label="Work authorization", value=_clipped(labelled.group(1), 80),
                confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
            )
    for line in lines:
        for pattern in _AUTHORIZATION_PHRASES:
            match = pattern.search(line)
            if match:
                return FieldProposal(
                    key="work_authorization", label="Work authorization",
                    value=_clipped(match.group(0), 80),
                    confidence=ProposalConfidence.NEEDS_REVIEW, evidence=_snippet(line),
                )
    return None


def _name_proposal(header_lines: Sequence[str]) -> str | None:
    """A plausible name: the first short capitalised line with no digits, '@' or label punctuation."""
    for line in header_lines[:6]:
        if len(line) > 60 or "@" in line or any(character.isdigit() for character in line):
            continue
        if ":" in line or _section_of(line) is not None:
            continue
        if _NAME_LINE_PATTERN.match(line):
            return line
    return None


def _unmapped_items(lines: Sequence[str]) -> tuple[UnmappedItem, ...]:
    """Name, email, phone and links: shown for information, never written into a profile field."""
    text = "\n".join(lines)
    items: list[UnmappedItem] = []
    name = _name_proposal(lines)
    note = "Not stored: the profile has no field for this."
    if name:
        items.append(UnmappedItem(label="Name", value=_clipped(name), note=note))
    email = _EMAIL_PATTERN.search(text)
    if email:
        items.append(UnmappedItem(label="Email", value=_clipped(email.group(0)), note=note))
    phone = None
    for match in _PHONE_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 8 <= len(digits) <= 15 and not 1900 <= int(digits[:4]) <= 2100:
            phone = match.group(0)
            break
    if phone:
        items.append(UnmappedItem(label="Phone", value=_clipped(phone), note=note))
    links: list[str] = []
    for match in _LINK_PATTERN.finditer(text):
        value = match.group(0).rstrip(".,;")
        if value not in links:
            links.append(value)
        if len(links) == 3:
            break
    if links:
        items.append(UnmappedItem(label="Links", value=_clipped(", ".join(links)), note=note))
    return tuple(items)


def parse_resume_text(text: str) -> tuple[tuple[FieldProposal, ...], tuple[UnmappedItem, ...], tuple[str, ...]]:
    """Turn extracted text into proposals, informational items, and notes about what was skipped.

    Deterministic and template-agnostic: every rule is a documented pattern over the text, and a rule
    that does not match simply produces nothing. No value is guessed, adapted to one résumé layout, or
    promoted out of an uncertain match.
    """
    lines = _lines(text)
    if not lines:
        return (), (), ("The document's text was empty after cleaning.",)
    sections = _sections(lines)
    notes: list[str] = []
    proposals: list[FieldProposal] = []
    skills = _skills_proposal(sections.get("skills", ()))
    if skills:
        proposals.append(skills)
    elif "skills" in sections:
        # A heading was recognised but no value followed it: say so instead of reporting that the
        # document has no skills section, which is a different problem with a different next step.
        notes.append(
            "A skills heading was recognised, but no list of skills followed it, so no skills were "
            "proposed. If the document lists them elsewhere, type them into the Skills field."
        )
    else:
        notes.append(
            "No skills heading was recognised in this document (headings such as Skills, Technical "
            "Skills, Competencies, Expertise, Technologies and Tools are recognised), so no skills "
            "were proposed. Type them into the Skills field if you want them stored."
        )
    education_lines = sections.get("education", ())
    degree = _degree_proposal(education_lines, lines)
    if degree:
        proposals.append(degree)
    graduation = _graduation_year_proposal(list(education_lines) + lines)
    if graduation:
        proposals.append(graduation)
    experience = _experience_proposal(lines)
    if experience:
        proposals.append(experience)
    study_status = _study_status_proposal(lines)
    if study_status:
        proposals.append(study_status)
    country = _country_proposal(lines)
    if country:
        proposals.append(country)
    authorization = _work_authorization_proposal(lines)
    if authorization:
        proposals.append(authorization)
    return tuple(proposals), _unmapped_items(lines), tuple(notes)


def parse_resume(path: str | Path) -> ResumeParseResult:
    """Read a local résumé file, extract its text locally, and propose profile values.

    Nothing is written, copied or transmitted: the extracted text is discarded when this function
    returns, and the result carries only proposals with short quotations, informational items that
    have no profile field, and notes about what was refused or skipped.
    """
    source = Path(path)
    document = extract_text(source)
    proposals, unmapped, notes = parse_resume_text(document.text)
    if not proposals:
        notes = notes + (
            "No supported profile value could be read from this document. The saved profile is "
            "unchanged; you can type the values yourself.",
        )
    return ResumeParseResult(
        file_name=source.name,
        source_format=document.source_format,
        proposals=proposals,
        unmapped=unmapped,
        notes=tuple(document.notes) + tuple(notes),
        text_characters=len(document.text),
    )


def missing_field_labels(proposals: Iterable[FieldProposal]) -> tuple[str, ...]:
    """Labels of the résumé-supportable fields the document did not provide.

    Shown in the review screen so "the document said nothing about this" is visible rather than
    implied by a silently absent row.
    """
    supplied = {proposal.key for proposal in proposals}
    return tuple(
        label for key, label in PROFILE_FIELD_LABELS if key in RESUMABLE_FIELD_KEYS and key not in supplied
    )


def study_status_choices() -> tuple[str, ...]:
    """The study-status values the profile accepts, for validating a proposed value."""
    return _STUDY_STATUS_CHOICES


def proposal_by_key(result: ResumeParseResult, key: str) -> FieldProposal | None:
    """The proposal for ``key``, or ``None`` when the document did not provide that field."""
    for proposal in result.proposals:
        if proposal.key == key:
            return proposal
    return None


def accepted_values(proposals: Iterable[FieldProposal], accepted: Mapping[str, bool]) -> dict[str, str]:
    """The values to save: one per proposal the person selected.

    Accepting a proposal that does not exist raises ``KeyError``: the caller and the review screen
    both work from the same proposal list, so a mismatch is a programming error rather than
    something to paper over.
    """
    chosen: dict[str, str] = {}
    for proposal in proposals:
        if accepted.get(proposal.key):
            chosen[proposal.key] = proposal.value
    return chosen


def format_result_summary(result: ResumeParseResult) -> str:
    """A short, factual line for the status bar: format, proposals, informational items, notes."""
    parts = [
        f"{result.source_format.value} résumé read locally",
        f"{len(result.proposals)} proposed value(s)",
    ]
    if result.unmapped:
        parts.append(f"{len(result.unmapped)} item(s) with no profile field")
    if result.notes:
        parts.append(f"{len(result.notes)} note(s)")
    return "; ".join(parts) + "."
