"""The HR contact list as a file a person owns: the format, and the one place it is written.

This module is the contract for the export the HR contacts tab and ``--export-contacts-to`` both write.
It reads the stored contacts and nothing else, it writes nothing into the database, and it is the only
writer of this format - so the file cannot drift from the columns documented here.

The format (version ``hr-contact-export/1``)
--------------------------------------------

One comma-separated file, UTF-8 with a byte-order mark, lines ended ``\\r\\n``, one header row and one row
per stored contact, in the order the contacts were first stored (the database's own order, ``contact_id``).

===========================  ==========================================================================
``Email``                    The address as stored. The key an import matches on, normalised by
                             stripping and case-folding it and by nothing else.
``Name``                     The person's name as stored, empty when the record has none.
``Company``                  The company label as stored, empty when the record has none.
``Do Not Contact``           ``yes`` when the record carries the do-not-contact mark, ``no`` when it does
                             not. This is the safety-critical column: see below.
``Export Format``            ``hr-contact-export/1`` on every row, so a file that is renamed, trimmed or
                             handed on can still say what it is.
===========================  ==========================================================================

Excluded on purpose, because a portable list of contacts does not need them and a backup of the database
does not come from this file: internal identifiers, first and last seen dates, import counts, the source
file and source row, review flags and reasons, disagreement values, the date and the note a
do-not-contact mark carries, and every activity record. The whole-database backup on the Data safety tab
is what copies those - it copies the database itself.

Cells holding a comma, a quote or a line ending are quoted and their quotes doubled (RFC 4180), which is
what ``career_agent.contacts.read_contact_csv`` reads back. A cell whose first character is ``=``, ``+``,
``-`` or ``@`` is written with a leading apostrophe, because a spreadsheet would otherwise read a name
from somebody else's file as a formula and run it. That apostrophe is part of the text in the file: it is
the price of the file being safe to open, it is added only where the first character would otherwise make
a spreadsheet try to evaluate the cell, and this application's own reader sees it as the first character
of the value.

Suppression safety, and why this is not a backup
------------------------------------------------

The do-not-contact mark is written into the file as readable text above, and **an import of this file
cannot set or clear it**. That is deliberate and it is a limitation, not an accident: the mark is the
person's own decision about somebody on their list, and the store's comments, the import's statements and
its tests all hold that no file may write that column - a file that could set a mark could also set one
for an address it had no business deciding about. So the export does not claim to preserve that state: the
column is there for a person to read after a transfer, and re-applying a mark is a decision they make in
the window that has always made it. A file this module writes therefore must never be described as a
safety-preserving backup; the whole-database backup, which copies the mark with everything else, is the
thing that is.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from . import contacts
from .store import PrivateWriteError, write_private_bytes_file

if TYPE_CHECKING:  # pragma: no cover - imported for typing only, so a headless command can run
    from .store import CareerStore, ContactRecord

#: The format's own name and version, and the single cell that states them in the file.
CONTACT_EXPORT_FORMAT_NAME = "hr-contact-export"
CONTACT_EXPORT_FORMAT_VERSION = 1
CONTACT_EXPORT_FORMAT = f"{CONTACT_EXPORT_FORMAT_NAME}/{CONTACT_EXPORT_FORMAT_VERSION}"

#: The columns, in the order they are written. Fixed: a reader that finds them in another order is still
#: reading this format (the header row names them), but this is what this version writes.
CONTACT_EXPORT_HEADERS: tuple[str, ...] = ("Email", "Name", "Company", "Do Not Contact", "Export Format")

#: What the do-not-contact column holds. Two literals, never an empty cell: an empty cell would have to be
#: read as "no", and a person filtering the column cannot filter by an absence.
DO_NOT_CONTACT_YES = "yes"
DO_NOT_CONTACT_NO = "no"

#: A byte-order mark, written as the first character of the file. It is what tells a spreadsheet that the
#: file is UTF-8 rather than the platform's older code page, and this application's reader expects one and
#: strips it. Written as an escape so the source file itself stays plain ASCII at this point.
_BYTE_ORDER_MARK = "\ufeff"

#: RFC 4180's line ending, and the reason this module writes bytes rather than text: a text write would
#: translate it to the platform's own separator, which would make one documented format two files.
_LINE_TERMINATOR = "\r\n"

#: The characters that make a spreadsheet read a cell as a formula rather than as text. Checked against the
#: first character only: that is what decides how the whole cell is read.
_FORMULA_LEADERS = ("=", "+", "-", "@")

#: The one sentence about the do-not-contact column that the window, the command line and the research note
#: must not disagree about. Defined here because it is a claim about the format, and a claim written twice
#: is a claim that can be written differently twice.
MARK_COLUMN_LIMITATION = (
    "The \"Do Not Contact\" column says which contacts are marked do not contact in the database they "
    "were exported from. An import of this file cannot set or clear that mark - a mark is only ever made "
    "in the database it belongs to - so read the column rather than expecting it to be applied."
)


class ContactExportRefused(Exception):
    """The stored list cannot be written as a file this application could read back.

    Raised before anything is written, with a sentence that says what was found, what the limit is and
    what to use instead. A file too large to read back is not an export of the person's list, and this
    program must not call one.
    """


@dataclass(frozen=True)
class ContactExport:
    """One built export: the rows it would hold, and the counts a report may carry.

    ``rows`` starts with the header row, so ``len(rows) - 1`` is the number of contacts. Values are kept
    exactly as they will be written, apostrophe guard included, so a test can compare the file with what
    this object says it holds rather than with a second implementation of the same rules.
    """

    rows: tuple[tuple[str, ...], ...]
    contacts: int
    marked: int

    def text(self) -> str:
        """The file's text, byte-order mark included, exactly as it is written."""
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator=_LINE_TERMINATOR, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(self.rows)
        return _BYTE_ORDER_MARK + buffer.getvalue()

    def payload(self) -> bytes:
        """The file's bytes. UTF-8, and the only encoding this format has."""
        return self.text().encode("utf-8")


