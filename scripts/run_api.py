#!/usr/bin/env python
"""Run the Chiron API server."""

import uvicorn

from src.api.config import api_settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=api_settings.host,
        port=api_settings.port,
        reload=api_settings.debug,
    )
