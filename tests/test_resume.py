import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

from career_agent import resume as resume_module
from career_agent.resume import (
    MAX_RESUME_BYTES,
    ResumeError,
    propose_fields,
    read_resume,
)

LABELLED = """Ravi Example
Country: India
Degree: Electronics and Communication Engineering
Study status: undergraduate
Graduation year: 2027
Experience: 0.5 years of experience
Work authorization: authorized_without_sponsorship
Skills: Python, RAG, python, SQL
Preferred locations: Bengaluru, Remote
Preferred work modes: remote, hybrid
Preferred role types: internship
"""


def docx_bytes(body: str) -> bytes:
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in body.splitlines())
        + "</w:body></w:document>"
    )
    buffer = Path(tempfile.mkdtemp()) / "synthetic.docx"
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    return buffer.read_bytes()


def pdf_bytes(text: str, *, compress: bool = False, encrypt: bool = False) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    payload = zlib.compress(stream) if compress else stream
    parts = [b"%PDF-1.4\n"]
    if encrypt:
        parts.append(b"trailer << /Encrypt 9 0 R >>\n")
    parts.append(b"4 0 obj << /Length %d >>\nstream\n" % len(payload))
    parts.append(payload)
    parts.append(b"\nendstream\nendobj\n%%EOF\n")
    return b"".join(parts)


class ResumeFixtureTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def write(self, name: str, data: bytes) -> Path:
        path = self.folder / name
        path.write_bytes(data)
        return path

    def test_text_resume_proposes_only_labelled_fields(self):
        path = self.write("resume.txt", LABELLED.encode("utf-8"))
        result = read_resume(path)
        fields = dict((item.field, item.value) for item in result.proposals)
        self.assertEqual(fields["candidate_country"], "India")
        self.assertEqual(fields["degree_discipline"], "Electronics and Communication Engineering")
        self.assertEqual(fields["study_status"], "undergraduate")
        self.assertEqual(fields["graduation_year"], "2027")
        self.assertEqual(fields["experience_years"], "0.5")
        self.assertEqual(fields["work_authorization"], "authorized_without_sponsorship")
        self.assertEqual(fields["skills"], "Python, RAG, SQL")
        self.assertEqual(fields["preferred_work_modes"], "remote, hybrid")
        self.assertEqual(result.source_name, "resume.txt")
        self.assertEqual(result.warnings, ())

    def test_every_proposal_quotes_its_evidence_line(self):
        path = self.write("resume.txt", LABELLED.encode("utf-8"))
        for proposal in read_resume(path).proposals:
            self.assertIn(proposal.value.split(",")[0].strip(), proposal.evidence)
            self.assertEqual(proposal.confidence, "review")

    def test_unlabelled_document_proposes_nothing_and_says_so(self):
        path = self.write("plain.txt", b"I am a designer who likes portfolios.\n")
        result = read_resume(path)
        self.assertEqual(result.proposals, ())
        self.assertTrue(any("No labelled resume sections" in warning for warning in result.warnings))

    def test_docx_text_is_extracted(self):
        path = self.write("resume.docx", docx_bytes(LABELLED))
        result = read_resume(path)
        fields = dict((item.field, item.value) for item in result.proposals)
        self.assertEqual(fields["skills"], "Python, RAG, SQL")
        self.assertIn("Ravi Example", result.text)

    def test_plain_pdf_stream_is_extracted(self):
        path = self.write("resume.pdf", pdf_bytes("Skills: Python, SQL"))
        fields = dict((item.field, item.value) for item in read_resume(path).proposals)
        self.assertEqual(fields["skills"], "Python, SQL")

    def test_compressed_pdf_stream_is_extracted(self):
        path = self.write("resume.pdf", pdf_bytes("Country: India", compress=True))
        fields = dict((item.field, item.value) for item in read_resume(path).proposals)
        self.assertEqual(fields["candidate_country"], "India")

    def test_image_only_pdf_reports_missing_ocr_instead_of_guessing(self):
        raw = self.write("scan.pdf", pdf_bytes("(ignored)").replace(b"Tj", b"Do"))
        result = read_resume(raw)
        self.assertEqual(result.proposals, ())
        self.assertTrue(any("OCR" in warning for warning in result.warnings))

    def test_encrypted_pdf_is_refused(self):
        path = self.write("locked.pdf", pdf_bytes("Skills: Python", encrypt=True))
        with self.assertRaisesRegex(ResumeError, "encrypted"):
            read_resume(path)

    def test_malformed_docx_is_refused(self):
        path = self.write("broken.docx", b"not a zip file")
        with self.assertRaisesRegex(ResumeError, "DOCX"):
            read_resume(path)

    def test_docx_without_a_body_is_refused(self):
        path = self.folder / "empty.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("docProps/core.xml", "<x/>")
        with self.assertRaisesRegex(ResumeError, "document body"):
            read_resume(path)

    def test_not_a_pdf_is_refused(self):
        path = self.write("fake.pdf", b"just text in a pdf-named file")
        with self.assertRaisesRegex(ResumeError, "does not look like a PDF"):
            read_resume(path)

    def test_empty_file_is_refused(self):
        path = self.write("empty.txt", b"   ")
        with self.assertRaisesRegex(ResumeError, "empty"):
            read_resume(path)

    def test_non_utf8_text_file_is_refused(self):
        path = self.write("latin.txt", "Résumé skills: Python".encode("latin-1"))
        with self.assertRaisesRegex(ResumeError, "UTF-8"):
            read_resume(path)

    def test_unsupported_extension_is_refused(self):
        path = self.write("resume.rtf", b"{\\rtf1}")
        with self.assertRaisesRegex(ResumeError, "Unsupported resume format"):
            read_resume(path)

    def test_oversized_file_is_refused_before_parsing(self):
        path = self.write("big.txt", b"x" * (MAX_RESUME_BYTES + 1))
        with self.assertRaisesRegex(ResumeError, "import limit"):
            read_resume(path)

    def test_long_documents_are_truncated_with_a_warning(self):
        path = self.write("long.txt", (LABELLED * 50).encode("utf-8"))
        with mock.patch.object(resume_module, "MAX_TEXT_CHARS", 40):
            result = read_resume(path)
        self.assertLessEqual(len(result.text), 40)
        self.assertTrue(any("first part" in warning for warning in result.warnings))

    def test_missing_file_is_refused(self):
        with self.assertRaisesRegex(ResumeError, "Could not read"):
            read_resume(self.folder / "missing.txt")


