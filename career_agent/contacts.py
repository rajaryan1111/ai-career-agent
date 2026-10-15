"""Local-only HR contact CSV reading, validation and a review preview.

Design rules this module follows, and the reasons
-------------------------------------------------
* **Local only.** A file the person chose is read from disk and parsed in this process with the standard
  library's :mod:`csv`. No network call, no upload, no hosted parser, no LLM, no third-party package. The
  module imports nothing else, and it is covered by the "nothing in the shipped code can open a
  connection" test that reads the source.
* **The file is the person's, and it is only ever read.** It is opened ``"rb"``, bounded by a documented
  size limit, and never written, moved, renamed or repaired. Nothing is copied anywhere: no database, no
  cache, no temporary file. A preview therefore cannot half-import anything - there is nothing to undo.
* **No contact value is ever printed or logged.** :meth:`ContactImport.describe` reports counts, flag
  names, and *line numbers*, which is what a person needs to judge a list without the list being copied
  into a terminal, a log, a screenshot or a CI artefact. The parsed values are held in memory so a review
  screen can show them to the person who owns the file, and they go nowhere else.
* **Ambiguity is surfaced, never resolved silently.** Column names are matched against a documented list
  of spellings; when two columns could be the one that identifies a contact, that is a refusal naming
  both, rather than a guess. Company labels that disagree inside one email group are kept exactly as they
  are and flagged; the module never picks a winner, invents an employer or rewrites a cell.
* **Syntax checks are heuristics.** :func:`looks_like_email` reads the shape of a string. It does not
  resolve DNS, contact a mailbox, prove deliverability, show that anybody consented to being contacted,
  show that anybody still works where the file says, or show that the list may lawfully be used. Nothing
  in this module may be reported as any of those things.
* **Nothing is persisted, on purpose.** This increment has no store: it reads, checks and reports. The
  comparison key it computes (the email trimmed and case-folded) is the key a later store would have to
  use to make a re-import idempotent, and it is computed here so that the review screen and the store
  cannot disagree about what "the same contact" means.

This follows the shape the rest of the project already uses rather than inventing one: the bounded read and
the "one actionable sentence, nothing changed" refusal come from :mod:`career_agent.resume`, and the command
that fronts it is one of the database-free read-only reports, like ``--sources`` and
``--integration-status``.

A note on what "the file" means to a later increment: the private exports this was built for are not in
this repository and their exact header spellings are not known here, so a caller can pin any field to a
named column (``columns={"email": "Email Key"}``) and detection fills in the rest. Whichever way a column
is chosen, the choice is reported in full - which columns were used, which were not, which fields could
not be matched at all - so a person sees what was assumed before anything is stored.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Sequence

#: Largest contact CSV accepted, checked before the file is read. A contact export of a few thousand rows
#: is well under a megabyte; this leaves room for a large one with long cells while refusing a file that
#: is plainly not a list of contacts without loading it into memory first.
MAX_CONTACT_CSV_BYTES = 20 * 1024 * 1024

#: Largest number of data rows read. Refused rather than truncated: a preview that silently stopped at
#: row 50,000 would report counts that are not the file's, which is worse than refusing the file.
MAX_CONTACT_ROWS = 50_000

#: How many unmatched header names and example line numbers the printed preview carries. The counts are
#: complete; only the lists are capped, and the cap is stated in the line that prints them.
MAX_HEADERS_LISTED = 6
MAX_EXAMPLE_ROWS = 12

#: Why a row, or the group it belongs to, needs a person to look at it. Every value is a heuristic
#: question about the file's own text, never a statement about a person or a mailbox.
class Flag(str, Enum):
    """One reason a row is worth reviewing."""

    #: The row's email cell is empty, so the row cannot be identified by email at all.
    EMAIL_MISSING = "email-missing"
    #: The email cell has text, and that text does not have the shape of an address (a heuristic).
    EMAIL_SYNTAX = "email-syntax"
    #: A name column was matched and this row's name cell is empty.
    NAME_MISSING = "name-missing"
    #: Another row in the file has the same email key, whatever its case or surrounding spaces.
    DUPLICATE_KEY = "duplicate-key"
    #: Rows sharing one email key carry different, non-empty company labels.
    COMPANY_CONFLICT = "company-conflict"


class ContactImportError(Exception):
    """A contact CSV could not be read. The message is written to be shown to the person.

    Messages carry the file's name, the line or the column names involved and what to do next. They never
    carry a cell's value: no email address, no name, no company label of a real row.
    """


class ContactFileUnreadable(ContactImportError):
    """The chosen path is not a file this module can read: missing, a folder, empty, or not UTF-8 text."""


class ContactFileTooLarge(ContactImportError):
    """The file, or the number of rows in it, exceeds a documented limit."""


class ContactSchemaError(ContactImportError):
    """The header row is missing, has no usable column, or does not name a column this module needs."""


class ContactCsvMalformed(ContactImportError):
    """The text is not well-formed CSV, or a record does not have as many fields as the header row."""


#: Documented spellings accepted for each field, compared after :func:`normalise_header`. Anything else is
#: reported as an unmatched header rather than being used, so a file whose columns mean something else is
#: never read as if it were this shape.
_HEADER_SPELLINGS: Mapping[str, tuple[str, ...]] = {
    "email": (
        "email", "email address", "e mail", "e mail address", "mail", "contact email", "work email",
        "email key", "email id", "normalised email", "normalized email",
    ),
    "name": ("name", "names", "full name", "contact name", "person name", "person", "recruiter name"),
    "company": (
        "company", "companies", "company label", "company labels", "company name", "employer",
        "organisation", "organization",
    ),
    "source_row": (
        "source row", "source rows", "source row id", "source rows id", "row", "row id", "row number",
        "source id", "original row", "original row number",
    ),
    "review_reason": (
        "review reason", "review reasons", "review queue", "reason", "flags", "flag", "review flag",
        "review flags",
    ),
}

#: The fields a caller can pin explicitly. ``email`` is the only one a file must have.
_MAPPING_FIELDS = ("email", "name", "company", "source_row", "review_reason")


def normalise_header(text: str) -> str:
    """A header name reduced to what comparisons use: trimmed, case-folded, separators as one space."""
    collapsed = re.sub(r"[\s_\-]+", " ", text.strip().casefold())
    return collapsed


def normalise_email_key(value: str) -> str:
    """The comparison key for an email cell: trimmed and case-folded, and nothing else.

    Only the email is normalised, and only these two operations are applied to it: a local part is
    technically case-sensitive, so no library lower-cases it silently, and no dots are removed. The
    original cell keeps its own text and is what a person is shown.
    """
    return value.strip().casefold()


def looks_like_email(value: str) -> bool:
    """Whether this text has the shape of one email address. A heuristic, and only a heuristic.

    Deliberately conservative about what it rejects and honest about what it proves: it checks that there
    is one ``@``, that the parts around it are non-empty and free of spaces, that the domain has at least
    two labels with sane lengths, and that no label begins or ends with a hyphen. It does not resolve the
    domain, does not know the local part's provider rules, and cannot say that a mailbox exists. A row
    this returns ``False`` for is not deleted or changed - it is flagged for a person to look at.
    """
    text = value.strip()
    if not text or len(text) > 254 or any(character.isspace() for character in text):
        return False
    if text.count("@") != 1:
        return False
    local, _, domain = text.partition("@")
    if not local or len(local) > 64:
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    if any(character in local for character in ',;:<>()[]"\\'):
        return False
    if not domain or domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    for label in labels:
        if not label or len(label) > 63 or label.startswith("-") or label.endswith("-"):
            return False
        if not all(character.isascii() and (character.isalnum() or character == "-")
                   for character in label):
            return False
    # The last label is the one that would be a top-level domain. It must not be a single character or
    # entirely numeric; beyond that this is not a place to hold an opinion about which domains exist.
    return len(labels[-1]) >= 2 and not labels[-1].isdigit()


@dataclass(frozen=True)
class ColumnMapping:
    """Which column of one file holds which field, by the file's own header name.

    ``email`` is the only field a file must have. The rest are optional because a contact list may carry
    only addresses, and because a field that was not matched must be reported as unchecked rather than
    guessed at.
    """

    email: str
    name: str | None = None
    company: str | None = None
    source_row: str | None = None
    review_reason: str | None = None

    def named(self, field: str) -> str | None:
        """The header this mapping uses for ``field``, or ``None`` when it does not use one."""
        return getattr(self, field)

    def describe(self) -> tuple[str, ...]:
        """The mapping in the order a person reads it, one short line per field."""
        lines = [f"email: {self.email!r}"]
        for field, label in (("name", "name"), ("company", "company label"),
                             ("source_row", "source row"), ("review_reason", "review reason")):
            used = self.named(field)
            lines.append(f"{label}: {used!r}" if used else f"{label}: not used")
        return tuple(lines)


@dataclass(frozen=True)
class ColumnProposal:
    """What header detection matched, and what it could not, before anything is read.

    ``ambiguous_fields`` is the whole reason this type exists rather than a bare mapping: a file with
    both ``Email`` and ``Email Key`` columns cannot be read as one shape without choosing, and choosing
    is exactly what this module refuses to do quietly.
    """

    mapping: ColumnMapping | None
    matches: Mapping[str, tuple[str, ...]]
    unmatched_headers: tuple[str, ...]

    def ambiguous_fields(self) -> tuple[str, ...]:
        """Fields that more than one column could be, in the order a person would ask about them."""
        return tuple(field for field in _MAPPING_FIELDS if len(self.matches.get(field, ())) > 1)

    def describe(self) -> tuple[str, ...]:
        """One line per field saying what was matched, for a review screen or a report."""
        lines = []
        for field in _MAPPING_FIELDS:
            found = self.matches.get(field, ())
            if len(found) == 1:
                lines.append(f"{field} column: {found[0]!r}")
            elif found:
                lines.append(f"{field} column: not used - {len(found)} columns match "
                             f"({', '.join(repr(item) for item in found)})")
            else:
                lines.append(f"{field} column: not used - no column matches")
        return tuple(lines)


def _proposal(headers: Sequence[str]) -> ColumnProposal:
    """Match every header against the documented spellings, keeping every candidate."""
    matches: dict[str, list[str]] = {field: [] for field in _MAPPING_FIELDS}
    unmatched = []
    for header in headers:
        wanted = normalise_header(header)
        hit = None
        for field, spellings in _HEADER_SPELLINGS.items():
            if wanted in spellings:
                hit = field
                break
        if hit is None:
            unmatched.append(header)
        else:
            matches[hit].append(header)

    def single(field: str) -> str | None:
        found = matches[field]
        return found[0] if len(found) == 1 else None

    email = single("email")
    mapping = None if email is None else ColumnMapping(
        email=email, name=single("name"), company=single("company"),
        source_row=single("source_row"), review_reason=single("review_reason"),
    )
    return ColumnProposal(
        mapping=mapping,
        matches={field: tuple(found) for field, found in matches.items()},
        unmatched_headers=tuple(unmatched),
    )


def detect_columns(headers: Sequence[str]) -> ColumnProposal:
    """Propose a mapping for these headers without reading any row.

    The proposal is reported in full by :meth:`ContactImport.describe`, so a person can see what would be
    used before anything is. Detection never refuses on its own: :func:`read_contact_csv` turns an
    unusable proposal into a refusal, and a caller that knows the file can pass its own mapping.
    """
    return _proposal(headers)


@dataclass(frozen=True)
class ContactRow:
    """One source row, with its own text preserved and the key computed separately.

    ``line`` is the line in the file the record ends on (a record whose quotes span lines ends on the
    last of them), so every row can be found again in the person's own editor. ``key`` is ``None`` when
    the email cell is empty: such a row is not grouped with anything.
    """

    line: int
    key: str | None
    email: str
    name: str
    company: str
    source_row: str
    recorded_reasons: str
    flags: tuple[Flag, ...]

    def describe_flags(self) -> str:
        """The row's flags as text, never its values."""
        return ", ".join(flag.value for flag in self.flags)


