from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from urllib.parse import unquote

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

try:
    import frontmatter  # pip install python-frontmatter
except ImportError:  # pragma: no cover - handled in main
    frontmatter = None

from dataclasses import dataclass, field
from enum import Enum


# Enums for configuration options
class DuplicateStrategy(Enum):
    """Strategy for handling notes in multiple notebooks."""
    COPY_ALL = "copy-all"
    FIRST_ONLY = "first-only"
    WITH_ALIASES = "aliases"


class WikilinkMode(Enum):
    """Mode for handling wikilinks in notes."""
    PRESERVE = "preserve"
    TO_WIKILINK = "to-wikilink"
    TO_MARKDOWN = "to-markdown"


class CollisionStrategy(Enum):
    """Strategy for handling file name collisions."""
    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"


# Data models
@dataclass
class WikiLink:
    """Represents a wikilink [[target|alias]]."""
    target: str
    alias: Optional[str] = None


@dataclass
class AttachmentReference:
    """Represents an attachment reference in markdown."""
    rel_raw: str           # URL-encoded path
    rel_decoded: str       # Decoded path
    source_path: Optional[Path] = None
    exists: bool = False


@dataclass
class MigrationConfig:
    """Configuration for migration process."""
    source_dir: Path
    base_dir: Path
    attachments_dir: str
    keep_frontmatter: bool
    dry_run: bool
    skip_attachments: bool
    fail_on_missing: bool
    report_path: Path
    report_format: str
    report_redact: bool
    # New options
    wikilink_mode: WikilinkMode = WikilinkMode.PRESERVE
    update_internal_links: bool = False
    convert_tags: bool = False
    tag_prefix: str = ""
    duplicate_strategy: DuplicateStrategy = DuplicateStrategy.COPY_ALL
    verbose: int = 0
    quiet: bool = False
    no_progress: bool = False
    collision_strategy: CollisionStrategy = CollisionStrategy.SKIP
    skip_empty_notes: bool = False


# Logging configuration
logger = logging.getLogger(__name__)


def setup_logging(verbose: int = 0, quiet: bool = False, log_file: Optional[Path] = None) -> None:
    """Configure logging based on verbosity settings.

    Args:
        verbose: Verbosity level (0=WARNING, 1=INFO, 2+=DEBUG)
        quiet: If True, only show ERROR messages
        log_file: Optional path to log file (always logs at DEBUG level)

    Examples:
        >>> setup_logging(verbose=0)  # Default: WARNING level
        >>> setup_logging(verbose=1)  # INFO level
        >>> setup_logging(verbose=2)  # DEBUG level
        >>> setup_logging(quiet=True)  # ERROR level only
    """
    # Determine console log level
    if quiet:
        level = logging.ERROR
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True  # Override any existing config
    )

    # Add file handler if log file specified
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)  # Always log DEBUG to file
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        logging.getLogger().addHandler(fh)
        logger.info(f"Logging to file: {log_file}")


# Match image or link markdown with optional title.
LINK_RE = re.compile(
    r'!?\[[^\]]*]\((?P<target><[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)'
)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
# Match wikilinks [[target]] or [[target|alias]]
WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')


def normalize_categories(raw_categories: Optional[str | List[str]], base_dir: Path) -> List[Path]:
    """Normalize category strings into Path objects.

    Takes UpNote category metadata (e.g., "Work/Projects" or ["Work/Projects", "Archive"])
    and converts them into Path objects relative to base_dir.

    Args:
        raw_categories: String or list of category paths with "/" separators, or None
        base_dir: Base directory path for output

    Returns:
        List of Path objects for each destination folder. Returns [base_dir] if
        no categories provided.

    Examples:
        >>> normalize_categories(["Work/Projects"], Path("Notes"))
        [Path("Notes/Work/Projects")]
        >>> normalize_categories("Personal / Health", Path("Notes"))
        [Path("Notes/Personal/Health")]
    """
    if not raw_categories:
        return [base_dir]
    if isinstance(raw_categories, str):
        raw_categories = [raw_categories]

    paths = []
    for raw in raw_categories:
        if not raw:
            continue
        parts = [p.strip() for p in re.split(r"\s*/\s*", raw) if p.strip()]
        if not parts:
            continue
        paths.append(base_dir.joinpath(*parts))
    return paths or [base_dir]


