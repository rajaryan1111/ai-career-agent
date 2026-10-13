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


if __name__ == "__main__":
    unittest.main()
