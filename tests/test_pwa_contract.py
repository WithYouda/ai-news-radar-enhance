import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_exists_and_names_app():
    manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == "AI News Radar"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"


def test_index_links_manifest_and_service_worker():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "serviceWorker.register" in html
