"""Tests for local résumé import (PDF and DOCX): extraction, limits, parsing, and privacy.

Fixtures are built in the test process: a small PDF writer for the PDF cases, and :mod:`zipfile` for
the DOCX cases. Nothing is downloaded and no real résumé (or real candidate detail) is used - every
document here is synthetic. PDF cases are skipped, with a stated reason, when the optional
``pypdf`` package is not installed; they run in CI, which installs it.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from dataclasses import fields
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import escape

from career_agent import resume
from career_agent.resume import (
    DocumentFormat, FieldProposal, ProposalConfidence, ResumeEncrypted, ResumeImportError,
    ResumeNoText, ResumeTooLarge, ResumeUnreadable,
)

PDF_AVAILABLE = resume.PDF_SUPPORT_AVAILABLE

# --------------------------------------------------------------------------------------
# Synthetic fixtures
# --------------------------------------------------------------------------------------

PDF_HEADER = b"%PDF-1.4\n"


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _text_stream(lines) -> str:
    body = ["BT /F1 12 Tf 72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            body.append("0 -16 Td")
        body.append(f"({_escape_pdf_text(line)}) Tj")
    body.append("ET")
    return "\n".join(body)


def build_pdf(pages, *, extra_objects: bool = True) -> bytes:
    """A minimal, valid PDF with the given text lines on each page.

    ``pages`` is a sequence of line sequences; a page with no lines has an empty content stream, which
    is what a scanned page looks like to a text extractor.
    """
    count = len(pages)
    font_number = 3 + 2 * count
    content_numbers = [3 + count + index for index in range(count)]
    page_numbers = [3 + index for index in range(count)]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{number} 0 R' for number in page_numbers)}] /Count {count} >>".encode(),
    ]
    for index in range(count):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
            f"<< /Font << /F1 {font_number} 0 R >> >> /Contents {content_numbers[index]} 0 R >>".encode()
        )
    for lines in pages:
        stream = _text_stream(lines).encode("latin-1", "replace") if lines else b"0.9 0.9 0.9 rg"
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    document = bytearray(PDF_HEADER)
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n".encode()
    document += b"0000000000 65535 f \n"
    for offset in offsets:
        document += f"{offset:010d} 00000 n \n".encode()
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(document)


def encrypt_pdf(data: bytes, password: str) -> bytes:
    """Re-write ``data`` as an encrypted PDF (used only to produce this test's own fixtures)."""
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _docx_paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def _docx_table(rows) -> str:
    body = []
    for row in rows:
        if isinstance(row, str):
            # A bare string "row" would iterate as its characters, producing a table of one-letter
            # cells that still looks plausible when it is extracted. Refuse it here instead.
            raise TypeError("a table row must be a sequence of cell strings, not a string")
        cells = "".join(f"<w:tc>{_docx_paragraph(str(cell))}</w:tc>" for cell in row)
        body.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(body)}</w:tbl>"


def _patch_zip_headers(data: bytes, fields) -> bytes:
    """Rewrite fields in every ZIP local header and central entry of an already-built archive.

    ``fields`` is a sequence of ``(signature, offset_in_header, width, value)``. This is how the tests
    reproduce a DOCX written by another tool - a password-protected member, or a compression method
    this build cannot read - without depending on that tool being installed.
    """
    patched = bytearray(data)
    for signature, offset, width, value in fields:
        position = patched.find(signature)
        while position != -1:
            patched[position + offset:position + offset + width] = value.to_bytes(width, "little")
            position = patched.find(signature, position + 4)
    return bytes(patched)


def encrypt_docx_members(data: bytes) -> bytes:
    """A DOCX whose ZIP members carry the encryption flag, as a password-protected re-save looks."""
    return _patch_zip_headers(data, [(b"PK\x03\x04", 6, 2, 0x1), (b"PK\x01\x02", 8, 2, 0x1)])


def set_docx_compression(data: bytes, method: int) -> bytes:
    """A DOCX whose members declare ``method`` as their compression method."""
    return _patch_zip_headers(data, [(b"PK\x03\x04", 8, 2, method), (b"PK\x01\x02", 10, 2, method)])


def build_docx_without_document_part() -> bytes:
    """A ZIP that is not a DOCX: it has no ``word/document.xml`` part."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    return buffer.getvalue()


def build_docx(*, paragraphs=(), tables=(), document_xml=None, macro=False, extra_parts=()) -> bytes:
    """A minimal but structurally real DOCX built with the standard library."""
    if document_xml is None:
        body = "".join(_docx_paragraph(text) for text in paragraphs)
        body += "".join(_docx_table(rows) for rows in tables)
        document_xml = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body></w:document>"
        )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<?xml version='1.0' encoding='UTF-8'?>"
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            "<?xml version='1.0' encoding='UTF-8'?>"
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        )
        archive.writestr("word/document.xml", document_xml)
        if macro:
            archive.writestr("word/vbaProject.bin", b"synthetic macro payload, never executed")
        for name, payload in extra_parts:
            archive.writestr(name, payload)
    return buffer.getvalue()


RESUME_PARAGRAPHS = (
    "Sample Candidate",
    "sample.candidate@example.invalid | +91 90000 00000",
    "Summary",
    "A synthetic résumé used only by the test suite.",
    "Education",
    "B.Tech in Computer Science, Example Institute of Technology",
    "Expected graduation: 2027",
    "Skills",
    "Python, SQL, Data Structures",
    "Experience",
    "3 years of experience with Python and SQL",
)


class ResumeTestCase(unittest.TestCase):
    """A temporary folder per test; fixtures are written there and nothing else is created."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.folder = Path(self._directory.name)

    def write(self, name: str, data: bytes) -> Path:
        path = self.folder / name
        path.write_bytes(data)
        return path

    def write_pdf(self, name="resume.pdf", pages=(("Sample Candidate",),)) -> Path:
        return self.write(name, build_pdf(list(pages)))

    def write_docx(self, name="resume.docx", **kwargs) -> Path:
        return self.write(name, build_docx(**kwargs))


# --------------------------------------------------------------------------------------
# PDF extraction
# --------------------------------------------------------------------------------------


@unittest.skipUnless(PDF_AVAILABLE, "the optional pypdf package is not installed")
@unittest.skipUnless(PDF_AVAILABLE, "the optional pypdf package is not installed")
class PdfSidebarLayoutTests(ResumeTestCase):
    """The reported case, end to end: pypdf returns a sidebar heading and its list as one line."""

    def test_a_sidebar_heading_and_its_list_on_one_line_are_parsed(self):
        path = self.write("sidebar.pdf", build_pdf_runs([
            (72, 720, "Sample Candidate"),
            (72, 700, "SKILLS"),
            (190, 700, "Python, SQL, PyTorch"),
            (72, 680, "EDUCATION"),
            (190, 680, "B.Tech in Computer Science, 2027"),
        ]))

        document = resume.extract_text(path)
        self.assertIn("SKILLS Python, SQL, PyTorch", document.text, "the extractor joins the two columns")

        result = resume.parse_resume(path)

        skills = resume.proposal_by_key(result, "skills")
        self.assertIsNotNone(skills, "a sidebar layout must not lose its skills list")
        self.assertEqual(skills.value, "Python, SQL, PyTorch")
        self.assertIsNotNone(resume.proposal_by_key(result, "degree"))


