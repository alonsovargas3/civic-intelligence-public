"""Guard: every story the frontend fetches must be baked by the static exporter.

The static build's exporter (scripts/export_static.py) hardcodes STORY_SLUGS.
If someone adds a story getter to frontend/src/api.js but forgets to add its slug
to STORY_SLUGS, that story would 404 ONLY in the static build — invisible to the
live app and to every other test. This test fails the moment those two drift apart.

(A superset the other way is fine: the exporter may bake slugs the frontend never
fetches — harmless, gitignored, never requested. So we only assert frontend ⊆ exporter.)
"""
import re
from pathlib import Path

from scripts.export_static import STORY_SLUGS

ROOT = Path(__file__).resolve().parent.parent
API_JS = ROOT / "frontend" / "src" / "api.js"


def _frontend_story_slugs() -> set[str]:
    return set(re.findall(r"/v1/stories/([a-z0-9-]+)", API_JS.read_text()))


def test_every_frontend_story_is_baked():
    frontend = _frontend_story_slugs()
    assert frontend, "no /v1/stories/<slug> found in api.js — regex or file path is wrong"
    missing = frontend - set(STORY_SLUGS)
    assert not missing, (
        f"api.js fetches stories the exporter does not bake (static-only 404): "
        f"{sorted(missing)}. Add them to STORY_SLUGS in scripts/export_static.py."
    )
