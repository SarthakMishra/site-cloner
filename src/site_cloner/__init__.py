"""
Site Cloner - MCP server for cloning websites.

A tool to fetch, analyze, and download website assets
via the Model Context Protocol (MCP).
"""

__version__ = "0.1.0"

# Don't import everything from main to avoid circular imports
# Just list the exports in __all__ without importing

__all__ = [
    "analyze_page_structure",
    "create_site_map",
    "download_asset",
    "extract_assets",
    "fetch_page",
    "main",
    "parse_css_for_assets",
]
