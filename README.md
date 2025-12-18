# Confluence to Markdown Exporter

Exports a Confluence space to local Markdown files with folder hierarchy and attachments preserved.

## Features

- ✅ Preserves page hierarchy as nested folders
- ✅ Downloads all attachments (including `.drawio` files)
- ✅ Converts HTML content to Markdown
- ✅ Creates an index file with links to all pages
- ✅ Handles labels/metadata
- ✅ Filter by date to export only recently modified pages

## Prerequisites

1. **Python 3.7+**
2. **Atlassian API Token** - Create one at:
   https://id.atlassian.com/manage-profile/security/api-tokens

## Installation

### Option 1: Using Virtual Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/arielna/confluence-space-exporter.git
cd confluence-space-exporter

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Direct Installation

```bash
pip install atlassian-python-api markdownify requests
```

(The script will also auto-install dependencies if missing)

## Usage

```bash
python confluence-exporter.py \
  --username your.email@company.com \
  --token YOUR_API_TOKEN \
  --url https://centrica-bs.atlassian.net \
  --space ISDops \
  --output ./ISDops_backup
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--username` | Your Atlassian email | (required) |
| `--token` | API token from Atlassian | (required) |
| `--url` | Confluence site URL | `https://centrica-bs.atlassian.net` |
| `--space` | Space key to export | `ISDops` |
| `--output` | Output directory | `./confluence_export` |
| `--since` | Only export pages modified since this date (YYYY-MM-DD) | (all pages) |

### Export Only Recent Changes

To export only pages modified after a specific date:

```bash
source venv/bin/activate  # If using virtual environment
python confluence-exporter.py \
  --username your.email@company.com \
  --token YOUR_API_TOKEN \
  --since 2024-06-01
```

This is useful for incremental backups or exporting recent updates only.

## Output Structure

```
confluence_export/
├── INDEX.md                    # Table of contents with links
├── Parent_Page_1/
│   ├── index.md               # Page content
│   ├── attachments/           # Page attachments
│   │   ├── diagram.drawio
│   │   └── image.png
│   └── Child_Page/
│       ├── index.md
│       └── attachments/
└── Parent_Page_2/
    └── index.md
```

## Draw.io Diagrams

Draw.io diagrams are downloaded as `.drawio` files in each page's `attachments/` folder. You can:
- Open them with the draw.io desktop app
- Import them to draw.io online (diagrams.net)
- Keep them as backup alongside your markdown

## Notes

- Page titles are sanitized for filesystem compatibility
- The script handles pagination automatically (works for spaces with 100+ pages)
- Labels are preserved in YAML frontmatter
- Relative links between pages may need manual adjustment after export