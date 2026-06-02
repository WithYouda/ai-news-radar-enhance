from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_index_loads_config_before_app():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "./assets/config.js" in html
    assert html.index("./assets/config.js") < html.index("./assets/app.js")


def test_app_contains_backend_client_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "apiFetch" in js
    assert "window.AI_NEWS_RADAR_CONFIG" in js
    assert "credentials: \"include\"" in js