@dataclass(frozen=True)
class ContactGroup:
    """Every source row that shares one email key, and the labels they disagree about.

    ``companies`` holds the distinct non-empty company labels in the order they first appear and is never
    reduced to one: an email key listed under two employers is a question for the person, not for this
    module.
    """

    key: str
    rows: tuple[ContactRow, ...]
    companies: tuple[str, ...]

    @property
    def conflicts(self) -> bool:
        """Whether these rows disagree about the company, on more than one non-empty label."""
        return len(self.companies) > 1


@dataclass(frozen=True)
class ContactImport:
    """One contact CSV, read and checked, and nothing else. No store, no file, no network."""

    file_name: str
    file_bytes: int
    headers: tuple[str, ...]
    mapping: ColumnMapping
    proposal: ColumnProposal
    rows: tuple[ContactRow, ...]
    groups: tuple[ContactGroup, ...]
    rows_without_key: tuple[ContactRow, ...]
    #: The fields the caller pinned to a named column, as opposed to the ones this module matched from the
    #: header row. A report that did not say which happened would leave a person unable to tell an
    #: assumption they never confirmed from a column set they chose.
    pinned: tuple[str, ...] = ()

    def counts(self) -> Mapping[str, int]:
        """The numbers a preview reports, in the order a person reads them.

        Every count is a count of rows, keys or groups - never of values, and never of anything this
        module cannot see (a mailbox, a consent record, an employer's records).
        """
        flagged = {flag: sum(1 for row in self.rows if flag in row.flags) for flag in Flag}
        counts: dict[str, int] = {
            "rows read": len(self.rows),
            "rows with an email key": len(self.rows) - len(self.rows_without_key),
            "unique email keys": len(self.groups),
            "keys shared by more than one row": sum(1 for group in self.groups if len(group.rows) > 1),
            "rows sharing a key": sum(len(group.rows) for group in self.groups if len(group.rows) > 1),
            # Scoped to the rows that have a key on purpose: a label on a row whose email cell is empty
            # belongs to no group, and counting it here would make this line and the group count disagree.
            "distinct company labels among rows with a key": len({
                label for group in self.groups for label in group.companies
            }),
            "keys whose rows disagree about the company": sum(
                1 for group in self.groups if group.conflicts
            ),
            "keys where no row names a person": (
                sum(1 for group in self.groups if not any(row.name.strip() for row in group.rows))
                if self.mapping.name else 0
            ),
        }
        for flag in Flag:
            counts[f"rows flagged {flag.value}"] = flagged[flag]
        counts["rows with a review note already in the file"] = (
            sum(1 for row in self.rows if row.recorded_reasons.strip()) if self.mapping.review_reason
            else 0
        )
        counts["rows to review"] = sum(1 for row in self.rows if self.needs_review(row))
        return counts

    def needs_review(self, row: ContactRow) -> bool:
        """Whether a person should look at this row: a flag of this module's, or a note in the file."""
        return bool(row.flags) or bool(row.recorded_reasons.strip())

    def rows_to_review(self) -> tuple[ContactRow, ...]:
        """Every row worth a person's attention, in file order."""
        return tuple(row for row in self.rows if self.needs_review(row))

    def describe(self, *, max_example_rows: int = MAX_EXAMPLE_ROWS) -> tuple[str, ...]:
        """The printable preview: what was read, what was checked, and where to look.

        Deliberately contains no cell value from any row - not an email address, not a name, not a
        company label - so it can be read, pasted, logged or attached to a report without copying a
        person's contact details anywhere. Row numbers are the pointer instead.
        """
        counts = self.counts()
        lines = [f"File: {self.file_name} ({self.file_bytes:,} bytes, read only, unchanged)"]
        lines.append(f"Columns in the file: {len(self.headers)}")
        lines.append(
            "Columns used (proposed from the header row; "
            f"{', '.join(self.pinned)} pinned by you - check the rest are the ones you meant):"
            if self.pinned else
            "Columns used (proposed from the header row - check these are the ones you meant):"
        )
        for line in self.mapping.describe():
            lines.append(f"  {line}")
        unmatched = self.proposal.unmatched_headers
        if unmatched:
            shown = ", ".join(repr(name) for name in unmatched[:MAX_HEADERS_LISTED])
            more = f" and {len(unmatched) - MAX_HEADERS_LISTED} more" if len(unmatched) > MAX_HEADERS_LISTED else ""
            lines.append(f"  not used: {len(unmatched)} column(s): {shown}{more}")
        for field in self.proposal.ambiguous_fields():
            if self.mapping.named(field) is not None:
                # The caller said which of the matching columns to use, so this is not an open question.
                continue
            found = self.proposal.matches[field]
            lines.append(
                f"  {field}: not used, because {len(found)} columns match "
                f"({', '.join(repr(item) for item in found)}) - passing a mapping says which one"
            )
        for field, label in (("name", "names"), ("company", "company labels"),
                            ("source_row", "source row numbers")):
            if self.mapping.named(field) is None:
                lines.append(f"  {label}: not checked, because no single column was matched")
        lines.append("")
        for name, value in counts.items():
            lines.append(f"  {name}: {value}")
        for flag in Flag:
            rows = [row for row in self.rows if flag in row.flags]
            if not rows:
                continue
            shown = ", ".join(str(row.line) for row in rows[:max_example_rows])
            more = f" and {len(rows) - max_example_rows} more" if len(rows) > max_example_rows else ""
            lines.append(f"  first lines flagged {flag.value}: {shown}{more}")
        review = self.rows_to_review()
        if review:
            shown = ", ".join(str(row.line) for row in review[:max_example_rows])
            more = f" and {len(review) - max_example_rows} more" if len(review) > max_example_rows else ""
            lines.append(f"  first lines to review: {shown}{more}")
        lines.append("")
        lines.append(
            "Nothing was written: no database, no file, no copy of this one, and no network was used to "
            "read it. Cancelling is free here because no step of this command stores anything."
        )
        lines.append(
            "Checked: the shape of each email address, which is a heuristic about text, and whether the "
            "columns agree with each other. Not checked, and not claimable from a file: whether a mailbox "
            "exists or is reachable, whether anybody agreed to be contacted, who still works where the "
            "file says, or whether this list may be used for outreach at all."
        )
        return tuple(lines)


