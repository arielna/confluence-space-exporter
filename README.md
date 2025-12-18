# Confluence to Markdown Exporter

Exports a Confluence space to local Markdown files with folder hierarchy and attachments preserved.

## Features

- ✅ Preserves page hierarchy as nested folders
- ✅ Downloads all attachments (including `.drawio` files)
- ✅ Converts HTML content to Markdown
- ✅ Creates an index file with links to all pages
- ✅ Handles labels/metadata

## Prerequisites

1. **Python 3.7+**
2. **Atlassian API Token** - Create one at:
   https://id.atlassian.com/manage-profile/security/api-tokens

## Installation

```bash
pip install atlassian-python-api markdownify requests
```

(The script will auto-install these if missing)

## Usage

```bash
python confluence_export.py \
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