"""Pytest fixtures for UpNote Reorganizer tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_migration_dir(tmp_path):
    """Create temporary source and output directories.

    Returns:
        Tuple of (source_dir, output_dir) Path objects
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "Files").mkdir()  # Create Files directory for attachments
    output = tmp_path / "output"
    output.mkdir()
    return source, output


@pytest.fixture
def sample_note_simple():
    """Simple note with frontmatter and basic content."""
    return """---
categories: Work/Projects
---
# Simple Note
Basic content here."""


@pytest.fixture
def sample_note_with_attachments():
    """Note with image and file attachments."""
    return """---
categories: Test
---
# Note with Attachments
Here's an image: ![image](Files/test%20image.png)
And a document: [doc](Files/document.pdf)
"""


@pytest.fixture
def sample_note_with_wikilinks():
    """Note containing wikilinks."""
    return """# Note with Wikilinks
See [[Other Note]] for details.
Check [[Another Note|alias here]] for more info.
Regular [markdown link](https://example.com) should be unchanged.
"""


@pytest.fixture
def sample_note_with_code():
    """Note with code fence containing links that shouldn't be processed."""
    return """# Note with Code
Normal link: ![image](Files/normal.png)

```python
# This should not be rewritten
def test():
    return "![code](Files/code.png)"
```

Another normal link: [doc](Files/doc.pdf)
"""


@pytest.fixture
def sample_note_multicat():
    """Note with multiple categories."""
    return """---
categories:
  - Work/Projects/Active
  - Personal/Archive
---
# Multi-Category Note
This note belongs to multiple notebooks.
"""


@pytest.fixture
def sample_note_empty():
    """Empty note (just frontmatter)."""
    return """---
categories: Empty
---
"""


@pytest.fixture
def sample_attachment_image(tmp_path):
    """Create a sample image file.

    Returns:
        Path to created image file
    """
    img_path = tmp_path / "test_image.png"
    # Create a minimal valid PNG file (1x1 transparent pixel)
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    img_path.write_bytes(png_data)
    return img_path


@pytest.fixture
def sample_attachment_pdf(tmp_path):
    """Create a sample PDF file.

    Returns:
        Path to created PDF file
    """
    pdf_path = tmp_path / "test_doc.pdf"
    # Create a minimal valid PDF file
    pdf_data = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Count 0 /Kids [] >>
endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer
<< /Size 3 /Root 1 0 R >>
startxref
109
%%EOF
"""
    pdf_path.write_bytes(pdf_data)
    return pdf_path


@pytest.fixture
def mock_args():
    """Mock argparse.Namespace with default arguments."""
    from argparse import Namespace
    return Namespace(
        source_dir=".",
        base_dir="Notes",
        attachments_dir="",
        keep_frontmatter=True,
        dry_run=False,
        skip_attachments=False,
        fail_on_missing=False,
        report="migration-report.json",
        report_format="json",
        report_redact=False,
    )