class ProposalTests(unittest.TestCase):
    def test_values_are_split_trimmed_and_deduplicated(self):
        proposals, _ = propose_fields("Skills: Python ,  SQL ;; Python ,, RAG\n")
        values = dict((item.field, item.value) for item in proposals)
        self.assertEqual(values["skills"], "Python, SQL, RAG")

    def test_graduation_year_from_an_unlabelled_sentence_is_review_only(self):
        proposals, _ = propose_fields("B.Tech ECE, graduating 2028 with distinction\n")
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].field, "graduation_year")
        self.assertEqual(proposals[0].value, "2028")
        self.assertEqual(proposals[0].confidence, "review")

    def test_experience_phrase_without_a_label_is_still_evidence_backed(self):
        proposals, _ = propose_fields("Over 4 years of experience building tools.\n")
        values = dict((item.field, item.value) for item in proposals)
        self.assertEqual(values["experience_years"], "4")

    def test_first_labelled_value_wins_for_each_field(self):
        proposals, _ = propose_fields("Country: India\nCountry: Germany\n")
        self.assertEqual([item.value for item in proposals], ["India"])

    def test_unknown_labels_are_ignored(self):
        proposals, warnings = propose_fields("Hobbies: chess\nLanguages: English\n")
        self.assertEqual(proposals, ())
        self.assertTrue(warnings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
