"""Integration tests for UpNote Reorganizer."""

import json
import unittest
from pathlib import Path
from argparse import Namespace

import frontmatter

from UpNote_Reorganizer import (
    initialize_report,
    copy_note_attachments,
    write_note_to_destinations,
    write_report,
    process_markdown,
)


class TestInitializeReport(unittest.TestCase):
    """Tests for initialize_report function."""

    def test_basic_report_structure(self):
        """Test basic report initialization."""
        args = Namespace(
            report_redact=False,
            dry_run=False,
            keep_frontmatter=True,
            skip_attachments=False,
        )
        report = initialize_report("/source", Path("Notes"), "_attachments", args)

        self.assertIn("generated_utc", report)
        self.assertEqual(report["dry_run"], False)
        self.assertEqual(report["source_dir"], "/source")
        self.assertEqual(report["base_dir"], "Notes")
        self.assertEqual(report["attachments_dir"], "_attachments")
        self.assertIn("summary", report)
        self.assertEqual(report["summary"]["notes_processed"], 0)

    def test_redacted_report(self):
        """Test report with redaction enabled."""
        args = Namespace(
            report_redact=True,
            dry_run=True,
            keep_frontmatter=False,
            skip_attachments=True,
        )
        report = initialize_report("/source", Path("Notes"), "", args)

        self.assertEqual(report["source_dir"], "<redacted>")
        self.assertEqual(report["base_dir"], "<redacted>")


class TestCopyNoteAttachments(unittest.TestCase):
    """Tests for copy_note_attachments function."""

    def test_copy_attachments_dry_run(self):
        """Dry run should not copy files."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()
        (source_dir / "Files").mkdir()

        # Create test file
        test_file = source_dir / "Files" / "test.png"
        test_file.write_text("test")

        args = Namespace(dry_run=True, skip_attachments=False)
        attachments = [("test.png", "test.png")]

        copied, missing = copy_note_attachments(
            attachments, dest_dir, source_dir, "_attachments", args
        )

        self.assertEqual(copied, 0)
        self.assertEqual(missing, [])
        # File should not exist in destination
        self.assertFalse((dest_dir / "_attachments" / "test.png").exists())

    def test_copy_attachments_skip(self):
        """Skip attachments should not copy."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        args = Namespace(dry_run=False, skip_attachments=True)
        attachments = [("test.png", "test.png")]

        copied, missing = copy_note_attachments(
            attachments, dest_dir, tmp_path, "_attachments", args
        )

        self.assertEqual(copied, 0)
        self.assertEqual(missing, [])

    def test_copy_missing_attachment(self):
        """Missing attachment should be reported."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()
        (source_dir / "Files").mkdir()

        args = Namespace(dry_run=False, skip_attachments=False)
        attachments = [("missing.png", "missing.png")]

        copied, missing = copy_note_attachments(
            attachments, dest_dir, source_dir, "_attachments", args
        )

        self.assertEqual(copied, 0)
        self.assertEqual(len(missing), 1)
        self.assertIn("Files/missing.png", missing[0])

    def test_copy_real_attachment(self):
        """Actually copy attachment file."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()
        (source_dir / "Files").mkdir()

        # Create test file
        test_file = source_dir / "Files" / "test.png"
        test_file.write_text("test content")

        args = Namespace(dry_run=False, skip_attachments=False)
        attachments = [("test.png", "test.png")]

        copied, missing = copy_note_attachments(
            attachments, dest_dir, source_dir, "_attachments", args
        )

        self.assertEqual(copied, 1)
        self.assertEqual(missing, [])
        # File should exist in destination
        dest_file = dest_dir / "_attachments" / "test.png"
        self.assertTrue(dest_file.exists())
        self.assertEqual(dest_file.read_text(), "test content")


