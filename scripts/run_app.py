#!/usr/bin/env python
"""Run the Chiron Streamlit app."""

import subprocess
import sys
from pathlib import Path

# Get project root
project_root = Path(__file__).parent.parent

if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app/main.py"],
        cwd=project_root,
    )