@unittest.skipUnless(PDF_AVAILABLE, "the optional pypdf package is not installed")
class PdfExtractionTests(ResumeTestCase):
    def test_text_is_extracted_from_a_text_based_pdf(self):
        path = self.write_pdf(pages=(("Sample Candidate", "B.Tech in Computer Science", "Skills: Python"),))

        document = resume.extract_text(path)

        self.assertIs(document.source_format, DocumentFormat.PDF)
        self.assertIn("Sample Candidate", document.text)
        self.assertIn("B.Tech in Computer Science", document.text)

    def test_every_page_contributes_text(self):
        path = self.write_pdf(pages=(("First page line",), ("Second page line",)))

        document = resume.extract_text(path)

        self.assertIn("First page line", document.text)
        self.assertIn("Second page line", document.text)

    def test_a_page_without_text_is_reported_as_a_note(self):
        path = self.write_pdf(pages=(("Text page",), ()))

        document = resume.extract_text(path)

        self.assertTrue(any("no selectable text" in note for note in document.notes), document.notes)

    def test_a_pdf_with_no_text_at_all_is_refused_as_scanned(self):
        path = self.write_pdf(pages=((),))

        with self.assertRaises(ResumeNoText) as caught:
            resume.extract_text(path)

        message = str(caught.exception)
        self.assertIn("no selectable text", message)
        self.assertIn("OCR", message, "the message must say that OCR is not included")
        self.assertIn("resume.pdf", message)

    def test_reading_a_damaged_pdf_prints_nothing(self):
        """pypdf logs structural complaints to stderr; a document must not reach the terminal."""
        whole = build_pdf([("Confidential marker sentence",)])
        path = self.write("damaged.pdf", whole[: len(whole) // 2])
        captured = io.StringIO()

        with mock.patch("sys.stderr", captured):
            with self.assertRaises(ResumeUnreadable):
                resume.extract_text(path)

        self.assertEqual(captured.getvalue(), "", "nothing may be printed while reading a document")

    def test_a_damaged_page_does_not_silently_vanish(self):
        import pypdf

        path = self.write_pdf(pages=(("First page",), ("Second page",)))
        real_extract = pypdf.PageObject.extract_text
        calls = []

        def flaky(self, *args, **kwargs):
            calls.append(self)
            if len(calls) == 1:  # the first page fails to extract, the second must still be read
                raise ValueError("synthetic extraction failure")
            return real_extract(self, *args, **kwargs)

        with mock.patch.object(pypdf.PageObject, "extract_text", flaky):
            document = resume.extract_text(path)

        self.assertEqual(len(calls), 2, "every page must still be attempted")
        self.assertIn("Second page", document.text)
        self.assertTrue(any("no selectable text" in note for note in document.notes))

    def test_a_password_protected_pdf_is_refused_with_a_clear_message(self):
        source = build_pdf([("Protected content must not appear",)])
        path = self.write("protected.pdf", encrypt_pdf(source, "synthetic-password"))

        with self.assertRaises(ResumeEncrypted) as caught:
            resume.extract_text(path)

        message = str(caught.exception)
        self.assertIn("password-protected", message)
        self.assertNotIn("Protected content", message, "no document text may appear in an error")

    def test_a_pdf_encrypted_with_an_empty_password_is_read(self):
        source = build_pdf([("Empty password text",)])
        path = self.write("empty-password.pdf", encrypt_pdf(source, ""))

        document = resume.extract_text(path)

        self.assertIn("Empty password text", document.text)

    def test_a_truncated_pdf_is_refused(self):
        whole = build_pdf([("Some text",)])
        path = self.write("truncated.pdf", whole[: max(1, len(whole) // 2)])

        with self.assertRaises(ResumeUnreadable):
            resume.extract_text(path)

    def test_a_file_that_only_calls_itself_a_pdf_is_refused(self):
        path = self.write("not-really.pdf", b"This is plain text with a .pdf extension.")

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("does not start like a PDF", str(caught.exception))

    def test_too_many_pages_are_refused_rather_than_partly_read(self):
        pages = [(f"Page {index} line",) for index in range(resume.MAX_PDF_PAGES + 1)]
        path = self.write_pdf(name="long.pdf", pages=pages)

        with self.assertRaises(ResumeTooLarge) as caught:
            resume.extract_text(path)

        self.assertIn(str(resume.MAX_PDF_PAGES), str(caught.exception))


# --------------------------------------------------------------------------------------
# DOCX extraction
# --------------------------------------------------------------------------------------


class DocxExtractionTests(ResumeTestCase):
    def test_paragraphs_are_extracted(self):
        path = self.write_docx(paragraphs=("Sample Candidate", "B.Tech in Computer Science"))

        document = resume.extract_text(path)

        self.assertIs(document.source_format, DocumentFormat.DOCX)
        self.assertIn("Sample Candidate", document.text)
        self.assertIn("B.Tech in Computer Science", document.text)

    def test_table_cells_are_extracted_as_rows(self):
        path = self.write_docx(
            paragraphs=("Education",),
            tables=((("Institution", "Example Institute of Technology"),
                     ("Degree", "B.Tech in Computer Science"),
                     ("Graduation", "Expected 2027")),),
        )

        document = resume.extract_text(path)

        self.assertIn("Institution | Example Institute of Technology", document.text)
        self.assertIn("Degree | B.Tech in Computer Science", document.text)
        self.assertIn("Expected 2027", document.text)

    def test_a_macro_project_is_reported_and_never_run(self):
        path = self.write_docx(paragraphs=("Sample Candidate",), macro=True)

        document = resume.extract_text(path)

        self.assertIn("Sample Candidate", document.text)
        self.assertTrue(any("macro" in note.lower() for note in document.notes), document.notes)
        self.assertTrue(any("ignored" in note.lower() for note in document.notes), document.notes)

    def test_a_document_with_no_text_is_refused(self):
        path = self.write_docx(paragraphs=())

        with self.assertRaises(ResumeNoText):
            resume.extract_text(path)

    def test_an_invalid_xml_document_is_refused_without_echoing_it(self):
        path = self.write_docx(document_xml="<w:document><w:body><w:p>not closed")

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("not well formed", str(caught.exception))
        self.assertNotIn("not closed", str(caught.exception))

    def test_a_document_type_declaration_is_refused(self):
        payload = (
            "<?xml version='1.0'?><!DOCTYPE w:document [<!ENTITY x 'expanded text'>]>"
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>"
        )
        path = self.write_docx(document_xml=payload)

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("document type declaration", str(caught.exception))

    def test_a_zip_without_the_document_part_is_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/other.xml", "<x/>")
        path = self.write("no-document.docx", buffer.getvalue())

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("word/document.xml", str(caught.exception))

    def test_a_damaged_zip_is_refused(self):
        whole = build_docx(paragraphs=("Sample",))
        path = self.write("damaged.docx", whole[: len(whole) // 2])

        with self.assertRaises(ResumeUnreadable):
            resume.extract_text(path)

    def test_a_plain_text_file_named_docx_is_refused(self):
        path = self.write("not-really.docx", b"plain text, not a zip archive")

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("not a DOCX file", str(caught.exception))

    def test_an_encrypted_or_legacy_office_file_is_named_as_such(self):
        path = self.write("encrypted.docx", resume._OLE_CONTAINER_SIGNATURE + b"\x00" * 64)

        with self.assertRaises(ResumeEncrypted) as caught:
            resume.extract_text(path)

        self.assertIn("encrypted Office file", str(caught.exception))

    def test_a_document_that_expands_beyond_the_budget_is_refused_before_decompression(self):
        huge_text = "x" * (resume.MAX_DOCX_UNCOMPRESSED_BYTES + 1024)
        path = self.write_docx(document_xml=f"<w:document><w:body><w:p>{huge_text}</w:p></w:body></w:document>")

        with self.assertRaises(ResumeTooLarge) as caught:
            resume.extract_text(path)

        self.assertIn("uncompressed", str(caught.exception))


# --------------------------------------------------------------------------------------
# Limits and file handling that apply to both formats
# --------------------------------------------------------------------------------------


class FileHandlingTests(ResumeTestCase):
    def test_a_file_over_the_size_limit_is_refused_before_it_is_read(self):
        path = self.write("huge.docx", b"x" * 64)

        with mock.patch.object(resume, "MAX_RESUME_BYTES", 16):
            with self.assertRaises(ResumeTooLarge) as caught:
                resume.extract_text(path)

        self.assertIn("limit", str(caught.exception))

    def test_a_file_that_grows_past_the_limit_is_refused(self):
        small = build_docx(paragraphs=("Sample",))
        path = self.write("grows.docx", small)

        with mock.patch.object(resume, "MAX_RESUME_BYTES", len(small) - 1):
            with self.assertRaises(ResumeTooLarge):
                resume.extract_text(path)

    def test_documents_over_the_text_limit_are_refused_not_truncated(self):
        long_paragraph = "word " * (resume.MAX_EXTRACTED_CHARACTERS // 4)
        path = self.write_docx(paragraphs=(long_paragraph,))

        with self.assertRaises(ResumeTooLarge) as caught:
            resume.extract_text(path)

        self.assertIn("characters", str(caught.exception))

    def test_an_empty_file_is_refused(self):
        path = self.write("empty.pdf", b"")

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("empty", str(caught.exception))

    def test_a_missing_file_is_refused(self):
        with self.assertRaises(ResumeUnreadable):
            resume.extract_text(self.folder / "absent.pdf")

    def test_a_folder_is_refused(self):
        folder = self.folder / "folder.pdf"
        folder.mkdir()

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(folder)

        self.assertIn("folder", str(caught.exception))

    def test_unsupported_and_legacy_extensions_are_named(self):
        text_file = self.write("resume.txt", b"plain text")
        legacy = self.write("resume.doc", b"\xd0\xcf\x11\xe0legacy")

        with self.assertRaises(ResumeUnreadable) as unsupported:
            resume.extract_text(text_file)
        with self.assertRaises(ResumeUnreadable) as old:
            resume.extract_text(legacy)

        self.assertIn("not a supported", str(unsupported.exception))
        self.assertIn(".docx or PDF", str(old.exception))

    def test_reading_a_malformed_docx_prints_nothing(self):
        """A failed read reports through its message only: nothing is written to the console."""
        path = self.write("damaged.docx", b"PK\x03\x04damaged archive payload")
        captured = io.StringIO()

        with mock.patch("sys.stderr", captured):
            with self.assertRaises(ResumeUnreadable):
                resume.extract_text(path)

        self.assertEqual(captured.getvalue(), "")

    def test_reading_a_document_creates_no_files_and_keeps_no_copy(self):
        path = self.write_docx(paragraphs=RESUME_PARAGRAPHS)
        before = sorted(self.folder.iterdir())

        resume.parse_resume(path)

        self.assertEqual(sorted(self.folder.iterdir()), before, "no copy or temporary file may appear")


# --------------------------------------------------------------------------------------
# Parsing: proposals, evidence, confidence, and what is deliberately not guessed
# --------------------------------------------------------------------------------------

class FileHandlingTests(ResumeTestCase):
    def test_a_file_over_the_size_limit_is_refused_before_it_is_read(self):
        path = self.write("huge.docx", b"x" * 64)

        with mock.patch.object(resume, "MAX_RESUME_BYTES", 16):
            with self.assertRaises(ResumeTooLarge) as caught:
                resume.extract_text(path)

        self.assertIn("limit", str(caught.exception))

    def test_a_file_that_grows_past_the_limit_is_refused(self):
        small = build_docx(paragraphs=("Sample",))
        path = self.write("grows.docx", small)

        with mock.patch.object(resume, "MAX_RESUME_BYTES", len(small) - 1):
            with self.assertRaises(ResumeTooLarge):
                resume.extract_text(path)

    def test_documents_over_the_text_limit_are_refused_not_truncated(self):
        long_paragraph = "word " * (resume.MAX_EXTRACTED_CHARACTERS // 4)
        path = self.write_docx(paragraphs=(long_paragraph,))

        with self.assertRaises(ResumeTooLarge) as caught:
            resume.extract_text(path)

        self.assertIn("characters", str(caught.exception))

    def test_an_empty_file_is_refused(self):
        path = self.write("empty.pdf", b"")

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("empty", str(caught.exception))

    def test_a_missing_file_is_refused(self):
        with self.assertRaises(ResumeUnreadable):
            resume.extract_text(self.folder / "absent.pdf")

    def test_a_folder_is_refused(self):
        folder = self.folder / "folder.pdf"
        folder.mkdir()

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(folder)

        self.assertIn("folder", str(caught.exception))

    def test_unsupported_and_legacy_extensions_are_named(self):
        text_file = self.write("resume.txt", b"plain text")
        legacy = self.write("resume.doc", b"\xd0\xcf\x11\xe0legacy")

        with self.assertRaises(ResumeUnreadable) as unsupported:
            resume.extract_text(text_file)
        with self.assertRaises(ResumeUnreadable) as old:
            resume.extract_text(legacy)

        self.assertIn("not a supported", str(unsupported.exception))
        self.assertIn(".docx or PDF", str(old.exception))

    def test_reading_a_malformed_docx_prints_nothing(self):
        """A failed read reports through its message only: nothing is written to the console."""
        path = self.write("damaged.docx", b"PK\x03\x04damaged archive payload")
        captured = io.StringIO()

        with mock.patch("sys.stderr", captured):
            with self.assertRaises(ResumeUnreadable):
                resume.extract_text(path)

        self.assertEqual(captured.getvalue(), "")

    def test_reading_a_document_creates_no_files_and_keeps_no_copy(self):
        path = self.write_docx(paragraphs=RESUME_PARAGRAPHS)
        before = sorted(self.folder.iterdir())

        resume.parse_resume(path)

        self.assertEqual(sorted(self.folder.iterdir()), before, "no copy or temporary file may appear")


# --------------------------------------------------------------------------------------
# Parsing: proposals, evidence, confidence, and what is deliberately not guessed
# --------------------------------------------------------------------------------------

    def test_a_password_protected_docx_is_refused_as_encrypted(self):
        # Some archivers and online converters save a .docx as a ZIP whose member is encrypted. Reading
        # it raises RuntimeError from the zipfile module, which the review flow has no handler for, so
        # the file must be recognised and refused with the same plain explanation as an encrypted Word
        # file - never as a traceback and never as an empty "nothing found" result.
        path = self.write("protected.docx", encrypt_docx_members(build_docx(paragraphs=("Sample Candidate", "Skills", "Python, SQL"))))

        with self.assertRaises(ResumeEncrypted) as caught:
            resume.parse_resume(path)

        self.assertIn("password-protected", str(caught.exception))
        self.assertIn(path.name, str(caught.exception))
        self.assertNotIn(str(self.folder), str(caught.exception), "a folder on disk is never named")

    def test_a_docx_stored_with_an_unsupported_compression_method_is_refused(self):
        path = self.write("aes.docx", set_docx_compression(build_docx(paragraphs=("Sample Candidate",)), 99))

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("compression method", str(caught.exception))
        self.assertIn("99", str(caught.exception))

    def test_a_damaged_compression_stream_is_refused_with_the_docx_message(self):
        # Method 12 (bzip2) with data that is not bzip2: the decompressor raises OSError, which used to
        # surface as "could not be opened (it may be unreadable or in use by another program)" - a
        # message about a file that is in fact perfectly readable, holding a damaged document part.
        path = self.write("bzip2.docx", set_docx_compression(build_docx(paragraphs=("Sample Candidate",)), 12))

        with self.assertRaises(ResumeUnreadable) as caught:
            resume.extract_text(path)

        self.assertIn("could not be read as a DOCX document", str(caught.exception))
        self.assertNotIn("in use by another program", str(caught.exception))

    def test_every_unreadable_docx_is_refused_as_a_resume_import_error(self):
        """The invariant the desktop flow depends on: one catchable type, never a raw reader error.

        ``_import_resume`` catches ``ResumeImportError``; anything else would reach a Tk callback that
        has no handler for it, so the person would see a traceback instead of an explanation. Each
        fixture here is a shape a real file can arrive in.
        """
        good = build_docx(paragraphs=("Sample Candidate", "Skills", "Python, SQL"))
        fixtures = {
            "encrypted member": encrypt_docx_members(good),
            "unsupported compression method": set_docx_compression(good, 99),
            "damaged bzip2 stream": set_docx_compression(good, 12),
            "truncated archive": good[:-30],
            "no document part": build_docx_without_document_part(),
            "not a zip at all": b"this is not a zip archive",
            "OLE (encrypted or legacy) container": resume._OLE_CONTAINER_SIGNATURE + b"\x00" * 64,
            "empty file": b"",
            "still readable (control)": good,
        }
        for label, data in fixtures.items():
            with self.subTest(label=label):
                path = self.write(label.replace(" ", "-") + ".docx", data)
                if label.startswith("still readable"):
                    self.assertIsNotNone(resume.extract_text(path))
                    continue
                with self.assertRaises(ResumeImportError) as caught:
                    resume.parse_resume(path)
                self.assertIsInstance(caught.exception, ResumeImportError)
                self.assertNotIn(str(self.folder), str(caught.exception))

class ParsingTests(ResumeTestCase):
    def parse(self, paragraphs=RESUME_PARAGRAPHS, **kwargs):
        path = self.write_docx(paragraphs=paragraphs, **kwargs)
        return resume.parse_resume(path)

    def test_a_labelled_pdf_or_docx_produces_proposals_with_evidence(self):
        result = self.parse()

        keys = {proposal.key for proposal in result.proposals}
        self.assertIn("skills", keys)
        self.assertIn("degree", keys)
        self.assertIn("graduation_year", keys)
        self.assertIn("experience", keys)
        for proposal in result.proposals:
            self.assertTrue(proposal.evidence, f"{proposal.key} must quote its evidence")
            self.assertIsInstance(proposal.confidence, ProposalConfidence)

    def test_skills_come_from_a_skills_section(self):
        result = self.parse(paragraphs=("Sample Candidate", "Skills", "Python, SQL, Data Structures"))

        proposal = resume.proposal_by_key(result, "skills")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.value, "Python, SQL, Data Structures")
        self.assertIs(proposal.confidence, ProposalConfidence.CONFIDENT)
        self.assertIn("Python", proposal.evidence)

    def test_a_notice_after_skills_does_not_leak_into_the_skills_proposal(self):
        result = self.parse(paragraphs=(
            "Synthetic Test Candidate",
            "Skills",
            "Python, SQL, Git",
            "TEST SAFETY NOTE",
            "All values above are fictional test data. The year 2099 is intentionally unrealistic "
            "and must not be treated as a real qualification.",
        ))

        proposal = resume.proposal_by_key(result, "skills")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.value, "Python, SQL, Git")
        self.assertNotIn("TEST", proposal.value)
        self.assertNotIn("qualification", proposal.value)

    def test_a_table_row_holding_a_heading_and_its_list_is_read(self):
        """A table cell layout is common in Word résumés; the row arrives as "SKILLS | Python, SQL"."""
        result = self.parse(
            paragraphs=("Sample Candidate",),
            tables=(
                (("SKILLS", "Python, SQL, PyTorch"), ("EDUCATION", "B.Tech in Computer Science, 2027")),
            ),
        )

        skills = resume.proposal_by_key(result, "skills")
        degree = resume.proposal_by_key(result, "degree")

        self.assertIsNotNone(skills, "the row's second cell holds the skills")
        self.assertEqual(skills.value, "Python, SQL, PyTorch")
        self.assertNotIn("SKILLS", skills.value.upper())
        self.assertIsNotNone(degree, "the same rule must work for the education row")
        self.assertIn("Computer Science", degree.value)

    def test_a_category_name_before_a_column_gap_is_not_read_as_a_skill(self):
        # "Languages: Python, SQL" already reads correctly; the same statement written with the column
        # gap the extractors report must not disagree and offer the category name as a skill.
        for category in ("Languages", "Frameworks", "Tools", "Databases", "Cloud", "Testing"):
            with self.subTest(category=category):
                result = self.parse(paragraphs=("Sample Candidate", "Skills", f"{category} | Python, SQL"))

                proposal = resume.proposal_by_key(result, "skills")

                self.assertIsNotNone(proposal)
                self.assertEqual(proposal.value, "Python, SQL")
                self.assertNotIn(category, proposal.value)
                self.assertIs(proposal.confidence, ProposalConfidence.CONFIDENT)

    def test_a_merged_column_line_keeps_its_flag_when_another_line_is_labelled(self):
        # A labelled line later in the same section must not clear the flag set by an earlier merged
        # line: the proposal still holds values that were read out of a column nobody labelled.
        result = self.parse(paragraphs=(
            "Sample Candidate", "Skills", "Python, SQL    Built ETL pipelines", "Frameworks: Django",
        ))

        proposal = resume.proposal_by_key(result, "skills")

        self.assertIsNotNone(proposal)
        self.assertIn("Django", proposal.value)
        self.assertIs(proposal.confidence, ProposalConfidence.NEEDS_REVIEW)

    def test_a_plain_pipe_separated_list_of_skills_is_still_offered(self):
        result = self.parse(paragraphs=("Sample Candidate", "Skills", "Python | SQL | PyTorch"))

        proposal = resume.proposal_by_key(result, "skills")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.value, "Python, SQL, PyTorch")

    def test_a_skills_line_that_merges_two_columns_is_offered_for_review_not_pre_ticked(self):
        # Two near-identical Word layouts cannot both be decided by counting words: one merged column
        # held prose that reached the value, the other prose that was silently dropped. Neither may be
        # presented as a confident, pre-ticked skill, so both are offered for the person to confirm.
        for line in (
            "Python, SQL, Django    Built ETL pipelines",
            "Python, SQL    Built ETL pipelines at scale",
            "Python | SQL | PyTorch",
        ):
            with self.subTest(line=line):
                result = self.parse(paragraphs=("Sample Candidate", "Skills", line))

                proposal = resume.proposal_by_key(result, "skills")

                self.assertIsNotNone(proposal, "the values are still offered")
                self.assertIs(proposal.confidence, ProposalConfidence.NEEDS_REVIEW)
                self.assertTrue(proposal.evidence, "the whole original line is quoted for the reviewer")

    def test_a_single_column_skills_list_is_confident_and_unchanged(self):
        for line in ("Python, SQL, Data Structures", "Python, SQL", "Machine Learning, SQL"):
            with self.subTest(line=line):
                result = self.parse(paragraphs=("Sample Candidate", "Skills", line))

                proposal = resume.proposal_by_key(result, "skills")

                self.assertEqual(proposal.value, line)
                self.assertIs(proposal.confidence, ProposalConfidence.CONFIDENT)

    def test_a_keyword_in_the_body_is_not_treated_as_a_skill(self):
        result = self.parse(paragraphs=(
            "Sample Candidate", "Summary", "Built a project with Python and PostgreSQL.",
            "Projects", "A ward-winning student project.",
        ))

        self.assertIsNone(resume.proposal_by_key(result, "skills"))
        self.assertTrue(any("No skills heading was recognised" in note for note in result.notes), result.notes)

    def test_a_degree_with_a_subject_is_confident_and_a_level_alone_needs_review(self):
        with_subject = self.parse(paragraphs=("Education", "B.Tech in Computer Science"))
        level_only = self.parse(paragraphs=("Education", "Bachelor of Technology"))

        confident = resume.proposal_by_key(with_subject, "degree")
        review = resume.proposal_by_key(level_only, "degree")

        self.assertEqual(confident.value, "Computer Science")
        self.assertIs(confident.confidence, ProposalConfidence.CONFIDENT)
        self.assertIs(review.confidence, ProposalConfidence.NEEDS_REVIEW)

    def test_an_explicit_graduation_year_is_confident_and_a_bare_year_needs_review(self):
        explicit = self.parse(paragraphs=("Education", "B.Tech in ECE", "Expected graduation: 2027"))
        bare = self.parse(paragraphs=("Education", "Example Institute of Technology, 2026"))

        self.assertEqual(resume.proposal_by_key(explicit, "graduation_year").value, "2027")
        self.assertIs(
            resume.proposal_by_key(explicit, "graduation_year").confidence, ProposalConfidence.CONFIDENT
        )
        self.assertEqual(resume.proposal_by_key(bare, "graduation_year").value, "2026")
        self.assertIs(
            resume.proposal_by_key(bare, "graduation_year").confidence, ProposalConfidence.NEEDS_REVIEW
        )

    def test_no_graduation_year_is_offered_when_the_document_does_not_state_one(self):
        result = self.parse(paragraphs=("Sample Candidate", "Education", "B.Tech in Computer Science"))

        self.assertIsNone(resume.proposal_by_key(result, "graduation_year"))
        self.assertIn("Graduation year", resume.missing_field_labels(result.proposals))

    def test_employment_dates_are_never_turned_into_experience_years(self):
        result = self.parse(paragraphs=(
            "Sample Candidate", "Experience", "Example Corp, Aug 2021 - Jul 2023", "Built services.",
        ))

        self.assertIsNone(resume.proposal_by_key(result, "experience"))

    def test_an_experience_statement_is_used_and_an_approximation_is_marked_for_review(self):
        exact = self.parse(paragraphs=("Experience", "3 years of experience with Python"))
        approximate = self.parse(paragraphs=("Experience", "Over 5 years of experience in data work"))

        self.assertEqual(resume.proposal_by_key(exact, "experience").value, "3")
        self.assertIs(
            resume.proposal_by_key(exact, "experience").confidence, ProposalConfidence.CONFIDENT
        )
        self.assertEqual(resume.proposal_by_key(approximate, "experience").value, "5")
        self.assertIs(
            resume.proposal_by_key(approximate, "experience").confidence, ProposalConfidence.NEEDS_REVIEW
        )

    def test_a_labelled_experience_value_is_read(self):
        result = self.parse(paragraphs=("Experience", "Total experience: 2.5 years"))

        proposal = resume.proposal_by_key(result, "experience")

        self.assertEqual(proposal.value, "2.5")

    def test_study_status_is_mapped_only_from_an_explicit_phrase_and_always_needs_review(self):
        pursuing = self.parse(paragraphs=("Sample Candidate", "Currently pursuing a bachelor's degree in ECE"))
        graduated = self.parse(paragraphs=("Sample Candidate", "Graduated with a degree in ECE"))
        silent = self.parse(paragraphs=("Sample Candidate", "Education", "B.Tech in ECE"))

        bachelor = resume.proposal_by_key(pursuing, "study_status")
        finished = resume.proposal_by_key(graduated, "study_status")

        self.assertEqual(bachelor.value, "undergraduate")
        self.assertIs(bachelor.confidence, ProposalConfidence.NEEDS_REVIEW)
        self.assertEqual(finished.value, "graduated")
        self.assertIsNone(resume.proposal_by_key(silent, "study_status"))
        self.assertIn(bachelor.value, resume.study_status_choices())

    def test_country_comes_only_from_a_labelled_line_and_always_needs_review(self):
        from_location = self.parse(paragraphs=("Sample Candidate", "Location: Bengaluru, India"))
        from_country = self.parse(paragraphs=("Sample Candidate", "Country: Germany"))
        city_only = self.parse(paragraphs=("Sample Candidate", "Location: Bengaluru"))

        self.assertEqual(resume.proposal_by_key(from_location, "country").value, "India")
        self.assertIs(
            resume.proposal_by_key(from_location, "country").confidence, ProposalConfidence.NEEDS_REVIEW
        )
        self.assertEqual(resume.proposal_by_key(from_country, "country").value, "Germany")
        self.assertIsNone(resume.proposal_by_key(city_only, "country"))

    def test_work_authorization_is_quoted_and_always_needs_review(self):
        result = self.parse(paragraphs=(
            "Sample Candidate", "Authorized to work in the United States without sponsorship",
        ))

        proposal = resume.proposal_by_key(result, "work_authorization")

        self.assertIsNotNone(proposal)
        self.assertIs(proposal.confidence, ProposalConfidence.NEEDS_REVIEW)
        self.assertIn("Authorized to work", proposal.value)

    def test_a_labelled_authorization_line_is_preferred(self):
        result = self.parse(paragraphs=("Sample Candidate", "Work authorization: student visa (F-1)"))

        self.assertEqual(resume.proposal_by_key(result, "work_authorization").value, "student visa (F-1)")

    def test_contact_details_are_reported_as_items_with_no_profile_field(self):
        result = self.parse()

        labels = {item.label: item.value for item in result.unmapped}

        self.assertEqual(labels.get("Name"), "Sample Candidate")
        self.assertEqual(labels.get("Email"), "sample.candidate@example.invalid")
        self.assertIn("Phone", labels)
        for item in result.unmapped:
            self.assertIn("no field", item.note)

    def test_links_are_reported_without_being_followed(self):
        result = self.parse(paragraphs=("Sample Candidate", "https://example.invalid/portfolio"))

        links = [item for item in result.unmapped if item.label == "Links"]

        self.assertTrue(links)
        self.assertIn("example.invalid", links[0].value)

    def test_an_empty_document_yields_no_proposals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.docx"
            # A document whose paragraphs hold no text at all.
            path.write_bytes(build_docx(document_xml=(
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t></w:t></w:r></w:p></w:body></w:document>"
            )))
            with self.assertRaises(ResumeNoText):
                resume.parse_resume(path)

    def test_text_without_any_supported_value_produces_no_proposals_and_says_so(self):
        result = self.parse(paragraphs=("Just some prose about nothing in particular.",))

        self.assertEqual(result.proposals, ())
        self.assertTrue(any("No supported profile value" in note for note in result.notes), result.notes)

    def test_the_result_never_carries_the_document_text(self):
        marker = "verbatim résumé sentence that must never be retained"
        result = self.parse(paragraphs=(marker, "Skills", "Python"))

        for field in fields(result):
            value = getattr(result, field.name)
            if isinstance(value, str):
                self.assertNotIn("verbatim", value, f"{field.name} must not carry document text")
        self.assertGreater(result.text_characters, 0, "only the character count is kept")

    def test_missing_field_labels_list_supported_fields_the_document_did_not_supply(self):
        result = self.parse(paragraphs=("Skills", "Python"))

        missing = resume.missing_field_labels(result.proposals)

        self.assertIn("Graduation year", missing)
        self.assertIn("Country", missing)
        self.assertNotIn("Skills", missing)
        self.assertNotIn("Preferred work modes", missing, "the résumé has no vocabulary for preferences")

    def test_accepted_values_returns_only_selected_proposals(self):
        result = self.parse(paragraphs=("Skills", "Python, SQL", "Experience", "2 years of experience"))

        chosen = resume.accepted_values(result.proposals, {"skills": True, "experience": False})

        self.assertEqual(list(chosen), ["skills"])
        self.assertEqual(chosen["skills"], "Python, SQL")

    def test_the_summary_line_is_factual(self):
        result = self.parse(paragraphs=("Skills", "Python"))

        summary = resume.format_result_summary(result)

        self.assertIn("DOCX", summary)
        self.assertIn("proposed value", summary)

    def test_field_proposals_can_be_inspected_without_a_document(self):
        """The review screen is driven by plain data, so its contract is testable on its own."""
        proposal = FieldProposal(
            key="skills", label="Skills", value="Python",
            confidence=ProposalConfidence.CONFIDENT, evidence="Skills: Python",
        )

        self.assertEqual(proposal.key, "skills")


class PdfSupportMessageTests(ResumeTestCase):
    def test_pdf_import_explains_that_the_optional_package_is_missing(self):
        path = self.write("resume.pdf", build_pdf([("Text",)]))

        with mock.patch.object(resume, "pypdf", None):
            with self.assertRaises(ResumeImportError) as caught:
                resume.extract_text(path)

        self.assertIn("pypdf", str(caught.exception))
        self.assertIn("DOCX", str(caught.exception), "the message must name the option that still works")


# --------------------------------------------------------------------------------------
# Local-only behaviour
# --------------------------------------------------------------------------------------


class LocalOnlyTests(ResumeTestCase):
    BLOCKER = """\
import socket


class _Blocked(RuntimeError):
    pass


def _deny(*args, **kwargs):
    raise _Blocked("outbound network access is not permitted")


socket.socket = _deny
socket.create_connection = _deny
socket.getaddrinfo = _deny
"""

    def test_importing_a_resume_needs_no_network_access(self):
        """Run a real import in a child interpreter whose sockets are blocked."""
        path = self.write_docx(paragraphs=RESUME_PARAGRAPHS)
        blocker = self.folder / "sitecustomize.py"
        blocker.write_text(self.BLOCKER, encoding="utf-8")
        script = (
            "from career_agent import resume\n"
            f"result = resume.parse_resume({str(path)!r})\n"
            "print('PROPOSALS', len(result.proposals))\n"
            "print('FORMAT', result.source_format.value)\n"
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(Path(__file__).resolve().parent.parent),
            env=dict(
                os.environ, PYTHONPATH=str(self.folder), PYTHONDONTWRITEBYTECODE="1",
                PYTHONNOUSERSITE="1",
            ),
            capture_output=True, text=True, timeout=300,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PROPOSALS", completed.stdout)
        self.assertIn("FORMAT DOCX", completed.stdout)


# --------------------------------------------------------------------------------------
# Skills-section recognition: the layout shapes a real extractor produces
# --------------------------------------------------------------------------------------


def build_pdf_runs(runs) -> bytes:
    """A PDF whose text is positioned absolutely, so a heading and a value can share a baseline.

    ``build_pdf`` writes one line per row of a text block; this builder exists for the layouts a
    sidebar or tabular résumé produces, where two runs sit at different x positions on the same page
    line and the extractor therefore returns them as one line.
    """
    body = ["BT /F1 11 Tf"]
    for x, y, text in runs:
        body.append(f"1 0 0 1 {x} {y} Tm ({_escape_pdf_text(text)}) Tj")
    body.append("ET")
    stream = "\n".join(body).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> "
        b"/Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    document = bytearray(PDF_HEADER)
    offsets = []
    for number, blob in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f"{number} 0 obj\n".encode() + blob + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        document += f"{offset:010d} 00000 n \n".encode()
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(document)


class SkillsSectionRecognitionTests(unittest.TestCase):
    """The shapes a text extractor really produces must yield the skills the document lists.

    Every case here came out of a real extraction rather than a guess about one: a sidebar or a table
    cell puts a heading and its list on one line ("SKILLS Python, SQL"), a heading may be written with
    its list after a colon on the same line, two columns' headings can land on one line, and PDF
    tracking letter-spaces a heading. The rules stay conservative in the other direction: prose is
    never harvested as a skill, and a heading word that merely shares a line is not a value.
    """

    def skills_of(self, *lines):
        """The skills proposal for a text excerpt, or ``None``."""
        proposals, _unmapped, _notes = resume.parse_resume_text("\n".join(lines))
        for proposal in proposals:
            if proposal.key == "skills":
                return proposal
        return None

    def notes_of(self, *lines):
        return resume.parse_resume_text("\n".join(lines))[2]

    def test_a_heading_the_module_proposes_a_field_for_also_ends_the_skills_block(self):
        """The document's own vocabulary decides where a list stops, including for its own fields.

        Measured before this test existed: a résumé that writes its authorization as a heading
        (``WORK AUTHORIZATION`` on its own line, the wording beneath it) put that wording into the
        skills proposal, marked *confident*. ``COUNTRY`` did the same, and a ``Location:`` line put the
        country itself into the skills - a fact that then feeds eligibility checks, offered as a
        skill. Every one of these headings names a field this module proposes, so it cannot be
        unknown to the section vocabulary.
        """
        leaked = (
            ("SKILLS\nPython, SQL\nWORK AUTHORIZATION\nAuthorized to work in India.", "WORK AUTHORIZATION"),
            ("SKILLS\nPython, SQL\nWORK AUTHORIZATION\nAuthorized to work in India.", "Authorized"),
            ("SKILLS\nPython, SQL\nCOUNTRY\nIndia", "COUNTRY"),
            ("SKILLS\nPython, SQL\nCOUNTRY\nIndia", "India"),
            ("SKILLS\nPython, SQL\nLocation: Bengaluru, India", "India"),
            ("SKILLS\nPython, SQL\nVisa status\nNo sponsorship needed.", "sponsorship"),
            ("SKILLS\nPython, SQL\nAddress: Pune", "Pune"),
        )
        for text, fragment in leaked:
            with self.subTest(text=text, fragment=fragment):
                proposal = self.skills_of(*text.splitlines())
                self.assertIsNotNone(proposal)
                self.assertNotIn(
                    fragment, proposal.value,
                    "a heading for a field this module proposes is not a skill, and neither is what follows it",
                )
                self.assertIn("Python", proposal.value, "the real skills must survive the new heading")

        # The headings that already existed keep working, and the sub-label rule is untouched.
        self.assertEqual(self.skills_of("SKILLS", "Python, SQL", "AWARDS", "Best intern 2024").value, "Python, SQL")
        self.assertEqual(self.skills_of("SKILLS", "Python, SQL", "EDUCATION", "B.Tech, 2027").value, "Python, SQL")
        self.assertEqual(
            self.skills_of("SKILLS", "Languages: Python, C++", "Frameworks: Django, Flask").value,
            "Python, C++, Django, Flask",
        )

    def test_a_heading_and_its_list_on_one_line_are_both_read(self):
        """The reported bug: the whole line was consumed as a heading and the list was discarded."""
        for line in (
            "SKILLS Python, SQL",
            "SKILLS: Python, SQL",
            "Skills:Python, SQL",
            "SKILLS | Python, SQL",
            "Skills\tPython, SQL",
            "SKILLS    Python, SQL",
            "Skills Python",
            "=== SKILLS ===  Python, SQL",
        ):
            with self.subTest(line=line):
                proposal = self.skills_of(line)
                self.assertIsNotNone(proposal, f"the list on {line!r} must not be discarded")
                self.assertIn("Python", proposal.value)
                self.assertNotIn("SKILLS", proposal.value.upper(), "the heading is not a skill")

    def test_common_skills_heading_names_are_recognised(self):
        for heading in (
            "Skills", "SKILLS", "Technical Skills", "Key Skills", "Core Skills", "Professional Skills",
            "Relevant Skills", "Additional Skills", "Other Skills", "Computer Skills", "Software Skills",
            "IT Skills", "Soft Skills", "Skillset", "Skill Set", "Areas of Expertise", "Expertise",
            "Technical Expertise", "Key Competencies", "Core Competencies", "Competencies",
            "Technical Proficiencies", "Proficiencies", "Technologies", "Technology", "Tools",
            "Tools & Technologies", "Tools and Technologies", "Software & Tools", "Tech Stack",
            "Programming Languages", "Skills & Interests", "TECHNICAL SKILLS:", "Skills / Abilities",
        ):
            with self.subTest(heading=heading):
                proposal = self.skills_of(heading, "Python, SQL")
                self.assertIsNotNone(proposal, f"{heading!r} should open a skills section")
                self.assertEqual(proposal.value, "Python, SQL")

    def test_decoration_and_letter_spacing_do_not_hide_a_heading(self):
        for heading in ("=== SKILLS ===", "*** Skills ***", "--- SKILLS ---", "• Skills", "S K I L L S",
                        "T E C H N I C A L   S K I L L S"):
            with self.subTest(heading=heading):
                proposal = self.skills_of(heading, "Python, SQL")
                self.assertIsNotNone(proposal, f"{heading!r} should open a skills section")
                self.assertEqual(proposal.value, "Python, SQL")

    def test_a_heading_word_that_shares_a_line_is_never_a_skill(self):
        """Two columns' headings merge into one extracted line; neither word is a value."""
        merged_columns = self.skills_of("SKILLS EXPERIENCE", "Python, SQL")
        joined_heading = self.skills_of("SKILLS & INTERESTS", "Python, SQL")

        self.assertIsNotNone(merged_columns)
        self.assertEqual(merged_columns.value, "Python, SQL")
        self.assertIsNotNone(joined_heading)
        self.assertEqual(joined_heading.value, "Python, SQL")
        for proposal in (merged_columns, joined_heading):
            self.assertNotIn("EXPERIENCE", proposal.value.upper())
            self.assertNotIn("INTERESTS", proposal.value.upper())

    def test_a_sentence_that_starts_with_a_heading_word_produces_nothing(self):
        """Prose must never become a skill: the reminder that a heading was seen is not a value."""
        for sentence in (
            "Skills are the reason I applied to this role and I would like to discuss them.",
            "Experience gained through coursework and personal projects over the last two years.",
            "Interests include hiking and reading.",
        ):
            with self.subTest(sentence=sentence):
                self.assertIsNone(self.skills_of(sentence), "prose is not a list of skills")

    def test_a_wide_gap_or_tab_between_columns_keeps_every_value(self):
        """The two-column split had been unreachable, so a second column was merged into one token."""
        for row in ("Python, SQL\tGit, Docker", "Python, SQL    Git, Docker"):
            with self.subTest(row=row):
                proposal = self.skills_of("Skills", row)
                self.assertIsNotNone(proposal)
                self.assertEqual(
                    {part.strip() for part in proposal.value.split(",")},
                    {"Python", "SQL", "Git", "Docker"},
                )

    def test_an_ampersand_inside_a_skill_name_is_kept(self):
        """Found by the Phase 4 corpus: the mechanical résumé's headline skill was silently dropped.

        The token filter allowed ``+#.()`` inside a name but not ``&``, so "GD&T" - the standard
        mechanical-engineering abbreviation - never reached the proposal, and a finance résumé's "M&A"
        would have gone the same way. Dropping a stated skill is worse than proposing a noisy one,
        because the person reviews what is proposed and never sees what was thrown away.
        """
        for line, expected in (
            ("SolidWorks, GD&T, CATIA", "GD&T"),
            ("Financial Modelling, M&A, Valuation", "M&A"),
            ("C, C++, C#", "C#"),
            ("Python & SQL", "SQL"),
        ):
            with self.subTest(line=line):
                proposal = self.skills_of("SKILLS", line)
                self.assertIsNotNone(proposal)
                self.assertIn(expected, proposal.value, f"{expected} is a stated skill")

    def test_labelled_categories_keep_their_values_without_the_labels(self):
        proposal = self.skills_of("Technical Skills", "Languages: Python, C++", "Frameworks: Django, PyTorch")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.value, "Python, C++, Django, PyTorch")
        for label in ("Languages", "Frameworks"):
            self.assertNotIn(label, proposal.value, "a category label is not a skill")
        self.assertIn("Languages: Python, C++", proposal.evidence, "the evidence is the whole line")

    def test_a_bare_languages_label_is_left_to_open_its_own_section(self):
        """A list under a bare "Languages" heading may be spoken languages, not skills."""
        proposal = self.skills_of("Skills", "Python, SQL", "Languages", "English, Hindi")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.value, "Python, SQL")
        self.assertNotIn("English", proposal.value)

    def test_an_education_line_is_read_whatever_the_discipline_calls_its_degree(self):
        """Cross-industry blindness found by the Phase 4 evaluation corpus.

        The degree vocabulary recognised engineering, science and commerce abbreviations, so a design,
        architecture, medical, pharmacy, law or education qualification was not recognised *at all*:
        neither a degree nor a graduation year was proposed from the line, because the year rule needs a
        degree or institution on that line. A person with a B.Des, an MBBS or an LL.B was served worse
        than a person with a B.Tech, which is exactly what "not effectively an AI/ML-only tool" means.
        Every qualification is spelled out here, and each is checked against an education line.
        """
        qualifications = (
            ("B.Des in Design, 2026", "Design", "2026"),
            ("M.Des in Communication Design, 2028", "Communication Design", "2028"),
            ("BFA in Painting, 2025", "Painting", "2025"),
            ("B.Arch in Architecture, 2027", "Architecture", "2027"),
            ("MBBS in Medicine, 2029", "Medicine", "2029"),
            ("B.Pharm in Pharmacy, 2026", "Pharmacy", "2026"),
            ("LL.B in Law, 2026", "Law", "2026"),
            ("B.Ed in Education, 2025", "Education", "2025"),
            ("BHM in Hospitality, 2026", "Hospitality", "2026"),
            ("B.Tech in Computer Science, 2027", "Computer Science", "2027"),
        )
        for line, subject, year in qualifications:
            with self.subTest(line=line):
                proposals, _unmapped, _notes = resume.parse_resume_text("\n".join(("Sample Candidate", "EDUCATION", line)))
                by_key = {proposal.key: proposal for proposal in proposals}
                self.assertIn("degree", by_key, f"{line!r} states a degree and must propose one")
                self.assertIn(subject.casefold(), by_key["degree"].value.casefold())
                self.assertIn("graduation_year", by_key, f"{line!r} states a year and must propose one")
                self.assertEqual(by_key["graduation_year"].value, year)

    def test_a_full_stop_after_the_abbreviation_does_not_lose_the_discipline(self):
        """The same qualification written the ordinary way must not produce a worse proposal.

        Measured before this test existed: "B.Sc. in Biotechnology, 2026" proposed the *level* only
        ("B.Sc", unselected), because the degree pattern consumed the abbreviation's own full stop and
        the discipline pattern then expected a separator instead of that stop. Exactly the same line
        without the stop proposed "Biotechnology" confidently. A dot must not change the answer.
        """
        for line, subject in (
            ("B.Sc. in Biotechnology, 2026", "Biotechnology"),
            ("B.E. in Mechanical Engineering, 2026", "Mechanical Engineering"),
            ("M.Tech. in Data Science, 2027", "Data Science"),
            ("B.A. in Economics, 2026", "Economics"),
            ("B.Com. in Commerce, 2025", "Commerce"),
        ):
            with self.subTest(line=line):
                proposals, _unmapped, _notes = resume.parse_resume_text("\n".join(("Sample Candidate", "EDUCATION", line)))
                degree = {proposal.key: proposal for proposal in proposals}.get("degree")
                self.assertIsNotNone(degree, f"{line!r} states a degree")
                self.assertIn(subject.casefold(), degree.value.casefold(), f"{line!r} names its subject")

    def test_a_discipline_prefix_before_the_word_skills_is_still_a_skills_heading(self):
        """Cross-industry vocabulary, found by the Phase 4 corpus.

        The recognised headings were technical/key/core/professional/... so a laboratory, clinical,
        research, engineering, analytical or design skills heading was invisible: the résumé's skills
        list produced no proposal at all, and the person was told their document has no skills heading
        even though it has one. A résumé that writes "LABORATORY SKILLS" is not a worse résumé.
        """
        for heading in (
            "LABORATORY SKILLS", "Laboratory skills", "CLINICAL SKILLS", "RESEARCH SKILLS",
            "ENGINEERING SKILLS", "ANALYTICAL SKILLS", "DESIGN SKILLS", "Business Skills",
            "FINANCIAL SKILLS", "DATA SKILLS", "MECHANICAL SKILLS", "CIVIL SKILLS",
        ):
            with self.subTest(heading=heading):
                proposal = self.skills_of(heading, "PCR, Cell Culture")
                self.assertIsNotNone(proposal, f"{heading} is a skills heading")
                self.assertEqual(proposal.value, "PCR, Cell Culture")

    def test_an_ordinary_word_is_not_read_as_a_degree_abbreviation(self):
        """Widening the vocabulary must not turn prose into a qualification."""
        for line in (
            "Comfortable in a fast bed of changing priorities.",
            "Led the redesign of the checkout flow.",
            "Managed a small team of two designers.",
        ):
            with self.subTest(line=line):
                proposals, _unmapped, _notes = resume.parse_resume_text("\n".join(("Sample Candidate", line)))
                self.assertNotIn("degree", {proposal.key for proposal in proposals})

    def test_a_heading_found_without_a_list_is_reported_as_its_own_case(self):
        """The two failures need different next steps, so the notes must not conflate them."""
        heading_without_list = self.notes_of("Skills")
        no_heading = self.notes_of("Sample Candidate", "A summary sentence about the candidate.")

        self.assertTrue(any("no list of skills followed it" in note for note in heading_without_list))
        self.assertTrue(any("No skills heading was recognised" in note for note in no_heading))
        for note in heading_without_list + no_heading:
            self.assertNotIn("Sample Candidate", note, "notes never quote the document")

    def test_education_content_on_a_heading_line_is_used(self):
        """The same rule fixes the other section: "EDUCATION B.Tech ..., 2028" used to lose its content."""
        proposals, _unmapped, _notes = resume.parse_resume_text(
            "\n".join(("Sample Candidate", "EDUCATION B.Tech in Electronics, 2028"))
        )
        by_key = {proposal.key: proposal for proposal in proposals}

        self.assertIn("degree", by_key)
        self.assertIn("Electronics", by_key["degree"].value)
        self.assertIn("graduation_year", by_key)
        self.assertEqual(by_key["graduation_year"].value, "2028")

    def test_the_proposals_never_carry_the_document_text(self):
        """Recognition was widened, so re-assert the privacy property over the new paths."""
        result = resume.parse_resume_text(
            "\n".join((
                "Sample Candidate", "sample.candidate@example.invalid",
                "Technical Skills", "Languages: Python, C++", "Frameworks: Django",
                "A long paragraph of prose that must never be repeated back as a value, because it "
                "belongs to the document and not to the profile being built from it.",
            ))
        )
        for proposal in result[0]:
            self.assertLessEqual(len(proposal.evidence), resume.MAX_EVIDENCE_CHARACTERS)
            self.assertNotIn("must never be repeated back", proposal.value)
            self.assertNotIn("example.invalid", proposal.value)


if __name__ == "__main__":
    unittest.main()
