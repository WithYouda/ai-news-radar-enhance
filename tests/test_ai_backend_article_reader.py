import json

from fastapi.testclient import TestClient

from server.ai_radar_api.article_reader import extract_article_from_html
from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.main import create_app
from server.ai_radar_api.radar_data import item_identity


def _config(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    item = {
        "title": "Original model launch",
        "url": "https://example.com/posts/model-launch?utm_source=noise",
        "site_name": "Example AI",
        "source": "official",
        "published_at": "2026-06-03T04:30:00Z",
    }
    (data_dir / "latest-24h.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
    (data_dir / "latest-24h-all.json").write_text(json.dumps({"items_all": [item]}), encoding="utf-8")
    return AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
        data_dir=data_dir,
        data_cache_dir=tmp_path / "cache",
    ), item


def test_extract_article_from_html_removes_chrome_and_keeps_readable_body():
    payload = extract_article_from_html(
        """
        <html>
          <head>
            <title>Fallback title</title>
            <meta property="og:title" content="Clean Article Title">
            <style>.ad{display:none}</style>
            <script>window.bad = true</script>
          </head>
          <body>
            <nav>site navigation</nav>
            <main>
              <article>
                <h1>Clean Article Title</h1>
                <p>First paragraph with enough detail about the launch and why it matters.</p>
                <p>Second paragraph links to <a href="/docs">technical docs</a> for readers.</p>
                <footer>share buttons</footer>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://example.com/posts/model-launch",
        fallback_title="Original model launch",
    )

    assert payload["title"] == "Clean Article Title"
    assert "First paragraph" in payload["text"]
    assert "Second paragraph" in payload["text"]
    assert "site navigation" not in payload["text"]
    assert "share buttons" not in payload["text"]
    assert "script" not in payload["content_html"]
    assert 'href="https://example.com/docs"' in payload["content_html"]


def test_read_article_endpoint_fetches_known_news_item_and_reuses_cache(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    calls = 0

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Fetched clean title</h1>
          <p>This extracted body is long enough to be treated as article content.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader.httpx.get", fake_get)
    client = TestClient(create_app(config), base_url="https://testserver")
    identity = item_identity(item)

    first = client.get(f"/api/read/{identity}")
    second = client.get(f"/api/read/{identity}")

    assert first.status_code == 200
    assert first.json()["title"] == "Fetched clean title"
    assert first.json()["item"]["title"] == "Original model launch"
    assert first.json()["cache_status"] == "miss"
    assert second.status_code == 200
    assert second.json()["cache_status"] == "hit"
    assert calls == 1


def test_read_article_endpoint_rejects_unknown_item(tmp_path):
    config, _ = _config(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get("/api/read/not-a-known-item")

    assert res.status_code == 404
