"""Private local process entry point; takes a persisted job, never model commands."""
from pathlib import Path
import sys

from .ffmpeg import LocalRender

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    LocalRender(Path(sys.argv[1]).resolve()).execute()
