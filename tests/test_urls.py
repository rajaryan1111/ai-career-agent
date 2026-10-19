"""Regression tests for career_agent.urls — untrusted link validation and display redaction.

These tests are deterministic and make no network call: they only check literal URL parsing.
Passing them does **not** prove SSRF protection (no DNS resolution or redirect handling happens
anywhere in this project yet); see the module docstring for that limitation.
"""
import unittest

from career_agent.urls import is_public_http_url, redact_url_credentials, validate_public_http_url


class AcceptsPublicHttpUrls(unittest.TestCase):
    def test_plain_public_urls_are_accepted_and_returned_unchanged(self):
        for url in (
            "https://jobs.example/role/1",
            "http://jobs.example/role/1",
            "HTTPS://JOBS.EXAMPLE/role/1",
            "https://jobs.example:8443/role/1",
            "https://8.8.8.8/role/1",
            "https://[2606:4700::1111]/role/1",
            "https://jobs.example./role/1",
            "https://jobs.example/role/1?utm_source=manual",
        ):
            with self.subTest(url=url):
                self.assertEqual(validate_public_http_url(url), url)

    def test_surrounding_whitespace_is_trimmed_but_nothing_else_is_rewritten(self):
        self.assertEqual(validate_public_http_url("  https://jobs.example/1  "), "https://jobs.example/1")

    def test_label_appears_in_the_message_for_caller_specific_field_names(self):
        with self.assertRaisesRegex(ValueError, "Employer apply URL must start with"):
            validate_public_http_url("employer.example/apply", label="Employer apply URL")

    def test_is_public_http_url_matches_the_validator(self):
        self.assertTrue(is_public_http_url("https://jobs.example/1"))
        self.assertFalse(is_public_http_url("https://localhost/1"))


class RejectsNonHttpUrls(unittest.TestCase):
    def test_missing_scheme_and_other_schemes_are_refused_with_the_scheme_message(self):
        for url in ("", "   ", "jobs.example/1", "ftp://jobs.example/1", "javascript:alert(1)", "//jobs.example/1"):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "must start with http:// or https://"):
                    validate_public_http_url(url)


class RejectsNonPublicOrCredentialedUrls(unittest.TestCase):
    """Every case here reaches a non-public destination or smuggles credentials in the authority."""

    def assert_refused(self, url):
        with self.subTest(url=url):
            with self.assertRaisesRegex(ValueError, "public web address"):
                validate_public_http_url(url)

    def test_embedded_credentials_are_refused(self):
        for url in ("https://user:pass@jobs.example/1", "https://user@jobs.example/1"):
            self.assert_refused(url)

    def test_localhost_private_and_link_local_hosts_are_refused(self):
        for url in (
            "http://localhost/1",
            "http://localhost:8080/1",
            "http://127.0.0.1/1",
            "http://10.1.2.3/1",
            "http://192.168.1.5/1",
            "http://172.16.0.1/1",
            "http://169.254.169.254/latest/meta-data/",
            "http://0.0.0.0/1",
            "http://100.64.0.1/1",
            "http://198.18.0.1/1",
            "http://[::1]/1",
            "http://[::ffff:127.0.0.1]/1",
            "http://[fe80::1]/1",
        ):
            self.assert_refused(url)

    def test_legacy_ipv4_spellings_of_loopback_are_refused(self):
        """127.1, 2130706433, 0x7f.0.0.1 and 0177.0.0.1 all resolve to loopback for a fetcher."""
        for url in ("http://127.1/1", "http://2130706433/1", "http://0x7f.0.0.1/1", "http://0177.0.0.1/1"):
            self.assert_refused(url)

    def test_internal_and_single_label_hosts_are_refused(self):
        for url in (
            "https://internal/1",
            "https://careers/1",
            "https://jobs.local/1",
            "https://jobs.internal/1",
            "https://metadata.google.internal/1",
            "https://instance-data/1",
            "https://host.home.arpa/1",
        ):
            self.assert_refused(url)

    def test_malformed_authorities_and_control_characters_are_refused(self):
        for url in (
            "http://jobs%2eexample/1",
            "https://jobs.example:not-a-port/x",
            "https://jobs.example:65536/x",
            "https://jobs.example\\@evil.test/1",
            "https://jobs.example/pa\nth",
            "https://jobs.example/pa th",
        ):
            self.assert_refused(url)

    def test_lookalike_domain_suffixes_are_still_ordinary_public_hosts(self):
        """This function validates shape and reachability class only — domain allow-listing is not its job."""
        self.assertTrue(is_public_http_url("https://jobs.example.evil.test/1"))


class RedactionForDisplay(unittest.TestCase):
    def test_userinfo_is_redacted_in_scheme_and_bare_forms(self):
        self.assertEqual(
            redact_url_credentials("https://user:pass@jobs.example/1"), "https://***@jobs.example/1"
        )
        self.assertEqual(redact_url_credentials("see user:pass@jobs.example/1 here"), "see ***@jobs.example/1 here")

    def test_sensitive_query_and_fragment_values_are_redacted(self):
        for text, expected in (
            ("https://jobs.example/1?token=abc123&page=2", "https://jobs.example/1?token=***&page=2"),
            ("https://jobs.example/1?api_key=abcd1234", "https://jobs.example/1?api_key=***"),
            ("https://jobs.example/1?password=hunter2", "https://jobs.example/1?password=***"),
            ("https://jobs.example/1#sig=deadbeef", "https://jobs.example/1#sig=***"),
            ("https://jobs.example/1?session=xyz", "https://jobs.example/1?session=***"),
        ):
            with self.subTest(text=text):
                self.assertEqual(redact_url_credentials(text), expected)

    def test_ordinary_parameters_and_text_are_untouched(self):
        for text in (
            "https://jobs.example/1?page=2&utm_source=manual",
            "Selected AI Intern at Example Inc",
            "No URL in this note at all",
        ):
            with self.subTest(text=text):
                self.assertEqual(redact_url_credentials(text), text)

    def test_redaction_is_idempotent_and_accepts_any_value(self):
        once = redact_url_credentials("https://user:pass@jobs.example/1?token=abcdef")
        self.assertEqual(redact_url_credentials(once), once)
        self.assertEqual(redact_url_credentials(None), "None")


if __name__ == "__main__":
    unittest.main(verbosity=2)
