import json

import httpx
from fastapi.testclient import TestClient

from server.ai_radar_api.article_reader import extract_article_from_html, store_article
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


def test_extract_article_filters_signup_noise_and_marks_restricted_access():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <h1>Important AI Platform Change</h1>
              <p>Sign up for our daily newsletter to continue reading premium updates.</p>
              <p>Log in or create an account to save this story.</p>
              <p>The company released a major platform update with new agent controls, pricing changes, and API behavior that developers need to understand before they migrate production workloads.</p>
              <p>Subscribe to continue reading this members-only analysis.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/platform-change",
        fallback_title="Important AI Platform Change",
    )

    assert "Sign up for our daily newsletter" not in payload["text"]
    assert "Log in or create an account" not in payload["text"]
    assert "major platform update" in payload["text"]
    assert payload["access_status"] == "restricted"
    assert payload["access_label"] == "可能需要登录/订阅"
    assert payload["language"] == "en"
    assert payload["translation_available"] is True


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


def test_read_article_endpoint_returns_cached_fallback_when_origin_blocks_fetch(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    calls = 0

    class Response:
        url = "https://example.com/posts/model-launch"
        text = ""
        status_code = 403

        def raise_for_status(self):
            raise httpx.HTTPStatusError("blocked", request=None, response=self)

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
    assert first.json()["access_status"] == "restricted"
    assert "原站限制" in first.json()["access_label"]
    assert second.status_code == 200
    assert second.json()["cache_status"] == "hit"
    assert calls == 1


def test_ask_item_scope_sends_cached_clean_article_text_to_ai(monkeypatch, tmp_path):
    captured = {}
    config, item = _config(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")
    client.post("/api/auth/login", json={"password": "pass"})
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": "Clean cached article",
            "site_name": "Example AI",
            "byline": "",
            "published_at": "",
            "excerpt": "Clean article excerpt",
            "text": "Clean article body explains the first question context in detail.",
            "content_html": "<p>Clean article body explains the first question context in detail.</p>",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )

    def fake_load_latest_items_with_source(config, mode="ai"):
        return ([item], "local")

    async def fake_answer_question(config, question, items, conversation_messages=None, system_prompt=None):
        captured["item"] = items[0]
        return {"answer": "ok", "title": "正文上下文", "citations": [], "model": config.ai_model}

    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items_with_source", fake_load_latest_items_with_source)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    res = client.post("/api/ask", json={"question": "这篇文章说了什么？", "scope": "today", "item_id": identity})

    assert res.status_code == 200
    assert captured["item"]["article_text"] == "Clean article body explains the first question context in detail."
