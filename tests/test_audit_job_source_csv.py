import csv
import tempfile
import unittest
from pathlib import Path

from scripts.audit_job_source_csv import audit_csv


class AuditJobSourceCsvTests(unittest.TestCase):
    def test_reports_integrity_counts_and_does_not_invent_link_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    "listing_id", "canonical_employer_url", "status",
                    "permission_status", "apply_route_outcome",
                ])
                writer.writerow(["A", "https://jobs.example/1", "open", "unknown", "reachable_application_form"])
                writer.writerow(["B", "https://jobs.example/1", "unknown", "unknown", ""])
                writer.writerow(["C", "https://jobs.example/3", "closed", "approved", "unreachable"])
                writer.writerow(["malformed", "only-two"])
            report = audit_csv(path)
            self.assertEqual(report["record_count"], 3)
            self.assertEqual(report["malformed_width_rows_excluded"], 1)
            self.assertEqual(report["duplicate_listing_id_count"], 0)
            self.assertEqual(report["distinct_canonical_employer_urls"], 2)
            self.assertEqual(report["repeated_canonical_url_group_count"], 1)
            self.assertEqual(report["permission_unknown_count"], 2)
            self.assertIsNone(report["direct_link_validity_percentage"])
            self.assertEqual(report["apply_route_observed_record_count"], 2)

    def test_duplicate_listing_ids_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.csv"
            path.write_text(
                "listing_id,canonical_employer_url,status,permission_status,apply_route_outcome\n"
                "X,https://jobs.example/1,open,unknown,\n"
                "X,https://jobs.example/2,open,unknown,\n",
                encoding="utf-8",
            )
            report = audit_csv(path)
            self.assertEqual(report["duplicate_listing_id_count"], 1)
            self.assertEqual(report["duplicate_listing_ids"], {"X": 2})


if ( __name__ == "__main__" ):
    unittest.main()