def _read_bounded(path: Path, limit: int) -> bytes:
    """Read at most ``limit`` bytes, and refuse a file that is larger by reading one byte past it.

    The size was already checked by the caller; it is checked again here because a file can grow between
    the two, and reading one byte over the limit is how that is noticed without ever holding an
    unbounded amount of someone else's data in memory.
    """
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ContactFileTooLarge(
            f"{path.name} is larger than the {limit // (1024 * 1024)} MB limit for a contact CSV. "
            "Nothing was read past the limit and nothing was changed; check that you chose the right file."
        )
    return data


def _existing_file(path: Path) -> Path:
    """Check the chosen path before a byte of it is read."""
    if path.is_dir():
        raise ContactFileUnreadable(
            f"{path.name} is a folder, not a contact CSV file. Nothing was read and nothing was changed."
        )
    if not path.exists():
        raise ContactFileUnreadable(
            f"There is no file at {path.name}. Choose the CSV you exported; nothing was read and nothing "
            "was changed."
        )
    if not path.is_file():
        raise ContactFileUnreadable(
            f"{path.name} is not a regular file that can be read. Nothing was read and nothing was changed."
        )
    if path.stat().st_size == 0:
        raise ContactFileUnreadable(
            f"{path.name} is empty (0 bytes), so it holds no contacts. Export the list again and choose "
            "that file; nothing was read and nothing was changed."
        )
    return path