@dataclass(frozen=True)
class ContactExportOutcome:
    """What one completed export did: where it went and what it holds, counted."""

    path: Path
    contacts: int
    marked: int
    bytes_written: int

    def describe(self) -> str:
        """One sentence for the window's report: counts and a size, never a value and never a path.

        The path is deliberately not in it. A dialog is the part of this program that ends up in a
        screenshot, and a folder name is somebody's account name as often as it is anything else; the
        command line prints the path instead, because that is the person's own terminal.
        """
        return (
            f"Wrote {self.contacts} contact(s) - {self.marked} marked do not contact - "
            f"to the file you chose ({self.bytes_written:,} bytes)."
        )


def spreadsheet_safe(value: str) -> str:
    """``value`` as a spreadsheet-safe cell: a leading apostrophe where a formula would otherwise start.

    A comma, a quote or a line ending is handled by the writer's own quoting; this handles the one thing
    quoting does not, which is a cell a spreadsheet *executes*. The apostrophe is the convention every
    spreadsheet understands as "treat what follows as text", and it is only added when the first character
    would otherwise make the cell a formula, so ordinary names, addresses and company labels are written
    exactly as they are stored.
    """
    if value[:1] in _FORMULA_LEADERS:
        return "'" + value
    return value


def export_row(record: ContactRecord) -> tuple[str, ...]:
    """One stored contact as one row of this format, in the documented column order."""
    return (
        spreadsheet_safe(record.email),
        spreadsheet_safe(record.name or ""),
        spreadsheet_safe(record.company or ""),
        DO_NOT_CONTACT_YES if record.suppressed else DO_NOT_CONTACT_NO,
        CONTACT_EXPORT_FORMAT,
    )


def export_document(store: CareerStore) -> ContactExport:
    """Read the stored contact list and build the export, writing nothing anywhere.

    Read-only: the contacts are read through the store's own list method and no statement here changes a
    row. A record this build cannot decode raises the store's ``StoredRecordError`` and is never skipped,
    because an export that quietly left a contact out would be a shorter list the person believes is
    whole. A list larger than this application can read back raises :class:`ContactExportRefused` before a
    path is even created.
    """
    records: Sequence[ContactRecord] = store.list_contacts()
    if len(records) > contacts.MAX_CONTACT_ROWS:
        raise ContactExportRefused(
            f"This database holds {len(records):,} contacts, more than the {contacts.MAX_CONTACT_ROWS:,} "
            "rows this application's contact format reads back, so nothing was written. A file this "
            "program could not read again would not be an export of your list: use the whole-database "
            "backup on the Data safety tab to copy every contact and every mark."
        )
    rows = (CONTACT_EXPORT_HEADERS, *(export_row(record) for record in records))
    export = ContactExport(
        rows=rows,
        contacts=len(records),
        marked=sum(1 for record in records if record.suppressed),
    )
    size = len(export.payload())
    if size > contacts.MAX_CONTACT_CSV_BYTES:
        raise ContactExportRefused(
            f"The contact list is {size:,} bytes as this format writes it, over the "
            f"{contacts.MAX_CONTACT_CSV_BYTES:,} bytes this application reads back, so nothing was "
            "written. Use the whole-database backup on the Data safety tab to copy every contact and "
            "every mark."
        )
    return export


def write_export(store: CareerStore, path: str | Path) -> ContactExportOutcome:
    """Write the stored contact list to ``path`` and report what was written, or raise.

    The file is created through the store's own private write path, so it is owner-only from the first
    byte where the platform has POSIX permissions and it is never written through a symbolic link. An
    existing file at ``path`` is replaced, which is why the window only ever calls this with a path a
    person confirmed in a save dialog and the command line refuses an existing path outright.

    Success is reported only after the file has been read back and compared with what was written. A file
    that does not hold exactly that is removed where possible and the call raises instead of returning: an
    export that claims a list it did not write is worse than one that failed.
    """
    export = export_document(store)
    payload = export.payload()
    target = Path(path)
    write_private_bytes_file(target, payload)
    try:
        written = target.read_bytes()
    except OSError as exc:
        raise PrivateWriteError(
            f"{target} was written but could not be read back to check it: {exc.strerror or exc}. Delete "
            "the export and write it again."
        ) from exc
    if written != payload:
        try:
            target.unlink()
            outcome = "so it was removed"
        except OSError:
            outcome = "so delete it yourself"
        raise PrivateWriteError(
            f"{target} did not hold what was written ({len(written):,} of {len(payload):,} bytes "
            f"readable), {outcome}. Nothing was exported."
        )
    return ContactExportOutcome(
        path=target, contacts=export.contacts, marked=export.marked, bytes_written=len(payload)
    )
