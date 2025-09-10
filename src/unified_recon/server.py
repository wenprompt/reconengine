#!/usr/bin/env python
"""Uvicorn server for the reconciliation API."""

import logging
import os
import uvicorn


def setup_logging():
    """Configure logging for the API server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set specific log levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("src.unified_recon").setLevel(logging.DEBUG)


def main():
    """Run the FastAPI application with uvicorn."""
    setup_logging()

    logger = logging.getLogger(__name__)

    # Get configuration from environment variables with defaults
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "7777"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

    logger.info(f"Starting Trade Reconciliation API server on {host}:{port}...")

    uvicorn.run(
        "src.unified_recon.api.app:app",
        host=host,
        port=port,
        reload=reload,  # Enable hot-reload for development
        log_level="info",
        access_log=True,
        reload_dirs=["src"],  # Only watch src directory for changes
    )


if __name__ == "__main__":
    main()
