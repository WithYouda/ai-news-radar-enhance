from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_index_loads_config_and_api_client_before_app():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "./assets/config.js" in html
    assert "./assets/api-client.js" in html
    assert html.index("./assets/config.js") < html.index("./assets/app.js")
    assert html.index("./assets/api-client.js") < html.index("./assets/app.js")
    assert html.index("./assets/config.js") < html.index("./assets/api-client.js")


def test_app_contains_backend_client_contract():
    app_js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    api_js = (ROOT / "assets/api-client.js").read_text(encoding="utf-8")

    assert "apiFetch" in api_js
    assert "fetchFreshJson" in api_js
    assert "window.AI_NEWS_RADAR_CONFIG" in api_js
    assert "window.AI_NEWS_RADAR_API" in api_js
    assert "credentials: \"include\"" in api_js
    assert "window.AI_NEWS_RADAR_API" in app_js


def test_app_has_api_client_fallback_for_cached_mobile_html():
    app_js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    assert "createFallbackApiClient" in app_js
    assert "window.AI_NEWS_RADAR_API || createFallbackApiClient()" in app_js


def test_app_keeps_api_base_url_for_sync_reader_controls():
    app_js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    assert app_js.startswith("const appConfig = window.AI_NEWS_RADAR_CONFIG || {};")
    assert "const appConfig = window.AI_NEWS_RADAR_CONFIG || {};" in app_js
    assert "const apiBaseUrl = String(appConfig.apiBaseUrl || \"\").replace" in app_js
    assert "readerBtn.disabled = !apiBaseUrl" in app_js
