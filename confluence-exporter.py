#!/usr/bin/env python3
"""
Confluence Space Exporter
Exports a Confluence space to Markdown files with:
- Page hierarchy preserved as folder structure
- All attachments downloaded (including draw.io diagrams)
- HTML converted to Markdown
- Image links updated to local paths
"""

import os
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

try:
    from atlassian import Confluence
except ImportError:
    print("Installing atlassian-python-api...")
    os.system("pip install atlassian-python-api --break-system-packages -q")
    from atlassian import Confluence

try:
    import markdownify
except ImportError:
    print("Installing markdownify...")
    os.system("pip install markdownify --break-system-packages -q")
    import markdownify

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests --break-system-packages -q")
    import requests


def sanitize_filename(name: str) -> str:
    """Convert a page title to a safe filename."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    # Collapse multiple underscores/spaces
    name = re.sub(r'[\s_]+', '_', name)
    # Remove leading/trailing underscores and spaces
    name = name.strip('_ ')
    # Limit length
    if len(name) > 100:
        name = name[:100]
    return name


class ConfluenceExporter:
    def __init__(self, url: str, username: str, api_token: str, space_key: str, output_dir: str, since_date: datetime = None):
        self.confluence = Confluence(
            url=url,
            username=username,
            password=api_token,
            cloud=True
        )
        self.space_key = space_key
        self.output_dir = Path(output_dir)
        self.pages_by_id = {}
        self.page_paths = {}  # Maps page ID to its folder path
        self.since_date = since_date
        
    def fetch_all_pages(self) -> list:
        """Fetch all pages from the space with their content."""
        print(f"Fetching pages from space '{self.space_key}'...")

        all_pages = []
        start = 0
        limit = 50

        while True:
            pages = self.confluence.get_all_pages_from_space(
                self.space_key,
                start=start,
                limit=limit,
                expand='body.storage,ancestors,children.page,metadata.labels,version'
            )

            if not pages:
                break

            all_pages.extend(pages)
            print(f"  Fetched {len(all_pages)} pages...")

            if len(pages) < limit:
                break
            start += limit

        # Index pages by ID
        for page in all_pages:
            self.pages_by_id[page['id']] = page

        # Filter by date if specified
        if self.since_date:
            filtered_pages = []
            for page in all_pages:
                modified_str = page.get('version', {}).get('when', '')
                if modified_str:
                    # Parse ISO format: 2024-01-02T13:25:33.000Z
                    try:
                        modified_date = datetime.fromisoformat(modified_str.replace('Z', '+00:00'))
                        since_aware = self.since_date.replace(tzinfo=modified_date.tzinfo)
                        if modified_date >= since_aware:
                            filtered_pages.append(page)
                    except ValueError:
                        # If date parsing fails, include the page
                        filtered_pages.append(page)
                else:
                    filtered_pages.append(page)

            print(f"Pages modified since {self.since_date.date()}: {len(filtered_pages)} of {len(all_pages)}")
            return filtered_pages

        print(f"Total pages found: {len(all_pages)}")
        return all_pages
    
    def build_hierarchy(self, pages: list) -> dict:
        """Build a tree structure of pages based on parent-child relationships."""
        # Build set of page IDs in the current export set
        export_page_ids = {page['id'] for page in pages}

        # Find root pages (no ancestors in this space)
        roots = []
        children_map = {}  # parent_id -> list of child pages

        for page in pages:
            ancestors = page.get('ancestors', [])
            if not ancestors:
                roots.append(page)
            else:
                # Find the immediate parent (last ancestor)
                parent_id = ancestors[-1]['id']
                # If parent is not in the export set, treat as root
                if parent_id not in export_page_ids:
                    roots.append(page)
                else:
                    if parent_id not in children_map:
                        children_map[parent_id] = []
                    children_map[parent_id].append(page)

        return {'roots': roots, 'children_map': children_map}
    
    def determine_page_paths(self, hierarchy: dict):
        """Calculate the folder path for each page based on hierarchy."""
        def process_page(page, parent_path: Path):
            page_id = page['id']
            page_name = sanitize_filename(page['title'])
            page_path = parent_path / page_name
            self.page_paths[page_id] = page_path
            
            # Process children
            children = hierarchy['children_map'].get(page_id, [])
            for child in children:
                process_page(child, page_path)
        
        # Process all root pages
        for root_page in hierarchy['roots']:
            process_page(root_page, self.output_dir)
    
    def download_attachments(self, page_id: str, page_path: Path) -> dict:
        """Download all attachments for a page. Returns mapping of original URLs to local paths."""
        attachments_dir = page_path / 'attachments'
        url_mapping = {}
        
        try:
            attachments = self.confluence.get_attachments_from_content(page_id)
            results = attachments.get('results', [])
            
            if not results:
                return url_mapping
                
            attachments_dir.mkdir(parents=True, exist_ok=True)
            
            for attachment in results:
                filename = attachment['title']
                download_url = attachment['_links']['download']
                
                # Make full URL
                if download_url.startswith('/'):
                    full_url = self.confluence.url + download_url
                else:
                    full_url = download_url
                
                local_path = attachments_dir / sanitize_filename(filename)
                
                try:
                    # Download the file
                    response = self.confluence._session.get(full_url)
                    response.raise_for_status()
                    
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Store mapping for URL replacement
                    # Confluence uses various URL patterns for attachments
                    url_mapping[filename] = f"attachments/{sanitize_filename(filename)}"
                    url_mapping[download_url] = f"attachments/{sanitize_filename(filename)}"
                    
                    print(f"    Downloaded: {filename}")
                    
                except Exception as e:
                    print(f"    Warning: Failed to download {filename}: {e}")
                    
        except Exception as e:
            print(f"    Warning: Could not fetch attachments: {e}")
            
        return url_mapping
    
    def convert_to_markdown(self, html_content: str, url_mapping: dict) -> str:
        """Convert HTML content to Markdown and update attachment links."""
        
        # Custom markdownify options
        md_content = markdownify.markdownify(
            html_content,
            heading_style="ATX",
            bullets="-",
            strip=['script', 'style']
        )
        
        # Replace attachment URLs with local paths
        for original, local in url_mapping.items():
            md_content = md_content.replace(original, local)
        
        # Clean up excessive newlines
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
        
        return md_content
    
    def handle_drawio_embeds(self, html_content: str) -> str:
        """
        Handle embedded draw.io diagrams.
        Draw.io in Confluence often uses ac:structured-macro with specific attributes.
        """
        # Draw.io embeds are typically referenced via attachment, which we already download
        # But we can add a note in the markdown where they appear

        # Pattern for draw.io macros
        drawio_pattern = r'<ac:structured-macro[^>]*ac:name="drawio"[^>]*>.*?</ac:structured-macro>'

        def replace_drawio(_match):
            return '\n\n> 📊 **Draw.io Diagram** - See attachments folder for `.drawio` file\n\n'

        html_content = re.sub(drawio_pattern, replace_drawio, html_content, flags=re.DOTALL)

        return html_content
    
    def export_page(self, page: dict):
        """Export a single page to markdown with its attachments."""
        page_id = page['id']
        page_title = page['title']
        page_path = self.page_paths[page_id]
        
        print(f"Exporting: {page_title}")
        
        # Create directory
        page_path.mkdir(parents=True, exist_ok=True)
        
        # Download attachments first
        url_mapping = self.download_attachments(page_id, page_path)
        
        # Get HTML content
        html_content = page.get('body', {}).get('storage', {}).get('value', '')

        # Handle draw.io embeds
        html_content = self.handle_drawio_embeds(html_content)
        
        # Convert to markdown
        md_content = self.convert_to_markdown(html_content, url_mapping)
        
        # Add page title as H1
        md_content = f"# {page_title}\n\n{md_content}"
        
        # Add metadata header
        labels = page.get('metadata', {}).get('labels', {}).get('results', [])
        if labels:
            label_names = [label['name'] for label in labels]
            md_content = f"---\nlabels: {', '.join(label_names)}\n---\n\n{md_content}"
        
        # Write markdown file
        md_file = page_path / 'index.md'
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
    
    def export_space(self):
        """Main export function."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Fetch all pages
        pages = self.fetch_all_pages()
        
        if not pages:
            print("No pages found in space!")
            return
        
        # Build hierarchy
        hierarchy = self.build_hierarchy(pages)
        print(f"Found {len(hierarchy['roots'])} root pages")
        
        # Determine paths
        self.determine_page_paths(hierarchy)
        
        # Export each page
        for page in pages:
            self.export_page(page)
        
        print(f"\n✅ Export complete! Files saved to: {self.output_dir.absolute()}")
        
        # Create a simple index/TOC
        self.create_index(pages, hierarchy)
    
    def create_index(self, pages: list, hierarchy: dict):
        """Create an index.md file with links to all pages."""
        index_content = f"# {self.space_key} Space Export\n\n"
        index_content += f"Exported {len(pages)} pages.\n\n"
        index_content += "## Page Structure\n\n"
        
        def add_page_to_index(page, level=0):
            nonlocal index_content
            indent = "  " * level
            page_path = self.page_paths[page['id']]
            relative_path = page_path.relative_to(self.output_dir)
            index_content += f"{indent}- [{page['title']}]({relative_path}/index.md)\n"
            
            # Add children
            children = hierarchy['children_map'].get(page['id'], [])
            for child in sorted(children, key=lambda p: p['title']):
                add_page_to_index(child, level + 1)
        
        for root in sorted(hierarchy['roots'], key=lambda p: p['title']):
            add_page_to_index(root)
        
        index_file = self.output_dir / 'INDEX.md'
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        print(f"Created index at: {index_file}")


