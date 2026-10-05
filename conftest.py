"""Root conftest — ensures the project root is on sys.path so tests can
import atx_ingest and sibling packages without a package install or
PYTHONPATH prefix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
