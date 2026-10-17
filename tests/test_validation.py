import unittest

from career_agent.validation import optional_float, optional_int, split_values


class InputValidationTests(unittest.TestCase):
    def test_split_values_trims_blanks_and_case_insensitive_duplicates(self):
        self.assertEqual(split_values(" Python, RAG\npython, , SQL "), ("Python", "RAG", "SQL"))

    def test_optional_int_accepts_blank_or_whole_number(self):
        self.assertIsNone(optional_int("  ", "Year"))
        self.assertEqual(optional_int("2027", "Year"), 2027)
        with self.assertRaisesRegex(ValueError, "whole number"):
            optional_int("2027.5", "Year")

    def test_optional_float_rejects_negative_and_invalid_values(self):
        self.assertIsNone(optional_float("", "Experience"))
        self.assertEqual(optional_float("0.5", "Experience"), 0.5)
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            optional_float("-1", "Experience")
        with self.assertRaisesRegex(ValueError, "must be a number"):
            optional_float("many", "Experience")

    def test_optional_float_refuses_values_that_are_not_real_numbers(self):
        """``float()`` accepts these; a person cannot mean them, and a stored ``nan`` compares false.

        ``nan`` is false against every bound, so an experience range checked against it used to fall
        through to "within the stated range" - a fail-open result for a requirement nobody satisfied -
        and ``NaN`` is not valid JSON, so an export or backup holding one is unreadable to strict
        readers.
        """
        for raw in ("nan", "NaN", "NAN", "inf", "-inf", "Infinity", "infinity", "1e400", "-1e400"):
            with self.subTest(value=raw):
                with self.assertRaisesRegex(ValueError, "real, finite number"):
                    optional_float(raw, "Experience")

    def test_the_largest_ordinary_numbers_are_still_accepted(self):
        self.assertEqual(optional_float("0", "Experience"), 0.0)
        self.assertEqual(optional_float(" 40 ", "Experience"), 40.0)
        self.assertEqual(optional_float("1e308", "Experience"), 1e308)


if __name__ == "__main__":
    unittest.main()
