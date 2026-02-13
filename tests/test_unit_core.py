"""Unit tests for core UpNote Reorganizer functions."""

import unittest
from pathlib import Path

from UpNote_Reorganizer import (
    normalize_categories,
    split_files_target,
    resolve_source_path,
    safe_link_target,
    relpath_display,
)


class TestNormalizeCategories(unittest.TestCase):
    """Tests for normalize_categories function."""

    def test_empty_categories(self):
        """Empty categories should return base_dir."""
        base = Path("Notes")
        result = normalize_categories(None, base)
        self.assertEqual(result, [base])

        result = normalize_categories("", base)
        self.assertEqual(result, [base])

        result = normalize_categories([], base)
        self.assertEqual(result, [base])

    def test_single_category_string(self):
        """Single category as string."""
        base = Path("Notes")
        result = normalize_categories("Work", base)
        self.assertEqual(result, [base / "Work"])

    def test_single_category_with_slash(self):
        """Category with slash separator."""
        base = Path("Notes")
        result = normalize_categories("Work/Projects", base)
        self.assertEqual(result, [base / "Work" / "Projects"])

    def test_category_with_spaces(self):
        """Category with spaces around slashes."""
        base = Path("Notes")
        result = normalize_categories("Work / Projects / Active", base)
        self.assertEqual(result, [base / "Work" / "Projects" / "Active"])

    def test_multiple_categories_list(self):
        """Multiple categories as list."""
        base = Path("Notes")
        result = normalize_categories(["Work/Projects", "Personal"], base)
        self.assertEqual(result, [base / "Work" / "Projects", base / "Personal"])

    def test_nested_categories(self):
        """Deeply nested categories."""
        base = Path("Notes")
        result = normalize_categories("Level1/Level2/Level3/Level4", base)
        self.assertEqual(result, [base / "Level1" / "Level2" / "Level3" / "Level4"])

    def test_special_characters_in_categories(self):
        """Categories with special characters (but not slashes)."""
        base = Path("Notes")
        result = normalize_categories("Work & Projects", base)
        self.assertEqual(result, [base / "Work & Projects"])


class TestSplitFilesTarget(unittest.TestCase):
    """Tests for split_files_target function."""

    def test_simple_files_path(self):
        """Simple Files/ path without encoding."""
        result = split_files_target("Files/image.png")
        self.assertEqual(result, (False, "image.png", "image.png"))

    def test_wrapped_files_path(self):
        """Files/ path wrapped in angle brackets."""
        result = split_files_target("<Files/image.png>")
        self.assertEqual(result, (True, "image.png", "image.png"))

    def test_url_encoded_path(self):
        """Files/ path with URL encoding."""
        result = split_files_target("Files/test%20file.png")
        self.assertEqual(result, (False, "test%20file.png", "test file.png"))

    def test_wrapped_url_encoded(self):
        """Wrapped Files/ path with URL encoding."""
        result = split_files_target("<Files/test%20file.png>")
        self.assertEqual(result, (True, "test%20file.png", "test file.png"))

    def test_relative_files_path(self):
        """Files/ path with ./ prefix."""
        result = split_files_target("./Files/image.png")
        self.assertEqual(result, (False, "image.png", "image.png"))

    def test_non_files_path(self):
        """Path not starting with Files/."""
        result = split_files_target("images/photo.jpg")
        self.assertIsNone(result)

    def test_http_link(self):
        """HTTP URL should return None."""
        result = split_files_target("https://example.com/image.png")
        self.assertIsNone(result)

    def test_nested_files_path(self):
        """Nested folder structure under Files/."""
        result = split_files_target("Files/subfolder/image.png")
        self.assertEqual(result, (False, "subfolder/image.png", "subfolder/image.png"))

    def test_special_chars_encoded(self):
        """Special characters in filename (encoded)."""
        result = split_files_target("Files/file%28 1%29.pdf")
        self.assertEqual(result, (False, "file%28 1%29.pdf", "file( 1).pdf"))


class TestResolveSourcePath(unittest.TestCase):
    """Tests for resolve_source_path function."""

    def test_decoded_path_exists(self, tmp_path=None):
        """Prefer decoded filename when it exists."""
        if tmp_path is None:
            import tempfile
            tmp_path = Path(tempfile.mkdtemp())

        files_dir = tmp_path / "Files"
        files_dir.mkdir()
        test_file = files_dir / "test file.png"
        test_file.write_text("test")

        result = resolve_source_path("test%20file.png", "test file.png", tmp_path)
        self.assertEqual(result, test_file)

    def test_raw_path_exists(self, tmp_path=None):
        """Fall back to raw filename when decoded doesn't exist."""
        if tmp_path is None:
            import tempfile
            tmp_path = Path(tempfile.mkdtemp())

        files_dir = tmp_path / "Files"
        files_dir.mkdir()
        # Create file with URL-encoded name
        test_file = files_dir / "test%20file.png"
        test_file.write_text("test")

        result = resolve_source_path("test%20file.png", "test file.png", tmp_path)
        self.assertEqual(result, test_file)

    def test_neither_exists(self, tmp_path=None):
        """Return None when neither version exists."""
        if tmp_path is None:
            import tempfile
            tmp_path = Path(tempfile.mkdtemp())

        files_dir = tmp_path / "Files"
        files_dir.mkdir()

        result = resolve_source_path("missing.png", "missing.png", tmp_path)
        self.assertIsNone(result)


class TestSafeLinkTarget(unittest.TestCase):
    """Tests for safe_link_target function."""

    def test_simple_filename(self):
        """Simple filename without special chars."""
        result = safe_link_target("image.png")
        self.assertEqual(result, "image.png")

    def test_filename_with_space(self):
        """Filename with space should be wrapped."""
        result = safe_link_target("my file.png")
        self.assertEqual(result, "<my file.png>")

    def test_filename_with_parentheses(self):
        """Filename with parentheses should be wrapped."""
        result = safe_link_target("file(1).png")
        self.assertEqual(result, "<file(1).png>")

    def test_path_with_spaces(self):
        """Path with spaces should be wrapped."""
        result = safe_link_target("_attachments/my file.png")
        self.assertEqual(result, "<_attachments/my file.png>")

    def test_already_safe_path(self):
        """Path without special chars should not be wrapped."""
        result = safe_link_target("_attachments/image.png")
        self.assertEqual(result, "_attachments/image.png")


class TestRelpathDisplay(unittest.TestCase):
    """Tests for relpath_display function."""

    def test_relative_path(self):
        """Path relative to base_dir."""
        path = Path("/notes/work/project")
        base = Path("/notes")
        result = relpath_display(path, base)
        self.assertEqual(result, "work/project")

    def test_non_relative_path(self):
        """Path not under base_dir returns absolute path."""
        path = Path("/other/location")
        base = Path("/notes")
        result = relpath_display(path, base)
        # Should return the absolute POSIX path
        self.assertIn("other/location", result)

    def test_same_path(self):
        """Same path as base_dir."""
        path = Path("/notes")
        base = Path("/notes")
        result = relpath_display(path, base)
        self.assertEqual(result, ".")


if __name__ == "__main__":
    unittest.main()
