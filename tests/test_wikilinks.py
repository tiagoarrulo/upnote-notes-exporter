"""Tests for wikilink functionality."""

import unittest
from UpNote_Reorganizer import (
    WikiLink,
    WikilinkMode,
    detect_wikilinks_in_text,
    rewrite_wikilinks,
)


class TestDetectWikilinksInText(unittest.TestCase):
    """Tests for detect_wikilinks_in_text function."""

    def test_simple_wikilink(self):
        """Detect simple wikilink without alias."""
        text = "See [[Note]] for details."
        wikilinks = detect_wikilinks_in_text(text)
        self.assertEqual(len(wikilinks), 1)
        self.assertEqual(wikilinks[0].target, "Note")
        self.assertIsNone(wikilinks[0].alias)

    def test_wikilink_with_alias(self):
        """Detect wikilink with alias."""
        text = "Check [[Note Name|alias here]]."
        wikilinks = detect_wikilinks_in_text(text)
        self.assertEqual(len(wikilinks), 1)
        self.assertEqual(wikilinks[0].target, "Note Name")
        self.assertEqual(wikilinks[0].alias, "alias here")

    def test_multiple_wikilinks(self):
        """Detect multiple wikilinks."""
        text = "[[First]] and [[Second|alias]] and [[Third]]"
        wikilinks = detect_wikilinks_in_text(text)
        self.assertEqual(len(wikilinks), 3)
        self.assertEqual(wikilinks[0].target, "First")
        self.assertEqual(wikilinks[1].target, "Second")
        self.assertEqual(wikilinks[1].alias, "alias")
        self.assertEqual(wikilinks[2].target, "Third")

    def test_no_wikilinks(self):
        """No wikilinks should return empty list."""
        text = "Regular text with [markdown link](url)"
        wikilinks = detect_wikilinks_in_text(text)
        self.assertEqual(len(wikilinks), 0)

    def test_wikilink_with_spaces(self):
        """Wikilinks with spaces in target."""
        text = "[[Note With Spaces]]"
        wikilinks = detect_wikilinks_in_text(text)
        self.assertEqual(len(wikilinks), 1)
        self.assertEqual(wikilinks[0].target, "Note With Spaces")

    def test_nested_brackets(self):
        """Text with brackets but not wikilinks."""
        text = "[regular](link) and [another](link)"
        wikilinks = detect_wikilinks_in_text(text)
        self.assertEqual(len(wikilinks), 0)


class TestRewriteWikilinks(unittest.TestCase):
    """Tests for rewrite_wikilinks function."""

    def test_preserve_mode(self):
        """Preserve mode should not change wikilinks."""
        text = "[[Note]] and [[Other|alias]]"
        result = rewrite_wikilinks(text, WikilinkMode.PRESERVE)
        self.assertEqual(result, text)

    def test_to_markdown_simple(self):
        """Convert simple wikilink to markdown."""
        text = "[[Note]]"
        result = rewrite_wikilinks(text, WikilinkMode.TO_MARKDOWN)
        self.assertEqual(result, "[Note](Note.md)")

    def test_to_markdown_with_alias(self):
        """Convert wikilink with alias to markdown."""
        text = "[[Note Name|My Alias]]"
        result = rewrite_wikilinks(text, WikilinkMode.TO_MARKDOWN)
        self.assertEqual(result, "[My Alias](Note Name.md)")

    def test_to_markdown_multiple(self):
        """Convert multiple wikilinks."""
        text = "[[First]] and [[Second|alias]]"
        result = rewrite_wikilinks(text, WikilinkMode.TO_MARKDOWN)
        self.assertIn("[First](First.md)", result)
        self.assertIn("[alias](Second.md)", result)

    def test_to_markdown_preserves_other_content(self):
        """Non-wikilink content should be preserved."""
        text = "Regular text [[Note]] more text"
        result = rewrite_wikilinks(text, WikilinkMode.TO_MARKDOWN)
        self.assertIn("Regular text", result)
        self.assertIn("[Note](Note.md)", result)
        self.assertIn("more text", result)

    def test_to_wikilink_simple(self):
        """Convert markdown link to wikilink."""
        text = "[Note](note.md)"
        result = rewrite_wikilinks(text, WikilinkMode.TO_WIKILINK)
        self.assertEqual(result, "[[note]]")

    def test_to_wikilink_with_different_text(self):
        """Convert markdown link with different text to wikilink with alias."""
        text = "[My Alias](note.md)"
        result = rewrite_wikilinks(text, WikilinkMode.TO_WIKILINK)
        self.assertEqual(result, "[[note|My Alias]]")

    def test_to_wikilink_with_path(self):
        """Convert markdown link with path to wikilink."""
        text = "[Note](path/to/note.md)"
        result = rewrite_wikilinks(text, WikilinkMode.TO_WIKILINK)
        # Should use just filename, not full path
        self.assertIn("[[note", result)

    def test_to_wikilink_preserves_non_md_links(self):
        """Non-.md links should not be converted."""
        text = "[External](https://example.com) and [Local](note.md)"
        result = rewrite_wikilinks(text, WikilinkMode.TO_WIKILINK)
        self.assertIn("https://example.com", result)
        self.assertIn("[[note|Local]]", result)  # Local != note, so includes alias

    def test_mixed_content(self):
        """Mixed wikilinks and regular markdown."""
        text = "# Title\n[[Wikilink]] and [external](https://example.com)"
        result_preserve = rewrite_wikilinks(text, WikilinkMode.PRESERVE)
        self.assertEqual(result_preserve, text)

        result_to_md = rewrite_wikilinks(text, WikilinkMode.TO_MARKDOWN)
        self.assertIn("[Wikilink](Wikilink.md)", result_to_md)
        self.assertIn("https://example.com", result_to_md)


if __name__ == "__main__":
    unittest.main()
