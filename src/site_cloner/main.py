"""
Site Cloner MCP Server - An MCP server for cloning websites.

This module provides a set of tools to fetch, analyze, and download website assets,
including HTML content, CSS, JavaScript, images, fonts, and more. It's designed to
be used with Claude or other LLMs via the Model Context Protocol (MCP).
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("site-cloner")

# Constants
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}


# Helper functions
async def fetch_url(
    url: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Fetch content from a URL with proper error handling."""
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # No try/except here - let exceptions propagate to callers
        response = await client.get(url, headers=request_headers, timeout=30.0)
        response.raise_for_status()
        return response


def get_base_url(url: str) -> str:
    """Extract the base URL from a full URL."""
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_absolute_url(url: str) -> bool:
    """Check if a URL is absolute."""
    return bool(urllib.parse.urlparse(url).netloc)


def normalize_url(base_url: str, url: str) -> str:
    """Convert relative URLs to absolute URLs."""
    if is_absolute_url(url):
        return url
    return urllib.parse.urljoin(base_url, url)


# MCP tools
@mcp.tool()
async def fetch_page(url: str) -> dict[str, Any]:
    """Fetch the HTML content of a webpage.

    Args:
        url: The URL of the webpage to fetch
    """
    try:
        response = await fetch_url(url)
        html_content = response.text

        return {
            "content": html_content,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "url": str(response.url),
        }
    except Exception as e:  # noqa: BLE001
        # Broad exception is justified as we're returning error information to users
        return {
            "error": str(e),
            "content": None,
            "status_code": None,
            "headers": None,
            "url": url,
        }


@mcp.tool()
async def extract_assets(url: str, html_content: str) -> dict[str, list[str]]:
    """Extract links to assets from HTML content.

    Args:
        url: The URL of the webpage (used for resolving relative URLs)
        html_content: The HTML content to parse
    """
    base_url = get_base_url(url)
    soup = BeautifulSoup(html_content, "html.parser")

    # Initialize asset containers
    assets = {
        "css": [],
        "javascript": [],
        "images": [],
        "fonts": [],
        "videos": [],
        "other": [],
    }

    # Extract CSS links
    for link in soup.find_all("link", rel="stylesheet"):
        if "href" in link.attrs:
            css_url = normalize_url(base_url, link["href"])
            assets["css"].append(css_url)

    # Extract JavaScript
    for script in soup.find_all("script"):
        if "src" in script.attrs:
            js_url = normalize_url(base_url, script["src"])
            assets["javascript"].append(js_url)

    # Extract images
    for img in soup.find_all("img"):
        if "src" in img.attrs:
            img_url = normalize_url(base_url, img["src"])
            assets["images"].append(img_url)
        # Also check srcset attribute
        if "srcset" in img.attrs:
            srcset = img["srcset"]
            for src_item in srcset.split(","):
                src_parts = src_item.strip().split(" ")
                if len(src_parts) >= 1:
                    img_url = normalize_url(base_url, src_parts[0].strip())
                    assets["images"].append(img_url)

    # Extract background images from inline styles
    for tag in soup.find_all(style=True):
        style = tag["style"]
        style_urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', style)
        for style_url in style_urls:
            full_url = normalize_url(base_url, style_url)
            assets["images"].append(full_url)

    # Extract fonts (typically in CSS, but sometimes directly linked)
    for link in soup.find_all("link", rel="preload"):
        if "href" in link.attrs and "as" in link.attrs and link["as"] == "font":
            font_url = normalize_url(base_url, link["href"])
            assets["fonts"].append(font_url)

    # Extract videos
    for video in soup.find_all("video"):
        for source in video.find_all("source"):
            if "src" in source.attrs:
                video_url = normalize_url(base_url, source["src"])
                assets["videos"].append(video_url)

    # Extract iframes
    for iframe in soup.find_all("iframe"):
        if "src" in iframe.attrs:
            iframe_url = normalize_url(base_url, iframe["src"])
            assets["other"].append(iframe_url)

    return assets


@mcp.tool()
async def download_asset(
    url: str,
    output_dir: str = "downloaded_site",
) -> dict[str, Any]:
    """Download an asset from a URL and save it to the specified directory.

    Args:
        url: The URL of the asset to download
        output_dir: The directory to save the asset to (default: downloaded_site)
    """
    try:
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Determine the filename
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path

        if not path or path.endswith("/"):
            # Handle URLs without a path or ending with /
            filename = "index.html"
        else:
            filename = Path(path).name
            if not filename:
                filename = "unknown_file"

            # Handle query parameters in URLs
            if parsed_url.query:
                # Remove invalid characters for filenames
                safe_query = re.sub(r"[^\w\-\.]", "_", parsed_url.query)
                filename = f"{filename}_{safe_query}"

        # Create subdirectories based on content type
        response = await fetch_url(url)
        content_type = response.headers.get("content-type", "").split(";")[0]

        if "text/html" in content_type:
            subdir = "html"
        elif "text/css" in content_type:
            subdir = "css"
        elif "javascript" in content_type:
            subdir = "js"
        elif "image/" in content_type:
            subdir = "images"
        elif "font/" in content_type or "application/font" in content_type:
            subdir = "fonts"
        elif "video/" in content_type:
            subdir = "videos"
        else:
            subdir = "other"

        # Create the subdirectory
        subdir_path = output_path / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)

        # Save the file
        file_path = subdir_path / filename

        # Check for potential duplicates by adding a counter if needed
        counter = 1
        original_file_path = file_path
        while file_path.exists():
            file_path = subdir_path / f"{original_file_path.stem}_{counter}{original_file_path.suffix}"
            counter += 1

        # Write the content
        # Using synchronous file operation as we already have the content in memory
        file_path.write_bytes(response.content)

        return {
            "success": True,
            "url": url,
            "saved_to": str(file_path),
            "content_type": content_type,
            "size": len(response.content),
        }
    except Exception as e:  # noqa: BLE001
        # Broad exception is justified as we're returning error information to users
        return {"success": False, "url": url, "error": str(e)}