class TestWriteNoteToDestinations(unittest.TestCase):
    """Tests for write_note_to_destinations function."""

    def test_write_note_dry_run(self):
        """Dry run should not write files."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        note = frontmatter.loads("---\ntitle: Test\n---\nContent")
        args = Namespace(dry_run=True, keep_frontmatter=True)

        written = write_note_to_destinations(
            note, "Content", Path("test.md"), [dest_dir], args
        )

        self.assertEqual(written, 0)
        self.assertFalse((dest_dir / "test.md").exists())

    def test_write_note_with_frontmatter(self):
        """Write note keeping frontmatter."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        note = frontmatter.loads("---\ntitle: Test\n---\nContent")
        args = Namespace(dry_run=False, keep_frontmatter=True)

        written = write_note_to_destinations(
            note, "Content", Path("test.md"), [dest_dir], args
        )

        self.assertEqual(written, 1)
        output_file = dest_dir / "test.md"
        self.assertTrue(output_file.exists())

        # Check frontmatter is present
        loaded = frontmatter.loads(output_file.read_text())
        self.assertEqual(loaded["title"], "Test")
        self.assertEqual(loaded.content, "Content")

    def test_write_note_without_frontmatter(self):
        """Write note without frontmatter."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        note = frontmatter.loads("---\ntitle: Test\n---\nContent")
        args = Namespace(dry_run=False, keep_frontmatter=False)

        written = write_note_to_destinations(
            note, "Content", Path("test.md"), [dest_dir], args
        )

        self.assertEqual(written, 1)
        output_file = dest_dir / "test.md"
        self.assertTrue(output_file.exists())

        # Check no frontmatter
        content = output_file.read_text()
        self.assertEqual(content, "Content")
        self.assertNotIn("---", content)

    def test_write_multiple_destinations(self):
        """Write note to multiple destinations."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        dest1 = tmp_path / "dest1"
        dest2 = tmp_path / "dest2"
        dest1.mkdir()
        dest2.mkdir()

        note = frontmatter.loads("---\ntitle: Test\n---\nContent")
        args = Namespace(dry_run=False, keep_frontmatter=False)

        written = write_note_to_destinations(
            note, "Content", Path("test.md"), [dest1, dest2], args
        )

        self.assertEqual(written, 2)
        self.assertTrue((dest1 / "test.md").exists())
        self.assertTrue((dest2 / "test.md").exists())


class TestWriteReport(unittest.TestCase):
    """Tests for write_report function."""

    def test_write_json_report(self):
        """Write report in JSON format."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        report_file = tmp_path / "report.json"

        report_data = {
            "generated_utc": "2024-01-01T00:00:00Z",
            "dry_run": False,
            "summary": {"notes_processed": 5},
            "notes": [],
        }

        write_report(report_file, "json", report_data)

        self.assertTrue(report_file.exists())
        loaded = json.loads(report_file.read_text())
        self.assertEqual(loaded["summary"]["notes_processed"], 5)

    def test_write_markdown_report(self):
        """Write report in Markdown format."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        report_file = tmp_path / "report.md"

        report_data = {
            "generated_utc": "2024-01-01T00:00:00Z",
            "dry_run": False,
            "skip_attachments": False,
            "report_redact": False,
            "summary": {
                "notes_processed": 3,
                "notes_written": 3,
                "attachments_copied": 5,
                "attachments_missing": 0,
            },
            "notes": [
                {
                    "note": "test.md",
                    "destinations": ["Notes/Work"],
                    "attachments_count": 2,
                    "missing_attachments_count": 0,
                    "missing_attachments": [],
                }
            ],
        }

        write_report(report_file, "md", report_data)

        self.assertTrue(report_file.exists())
        content = report_file.read_text()
        self.assertIn("# UpNote Migration Report", content)
        self.assertIn("Notes processed: 3", content)
        self.assertIn("test.md", content)


class TestFullWorkflow(unittest.TestCase):
    """End-to-end tests simulating full migration workflow."""

    def test_full_migration_single_note(self):
        """Test complete migration of a single note with attachment."""
        import tempfile
        tmp_path = Path(tempfile.mkdtemp())
        source_dir = tmp_path / "source"
        output_dir = tmp_path / "output"
        source_dir.mkdir()
        output_dir.mkdir()
        (source_dir / "Files").mkdir()

        # Create test note
        note_content = """---
categories: Work/Projects
---
# Test Note
Here's an image: ![image](Files/test.png)
"""
        note_file = source_dir / "test.md"
        note_file.write_text(note_content)

        # Create attachment
        attachment = source_dir / "Files" / "test.png"
        attachment.write_text("fake image")

        # Simulate processing
        note = frontmatter.load(note_file)
        post_content, attachments = process_markdown(note.content, "_attachments")

        # Check processing results
        self.assertIn("_attachments/test.png", post_content)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0], ("test.png", "test.png"))


if __name__ == "__main__":
    unittest.main()