def _decode(data: bytes, file_name: str) -> str:
    """Decode the file as UTF-8, reporting the encoding honestly rather than guessing one.

    A UTF-8 byte-order mark is expected and removed (spreadsheets write one). A UTF-16 mark is named
    specifically, because a spreadsheet that exported UTF-16 is the common case and "not UTF-8" alone
    would leave a person guessing which setting to change.
    """
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        raise ContactFileUnreadable(
            f"{file_name} looks like UTF-16 text. Re-export or save it as UTF-8 (comma-separated), then "
            "choose it again. Nothing was changed."
        )
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ContactFileUnreadable(
            f"{file_name} is not UTF-8 text: byte {exc.start} is not valid in UTF-8 (this usually means "
            "the file was saved in another encoding). Re-export it as UTF-8 and choose it again. Nothing "
            "was changed."
        ) from None


def _check_headers(headers: Sequence[str], file_name: str) -> None:
    """Refuse a header row that cannot be read as a schema."""
    if not headers:
        raise ContactSchemaError(
            f"{file_name} has no header row. The first line must name the columns, including one that "
            "holds the email address. Nothing was changed."
        )
    blank = [index for index, header in enumerate(headers, start=1) if not header.strip()]
    if blank:
        raise ContactSchemaError(
            f"{file_name} has {len(blank)} column(s) with no name in the header row (column "
            f"{', '.join(str(index) for index in blank)}). Every column needs a name so a preview can "
            "say which one it read. Nothing was changed."
        )
    seen: dict[str, str] = {}
    for header in headers:
        wanted = normalise_header(header)
        if wanted in seen:
            raise ContactSchemaError(
                f"{file_name} names two columns {seen[wanted]!r} and {header!r}, which differ only in "
                "case or spacing. A preview cannot tell them apart, so it reads neither. Nothing was "
                "changed."
            )
        seen[wanted] = header