@mcp.tool()
async def parse_css_for_assets(
    css_url: str,
    css_content: str | None = None,
) -> dict[str, list[str]]:
    """Parse CSS content to extract URLs of referenced assets like fonts and images.

    Args:
        css_url: The URL of the CSS file (used for resolving relative URLs)
        css_content: The CSS content to parse (if None, it will be fetched from css_url)
    """
    base_url = get_base_url(css_url)

    if css_content is None:
        try:
            response = await fetch_url(css_url)
            css_content = response.text
        except Exception as e:  # noqa: BLE001
            # Broad exception is justified as we're returning error information to users
            return {"error": str(e), "fonts": [], "images": []}

    # Extract URLs from the CSS
    fonts = []
    images = []

    # Find all url() patterns
    url_patterns = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', css_content)

    for url in url_patterns:
        full_url = normalize_url(base_url, url)

        # Try to determine if it's a font or image
        if any(ext in full_url.lower() for ext in [".woff", ".woff2", ".ttf", ".eot", ".otf"]):
            fonts.append(full_url)
        elif any(ext in full_url.lower() for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]):
            images.append(full_url)
        else:
            # If we can't determine the type, add it to both lists
            images.append(full_url)

    # Find @font-face rules and extract src URLs
    font_face_blocks = re.findall(r"@font-face\s*{[^}]+}", css_content)
    for block in font_face_blocks:
        urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', block)
        for url in urls:
            full_url = normalize_url(base_url, url)
            fonts.append(full_url)

    return {
        "fonts": list(set(fonts)),  # Remove duplicates
        "images": list(set(images)),  # Remove duplicates
    }


@mcp.tool()
async def create_site_map(url: str, max_depth: int = 1) -> dict[str, Any]:
    """Create a sitemap of the website starting from the given URL.

    Args:
        url: The starting URL to crawl
        max_depth: Maximum depth to crawl (default: 1)
    """
    base_url = get_base_url(url)
    visited = set()
    sitemap = []

    async def crawl(current_url: str, depth: int) -> None:
        if depth > max_depth or current_url in visited:
            return

        visited.add(current_url)

        try:
            response = await fetch_url(current_url)
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            page_info = {
                "url": current_url,
                "title": soup.title.text if soup.title else "No title",
                "links": [],
            }

            sitemap.append(page_info)

            if depth < max_depth:
                links = soup.find_all("a", href=True)
                for link in links:
                    href = link["href"]

                    # Skip empty links, anchors, javascript, and mailto
                    if not href or href.startswith(("#", "javascript:", "mailto:")):
                        continue

                    # Normalize URL
                    full_url = normalize_url(base_url, href)

                    # Only crawl URLs from the same domain
                    if get_base_url(full_url) == base_url:
                        page_info["links"].append(
                            {"url": full_url, "text": link.text.strip() or "No text"},
                        )
                        await crawl(full_url, depth + 1)

        except Exception as e:  # noqa: BLE001
            # Broad exception is justified as we're returning error information to users
            sitemap.append({"url": current_url, "error": str(e)})

    await crawl(url, 1)

    return {"base_url": base_url, "pages": len(sitemap), "sitemap": sitemap}


@mcp.tool()
async def analyze_page_structure(html_content: str) -> dict[str, Any]:
    """Analyze the structure of an HTML page and extract key components.

    Args:
        html_content: The HTML content to analyze
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract metadata
    metadata = {}
    for meta in soup.find_all("meta"):
        if "name" in meta.attrs and "content" in meta.attrs:
            metadata[meta["name"]] = meta["content"]
        elif "property" in meta.attrs and "content" in meta.attrs:
            metadata[meta["property"]] = meta["content"]

    # Extract main semantic elements
    semantic_elements = {}
    for element_type in [
        "header",
        "footer",
        "nav",
        "main",
        "aside",
        "section",
        "article",
    ]:
        elements = soup.find_all(element_type)
        if elements:
            semantic_elements[element_type] = len(elements)

    # Extract headings
    headings = {}
    for level in range(1, 7):
        heading_tag = f"h{level}"
        headings[heading_tag] = len(soup.find_all(heading_tag))

    # Find main content area (heuristic)
    main_content = soup.find("main")
    if not main_content:
        # Try to find the largest content area if <main> is not available
        candidates = soup.find_all(["article", "div", "section"])
        if candidates:
            main_content = max(candidates, key=lambda x: len(str(x)))

    # Analyze page layout
    layout_analysis = {
        "has_header": bool(soup.find("header")),
        "has_footer": bool(soup.find("footer")),
        "has_navigation": bool(soup.find("nav")),
        "has_sidebar": bool(soup.find("aside")),
        "has_main_content": bool(main_content),
    }

    return {
        "title": soup.title.text if soup.title else "No title",
        "metadata": metadata,
        "semantic_structure": semantic_elements,
        "headings": headings,
        "layout_analysis": layout_analysis,
        "total_elements": len(soup.find_all()),
        "total_links": len(soup.find_all("a")),
        "total_images": len(soup.find_all("img")),
        "total_forms": len(soup.find_all("form")),
    }


def main() -> None:
    """Run the site-cloner MCP server using stdio transport."""
    # Simply run the FastMCP server with stdio transport
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