def split_files_target(target: str) -> Optional[Tuple[bool, str, str]]:
    """Parse a markdown link target to extract Files/ attachment reference.

    Args:
        target: Link target from markdown (e.g., "Files/image.png" or "<Files/test%20file.png>")

    Returns:
        Tuple of (wrapped, raw_path, decoded_path) if target is a Files/ reference,
        None otherwise.
        - wrapped: True if target was wrapped in angle brackets
        - raw_path: Path with URL encoding (e.g., "test%20file.png")
        - decoded_path: Path with spaces and special chars decoded (e.g., "test file.png")

    Examples:
        >>> split_files_target("Files/image.png")
        (False, "image.png", "image.png")
        >>> split_files_target("<Files/test%20file.png>")
        (True, "test%20file.png", "test file.png")
    """
    wrapped = target.startswith("<") and target.endswith(">")
    raw = target[1:-1] if wrapped else target
    if raw.startswith("./"):
        raw = raw[2:]
    if not raw.startswith("Files/"):
        return None
    rel_raw = raw[len("Files/"):]
    rel_decoded = unquote(rel_raw)
    return wrapped, rel_raw, rel_decoded


def resolve_source_path(rel_raw: str, rel_decoded: str, source_dir: Path) -> Optional[Path]:
    """Resolve attachment path to actual file on disk.

    Tries decoded filename first (most common), then falls back to raw URL-encoded
    filename if decoded doesn't exist.

    Args:
        rel_raw: URL-encoded relative path (e.g., "test%20file.png")
        rel_decoded: Decoded relative path (e.g., "test file.png")
        source_dir: Source directory containing Files/ folder

    Returns:
        Path to existing file, or None if file not found

    Examples:
        >>> resolve_source_path("test%20file.png", "test file.png", Path("/export"))
        Path("/export/Files/test file.png")
    """
    # Prefer decoded filenames (typical on disk), but fall back to raw if needed.
    decoded_path = source_dir / "Files" / rel_decoded
    if decoded_path.exists():
        return decoded_path
    raw_path = source_dir / "Files" / rel_raw
    if raw_path.exists():
        return raw_path
    return None


def safe_link_target(path_str: str) -> str:
    """Wrap link target in angle brackets if it contains special characters.

    Prevents markdown parsing issues with spaces and parentheses in file paths.

    Args:
        path_str: File path string

    Returns:
        Path wrapped in <> if special characters present, unchanged otherwise

    Examples:
        >>> safe_link_target("image.png")
        "image.png"
        >>> safe_link_target("my file.png")
        "<my file.png>"
        >>> safe_link_target("file(1).png")
        "<file(1).png>"
    """
    # Wrap in angle brackets when spaces are present to avoid Markdown parsing issues.
    if " " in path_str or "(" in path_str or ")" in path_str:
        return f"<{path_str}>"
    return path_str


def rewrite_links_in_text(text: str, attachment_dirname: str) -> str:
    """Rewrite Files/ attachment links to new location.

    Updates markdown links from "Files/attachment.png" to appropriate relative
    paths based on attachment_dirname.

    Args:
        text: Markdown text containing links
        attachment_dirname: Subdirectory for attachments (e.g., "_attachments"), or empty

    Returns:
        Text with rewritten links

    Examples:
        >>> rewrite_links_in_text("![](Files/image.png)", "_attachments")
        "![](_attachments/image.png)"
        >>> rewrite_links_in_text("[doc](Files/file.pdf)", "")
        "[doc](file.pdf)"
    """
    def repl(match):
        target = match.group("target")
        split = split_files_target(target)
        if not split:
            return match.group(0)
        _wrapped, rel_raw, rel_decoded = split
        rel_posix = Path(rel_decoded).as_posix()
        if attachment_dirname:
            rel_posix = f"{attachment_dirname}/{rel_posix}"
        new_target = safe_link_target(rel_posix)
        return match.group(0).replace(target, new_target, 1)

    return LINK_RE.sub(repl, text)


def iter_attachments_in_text(text: str):
    """Iterate over all Files/ attachment references in text.

    Args:
        text: Markdown text

    Yields:
        Tuples of (raw_path, decoded_path) for each attachment reference

    Examples:
        >>> list(iter_attachments_in_text("![](Files/a.png) [link](Files/b.pdf)"))
        [("a.png", "a.png"), ("b.pdf", "b.pdf")]
    """
    for match in LINK_RE.finditer(text):
        target = match.group("target")
        split = split_files_target(target)
        if not split:
            continue
        _wrapped, rel_raw, rel_decoded = split
        yield rel_raw, rel_decoded