def _check_pinned(columns: Mapping[str, str], headers: Sequence[str], file_name: str) -> None:
    """Refuse a pinned column that is not a field, or names a column this file does not have."""
    known = {normalise_header(header): header for header in headers}
    for field, named in columns.items():
        if field not in _MAPPING_FIELDS:
            raise ContactImportError(
                f"{field!r} is not a column this preview reads, so nothing was read and nothing was "
                f"changed. It reads: {', '.join(_MAPPING_FIELDS)}."
            )
        if normalise_header(named) not in known:
            raise ContactSchemaError(
                f"{file_name} has no column named {named!r} for the {field.replace('_', ' ')}. Its "
                f"columns are: {', '.join(repr(header) for header in headers)}. Nothing was changed."
            )


def _mapping_for(headers: Sequence[str], file_name: str,
                 columns: Mapping[str, str] | None) -> tuple[ColumnMapping, ColumnProposal, tuple[str, ...]]:
    """The mapping to read with: what the caller pinned, and what detection could resolve around it."""
    proposal = detect_columns(headers)
    pinned = columns or {}
    _check_pinned(pinned, headers, file_name)

    resolved: dict[str, str | None] = {}
    for field in _MAPPING_FIELDS:
        if field in pinned:
            resolved[field] = pinned[field]
            continue
        found = proposal.matches.get(field, ())
        resolved[field] = found[0] if len(found) == 1 else None

    if resolved["email"] is None:
        ambiguous = proposal.matches.get("email", ())
        if ambiguous:
            raise ContactSchemaError(
                f"{file_name} has {len(ambiguous)} columns that could hold the email address "
                f"({', '.join(repr(name) for name in ambiguous)}), and a preview will not choose between "
                "them: name the one to use with --contact-email-column. Nothing was changed."
            )
        raise ContactSchemaError(
            f"{file_name} has no column this preview recognises as the email address. Its columns are: "
            f"{', '.join(repr(header) for header in headers)}. Nothing was changed; name the column that "
            "holds the address with --contact-email-column and read it again."
        )
    mapping = ColumnMapping(
        email=resolved["email"], name=resolved["name"], company=resolved["company"],
        source_row=resolved["source_row"], review_reason=resolved["review_reason"],
    )
    return mapping, proposal, tuple(field for field in _MAPPING_FIELDS if field in pinned)


