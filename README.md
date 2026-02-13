# UpNote To Obsidian

Enhanced migration tool to convert UpNote exports into Obsidian-compatible notes. Reorganizes exported notes into folder hierarchies, fixes attachment links, and provides Obsidian-specific features like wikilink support and tag conversion.

Fork lineage:
- Forked from [simonoliver/UpNote_To_Obsidian](https://github.com/simonoliver/UpNote_To_Obsidian)
- Which was originally forked from [adams141/UpNote_Reorganizer](https://github.com/adams141/UpNote_Reorganizer)

## Features

### Core Functionality
- ✅ Restore folder hierarchy from UpNote categories
- ✅ Fix attachment links (images, files)
- ✅ Handle URL-encoded filenames
- ✅ Code fence awareness (doesn't rewrite links in code blocks)
- ✅ Comprehensive error reporting

### Obsidian-Specific Features 🆕
- **Wikilink Support**: Convert between wikilink `[[Note]]` and markdown `[Note](note.md)` formats
- **Tag Conversion**: Convert UpNote categories to Obsidian tags in frontmatter
- **Progress Indicators**: Visual progress bar for large migrations
- **Extensive Testing**: Unit tests included

### Recent Improvements
- Dry-run mode with JSON/Markdown reporting
- Report redaction for safe sharing
- Deterministic processing order
- Validation checks before processing
- Logging controls and optional log file output
- GitHub Actions CI for tests

### Requirements

```bash
pip install -r requirements.txt
```

**Dependencies**:
- `python-frontmatter` - Parse YAML frontmatter
- `tqdm` - Progress bars

**Optional dev dependencies**:
- `pytest` and `pytest-cov` - Testing/coverage (optional, for development)

## Quick Start

### Basic Usage
```bash
# 1. Export all notes from UpNote to a folder (Markdown + additional data recommended)
# 2. Navigate to the export folder
cd /path/to/upnote/export

# 3. Run the migration
python UpNote_Reorganizer.py
```

This will create a `Notes/` directory with your reorganized notes.

### Dry Run (Recommended First)
```bash
# Preview changes without writing files
python UpNote_Reorganizer.py --dry-run --report migration-report.json
```

## Options

### Basic Options
```bash
--source-dir PATH         # Source directory with UpNote export (default: current directory)
--base-dir PATH           # Output base directory (default: Notes)
--attachments-dir NAME    # Subdirectory for attachments (e.g., _attachments)
--keep-frontmatter        # Keep UpNote frontmatter in output
--dry-run                 # Don't write files, only report changes
--skip-attachments        # Don't copy attachments (links still rewritten)
--fail-on-missing         # Exit with error if attachments missing
```

### Reporting Options
```bash
--report PATH             # Report file path (default: migration-report.json)
--report-format FORMAT    # Report format: json or md (default: json)
--report-redact           # Redact titles/attachments in report (for sharing)
```

### Obsidian Features 🆕
```bash
--wikilink-mode MODE      # Handle wikilinks: preserve, to-wikilink, or to-markdown
--convert-tags            # Convert categories to Obsidian tags in frontmatter
--tag-prefix PREFIX       # Prefix for converted tags (e.g., "upnote/")
--no-progress             # Disable progress bar
```

### Logging & Validation 🆕
```bash
--verbose, -v             # Increase verbosity (-v for INFO, -vv for DEBUG)
--quiet, -q               # Quiet mode (only show errors)
--log-file PATH           # Write detailed logs to file (always DEBUG level)
--validate-only           # Validate setup and exit (don't process files)
```

## Examples

### Basic Migration
```bash
python UpNote_Reorganizer.py
```

### Obsidian-Optimized Migration
```bash
python UpNote_Reorganizer.py \
  --attachments-dir _attachments \
  --wikilink-mode preserve \
  --convert-tags \
  --tag-prefix "upnote/"
```

This will:
- Place attachments in `_attachments/` subdirectories
- Keep existing wikilinks unchanged
- Convert UpNote categories to tags like `upnote/work`, `upnote/projects`

### Convert Wikilinks to Markdown
```bash
python UpNote_Reorganizer.py --wikilink-mode to-markdown
```

Converts `[[Note]]` → `[Note](Note.md)`

### Convert Markdown Links to Wikilinks
```bash
python UpNote_Reorganizer.py --wikilink-mode to-wikilink
```

Converts `[Note](note.md)` → `[[note]]`

### Dry Run with Full Report
```bash
python UpNote_Reorganizer.py \
  --dry-run \
  --report migration-report.json \
  --report-format json
```

### Production Migration
```bash
python UpNote_Reorganizer.py \
  --attachments-dir _attachments \
  --convert-tags \
  --fail-on-missing
```

### Validate Setup Before Processing
```bash
python UpNote_Reorganizer.py --validate-only
```

### Debug Mode with Logging
```bash
python UpNote_Reorganizer.py \
  -vv \
  --log-file migration.log
```

### Quiet Mode (for Scripts)
```bash
python UpNote_Reorganizer.py --quiet
```

## Wikilink Modes Explained

### `preserve` (default)
Leaves all links unchanged. Use this if you want to keep your notes exactly as they were in UpNote.

### `to-markdown`
Converts wikilinks to standard markdown links:
- `[[Note]]` → `[Note](Note.md)`
- `[[Note|Alias]]` → `[Alias](Note.md)`

Use this if you prefer standard markdown linking or plan to use the notes outside Obsidian.

### `to-wikilink`
Converts markdown links to wikilinks:
- `[Note](note.md)` → `[[note]]`
- `[Alias](note.md)` → `[[note|Alias]]`

Use this if you prefer Obsidian's wikilink format for internal links.

## Tag Conversion

When using `--convert-tags`, UpNote categories are converted to Obsidian tags:

**Example**:
- Category: `Work/Projects/Active`
- Tags: `work`, `projects`, `active`
- With `--tag-prefix "upnote/"`: `upnote/work`, `upnote/projects`, `upnote/active`

Tags are:
- Converted to lowercase
- Spaces replaced with hyphens
- Added to frontmatter `tags:` field
- Merged with existing tags (no duplicates)

Note: `--convert-tags` automatically enables frontmatter output even if `--keep-frontmatter` is not set.

## Logging Levels

### Default (WARNING)
Shows only important warnings and errors:
```bash
python UpNote_Reorganizer.py
```

### Verbose (-v, INFO)
Shows progress and key operations:
```bash
python UpNote_Reorganizer.py -v
```
Output: "Processing note X", "Found N files", etc.

### Debug (-vv, DEBUG)
Shows detailed internal operations:
```bash
python UpNote_Reorganizer.py -vv
```
Output: Destinations, attachments extracted, tag conversions, etc.

### Quiet (-q, ERROR)
Shows only errors:
```bash
python UpNote_Reorganizer.py -q
```
Perfect for automated scripts where you only care about failures.

### Log to File
Always logs at DEBUG level to file:
```bash
python UpNote_Reorganizer.py --log-file migration.log
```
Console shows WARNING, file gets DEBUG details.

## Validation

### Pre-flight Checks
Before processing, the tool validates:
- ✅ Source directory exists and is readable
- ✅ Source contains .md files
- ✅ Output directory is writable
- ⚠️ Warns if Files/ directory missing

### Validate-Only Mode
Check setup without processing:
```bash
python UpNote_Reorganizer.py --validate-only
```

Example output:
```
2026-02-13 17:00:53 - INFO - Running pre-flight validation...
2026-02-13 17:00:53 - WARNING - Files/ directory not found
2026-02-13 17:00:53 - INFO - Pre-flight validation passed
```

## Troubleshooting

### Missing Attachments
If you see "Missing attachment" warnings:
1. Ensure you exported with "additional data" option in UpNote
2. Check that the `Files/` directory exists in your export
3. Use `--fail-on-missing` to treat missing attachments as errors

### Progress Bar Not Showing
Progress bar requires:
- TTY environment (doesn't show in pipes or redirects)
- tqdm installed (`pip install tqdm`)
- Not disabled with `--no-progress`

### Special Characters in Filenames
The tool automatically handles:
- Spaces in filenames
- URL-encoded characters (`%20`, etc.)
- Parentheses and brackets
- Wraps problematic paths in angle brackets

### Notes in Multiple Notebooks
If a note exists in multiple UpNote notebooks:
- Default behavior: Creates a copy in each destination folder
- This is by design to preserve all category associations

## Development

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=UpNote_Reorganizer --cov-report=html

# Run specific test file
pytest tests/test_wikilinks.py -v
```

### Test Coverage
- 79 passing tests
- 70% code coverage
- Tests include unit, integration, and feature-specific tests

### Code Quality
- Type hints on all functions
- Comprehensive docstrings
- Modular design with focused functions
- Backwards compatible with original version

## License
MIT

## Privacy
- Export folders, output notes, and reports can contain personal data.
- `.gitignore` excludes common export/output paths by default.
- Use `--report-redact` if you need to share a report publicly.

## Credits

- Original: [Adams141's UpNoteReorganizer](https://github.com/adams141/UpNote_Reorganizer)
- Enhanced by: Community contributions
- Testing & Type Safety: Claude Code enhancements
