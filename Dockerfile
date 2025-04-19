FROM python:3.11-slim

WORKDIR /app

# Copy the entire project for installation
COPY . .

# Install dependencies and the project in development mode
RUN pip install --no-cache-dir --upgrade pip && \
    pip install -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# The entry point should run the MCP server
# Use -c to run code directly instead of -m for module import
ENTRYPOINT ["python", "-c", "from site_cloner.main import main; main()"] 