"""Per-file TCAD export layout dictionaries (generated from the Legacy-8.0.32 XLSX)."""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def load_layout(name: str) -> dict:
    """Load a layout JSON by base name, e.g. load_layout('property')."""
    return json.loads((_DIR / f"{name}.json").read_text())
