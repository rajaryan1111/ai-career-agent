"""Local-only resume import with review-only field proposals.

Text is extracted from plain text, DOCX, and simple text-based PDF files using
the standard library only. Nothing is uploaded, nothing is saved automatically,
and every proposed field carries the exact line it came from. Fields without an
explicit label are never guessed, and scanned or encrypted PDFs are reported as
unsupported instead of being silently treated as empty resumes.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import re
import zipfile
import zlib

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
TEXT_SUFFIXES = frozenset({".txt", ".md", ".markdown"})
SUPPORTED_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".docx", ".pdf"})
DOCUMENT_XML = "word/document.xml"
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ResumeError(ValueError):
    """Raised when a resume file cannot be read honestly."""


@dataclass(frozen=True)
class FieldProposal:
    """One candidate value with the evidence line that produced it."""

    field: str
    value: str
    evidence: str
    confidence: str = "review"


@dataclass(frozen=True)
class ResumeExtraction:
    source_name: str
    text: str
    proposals: tuple[FieldProposal, ...]
    warnings: tuple[str, ...]

    @property
    def proposed_fields(self) -> tuple[str, ...]:
        return tuple(item.field for item in self.proposals)


# ------------------------------------------------------------------ extraction

def _read_docx(raw: bytes) -> str:
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if DOCUMENT_XML not in archive.namelist():
                raise ResumeError("The DOCX file has no document body (word/document.xml).")
            xml = archive.read(DOCUMENT_XML)
    except zipfile.BadZipFile as exc:
        raise ResumeError("The file is not a readable DOCX archive.") from exc
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ResumeError("The DOCX document body is not valid XML.") from exc
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_WORD_NS}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t"))
        if text.strip():
            paragraphs.append(" ".join(text.split()))
    return "\n".join(paragraphs)


def _unescape_pdf_text(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\" or index + 1 >= len(value):
            result.append(char)
            index += 1
            continue
        nxt = value[index + 1]
        if nxt in "()\\":
            result.append(nxt)
            index += 2
        elif nxt == "n":
            result.append("\n")
            index += 2
        elif nxt == "t":
            result.append("\t")
            index += 2
        elif nxt.isdigit() and nxt < "8":
            octal = ""
            cursor = index + 1
            while cursor < len(value) and len(octal) < 3 and value[cursor].isdigit() and value[cursor] < "8":
                octal += value[cursor]
                cursor += 1
            result.append(chr(int(octal, 8)))
            index = cursor
        else:
            result.append(nxt)
            index += 2
    return "".join(result)


_TEXT_OPERATOR = re.compile(r"\((?:[^()\\]|\\.)*\)\s*Tj|\[(?:[^\[\]]|\\.)*\]\s*TJ")


def _pdf_stream_text(data: bytes) -> str:
    content = data.decode("latin-1", errors="replace")
    lines: list[str] = []
    for match in _TEXT_OPERATOR.finditer(content):
        token = match.group(0)
        if token.endswith("Tj"):
            start, end = token.find("("), token.rfind(")")
            if start != -1 and end > start:
                lines.append(_unescape_pdf_text(token[start + 1:end]))
        else:
            parts = re.findall(r"\((?:[^()\\]|\\.)*\)", token)
            lines.append("".join(_unescape_pdf_text(part[1:-1]) for part in parts))
    return "\n".join(line for line in lines if line.strip())


def _read_pdf(raw: bytes) -> tuple[str, tuple[str, ...]]:
    if not raw.lstrip().startswith(b"%PDF"):
        raise ResumeError("The file does not look like a PDF document.")
    if b"/Encrypt" in raw:
        raise ResumeError("This PDF is encrypted or password-protected and cannot be imported.")
    warnings: list[str] = []
    pages: list[str] = []
    for match in re.finditer(rb"stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end == -1:
            continue
        data = raw[start:end].rstrip(b"\r\n")
        if b"Tj" not in data and b"TJ" not in data:
            try:
                data = zlib.decompress(data)
            except zlib.error:
                continue
        if b"Tj" not in data and b"TJ" not in data:
            continue
        text = _pdf_stream_text(data)
        if text:
            pages.append(text)
    if not pages:
        warnings.append(
            "No extractable text was found. Scanned or image-only PDFs need OCR, "
            "which this local alpha does not provide."
        )
    return "\n".join(pages), tuple(warnings)


def read_resume(path: str | Path) -> ResumeExtraction:
    """Read a resume file and return its text plus review-only proposals."""
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ResumeError(
            f"Unsupported resume format {suffix or '(none)'}. "
            "Supported formats: DOCX, PDF with selectable text, TXT, MD."
        )
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise ResumeError(f"Could not read the resume file: {exc}") from exc
    if not raw.strip():
        raise ResumeError("The resume file is empty.")
    if len(raw) > MAX_RESUME_BYTES:
        raise ResumeError(
            f"The resume file is larger than the {MAX_RESUME_BYTES // (1024 * 1024)} MiB import limit."
        )

    warnings: list[str] = []
    if suffix in TEXT_SUFFIXES:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResumeError("The resume text file is not valid UTF-8.") from exc
    elif suffix == ".docx":
        text = _read_docx(raw)
    else:
        text, pdf_warnings = _read_pdf(raw)
        warnings.extend(pdf_warnings)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        warnings.append("Only the first part of the document was read; the rest was ignored.")

    proposals, proposal_warnings = propose_fields(text)
    return ResumeExtraction(source.name, text, proposals, tuple(warnings) + proposal_warnings)


# ------------------------------------------------------------------ proposals

_LABELS: dict[str, str] = {
    "skills": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "key skills": "skills",
    "country": "candidate_country",
    "location": "preferred_locations",
    "preferred locations": "preferred_locations",
    "preferred work mode": "preferred_work_modes",
    "preferred work modes": "preferred_work_modes",
    "work mode": "preferred_work_modes",
    "preferred role types": "preferred_role_types",
    "role types": "preferred_role_types",
    "degree": "degree_discipline",
    "discipline": "degree_discipline",
    "study status": "study_status",
    "work authorization": "work_authorization",
}

_MULTI_VALUE_FIELDS = frozenset({
    "skills", "preferred_locations", "preferred_work_modes", "preferred_role_types",
})
_LABEL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z /&()\-]{1,40}?)\s*[:\-–]\s*(\S.*)$")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_YEARS_EXPERIENCE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", re.I
)


def _split_values(value: str) -> tuple[str, ...]:
    parts = re.split(r"[,;|/\u2022]", value)
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        item = " ".join(part.split()).strip(" .-")
        if item and item.casefold() not in seen:
            cleaned.append(item)
            seen.add(item.casefold())
    return tuple(cleaned)


def propose_fields(text: str) -> tuple[tuple[FieldProposal, ...], tuple[str, ...]]:
    """Propose only labelled values, each with its source line as evidence."""
    proposals: list[FieldProposal] = []
    seen_fields: set[str] = set()

    def add(field: str, value: str, evidence: str) -> None:
        if field in seen_fields or not value.strip():
            return
        seen_fields.add(field)
        proposals.append(FieldProposal(field, value.strip(), evidence.strip()))

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        match = _LABEL_LINE.match(line)
        if match is None:
            if "graduation_year" not in seen_fields and "graduat" in line.casefold():
                found = _YEAR.search(line)
                if found:
                    add("graduation_year", found.group(0), line)
            continue
        label = match.group(1).strip().casefold()
        value = match.group(2).strip()
        field = _LABELS.get(label)
        if field is None:
            if label.startswith("graduat") or label in {"education", "graduation year"}:
                found = _YEAR.search(value) or _YEAR.search(line)
                if found:
                    add("graduation_year", found.group(0), line)
            elif label.startswith("experience"):
                years = _YEARS_EXPERIENCE.search(value)
                if years:
                    add("experience_years", years.group(1), line)
            continue
        if field in _MULTI_VALUE_FIELDS:
            items = _split_values(value)
            if items:
                add(field, ", ".join(items), line)
        else:
            add(field, value, line)

    if "experience_years" not in seen_fields:
        found = _YEARS_EXPERIENCE.search(text)
        if found:
            add("experience_years", found.group(1), found.group(0))

    warnings: list[str] = []
    if not proposals:
        warnings.append(
            "No labelled resume sections were found, so no fields were proposed. Enter facts "
            "manually or add explicit labels such as 'Skills:' and 'Graduation year:'."
        )
    return tuple(proposals), tuple(warnings)
