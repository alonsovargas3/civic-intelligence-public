import json
from pathlib import Path

from scripts.export_static import static_filename

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "static_slug_pairs.json"


def test_static_filename_matches_js_fixture():
    pairs = json.loads(FIXTURE.read_text())
    for pair in pairs:
        # JS staticPath returns "/data/<slug>.json"; Python returns "<slug>.json".
        expected = pair["path"].removeprefix("/data/")
        assert static_filename(pair["url"]) == expected, pair["url"]
