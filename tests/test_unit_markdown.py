"""Unit tests for markdown processing functions."""

import unittest
from UpNote_Reorganizer import (
    rewrite_links_in_text,
    iter_attachments_in_text,
    process_markdown,
)


class TestRewriteLinksInText(unittest.TestCase):
    """Tests for rewrite_links_in_text function."""

    def test_simple_image_link(self):
        """Rewrite simple image link."""
        text = "![image](Files/photo.png)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertEqual(result, "![image](_attachments/photo.png)")

    def test_simple_file_link(self):
        """Rewrite simple file link."""
        text = "[document](Files/doc.pdf)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertEqual(result, "[document](_attachments/doc.pdf)")

    def test_url_encoded_link(self):
        """Rewrite link with URL encoding."""
        text = "![image](Files/test%20file.png)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertEqual(result, "![image](<_attachments/test file.png>)")

    def test_no_attachments_dir(self):
        """Rewrite without attachments subdirectory."""
        text = "![image](Files/photo.png)"
        result = rewrite_links_in_text(text, "")
        self.assertEqual(result, "![image](photo.png)")

    def test_multiple_links(self):
        """Rewrite multiple links in same text."""
        text = "![img1](Files/a.png) and ![img2](Files/b.jpg)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertIn("_attachments/a.png", result)
        self.assertIn("_attachments/b.jpg", result)

    def test_non_files_links_unchanged(self):
        """Non-Files/ links should not be changed."""
        text = "[external](https://example.com) and [local](./other.md)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertEqual(result, text)

    def test_nested_path(self):
        """Rewrite nested path under Files/."""
        text = "![image](Files/subfolder/photo.png)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertEqual(result, "![image](_attachments/subfolder/photo.png)")

    def test_wrapped_link(self):
        """Rewrite already wrapped link."""
        text = "![image](<Files/test file.png>)"
        result = rewrite_links_in_text(text, "_attachments")
        self.assertEqual(result, "![image](<_attachments/test file.png>)")


class TestIterAttachmentsInText(unittest.TestCase):
    """Tests for iter_attachments_in_text function."""

    def test_single_attachment(self):
        """Extract single attachment."""
        text = "![image](Files/photo.png)"
        attachments = list(iter_attachments_in_text(text))
        self.assertEqual(attachments, [("photo.png", "photo.png")])

    def test_multiple_attachments(self):
        """Extract multiple attachments."""
        text = "![img](Files/a.png) [doc](Files/b.pdf)"
        attachments = list(iter_attachments_in_text(text))
        self.assertEqual(attachments, [("a.png", "a.png"), ("b.pdf", "b.pdf")])

    def test_url_encoded_attachment(self):
        """Extract URL-encoded attachment."""
        text = "![image](Files/test%20file.png)"
        attachments = list(iter_attachments_in_text(text))
        self.assertEqual(attachments, [("test%20file.png", "test file.png")])

    def test_no_attachments(self):
        """No Files/ links should return empty list."""
        text = "[external](https://example.com)"
        attachments = list(iter_attachments_in_text(text))
        self.assertEqual(attachments, [])

    def test_nested_attachment(self):
        """Extract nested path attachment."""
        text = "![image](Files/subfolder/photo.png)"
        attachments = list(iter_attachments_in_text(text))
        self.assertEqual(attachments, [("subfolder/photo.png", "subfolder/photo.png")])