def _row_from(record: Mapping[str, str], line: int, mapping: ColumnMapping) -> ContactRow:
    """One parsed record, with every cell kept exactly as the file wrote it."""

    def cell(field: str) -> str:
        named = mapping.named(field)
        if named is None:
            return ""
        value = record.get(named, "")
        return value if isinstance(value, str) else ""

    email = cell("email")
    key = normalise_email_key(email) or None
    return ContactRow(
        line=line, key=key, email=email, name=cell("name"), company=cell("company"),
        source_row=cell("source_row"), recorded_reasons=cell("review_reason"), flags=(),
    )


def _flagged(rows: Sequence[ContactRow], mapping: ColumnMapping) -> tuple[ContactRow, ...]:
    """Every row again, with the flags its own text and its group's text justify."""
    groups: dict[str, list[ContactRow]] = {}
    for row in rows:
        if row.key is not None:
            groups.setdefault(row.key, []).append(row)
    shared = {key for key, members in groups.items() if len(members) > 1}
    conflicting = set()
    if mapping.company:
        for key, members in groups.items():
            labels = {member.company.strip() for member in members if member.company.strip()}
            if len(labels) > 1:
                conflicting.add(key)

    flagged = []
    for row in rows:
        reasons = []
        if not row.email.strip():
            reasons.append(Flag.EMAIL_MISSING)
        elif not looks_like_email(row.email):
            reasons.append(Flag.EMAIL_SYNTAX)
        if mapping.name and not row.name.strip():
            reasons.append(Flag.NAME_MISSING)
        if row.key is not None and row.key in shared:
            reasons.append(Flag.DUPLICATE_KEY)
        if row.key is not None and row.key in conflicting:
            reasons.append(Flag.COMPANY_CONFLICT)
        flagged.append(ContactRow(
            line=row.line, key=row.key, email=row.email, name=row.name, company=row.company,
            source_row=row.source_row, recorded_reasons=row.recorded_reasons, flags=tuple(reasons),
        ))
    return tuple(flagged)