def process_markdown(content: str, attachment_dirname: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Process markdown content: rewrite links and extract attachments.

    Rewrites Files/ attachment links while skipping code fences. Extracts unique
    attachment references for copying.

    Args:
        content: Raw markdown content
        attachment_dirname: Subdirectory for attachments

    Returns:
        Tuple of (processed_content, unique_attachments)
        - processed_content: Markdown with rewritten links
        - unique_attachments: List of (raw_path, decoded_path) tuples

    Notes:
        - Preserves code fence content unchanged (doesn't rewrite links in code)
        - Deduplicates attachment list while preserving first occurrence order
        - Handles both ``` and ~~~ fence styles with nesting

    Examples:
        >>> process_markdown("![](Files/img.png)", "_attachments")
        ("![](_attachments/img.png)", [("img.png", "img.png")])
    """
    attachments = []
    out_lines = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in content.splitlines(keepends=True):
        match = FENCE_RE.match(line)
        if match:
            fence = match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = fence[0]
                fence_len = len(fence)
            else:
                if fence[0] == fence_char and len(fence) >= fence_len:
                    in_fence = False
            out_lines.append(line)
            continue

        if in_fence:
            out_lines.append(line)
            continue

        for rel_raw, rel_decoded in iter_attachments_in_text(line):
            attachments.append((rel_raw, rel_decoded))

        out_lines.append(rewrite_links_in_text(line, attachment_dirname))

    # Deduplicate attachments while preserving order
    seen = set()
    unique_attachments = []
    for rel_raw, rel_decoded in attachments:
        key = (rel_raw, rel_decoded)
        if key in seen:
            continue
        seen.add(key)
        unique_attachments.append((rel_raw, rel_decoded))

    return "".join(out_lines), unique_attachments


def detect_wikilinks_in_text(text: str) -> List[WikiLink]:
    """Extract all wikilinks from text.

    Args:
        text: Markdown text potentially containing wikilinks

    Returns:
        List of WikiLink objects found in text

    Examples:
        >>> detect_wikilinks_in_text("See [[Note]] and [[Other|alias]]")
        [WikiLink(target='Note', alias=None), WikiLink(target='Other', alias='alias')]
    """
    wikilinks = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        alias = match.group(2).strip() if match.group(2) else None
        wikilinks.append(WikiLink(target=target, alias=alias))
    return wikilinks


def rewrite_wikilinks(text: str, mode: WikilinkMode) -> str:
    """Convert wikilinks based on mode.

    Args:
        text: Markdown text containing wikilinks
        mode: Conversion mode (PRESERVE, TO_MARKDOWN, TO_WIKILINK)

    Returns:
        Text with wikilinks converted according to mode

    Modes:
        - PRESERVE: Leave wikilinks unchanged
        - TO_MARKDOWN: Convert [[Target|Alias]] to [Alias](Target.md)
        - TO_WIKILINK: Convert [text](note.md) to [[note|text]]

    Examples:
        >>> rewrite_wikilinks("[[Note]]", WikilinkMode.TO_MARKDOWN)
        "[Note](Note.md)"
        >>> rewrite_wikilinks("[[Note|Alias]]", WikilinkMode.TO_MARKDOWN)
        "[Alias](Note.md)"
    """
    if mode == WikilinkMode.PRESERVE:
        return text
    elif mode == WikilinkMode.TO_MARKDOWN:
        # Convert [[Target|Alias]] to [Alias](Target.md) or [[Target]] to [Target](Target.md)
        def repl(match):
            target = match.group(1).strip()
            alias = match.group(2).strip() if match.group(2) else target
            return f"[{alias}]({target}.md)"
        return WIKILINK_RE.sub(repl, text)
    elif mode == WikilinkMode.TO_WIKILINK:
        # Convert [text](note.md) to [[note|text]]
        # Match markdown links that point to .md files
        md_link_re = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
        def repl(match):
            text = match.group(1)
            target = match.group(2).replace('.md', '')
            # Remove path if present, just use filename
            if '/' in target:
                target = target.split('/')[-1]
            # If text matches target (case-insensitive), use simple wikilink
            if text.lower() == target.lower():
                return f"[[{target}]]"
            return f"[[{target}|{text}]]"
        return md_link_re.sub(repl, text)
    return text


def rewrite_wikilinks_safe(text: str, mode: WikilinkMode) -> str:
    """Rewrite wikilinks while skipping fenced code blocks."""
    if mode == WikilinkMode.PRESERVE:
        return text

    out_lines = []
    in_fence = False
    fence_char = ""
    fence_len = 0

    for line in text.splitlines(keepends=True):
        match = FENCE_RE.match(line)
        if match:
            fence = match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = fence[0]
                fence_len = len(fence)
            else:
                if fence[0] == fence_char and len(fence) >= fence_len:
                    in_fence = False
            out_lines.append(line)
            continue

        if in_fence:
            out_lines.append(line)
            continue

        out_lines.append(rewrite_wikilinks(line, mode))

    return "".join(out_lines)
def convert_categories_to_tags(categories: Optional[List[str]], prefix: str = "") -> List[str]:
    """Convert UpNote categories to Obsidian tags.

    Takes category paths like "Work/Projects" and converts them to tags like
    "work-projects" or with custom prefix "upnote/work-projects".

    Args:
        categories: List of category paths (e.g., ["Work/Projects", "Personal"])
        prefix: Optional prefix for tags (e.g., "upnote/")

    Returns:
        List of tag strings suitable for Obsidian frontmatter

    Examples:
        >>> convert_categories_to_tags(["Work/Projects"], "")
        ['work', 'projects']
        >>> convert_categories_to_tags(["Work/Projects"], "upnote/")
        ['upnote/work', 'upnote/projects']
    """
    if not categories:
        return []

    tags = []
    for category in categories:
        # Split on "/" to get individual parts
        parts = [p.strip() for p in category.split("/") if p.strip()]
        for part in parts:
            # Convert to lowercase and replace spaces with hyphens
            tag = part.replace(" ", "-").lower()
            if prefix:
                tag = f"{prefix}{tag}"
            if tag not in tags:
                tags.append(tag)

    return tags


def relpath_display(path: Path, base_dir: Path) -> str:
    """Get display-friendly relative path.

    Args:
        path: Absolute or relative path
        base_dir: Base directory for relative path calculation

    Returns:
        POSIX-style relative path if possible, absolute path otherwise

    Examples:
        >>> relpath_display(Path("/notes/work/project"), Path("/notes"))
        "work/project"
    """
    try:
        return path.relative_to(base_dir).as_posix()
    except ValueError:
        return path.as_posix()


def write_report(report_path: Path, report_format: str, data: Dict[str, Any]) -> None:
    """Write migration report to file.

    Args:
        report_path: Output file path
        report_format: "json" or "md" (markdown)
        data: Report data dictionary

    Output formats:
        - json: Structured JSON with full migration details
        - md: Human-readable markdown summary

    Examples:
        >>> write_report(Path("report.json"), "json", report_data)
        >>> write_report(Path("report.md"), "md", report_data)
    """
    if report_format == "json":
        report_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    # Markdown
    lines = []
    lines.append("# UpNote Migration Report")
    lines.append("")
    lines.append(f"- Generated: {data['generated_utc']}")
    lines.append(f"- Dry run: {data['dry_run']}")
    lines.append(f"- Notes processed: {data['summary']['notes_processed']}")
    lines.append(f"- Notes written: {data['summary']['notes_written']}")
    lines.append(f"- Attachments copied: {data['summary']['attachments_copied']}")
    lines.append(f"- Attachments missing: {data['summary']['attachments_missing']}")
    lines.append(f"- Attachments skipped: {data['skip_attachments']}")
    lines.append(f"- Report redacted: {data['report_redact']}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in data["notes"]:
        lines.append(f"### {note['note']}")
        lines.append("")
        lines.append(f"- Destinations: {', '.join(note['destinations']) if note['destinations'] else 'None'}")
        lines.append(f"- Attachments: {note['attachments_count']}")
        lines.append(f"- Missing attachments: {note['missing_attachments_count']}")
        if note["missing_attachments"]:
            lines.append("Missing:")
            for missing in note["missing_attachments"]:
                lines.append(f"- {missing}")
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace

    Available arguments:
        --source-dir: Folder with exported UpNote markdown
        --base-dir: Output base directory
        --attachments-dir: Optional subfolder for attachments
        --keep-frontmatter: Keep UpNote frontmatter in output
        --dry-run: Don't write files, only report changes
        --skip-attachments: Don't copy attachments
        --fail-on-missing: Exit with error if attachments missing
        --report: Path to report file
        --report-format: Report format (json/md)
        --report-redact: Redact sensitive data in report
    """
    parser = argparse.ArgumentParser(
        description="Rebuild UpNote export into notebook hierarchy and fix attachments for Obsidian."
    )
    parser.add_argument("--source-dir", default=".", help="Folder with exported UpNote markdown.")
    parser.add_argument("--base-dir", default="Notes", help="Output base directory.")
    parser.add_argument(
        "--attachments-dir",
        default="",
        help='Optional subfolder for attachments in each destination (e.g. "_attachments").',
    )
    parser.add_argument(
        "--keep-frontmatter",
        action="store_true",
        help="Keep UpNote frontmatter in output markdown.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; only report planned changes.",
    )
    parser.add_argument(
        "--skip-attachments",
        action="store_true",
        help="Do not copy attachments (links are still rewritten).",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit with non-zero status if missing attachments are detected.",
    )
    parser.add_argument(
        "--report",
        default="migration-report.json",
        help="Path to report file (JSON or MD).",
    )
    parser.add_argument(
        "--report-format",
        choices=["json", "md"],
        default="json",
        help="Report format.",
    )
    parser.add_argument(
        "--report-redact",
        action="store_true",
        help="Redact note titles and attachment names in the report.",
    )
    parser.add_argument(
        "--wikilink-mode",
        choices=["preserve", "to-wikilink", "to-markdown"],
        default="preserve",
        help="How to handle wikilinks: preserve (default), convert to-wikilink, or to-markdown",
    )
    parser.add_argument(
        "--convert-tags",
        action="store_true",
        help="Convert UpNote categories to Obsidian tags in frontmatter",
    )
    parser.add_argument(
        "--tag-prefix",
        default="",
        help="Prefix for converted tags (e.g., 'upnote/')",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode (only show errors)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write detailed logs to file (always DEBUG level)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate setup and exit (don't process files)",
    )
    return parser.parse_args()


def initialize_report(source_dir_display: str, base_dir: Path,
                      attachment_dirname: str, args: argparse.Namespace) -> Dict[str, Any]:
    """Initialize the migration report structure.

    Args:
        source_dir_display: Display path for source directory
        base_dir: Base output directory
        attachment_dirname: Subdirectory name for attachments
        args: Command-line arguments

    Returns:
        Dictionary containing report structure
    """
    report_source_dir = source_dir_display
    report_base_dir = base_dir.as_posix()
    if args.report_redact:
        report_source_dir = "<redacted>"
        report_base_dir = "<redacted>"

    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": bool(args.dry_run),
        "source_dir": report_source_dir,
        "base_dir": report_base_dir,
        "attachments_dir": attachment_dirname,
        "keep_frontmatter": bool(args.keep_frontmatter),
        "skip_attachments": bool(args.skip_attachments),
        "report_redact": bool(args.report_redact),
        "summary": {
            "notes_processed": 0,
            "notes_written": 0,
            "attachments_copied": 0,
            "attachments_missing": 0,
        },
        "notes": [],
    }


def copy_note_attachments(attachments: List[Tuple[str, str]], dest: Path,
                         source_dir: Path, attachment_dirname: str,
                         args: argparse.Namespace) -> Tuple[int, List[str]]:
    """Copy attachments for a single destination.

    Args:
        attachments: List of (raw_path, decoded_path) tuples
        dest: Destination directory
        source_dir: Source directory containing Files/
        attachment_dirname: Subdirectory name for attachments
        args: Command-line arguments

    Returns:
        Tuple of (attachments_copied_count, missing_attachments_list)
    """
    attachments_copied = 0
    missing_attachments = []

    if args.skip_attachments:
        return attachments_copied, missing_attachments

    attachment_root = dest / attachment_dirname if attachment_dirname else dest
    if not args.dry_run:
        attachment_root.mkdir(parents=True, exist_ok=True)

    for rel_raw, rel_decoded in attachments:
        source_path = resolve_source_path(rel_raw, rel_decoded, source_dir)
        if not source_path:
            missing_attachments.append(f"Files/{rel_raw}")
            continue

        dest_path = attachment_root / Path(rel_decoded)
        if not args.dry_run:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if not dest_path.exists():
                shutil.copy2(source_path, dest_path)
                attachments_copied += 1

    return attachments_copied, missing_attachments


def write_note_to_destinations(note, post_content: str, note_path: Path,
                              destinations: List[Path], args: argparse.Namespace) -> int:
    """Write note to all destination directories.

    Args:
        note: Frontmatter note object
        post_content: Processed note content
        note_path: Original note file path
        destinations: List of destination directories
        args: Command-line arguments

    Returns:
        Number of notes written
    """
    notes_written = 0

    for dest in destinations:
        if not args.dry_run:
            dest.mkdir(parents=True, exist_ok=True)
            note.content = post_content
            output = frontmatter.dumps(note) if args.keep_frontmatter else post_content
            out_path = dest / note_path.name
            with open(out_path, "w", encoding="utf-8") as outfile:
                outfile.write(output)
            notes_written += 1

    return notes_written


def validate_migration_setup(source_dir: Path, base_dir: Path,
                            dry_run: bool, skip_attachments: bool) -> List[str]:
    """Validate migration setup before processing.

    Checks for common issues that would cause migration to fail:
    - Source directory exists and is accessible
    - Source contains markdown files
    - Output directory is writable (if not dry-run)
    - Files/ directory exists for attachments (if not skip-attachments)

    Args:
        source_dir: Source directory with UpNote export
        base_dir: Output base directory
        dry_run: Whether this is a dry run
        skip_attachments: Whether attachments will be skipped

    Returns:
        List of error messages (empty if validation passes)

    Examples:
        >>> errors = validate_migration_setup(Path("export"), Path("output"), False, False)
        >>> if errors:
        ...     print("Validation failed:", errors)
    """
    errors = []

    # Check source directory exists
    if not source_dir.exists():
        errors.append(f"Source directory not found: {source_dir}")
        return errors  # Can't continue checking

    if not source_dir.is_dir():
        errors.append(f"Source is not a directory: {source_dir}")
        return errors

    # Check for markdown files
    md_files = list(source_dir.glob("*.md"))
    if not md_files:
        errors.append(f"No .md files found in source directory: {source_dir}")

    # Check Files/ directory if processing attachments
    if not skip_attachments:
        files_dir = source_dir / "Files"
        if not files_dir.exists():
            logger.warning(f"Files/ directory not found: {files_dir}")
            logger.warning("Attachments may be missing. Consider using --skip-attachments if no attachments expected.")
        elif not files_dir.is_dir():
            errors.append(f"Files/ exists but is not a directory: {files_dir}")

    # Check output directory is writable (if not dry-run)
    if not dry_run:
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            # Try to create a test file to verify write permissions
            test_file = base_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            errors.append(f"Cannot write to output directory: {base_dir}")
        except OSError as e:
            errors.append(f"Error accessing output directory {base_dir}: {e}")

    return errors


def main() -> None:
    """Main entry point for UpNote to Obsidian migration."""
    args = parse_args()

    # Setup logging first
    setup_logging(verbose=args.verbose, quiet=args.quiet, log_file=args.log_file)

    if frontmatter is None:
        logger.error("Missing dependency: python-frontmatter. Install with `pip install -r requirements.txt`.")
        sys.exit(2)

    # Apply derived behavior
    if args.convert_tags and not args.keep_frontmatter:
        logger.warning("--convert-tags requires frontmatter. Enabling --keep-frontmatter.")
        args.keep_frontmatter = True

    # Setup directories
    source_dir = Path(args.source_dir).resolve()
    source_dir_display = Path(args.source_dir).as_posix()
    base_dir = Path(args.base_dir)
    attachment_dirname = args.attachments_dir.strip()

    logger.debug(f"Source directory: {source_dir}")
    logger.debug(f"Base directory: {base_dir}")
    logger.debug(f"Attachments subdirectory: {attachment_dirname if attachment_dirname else '(none)'}")
    logger.debug(f"Dry run: {args.dry_run}")

    # Run pre-flight validation
    logger.info("Running pre-flight validation...")
    validation_errors = validate_migration_setup(
        source_dir, base_dir, args.dry_run, args.skip_attachments
    )

    if validation_errors:
        logger.error("Validation failed:")
        for error in validation_errors:
            logger.error(f"  - {error}")
        sys.exit(1)

    logger.info("Pre-flight validation passed")

    # If validate-only mode, exit now
    if args.validate_only:
        logger.info("Validate-only mode: Setup is valid, exiting without processing")
        sys.exit(0)

    if not args.dry_run:
        base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created output directory: {base_dir}")

    # Initialize report
    report = initialize_report(source_dir_display, base_dir, attachment_dirname, args)
    missing_attachments_total = 0
    note_index = 0

    # Get list of markdown files
    note_paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md"]
    note_paths.sort(key=lambda p: p.name.lower())

    logger.info(f"Found {len(note_paths)} markdown files to process")

    # Add progress bar if available and not disabled
    if tqdm and not args.no_progress and sys.stdout.isatty():
        note_paths = tqdm(note_paths, desc="Processing notes", unit="note")
    elif not sys.stdout.isatty():
        logger.debug("TTY not detected, progress bar disabled")

    # Process all markdown notes
    for path in note_paths:
        note_index += 1
        report["summary"]["notes_processed"] += 1

        # Load note and get destinations
        note = frontmatter.load(path)
        post_content = note.content
        destinations = normalize_categories(note.get("categories"), base_dir)

        logger.debug(f"Note destinations: {[str(d) for d in destinations]}")

        # Deduplicate destinations while preserving order
        seen = set()
        unique_destinations = []
        for d in destinations:
            if d not in seen:
                seen.add(d)
                unique_destinations.append(d)

        logger.info(f"Processing note {path.name}")

        # Process markdown and extract attachments
        post_content, attachments = process_markdown(post_content, attachment_dirname)
        logger.debug(f"Extracted {len(attachments)} attachments from {path.name}")

        # Apply wikilink conversion if requested
        if args.wikilink_mode != "preserve":
            wikilink_mode = WikilinkMode(args.wikilink_mode)
            post_content = rewrite_wikilinks_safe(post_content, wikilink_mode)

        # Convert categories to tags if requested
        if args.convert_tags:
            categories = note.get("categories", [])
            if isinstance(categories, str):
                categories = [categories]
            tags = convert_categories_to_tags(categories, args.tag_prefix)
            if tags:
                # Add tags to frontmatter (merge with existing tags)
                existing_tags = note.get("tags", [])
                if isinstance(existing_tags, str):
                    existing_tags = [existing_tags]
                all_tags = list(set(existing_tags + tags))  # Deduplicate
                note["tags"] = all_tags
                logger.debug(f"Added tags to {path.name}: {tags}")

        # Build note report
        note_title = path.name if not args.report_redact else f"note-{note_index}"
        note_report = {
            "note": note_title,
            "destinations": [relpath_display(d, base_dir) for d in unique_destinations],
            "attachments": [rel_raw for rel_raw, _ in attachments],
            "missing_attachments": [],
            "attachments_count": len(attachments),
            "missing_attachments_count": 0,
        }

        # Process each destination
        for dest in unique_destinations:
            # Copy attachments
            copied, missing = copy_note_attachments(attachments, dest, source_dir,
                                                   attachment_dirname, args)
            report["summary"]["attachments_copied"] += copied
            note_report["missing_attachments"].extend(missing)

            # Log missing attachments
            for missing_att in missing:
                logger.warning(f"Missing attachment {missing_att} referenced by {path.name}")
                report["summary"]["attachments_missing"] += 1
                missing_attachments_total += 1

        # Write note to destinations
        notes_written = write_note_to_destinations(note, post_content, path,
                                                   unique_destinations, args)
        report["summary"]["notes_written"] += notes_written

        # Finalize note report
        note_report["missing_attachments_count"] = len(note_report["missing_attachments"])
        if args.report_redact:
            note_report["attachments"] = []
            note_report["missing_attachments"] = []
            note_report["destinations"] = []

        report["notes"].append(note_report)

    # Write final report
    report_path = Path(args.report)
    write_report(report_path, args.report_format, report)

    # Exit with error if missing attachments and fail_on_missing is set
    if args.fail_on_missing and missing_attachments_total > 0:
        logger.error(f"Missing attachments detected: {missing_attachments_total}")
        sys.exit(1)

    logger.info(f"Migration complete: {report['summary']['notes_processed']} notes processed, "
                f"{report['summary']['notes_written']} notes written, "
                f"{report['summary']['attachments_copied']} attachments copied")
    if missing_attachments_total > 0:
        logger.warning(f"Total missing attachments: {missing_attachments_total}")


if __name__ == "__main__":
    main()
    