def main():
    parser = argparse.ArgumentParser(description='Export Confluence space to Markdown')
    parser.add_argument('--url', default='https://centrica-bs.atlassian.net',
                        help='Confluence site URL')
    parser.add_argument('--space', default='ISDops',
                        help='Space key to export')
    parser.add_argument('--username', required=True,
                        help='Your Atlassian email/username')
    parser.add_argument('--token', required=True,
                        help='Atlassian API token')
    parser.add_argument('--output', default='./confluence_export',
                        help='Output directory')
    parser.add_argument('--since', type=str, default=None,
                        help='Only export pages modified since this date (format: YYYY-MM-DD)')

    args = parser.parse_args()

    # Parse since date if provided
    since_date = None
    if args.since:
        try:
            since_date = datetime.strptime(args.since, '%Y-%m-%d')
            print(f"Filtering pages modified since: {since_date.date()}")
        except ValueError:
            print(f"Error: Invalid date format '{args.since}'. Use YYYY-MM-DD (e.g., 2024-01-15)")
            sys.exit(1)

    exporter = ConfluenceExporter(
        url=args.url,
        username=args.username,
        api_token=args.token,
        space_key=args.space,
        output_dir=args.output,
        since_date=since_date
    )

    exporter.export_space()


if __name__ == '__main__':
    main()