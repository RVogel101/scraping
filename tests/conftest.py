"""Pytest configuration and fixtures.

Automatically adds the src directory to Python path so tests can import
from armenian_anki and wa_corpus packages.
"""

import sys
from pathlib import Path

# Add src directory to path for test discovery
project_root = Path(__file__).parent.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
