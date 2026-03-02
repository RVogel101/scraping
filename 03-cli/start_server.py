#!/usr/bin/env python3
"""Start the Armenian Cards API development server."""

import sys
from pathlib import Path

# Add 02-src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / '02-src'))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "armenian_anki.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
