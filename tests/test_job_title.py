import unittest

from copilot_apply import clean_job_title


class TestJobTitleCleaning(unittest.TestCase):
    def test_removes_parenthetical_role_details(self):
        self.assertEqual(
            clean_job_title("Softwareentwickler / Absolvent IT (Fullstack)"),
            "Softwareentwickler / Absolvent IT",
        )

    def test_removes_multiple_parenthetical_segments(self):
        self.assertEqual(
            clean_job_title("Softwareentwickler (m/w/d) (Remote)"),
            "Softwareentwickler",
        )

    def test_removes_nested_parentheses_and_normalizes_whitespace(self):
        self.assertEqual(
            clean_job_title("Entwickler (Schwerpunkt (Backend))  Python"),
            "Entwickler Python",
        )

    def test_keeps_title_without_parentheses(self):
        self.assertEqual(
            clean_job_title("Senior Softwareentwickler"),
            "Senior Softwareentwickler",
        )


if __name__ == "__main__":
    unittest.main()