def _groups(rows: Sequence[ContactRow]) -> tuple[tuple[ContactGroup, ...], tuple[ContactRow, ...]]:
    """Group the rows by their email key, keeping each group's labels in first-seen order."""
    order: list[str] = []
    members: dict[str, list[ContactRow]] = {}
    for row in rows:
        if row.key is None:
            continue
        if row.key not in members:
            members[row.key] = []
            order.append(row.key)
        members[row.key].append(row)
    groups = []
    for key in order:
        labels: list[str] = []
        for row in members[key]:
            label = row.company.strip()
            if label and label not in labels:
                labels.append(label)
        groups.append(ContactGroup(key=key, rows=tuple(members[key]), companies=tuple(labels)))
    orphans = tuple(row for row in rows if row.key is None)
    return tuple(groups), orphans


def read_contact_csv(path: Path | str, *, columns: Mapping[str, str] | None = None) -> ContactImport:
    """Read one contact CSV locally, check it, and return everything a preview needs.

    Reads nothing but the file, writes nothing anywhere, and reaches no network. ``columns`` pins any
    field to a named column (``{"email": "Email Key"}``) when the caller knows the file better than the
    detection does; everything else is detected, and any ambiguity that would change what is read is
    refused rather than guessed. The returned object is frozen, and reading the same file twice returns
    equal objects, which is the whole of what "idempotent" means while nothing is stored: there is no
    state to duplicate.
    """
    source = _existing_file(Path(path).expanduser())
    data = _read_bounded(source, MAX_CONTACT_CSV_BYTES)
    text = _decode(data, source.name)
    stream = io.StringIO(text, newline="")
    reader = csv.DictReader(stream, restval="")
    rows: list[ContactRow] = []
    try:
        # The header is read through the same try block as the rows: the parser can refuse the very first
        # line (a NUL byte in it, for instance), and a refusal about line 1 must be this module's sentence
        # rather than an unexpected failure.
        headers = tuple(reader.fieldnames or ())
        _check_headers(headers, source.name)
        resolved, proposal, pinned = _mapping_for(headers, source.name, columns)
        for record in reader:
            if len(rows) >= MAX_CONTACT_ROWS:
                raise ContactFileTooLarge(
                    f"{source.name} holds more than {MAX_CONTACT_ROWS:,} rows, over the limit for a "
                    "preview. Nothing was read past the limit and nothing was changed."
                )
            extras = record.get(None)
            if extras:
                raise ContactCsvMalformed(
                    f"{source.name} has a record with more fields than its header row: line "
                    f"{reader.line_num} has {len(headers) + len(extras)} values where the header names "
                    f"{len(headers)} columns. Nothing was changed."
                )
            rows.append(_row_from(record, reader.line_num, resolved))
    except csv.Error as exc:
        raise ContactCsvMalformed(
            f"{source.name} is not well-formed CSV: the parser could not read line "
            f"{reader.line_num or 1} ({exc}). Nothing was changed; re-export the file and choose it again."
        ) from None

    flagged = _flagged(rows, resolved)
    groups, orphans = _groups(flagged)
    return ContactImport(
        file_name=source.name, file_bytes=len(data), headers=headers, mapping=resolved,
        proposal=proposal, rows=flagged, groups=groups, rows_without_key=orphans, pinned=pinned,
    )


def read_contact_csvs(paths: Iterable[Path | str], *,
                      columns: Mapping[str, str] | None = None) -> tuple[ContactImport, ...]:
    """Read several files the same way, one at a time, refusing at the first that cannot be read.

    Here because a list exported in two batches (a deduplicated export and a review queue, say) with the
    same columns should be checkable as one job without a caller looping by hand. Each file is read
    independently: nothing is merged, and no key found in one file changes what another file reports.
    """
    return tuple(read_contact_csv(path, columns=columns) for path in paths)
