# Site Cloner MCP Server

This is an MCP (Model Context Protocol) server designed to help LLMs (like Claude) clone websites by providing tools to fetch, analyze, and download website assets.

## Features

- Fetch HTML content from any URL
- Extract assets (CSS, JavaScript, images, fonts, etc.) from HTML content
- Download individual assets to a local directory
- Parse CSS files to extract linked assets (fonts, images)
- Create a sitemap of a website
- Analyze page structure and layout

## Requirements

- Docker installed on your system

## Usage

### Running with Docker

1. Build the Docker image:
   ```bash
   docker build -t site-cloner-mcp .
   ```

2. Run the container:
   ```bash
   docker run -i --rm site-cloner-mcp
   ```

For persistent storage of downloaded files, you can mount a volume:
```bash
docker run -i --rm -v $(pwd)/downloaded_sites:/app/downloaded_site site-cloner-mcp
```

### Connecting to Cursor

To set up this MCP server in Cursor, you have two options:

#### 1. Project-specific configuration

Create a `.cursor/mcp.json` file in your project root with the following content:

```json
{
  "mcpServers": {
    "site-cloner": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "site-cloner-mcp"
      ]
    }
  }
}
```

#### 2. Global configuration

To make the MCP server available globally in Cursor, add the following configuration by going to `Cursor Settings` → `MCP` → `Add new Global MCP Server`:

```json
{
  "mcpServers": {
    "site-cloner": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "site-cloner-mcp"
      ]
    }
  }
}
```

## Available Tools

### 1. fetch_page

Fetches the HTML content of a webpage.

```
Args:
    url: The URL of the webpage to fetch
```

### 2. extract_assets

Extracts links to assets from HTML content.

```
Args:
    url: The URL of the webpage (used for resolving relative URLs)
    html_content: The HTML content to parse
```

### 3. download_asset

Downloads an asset from a URL and saves it to the specified directory.

```
Args:
    url: The URL of the asset to download
    output_dir: The directory to save the asset to (default: downloaded_site)
```

### 4. parse_css_for_assets

Parses CSS content to extract URLs of referenced assets like fonts and images.

```
Args:
    css_url: The URL of the CSS file (used for resolving relative URLs)
    css_content: The CSS content to parse (if None, it will be fetched from css_url)
```

### 5. create_site_map

Creates a sitemap of the website starting from the given URL.

```
Args:
    url: The starting URL to crawl
    max_depth: Maximum depth to crawl (default: 1)
```

### 6. analyze_page_structure

Analyzes the structure of an HTML page and extracts key components.

```
Args:
    html_content: The HTML content to analyze
```

## Example Usage with Claude

1. Ask Claude to clone a website: "Please clone the website at example.com"
2. Claude will use the available tools to:
   - Fetch the HTML content
   - Extract assets
   - Download necessary files
   - Analyze the structure
   - Create a local copy of the site

## Troubleshooting

### Server not showing up in Cursor

1. Restart Cursor
2. Check your configuration file syntax
3. Make sure Docker is installed and running correctly: `docker --version`
4. Look at Cursor's MCP logs for errors:
   - `Output` → Select `Cursor MCP` from Dropdown
5. Try running the server manually to see any errors:
   ```bash
   docker run -i --rm site-cloner-mcp
   ```

### Module Not Found Error

If you encounter a "ModuleNotFoundError: No module named 'site_cloner'" error:

1. Check that your package name in pyproject.toml is correct
2. Make sure the import statements in your Python files don't include "src." prefix
3. Rebuild the Docker image after making changes:
   ```bash
   docker build --no-cache -t site-cloner-mcp .
   ```

### Checking Docker Logs

To check Docker logs for any errors:
```bash
docker logs $(docker ps -q --filter ancestor=site-cloner-mcp)
```

## Notes

- The server automatically organizes downloaded assets into subdirectories based on content type (html, css, js, images, fonts, videos, other)
- When cloning a site, be mindful of copyright and terms of service restrictions
- Some websites may block automated requests, in which case you might need to adjust the user agent string in the code