class TestProcessMarkdown(unittest.TestCase):
    """Tests for process_markdown function."""

    def test_simple_markdown(self):
        """Process simple markdown with one attachment."""
        content = "# Title\n![image](Files/photo.png)"
        result, attachments = process_markdown(content, "_attachments")
        self.assertIn("_attachments/photo.png", result)
        self.assertEqual(attachments, [("photo.png", "photo.png")])

    def test_skips_code_blocks(self):
        """Links in code blocks should not be rewritten."""
        content = (
            "Before [one](Files/test%20file.png)\n"
            "```\n"
            "code [two](Files/skip.png)\n"
            "```\n"
            "After ![img](Files/img.png)\n"
        )
        rewritten, attachments = process_markdown(content, "_attachments")

        # Only non-code links should be rewritten
        self.assertIn("[one](<_attachments/test file.png>)", rewritten)
        self.assertIn("![img](_attachments/img.png)", rewritten)
        self.assertIn("code [two](Files/skip.png)", rewritten)

        # Attachments extracted from non-code blocks only
        self.assertEqual(
            attachments,
            [("test%20file.png", "test file.png"), ("img.png", "img.png")],
        )

    def test_nested_code_blocks(self):
        """Handle nested code fences correctly."""
        content = (
            "Normal ![img](Files/normal.png)\n"
            "```\n"
            "Outer code [link](Files/outer.png)\n"
            "```\n"
            "Middle ![img](Files/middle.png)\n"
            "~~~\n"
            "Different fence [link](Files/tilde.png)\n"
            "~~~\n"
            "End ![img](Files/end.png)\n"
        )
        rewritten, attachments = process_markdown(content, "_attachments")

        # Code block content should not be rewritten
        self.assertIn("[link](Files/outer.png)", rewritten)
        self.assertIn("[link](Files/tilde.png)", rewritten)

        # Non-code content should be rewritten
        self.assertIn("_attachments/normal.png", rewritten)
        self.assertIn("_attachments/middle.png", rewritten)
        self.assertIn("_attachments/end.png", rewritten)

        # Only non-code attachments extracted
        self.assertEqual(len(attachments), 3)
        self.assertIn(("normal.png", "normal.png"), attachments)
        self.assertIn(("middle.png", "middle.png"), attachments)
        self.assertIn(("end.png", "end.png"), attachments)

    def test_duplicate_attachments(self):
        """Duplicate attachments should be deduplicated."""
        content = (
            "![img1](Files/photo.png)\n"
            "![img2](Files/doc.pdf)\n"
            "![img3](Files/photo.png)\n"  # Duplicate
        )
        rewritten, attachments = process_markdown(content, "_attachments")

        # All links should be rewritten
        self.assertEqual(rewritten.count("_attachments/photo.png"), 2)
        self.assertEqual(rewritten.count("_attachments/doc.pdf"), 1)

        # But attachments list should be unique
        self.assertEqual(len(attachments), 2)
        self.assertIn(("photo.png", "photo.png"), attachments)
        self.assertIn(("doc.pdf", "doc.pdf"), attachments)

    def test_preserves_line_endings(self):
        """Line endings should be preserved."""
        content = "Line 1\r\nLine 2\n"
        rewritten, _ = process_markdown(content, "")
        self.assertEqual(rewritten, content)

    def test_empty_content(self):
        """Empty content should return empty."""
        content = ""
        rewritten, attachments = process_markdown(content, "_attachments")
        self.assertEqual(rewritten, "")
        self.assertEqual(attachments, [])

    def test_no_attachments(self):
        """Content without attachments."""
        content = "# Title\nJust text content."
        rewritten, attachments = process_markdown(content, "_attachments")
        self.assertEqual(rewritten, content)
        self.assertEqual(attachments, [])

    def test_mixed_content(self):
        """Mix of images, links, code, and text."""
        content = """# Title
Normal paragraph with ![image](Files/img.png).

```python
def foo():
    # This [link](Files/code.png) stays
    pass
```

Another paragraph with [doc](Files/doc.pdf).
"""
        rewritten, attachments = process_markdown(content, "_attachments")

        # Check rewrites
        self.assertIn("_attachments/img.png", rewritten)
        self.assertIn("_attachments/doc.pdf", rewritten)
        self.assertIn("Files/code.png", rewritten)  # Not rewritten (in code)

        # Check attachments
        self.assertEqual(len(attachments), 2)
        self.assertIn(("img.png", "img.png"), attachments)
        self.assertIn(("doc.pdf", "doc.pdf"), attachments)


if __name__ == "__main__":
    unittest.main()
