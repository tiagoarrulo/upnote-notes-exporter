import unittest
from pathlib import Path

from UpNote_Reorganizer import normalize_categories, process_markdown


class TestReorganizer(unittest.TestCase):
    def test_normalize_categories(self):
        base = Path("Notes")
        result = normalize_categories(["Devoteam / Pre-Sales Pipeline Monthly"], base)
        self.assertEqual(result, [base / "Devoteam" / "Pre-Sales Pipeline Monthly"])

    def test_process_markdown_skips_code_blocks(self):
        content = (
            "Before [one](Files/test%20file.png)\n"
            "```\n"
            "code [two](Files/skip.png)\n"
            "```\n"
            "After ![img](Files/img.png)\n"
        )
        rewritten, attachments = process_markdown(content, "_attachments")

        # Only non-code links should be rewritten.
        self.assertIn("[one](<_attachments/test file.png>)", rewritten)
        self.assertIn("![img](_attachments/img.png)", rewritten)
        self.assertIn("code [two](Files/skip.png)", rewritten)

        # Attachments extracted from non-code blocks only.
        self.assertEqual(
            attachments,
            [("test%20file.png", "test file.png"), ("img.png", "img.png")],
        )


if __name__ == "__main__":
    unittest.main()
