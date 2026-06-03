import json

import httpx
from fastapi.testclient import TestClient

from server.ai_radar_api.article_reader import extract_article_from_html, fetch_clean_article, resolve_google_news_url, store_article
from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.db import init_db
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


def test_extract_article_prefers_reader_like_content_over_sidebar_noise():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <section class="sidebar promo">
              <p>Popular links and account prompts can be quite long but should not be mixed into the readable story because they are navigation chrome rather than editorial content.</p>
            </section>
            <div class="story-body">
              <p>The actual article explains a new AI browser workflow with specific details about agents, summaries, retrieval, and product behavior.</p>
              <p>It also describes why developers should care about the implementation and what changed in the release.</p>
            </div>
          </body>
        </html>
        """,
        url="https://example.com/story",
        fallback_title="Reader story",
    )

    assert "actual article explains" in payload["text"]
    assert "Popular links and account prompts" not in payload["text"]


def test_extract_article_stops_before_recommendation_sections():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The actual article explains the product launch, the model behavior, and the API migration details readers need.</p>
              <h2>Recommended for you</h2>
              <p>This unrelated recommendation promotes another story and must not be included in the clean reader body.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/story",
        fallback_title="Reader story",
    )

    assert "actual article explains" in payload["text"]
    assert "unrelated recommendation" not in payload["text"]


def test_extract_article_removes_related_recommended_and_extension_reading_blocks():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <main>
              <article class="article-content">
                <p>The real story explains an AI agent release with concrete product behavior, model constraints, customer impact, and migration details for teams evaluating the update.</p>
                <p>The second real paragraph adds implementation notes and background that belong in the clean reader body.</p>
                <section class="article-content__related">
                  <p>This recommended story is long enough to look like editorial text, but it is not part of the current article and must be removed.</p>
                </section>
                <div class="recommended-list">
                  <p>Recommended reading about another company should not survive extraction.</p>
                </div>
                <div class="extension-reading content">
                  <p>这是一段扩展阅读内容，不应该进入清洗后的正文。</p>
                </div>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://example.com/story",
        fallback_title="Reader story",
    )

    assert "real story explains" in payload["text"]
    assert "second real paragraph" in payload["text"]
    assert "recommended story" not in payload["text"].lower()
    assert "Recommended reading" not in payload["text"]
    assert "扩展阅读内容" not in payload["text"]


def test_resolve_google_news_url_decodes_batchexecute_result(monkeypatch):
    captured = {}

    class Response:
        url = "https://news.google.com/read/article-id"
        text = """
        <html><body>
          <div data-n-a-id="encoded-article" data-n-a-ts="1780492486" data-n-a-sg="signature"></div>
        </body></html>
        """

        def raise_for_status(self):
            return None

    class DecodeResponse:
        text = """)]}'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://publisher.example/story\\"]",null,null,null,"generic"]]"""

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        captured["get_url"] = url
        return Response()

    def fake_post(url, **kwargs):
        captured["post_url"] = url
        captured["post_data"] = kwargs.get("data") or {}
        return DecodeResponse()

    monkeypatch.setattr("server.ai_radar_api.article_reader.httpx.get", fake_get)
    monkeypatch.setattr("server.ai_radar_api.article_reader.httpx.post", fake_post)

    resolved = resolve_google_news_url("https://news.google.com/read/article-id?hl=en-US&gl=US&ceid=US:en")

    assert resolved == "https://publisher.example/story"
    assert captured["get_url"].startswith("https://news.google.com/read/")
    assert "batchexecute" in captured["post_url"]
    assert "encoded-article" in captured["post_data"]["f.req"]
    assert "signature" in captured["post_data"]["f.req"]


def test_fetch_clean_article_resolves_google_news_url_before_extracting(monkeypatch, tmp_path):
    item = {
        "title": "Google News item",
        "url": "https://news.google.com/read/article-id",
        "site_name": "Google News",
    }
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password="pass",
        session_secret="session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )
    init_db(config.db_path)

    class Response:
        url = "https://publisher.example/story"
        text = """
        <html><body><article>
          <h1>Publisher story</h1>
          <p>The publisher article body has enough detail to be extracted after resolving the Google News wrapper.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        assert url == "https://publisher.example/story"
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader.resolve_google_news_url", lambda url, timeout_seconds=6: "https://publisher.example/story")
    monkeypatch.setattr("server.ai_radar_api.article_reader.httpx.get", fake_get)

    payload = fetch_clean_article(config, item)

    assert payload["url"] == "https://news.google.com/read/article-id"
    assert payload["final_url"] == "https://publisher.example/story"
    assert "publisher article body" in payload["text"]


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


def test_read_article_endpoint_retries_cached_unavailable_article(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    app = create_app(config)
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": item["title"],
            "site_name": "Example AI",
            "byline": "",
            "published_at": "",
            "excerpt": "暂时无法清洗原文",
            "text": "暂时无法清洗原文。可打开原文查看。",
            "content_html": "<p>暂时无法清洗原文。</p>",
            "access_status": "unavailable",
            "access_label": "暂时无法清洗原文",
            "language": "zh",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Fresh clean title</h1>
          <p>The retried article body is readable after the stale unavailable cache is bypassed.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader.httpx.get", fake_get)
    client = TestClient(app, base_url="https://testserver")

    res = client.get(f"/api/read/{identity}")

    assert res.status_code == 200
    assert res.json()["access_status"] == "open"
    assert res.json()["cache_status"] == "miss"
    assert "retried article body" in res.json()["text"]
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


def test_ask_item_scope_retries_cached_unavailable_article_text(monkeypatch, tmp_path):
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
            "title": item["title"],
            "site_name": "Example AI",
            "byline": "",
            "published_at": "",
            "excerpt": "暂时无法清洗原文",
            "text": "暂时无法清洗原文。可打开原文查看。",
            "content_html": "<p>暂时无法清洗原文。</p>",
            "access_status": "unavailable",
            "access_label": "暂时无法清洗原文",
            "language": "zh",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )

    class Response:
        url = item["url"]
        text = """
        <html><body><article>
          <p>Fresh article body should replace stale unavailable cache for Ask AI context.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        return Response()

    def fake_load_latest_items_with_source(config, mode="ai"):
        return ([item], "local")

    async def fake_answer_question(config, question, items, conversation_messages=None, system_prompt=None):
        captured["item"] = items[0]
        return {"answer": "ok", "title": "正文上下文", "citations": [], "model": config.ai_model}

    monkeypatch.setattr("server.ai_radar_api.article_reader.httpx.get", fake_get)
    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items_with_source", fake_load_latest_items_with_source)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    res = client.post("/api/ask", json={"question": "这篇文章说了什么？", "scope": "today", "item_id": identity})

    assert res.status_code == 200
    assert captured["item"]["article_text"] == "Fresh article body should replace stale unavailable cache for Ask AI context."
