import json

import httpx
from fastapi.testclient import TestClient

import server.ai_radar_api.article_reader as article_reader
from server.ai_radar_api.article_reader import extract_article_from_html, fetch_clean_article, resolve_google_news_url, store_article
from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.db import connect_db, init_db
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


def _write_latest_data(config, item):
    (config.data_dir / "latest-24h.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
    (config.data_dir / "latest-24h-all.json").write_text(json.dumps({"items_all": [item]}), encoding="utf-8")


def _store_article_alias(config, alias_id: str, item_id: str, item: dict):
    with connect_db(config.db_path) as conn:
        conn.execute(
            """
            create table if not exists article_cache_aliases (
              alias_id text primary key,
              item_id text not null,
              url text not null,
              title text not null default '',
              site_name text not null default '',
              published_at text not null default '',
              updated_at text not null
            )
            """
        )
        conn.execute(
            """
            insert into article_cache_aliases(alias_id, item_id, url, title, site_name, published_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alias_id,
                item_id,
                item["url"],
                item.get("title", ""),
                item.get("site_name", ""),
                item.get("published_at", ""),
                article_reader._now(),
            ),
        )


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


def test_extract_article_keeps_yahoo_finance_story_after_story_continues(monkeypatch):
    def fake_readability_html(_html):
        return """
        <article>
          <p>Yahoo Finance opens with a short setup about an AI stock rotation and why traders are watching the market reaction.</p>
        </article>
        """

    monkeypatch.setattr(article_reader, "_readability_html", fake_readability_html)

    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <main>
              <article class="caas-body">
                <p>Yahoo Finance opens with a short setup about an AI stock rotation and why traders are watching the market reaction.</p>
                <button type="button">Story Continues</button>
                <p>The continuation explains that chipmakers, cloud providers, and enterprise software firms moved differently after fresh guidance from analysts.</p>
                <p>It also includes concrete context from portfolio managers about margins, capital spending, and whether artificial intelligence demand is still broadening.</p>
                <h2>Recommended Stories</h2>
                <p>This unrelated story should still be cut from the clean article body.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://finance.yahoo.com/news/analysis-stock-market-ai-turns-160954707.html",
        fallback_title="For stock market, AI turns from lifting all boats to sinking ships",
    )

    assert "short setup about an AI stock rotation" in payload["text"]
    assert "continuation explains that chipmakers" in payload["text"]
    assert "portfolio managers about margins" in payload["text"]
    assert "Story Continues" not in payload["text"]
    assert "unrelated story" not in payload["text"]


def test_extract_article_keeps_yahoo_finance_hidden_read_more_story(monkeypatch):
    def fake_readability_html(_html):
        return """
        <article>
          <p>Anthropic opens with a short setup about its valuation, IPO plans, and why Amazon and Alphabet investors are watching the story.</p>
        </article>
        """

    monkeypatch.setattr(article_reader, "_readability_html", fake_readability_html)

    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <main>
              <article class="article-wrap">
                <div class="bodyItems-wrapper">
                  <p>Anthropic opens with a short setup about its valuation, IPO plans, and why Amazon and Alphabet investors are watching the story.</p>
                  <button type="button">Story Continues</button>
                  <p>The first section explains Amazon's existing investment and the possible future milestone payments tied to Anthropic's growth.</p>
                </div>
                <div class="read-more-wrapper" style="display: none" data-testid="read-more">
                  <h2>A $40 billion investment</h2>
                  <p>Alphabet recently said it plans to invest as much as $40 billion in Anthropic, extending the story after the continuation control.</p>
                  <p>The continuation also explains that Anthropic is buying cloud capacity from Amazon Web Services and using Alphabet infrastructure.</p>
                  <p>Investors may consider Amazon and Alphabet because both companies can benefit as Anthropic's products require more compute.</p>
                  <h2>Should you buy stock in Amazon right now?</h2>
                  <p>Before you buy stock in Amazon, consider this:</p>
                  <p>The Motley Fool Stock Advisor analyst team just identified what they believe are the 10 best stocks for investors to buy now.</p>
                </div>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://finance.yahoo.com/markets/stocks/articles/anthropics-valuation-just-hit-965-223000448.html",
        fallback_title="Anthropic valuation",
    )

    assert "short setup about its valuation" in payload["text"]
    assert "Amazon's existing investment" in payload["text"]
    assert "Alphabet recently said it plans" in payload["text"]
    assert "using Alphabet infrastructure" in payload["text"]
    assert "companies can benefit as Anthropic" in payload["text"]
    assert "Story Continues" not in payload["text"]
    assert "Should you buy stock" not in payload["text"]
    assert "Stock Advisor" not in payload["text"]


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


def test_extract_article_keeps_article_images_and_drops_unlabeled_recommendations():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <header>Navigation chrome</header>
            <main>
              <article>
                <h1>Model launch details</h1>
                <p>The real article opens with concrete product details, release timing, and migration notes for developers evaluating this model launch.</p>
                <figure>
                  <img src="/images/model-demo.jpg" alt="Model demo screenshot">
                  <figcaption>Model demo screenshot from the official launch article.</figcaption>
                </figure>
                <p><img data-src="/images/benchmark-chart.jpg" alt="Benchmark chart"></p>
                <p>The second real paragraph explains benchmark caveats, rollout constraints, and the teams affected by the API change.</p>
                <h3>Also read</h3>
                <p>This unrelated story is long enough to look like article text, but it points readers to a different article and must not survive reader extraction.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://example.com/posts/model-launch",
        fallback_title="Model launch",
    )

    assert "real article opens" in payload["text"]
    assert "second real paragraph" in payload["text"]
    assert "unrelated story" not in payload["text"]
    assert '<figure><img src="https://example.com/images/model-demo.jpg" alt="Model demo screenshot">' in payload["content_html"]
    assert "<figcaption>Model demo screenshot from the official launch article.</figcaption>" in payload["content_html"]
    assert '<figure><img src="https://example.com/images/benchmark-chart.jpg" alt="Benchmark chart"></figure>' in payload["content_html"]


def test_extract_article_keeps_github_style_code_blocks_intact():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <main>
              <article>
                <p>The README introduces the project and then shows setup instructions.</p>
                <pre><code><span>from</span> <span>fastapi</span> <span>import</span> <span>FastAPI</span>
<span>app = FastAPI()</span>
<span>@app.get("/")</span>
<span>def read_root():</span>
<span>    return {"hello": "world"}</span></code></pre>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://example.com/fastapi-readme",
        fallback_title="README",
    )

    assert "The README introduces" in payload["text"]
    assert "<pre>from fastapi import FastAPI" in payload["content_html"]
    assert 'def read_root():' in payload["content_html"]
    assert "from\nfastapi\nimport" not in payload["content_html"]


def test_extract_article_prefers_real_image_sources_over_placeholders():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <main>
              <article>
                <p>The article explains a model release with product screenshots, implementation details, and enough body text to be selected by the reader.</p>
                <figure>
                  <img src="/image.png" data-src="/assets/first-photo.jpg" alt="First real chart">
                </figure>
                <figure>
                  <img src="/image.png" srcset="/assets/second-small.jpg 640w, /assets/second-large.jpg 1200w" alt="Second real chart">
                </figure>
                <figure>
                  <picture>
                    <source srcset="https://cdn.example.com/third-small.webp 640w, https://cdn.example.com/third-large.webp 1200w">
                    <img src="/image.png" alt="Third real chart">
                  </picture>
                </figure>
                <figure>
                  <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==" data-lazy-src="/assets/fourth-photo.jpg" alt="Fourth real chart">
                </figure>
                <figure>
                  <img src="/assets/fifth-valid.jpg" data-src="/assets/fifth-lazy.jpg" alt="Fifth valid chart">
                </figure>
                <p>The second paragraph explains deployment risks, evaluation results, and user impact so the article remains long enough for extraction.</p>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://example.com/posts/model-images",
        fallback_title="Model images",
    )

    assert "first-photo.jpg" in payload["content_html"]
    assert "second-large.jpg" in payload["content_html"]
    assert "third-large.webp" in payload["content_html"]
    assert "fourth-photo.jpg" in payload["content_html"]
    assert "fifth-valid.jpg" in payload["content_html"]
    assert "fifth-lazy.jpg" not in payload["content_html"]
    assert "image.png" not in payload["content_html"]


def test_extract_article_uses_aibase_lazy_image_instead_of_placehold_placeholder():
    payload = extract_article_from_html(
        """
        <html lang="zh">
          <body>
            <main>
              <article>
                <p>这篇 AIbase 文章介绍模型发布背景、产品能力和上线计划，正文长度足够被阅读器识别为主内容。</p>
                <figure>
                  <img
                    src="https://placehold.co/600x400?text=AIBASE"
                    data-src="https://upload.chinaz.com/2026/0608/real-aibase-image.jpg"
                    alt="AIbase real launch image"
                  >
                </figure>
                <p>第二段继续说明技术细节、用户影响和后续安排，确保测试覆盖正文清洗后的图片选择。</p>
              </article>
            </main>
          </body>
        </html>
        """,
        url="https://www.aibase.com/zh/news/28747",
        fallback_title="AIbase lazy image",
    )

    assert "real-aibase-image.jpg" in payload["content_html"]
    assert "placehold.co" not in payload["content_html"]


def test_extract_article_keeps_standalone_reader_images():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The launch article explains the model architecture, benchmarks, training data, and product implications with enough detail to be treated as the primary readable body.</p>
              <img src="/images/model-sample.jpg" alt="Generated poster sample">
              <p>The next paragraph explains typography quality, layout control, and why visual examples are important to understanding the release.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/visual-model",
        fallback_title="Visual model",
    )

    assert '<figure><img src="https://example.com/images/model-sample.jpg" alt="Generated poster sample"></figure>' in payload["content_html"]


def test_extract_article_keeps_image_without_alt_out_of_article_text():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The launch article explains the model architecture, benchmarks, training data, and product implications with enough detail to be treated as the primary readable body.</p>
              <figure><img src="/images/model-sample.jpg"></figure>
              <p>The next paragraph explains typography quality, layout control, and why visual examples are important to understanding the release.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/visual-model",
        fallback_title="Visual model",
    )

    assert '<figure><img src="https://example.com/images/model-sample.jpg"></figure>' in payload["content_html"]
    assert "model-sample.jpg" not in payload["text"]


def test_extract_article_does_not_add_metadata_lead_image_when_body_has_no_images():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <head>
            <meta property="og:image" content="/images/social-card.jpg">
          </head>
          <body>
            <article>
              <p>The article explains a model release with product details, benchmark notes, and enough body text to be selected by the reader.</p>
              <p>The second paragraph explains deployment risks, evaluation results, and user impact so the clean reader remains useful.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/model-release",
        fallback_title="Visual model",
    )

    assert "<figure>" not in payload["content_html"]
    assert "social-card.jpg" not in payload["content_html"]
    assert "model release" in payload["text"]


def test_extract_article_does_not_use_json_ld_article_url_as_image():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <head>
            <script type="application/ld+json">
              {"@type":"NewsArticle","url":"https://example.com/posts/model-release"}
            </script>
          </head>
          <body>
            <article>
              <p>The article explains a model release with product details, benchmark notes, and enough body text to be selected by the reader.</p>
              <p>The second paragraph explains deployment risks, evaluation results, and user impact so the clean reader remains useful.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/model-release",
        fallback_title="Visual model",
    )

    assert "<figure>" not in payload["content_html"]
    assert "model release" in payload["text"]


def test_extract_article_uses_original_container_when_readability_drops_body_images(monkeypatch):
    def fake_readability_html(_html):
        return """
        <div class="article">
          <div class="article_info"><img class="avatar" src="/avatars/author.jpg"></div>
          <p>The article body remains long enough to be selected, but the reader summary lost the actual screenshots that explain the launch.</p>
          <p>The second paragraph keeps enough product context and implementation detail to represent the readable story.</p>
        </div>
        """

    monkeypatch.setattr(article_reader, "_readability_html", fake_readability_html)

    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <main>
              <div class="article">
                <div class="article_info"><img class="avatar" src="/avatars/author.jpg"></div>
                <p>The article body remains long enough to be selected, but the reader summary lost the actual screenshots that explain the launch.</p>
                <figure><img src="/images/first.webp"></figure>
                <p>The second paragraph keeps enough product context and implementation detail to represent the readable story.</p>
                <figure><img src="/images/second.webp"></figure>
                <figure><img src="/images/third.webp"></figure>
              </div>
            </main>
          </body>
        </html>
        """,
        url="https://example.com/posts/image-heavy-story",
        fallback_title="Image heavy story",
    )

    assert "author.jpg" not in payload["content_html"]
    assert payload["content_html"].count("<figure>") == 3
    assert "first.webp" in payload["content_html"]
    assert "second.webp" in payload["content_html"]
    assert "third.webp" in payload["content_html"]


def test_extract_article_deduplicates_nested_figure_image():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The article explains the launch with enough product and deployment detail to remain readable.</p>
              <figure>
                <img src="/images/product-demo.jpg" alt="Product demo">
                <figcaption>Product demo from the launch article.</figcaption>
              </figure>
              <p>The next paragraph explains why the visual example matters to the product announcement.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/product-demo",
        fallback_title="Product demo",
    )

    assert payload["content_html"].count("<figure>") == 1
    assert payload["content_html"].count("product-demo.jpg") == 1
    assert "Product demo from the launch article." in payload["text"]


def test_extract_article_deduplicates_image_size_variants():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The article explains the launch with enough product and deployment detail to remain readable.</p>
              <figure>
                <img src="https://cdn.example.com/images/product-demo.jpg?width=1200&quality=90" alt="Product demo">
              </figure>
              <figure>
                <img src="https://cdn.example.com/images/product-demo.jpg?width=640&quality=80" alt="Product demo">
              </figure>
              <p>The next paragraph explains why the visual example matters to the product announcement.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/product-demo",
        fallback_title="Product demo",
    )

    assert payload["content_html"].count("<figure>") == 1
    assert payload["content_html"].count("product-demo.jpg") == 1


def test_extract_article_keeps_distinct_query_backed_images():
    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The article explains the launch with enough product and deployment detail to remain readable.</p>
              <figure>
                <img src="https://cdn.example.com/render?image=first&w=1200" alt="First product view">
              </figure>
              <figure>
                <img src="https://cdn.example.com/render?image=second&w=1200" alt="Second product view">
              </figure>
              <p>The next paragraph explains why both visual examples matter to the product announcement.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/product-demo",
        fallback_title="Product demo",
    )

    assert payload["content_html"].count("<figure>") == 2
    assert "image=first" in payload["content_html"]
    assert "image=second" in payload["content_html"]


def test_extract_article_drops_reader_ui_images_from_body():
    payload = extract_article_from_html(
        """
        <html lang="zh-CN">
          <body>
            <article>
              <p>在2026腾讯AI产业应用峰会现场，腾讯首席AI科学家对AI下半场给出两个核心判断，说明这是一篇真实正文。</p>
              <img src="//i0cloud.jrjimg.cn/cloud/images/general/wechat-share.png" alt="分享到微信">
              <img src="//i0cloud.jrjimg.cn/cloud/images/general/arrow-grey.png">
              <img src="https://static.jrj.com.cn/resource/web/qr-jrj-app.png" alt="客户端下载二维码">
              <figure>
                <img src="https://static.example.com/articles/yao-stage.jpg" alt="大会现场">
                <figcaption>大会现场图片。</figcaption>
              </figure>
              <p>第二段继续解释多模态、具身智能和未来产品机会，确保正文长度足以被清洗器选中。</p>
            </article>
          </body>
        </html>
        """,
        url="https://stock.jrj.com.cn/2026/06/05132157349626.shtml",
        fallback_title="姚顺雨判断AI下半场",
    )

    assert "wechat-share.png" not in payload["content_html"]
    assert "arrow-grey.png" not in payload["content_html"]
    assert "qr-jrj-app.png" not in payload["content_html"]
    assert "yao-stage.jpg" in payload["content_html"]
    assert payload["content_html"].count("<figure>") == 1


def test_extract_article_preserves_unique_original_images_without_nested_duplicates(monkeypatch):
    def fake_readability_html(_html):
        return """
        <article>
          <p>The article body remains readable but the reader output kept only the first visual example.</p>
          <figure>
            <img src="/images/first.jpg" alt="First product view">
            <figcaption>First product view.</figcaption>
          </figure>
          <p>The second paragraph keeps enough product detail for extraction.</p>
        </article>
        """

    monkeypatch.setattr(article_reader, "_readability_html", fake_readability_html)

    payload = extract_article_from_html(
        """
        <html lang="en">
          <body>
            <article>
              <p>The article body remains readable but the reader output kept only the first visual example.</p>
              <figure>
                <img src="/images/first.jpg" alt="First product view">
                <figcaption>First product view.</figcaption>
              </figure>
              <p>The second paragraph keeps enough product detail for extraction.</p>
              <figure>
                <img src="/images/second.jpg" alt="Second product view">
                <figcaption>Second product view.</figcaption>
              </figure>
              <p>The final paragraph explains the second visual in context.</p>
            </article>
          </body>
        </html>
        """,
        url="https://example.com/posts/two-visuals",
        fallback_title="Two visuals",
    )

    assert payload["content_html"].count("<figure>") == 2
    assert payload["content_html"].count("first.jpg") == 1
    assert payload["content_html"].count("second.jpg") == 1
    assert "Second product view." in payload["text"]


def test_extract_article_uses_36kr_newsflash_detail_instead_of_ad_copy():
    payload = extract_article_from_html(
        """
        <html lang="zh-CN">
          <head>
            <meta property="og:title" content="姚顺雨判断AI下半场：多模态、具身智能等大量新方向正在或即将形成-36氪">
            <meta name="description" content="36氪获悉，腾讯云AI产业应用大会主论坛上，腾讯首席AI科学家姚顺雨对AI下半场给出两个核心判断。">
          </head>
          <body>
            <p>聚焦全球优秀创业者，项目融资率接近97%，领跑行业</p>
            <script>
              window.initialState={"newsflashDetail":{"detailData":{"data":{"widgetTitle":"姚顺雨判断AI下半场：多模态、具身智能等大量新方向正在或即将形成","widgetContent":"36氪获悉，腾讯云AI产业应用大会主论坛上，腾讯首席AI科学家姚顺雨对AI下半场给出两个核心判断：第一，AI是一个长期游戏，而非短期窗口。第二，AI将走向多元而非单一路径。"}}}};
            </script>
          </body>
        </html>
        """,
        url="https://www.36kr.com/newsflashes/3839787696491008",
        fallback_title="姚顺雨判断AI下半场",
    )

    assert "36氪获悉，腾讯云AI产业应用大会主论坛" in payload["text"]
    assert "聚焦全球优秀创业者" not in payload["text"]


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

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
    monkeypatch.setattr("server.ai_radar_api.article_reader._http_post", fake_post)

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
    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)

    payload = fetch_clean_article(config, item)

    assert payload["url"] == "https://news.google.com/read/article-id"
    assert payload["final_url"] == "https://publisher.example/story"
    assert "publisher article body" in payload["text"]


def test_fetch_clean_article_does_not_fetch_google_news_wrapper_when_resolution_fails(monkeypatch, tmp_path):
    item = {
        "title": "Google News unresolved item",
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

    def fail_resolve(url, timeout_seconds=6):
        raise httpx.ConnectTimeout("google news decode timed out")

    fetch_calls = []

    def fail_get(*args, **kwargs):
        fetch_calls.append(args[0] if args else "")
        raise AssertionError("fetch_clean_article must not fetch the Google News wrapper as article body")

    monkeypatch.setattr("server.ai_radar_api.article_reader.resolve_google_news_url", fail_resolve)
    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)

    payload = fetch_clean_article(config, item)

    assert payload["access_status"] == "unavailable"
    assert "Google News" in payload["fetch_error"]
    assert fetch_calls == []


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

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
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


def test_read_article_endpoint_returns_canonical_cache_without_news_lookup(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": "Cached clean title",
            "site_name": "Example AI",
            "byline": "",
            "published_at": item["published_at"],
            "excerpt": "Cached body",
            "text": "Cached body with enough detail to prove this came directly from article_cache.",
            "content_html": "<p>Cached body with enough detail to prove this came directly from article_cache.</p>",
            "access_status": "open",
            "access_label": "",
            "language": "en",
            "fetched_at": article_reader._now(),
        },
    )
    lookup_calls = 0

    def fail_load_latest_items(*args, **kwargs):
        nonlocal lookup_calls
        lookup_calls += 1
        raise AssertionError("canonical cache hit must not load latest news JSON")

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", fail_load_latest_items)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get(f"/api/read/{identity}")

    assert res.status_code == 200
    assert res.json()["cache_status"] == "hit"
    assert res.json()["title"] == "Cached clean title"
    assert lookup_calls == 0


def test_read_article_endpoint_returns_alias_cache_without_news_lookup(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    item["id"] = "feed-model-launch-1"
    _write_latest_data(config, item)
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": "Cached alias title",
            "site_name": "Example AI",
            "byline": "",
            "published_at": item["published_at"],
            "excerpt": "Cached alias body",
            "text": "Cached alias body with enough detail to prove feed ids can bypass JSON lookup.",
            "content_html": "<p>Cached alias body with enough detail to prove feed ids can bypass JSON lookup.</p>",
            "access_status": "open",
            "access_label": "",
            "language": "en",
            "fetched_at": article_reader._now(),
        },
    )
    _store_article_alias(config, item["id"], identity, item)
    lookup_calls = 0

    def fail_load_latest_items(*args, **kwargs):
        nonlocal lookup_calls
        lookup_calls += 1
        raise AssertionError("alias cache hit must not load latest news JSON")

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", fail_load_latest_items)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get(f"/api/read/{item['id']}")

    assert res.status_code == 200
    assert res.json()["cache_status"] == "hit"
    assert res.json()["title"] == "Cached alias title"
    assert lookup_calls == 0


def test_read_article_endpoint_prefills_alias_from_local_data_for_existing_cache(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    item["id"] = "feed-existing-cache"
    _write_latest_data(config, item)
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": "Existing cached title",
            "site_name": "Example AI",
            "byline": "",
            "published_at": item["published_at"],
            "excerpt": "Existing cached body",
            "text": "Existing cached body should be reachable by feed id immediately after app startup.",
            "content_html": "<p>Existing cached body should be reachable by feed id immediately after app startup.</p>",
            "access_status": "open",
            "access_label": "",
            "language": "en",
            "fetched_at": article_reader._now(),
        },
    )

    def fail_load_latest_items(*args, **kwargs):
        raise AssertionError("startup alias prefill should avoid per-request latest news lookup")

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", fail_load_latest_items)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get(f"/api/read/{item['id']}")

    assert res.status_code == 200
    assert res.json()["cache_status"] == "hit"
    assert res.json()["title"] == "Existing cached title"


def test_read_article_endpoint_stores_alias_after_news_item_lookup(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    item["id"] = "feed-model-launch-2"
    _write_latest_data(config, item)
    calls = 0

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Fresh title for alias storage</h1>
          <p>The first read should fetch the origin once and store an alias for the feed id.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
    client = TestClient(create_app(config), base_url="https://testserver")

    first = client.get(f"/api/read/{item['id']}")
    assert first.status_code == 200
    assert first.json()["cache_status"] == "miss"

    def fail_load_latest_items(*args, **kwargs):
        raise AssertionError("stored feed id alias should bypass latest news JSON")

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", fail_load_latest_items)
    second = client.get(f"/api/read/{item['id']}")

    assert second.status_code == 200
    assert second.json()["cache_status"] == "hit"
    assert second.json()["title"] == "Fresh title for alias storage"
    assert calls == 1


def test_read_article_endpoint_retries_stale_alias_cache_without_news_lookup(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    item["id"] = "feed-stale-unavailable"
    _write_latest_data(config, item)
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
            "published_at": item["published_at"],
            "excerpt": "暂时无法清洗原文",
            "text": "暂时无法清洗原文。可打开原文查看。",
            "content_html": "<p>暂时无法清洗原文。</p>",
            "access_status": "unavailable",
            "access_label": "暂时无法清洗原文",
            "language": "zh",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )
    _store_article_alias(config, item["id"], identity, item)
    lookup_calls = 0
    fetch_calls = 0

    def fail_load_latest_items(*args, **kwargs):
        nonlocal lookup_calls
        lookup_calls += 1
        raise AssertionError("stale alias cache retry should reconstruct item from article cache")

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Recovered alias title</h1>
          <p>The stale fallback should retry from the cached URL without scanning latest news JSON.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", fail_load_latest_items)
    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get(f"/api/read/{item['id']}")

    assert res.status_code == 200
    assert res.json()["cache_status"] == "miss"
    assert res.json()["access_status"] == "open"
    assert "stale fallback should retry" in res.json()["text"]
    assert fetch_calls == 1
    assert lookup_calls == 0


def test_read_article_endpoint_reuses_fresh_unavailable_alias_cache_without_fetch(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    item["id"] = "feed-fresh-unavailable"
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
            "published_at": item["published_at"],
            "excerpt": "暂时无法清洗原文",
            "text": "暂时无法清洗原文。可打开原文查看。",
            "content_html": "<p>暂时无法清洗原文。</p>",
            "access_status": "unavailable",
            "access_label": "暂时无法清洗原文",
            "language": "zh",
            "fetched_at": article_reader._now(),
        },
    )
    _store_article_alias(config, item["id"], identity, item)
    lookup_calls = 0
    fetch_calls = 0

    def fail_load_latest_items(*args, **kwargs):
        nonlocal lookup_calls
        lookup_calls += 1
        raise AssertionError("fresh unavailable alias cache should bypass latest news JSON")

    def fail_get(*args, **kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("fresh unavailable alias cache should not refetch origin")

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", fail_load_latest_items)
    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get(f"/api/read/{item['id']}")

    assert res.status_code == 200
    assert res.json()["cache_status"] == "hit"
    assert res.json()["access_status"] == "unavailable"
    assert lookup_calls == 0
    assert fetch_calls == 0


def test_read_article_endpoint_ignores_alias_without_cached_article(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    _store_article_alias(config, "orphan-feed-id", "missing-canonical-id", item)
    fetch_calls = 0

    def empty_load_latest_items(*args, **kwargs):
        return []

    def fail_get(*args, **kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("orphan aliases must not fetch arbitrary origin URLs")

    monkeypatch.setattr("server.ai_radar_api.article_reader.load_latest_items", empty_load_latest_items)
    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get("/api/read/orphan-feed-id")

    assert res.status_code == 404
    assert fetch_calls == 0


def test_read_article_endpoint_rejects_stale_alias_cache_with_unsafe_url(monkeypatch, tmp_path):
    config, _ = _config(tmp_path)
    init_db(config.db_path)
    item = {
        "id": "feed-unsafe-cache",
        "title": "Unsafe cached URL",
        "url": "file:///etc/passwd",
        "site_name": "Unsafe",
        "published_at": "2026-06-03T04:30:00Z",
    }
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": item["title"],
            "site_name": "Unsafe",
            "byline": "",
            "published_at": item["published_at"],
            "excerpt": "暂时无法清洗原文",
            "text": "暂时无法清洗原文。可打开原文查看。",
            "content_html": "<p>暂时无法清洗原文。</p>",
            "access_status": "unavailable",
            "access_label": "暂时无法清洗原文",
            "language": "zh",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )
    _store_article_alias(config, item["id"], identity, item)
    fetch_calls = 0

    def fail_get(*args, **kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("unsafe stale cached URLs must be rejected before fetching")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get(f"/api/read/{item['id']}")

    assert res.status_code == 422
    assert "Unsupported article URL" in res.text
    assert fetch_calls == 0


def test_read_article_endpoint_does_not_fetch_unknown_uncached_id(monkeypatch, tmp_path):
    config, _ = _config(tmp_path)
    fetch_calls = 0

    def fail_get(*args, **kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        raise AssertionError("unknown uncached ids must not fetch arbitrary origin URLs")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get("/api/read/not-a-known-item")

    assert res.status_code == 404
    assert fetch_calls == 0


def test_read_article_endpoint_does_not_add_item_image_when_fetched_body_has_no_images(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    item["image_url"] = "https://cdn.example.com/feed-card.jpg"
    (config.data_dir / "latest-24h.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
    (config.data_dir / "latest-24h-all.json").write_text(json.dumps({"items_all": [item]}), encoding="utf-8")

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Fetched clean title</h1>
          <p>This extracted body is long enough to be useful, but it has no inline article images.</p>
          <p>The feed card image should not be inserted into the clean reader as if it were body content.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", lambda *args, **kwargs: Response())
    client = TestClient(create_app(config), base_url="https://testserver")
    identity = item_identity(item)

    res = client.get(f"/api/read/{identity}")

    assert res.status_code == 200
    assert res.json()["access_status"] == "open"
    assert "feed-card.jpg" not in res.json()["content_html"]
    assert "<figure>" not in res.json()["content_html"]


def test_read_article_endpoint_rejects_unknown_item(tmp_path):
    config, _ = _config(tmp_path)
    client = TestClient(create_app(config), base_url="https://testserver")

    res = client.get("/api/read/not-a-known-item")

    assert res.status_code == 404


def test_read_article_endpoint_returns_cached_fallback_when_origin_blocks_fetch(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    item["image_url"] = "https://cdn.example.com/blocked-lead.jpg"
    (config.data_dir / "latest-24h.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
    (config.data_dir / "latest-24h-all.json").write_text(json.dumps({"items_all": [item]}), encoding="utf-8")
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

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
    client = TestClient(create_app(config), base_url="https://testserver")
    identity = item_identity(item)

    first = client.get(f"/api/read/{identity}")
    second = client.get(f"/api/read/{identity}")

    assert first.status_code == 200
    assert first.json()["access_status"] == "restricted"
    assert "原站限制" in first.json()["access_label"]
    assert "<img" not in first.json()["content_html"]
    assert second.status_code == 200
    assert second.json()["cache_status"] == "hit"
    assert "<img" not in second.json()["content_html"]
    assert calls == 1


def test_fetch_clean_article_retries_transient_transport_timeout(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    calls = []

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Recovered article</h1>
          <p>The retried article body is long enough to prove the transient network failure did not become a cached fallback.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("handshake operation timed out")
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)

    payload = fetch_clean_article(config, item)

    assert payload["access_status"] == "open"
    assert payload["cache_status"] == "miss"
    assert "retried article body" in payload["text"]
    assert len(calls) == 2


def test_fetch_clean_article_uses_x_status_text_without_fetching_x_shell(monkeypatch, tmp_path):
    item = {
        "title": "NotebookLM source attribution update",
        "url": "https://x.com/NotebookLM/status/2062653124326863077",
        "site_name": "X",
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

    def fail_get(*args, **kwargs):
        raise AssertionError("x.com status pages should use collected post text instead of fetching the shell")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)

    payload = fetch_clean_article(config, item)

    assert payload["access_status"] == "open"
    assert payload["cache_status"] == "miss"
    assert "Something went wrong" not in payload["text"]
    assert payload["text"] == "NotebookLM source attribution update"
    assert "NotebookLM source attribution update" in payload["content_html"]
    assert "暂时无法清洗原文" not in payload["content_html"]


def test_fetch_clean_article_does_not_use_x_status_fallback_for_profile_page(monkeypatch, tmp_path):
    item = {
        "title": "NotebookLM profile update",
        "url": "https://x.com/NotebookLM",
        "site_name": "X",
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
    calls = 0

    class Response:
        url = item["url"]
        text = """
        <html><body><article>
          <p>The profile page body was fetched through the normal reader path.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)

    payload = fetch_clean_article(config, item)

    assert calls == 1
    assert payload["access_status"] == "open"
    assert "profile page body" in payload["text"]


def test_fetch_clean_article_retries_cached_x_error_shell(monkeypatch, tmp_path):
    item = {
        "title": "NotebookLM source attribution update",
        "url": "https://x.com/NotebookLM/status/2062653124326863077",
        "site_name": "X",
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
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": item["title"],
            "site_name": "X",
            "byline": "",
            "published_at": "",
            "excerpt": "Something went wrong, but don’t fret — let’s give it another shot.",
            "text": "Something went wrong, but don’t fret — let’s give it another shot.\n\n⚠️",
            "content_html": "<p>Something went wrong, but don’t fret — let’s give it another shot.</p><p>⚠️</p>",
            "access_status": "open",
            "access_label": "",
            "language": "en",
            "fetched_at": "2026-06-05T00:00:00Z",
        },
    )
    def fake_get(*args, **kwargs):
        raise AssertionError("stale x.com shells should be replaced from collected post text without refetching")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)

    payload = fetch_clean_article(config, item)

    assert payload["access_status"] == "open"
    assert payload["text"] == "NotebookLM source attribution update"
    assert "Something went wrong" not in payload["text"]


def test_fetch_clean_article_replaces_fresh_x_unavailable_fallback(monkeypatch, tmp_path):
    item = {
        "title": "NotebookLM source attribution update",
        "url": "https://x.com/NotebookLM/status/2062653124326863077",
        "site_name": "X",
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
    identity = item_identity(item)
    store_article(
        config.db_path,
        {
            "item_id": identity,
            "url": item["url"],
            "final_url": item["url"],
            "title": item["title"],
            "site_name": "X",
            "byline": "",
            "published_at": "",
            "excerpt": "NotebookLM source attribution update\n\n暂时无法清洗原文。可打开原文查看。",
            "text": "NotebookLM source attribution update\n\n暂时无法清洗原文。可打开原文查看。",
            "content_html": "<p>暂时无法清洗原文。</p>",
            "access_status": "unavailable",
            "access_label": "暂时无法清洗原文",
            "language": "zh",
            "fetched_at": article_reader._now(),
        },
    )

    def fake_get(*args, **kwargs):
        raise AssertionError("fresh x.com unavailable fallback should be replaced from collected post text")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)

    payload = fetch_clean_article(config, item)

    assert payload["access_status"] == "open"
    assert payload["text"] == "NotebookLM source attribution update"
    assert "暂时无法清洗原文" not in payload["text"]


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

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
    client = TestClient(app, base_url="https://testserver")

    res = client.get(f"/api/read/{identity}")

    assert res.status_code == 200
    assert res.json()["access_status"] == "open"
    assert res.json()["cache_status"] == "miss"
    assert "retried article body" in res.json()["text"]
    assert calls == 1


def test_read_article_endpoint_does_not_add_item_image_to_cached_article_without_images(tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
    item["image_url"] = "https://cdn.example.com/lead-image.jpg"
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
            "excerpt": "Cached article body",
            "text": "Cached article body with enough details to remain useful without refetching the origin.",
            "content_html": "<p>Cached article body with enough details to remain useful without refetching the origin.</p>",
            "access_status": "open",
            "access_label": "",
            "language": "en",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )

    article = fetch_clean_article(config, item)

    assert article["cache_status"] == "hit"
    assert "lead-image.jpg" not in article["content_html"]
    assert "<figure>" not in article["content_html"]
    assert "Cached article body" in article["text"]


def test_fetch_clean_article_reuses_fresh_short_open_cache(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
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
            "excerpt": "简短正文",
            "text": "简短正文",
            "content_html": "<p>简短正文</p>",
            "access_status": "open",
            "access_label": "",
            "language": "zh",
            "fetched_at": article_reader._now(),
        },
    )

    def fail_get(*args, **kwargs):
        raise AssertionError("fresh open article cache should be reused without refetching")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)

    article = fetch_clean_article(config, item)

    assert article["cache_status"] == "hit"
    assert article["text"] == "简短正文"


def test_fetch_clean_article_reuses_fresh_unavailable_cache(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
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
            "fetched_at": article_reader._now(),
        },
    )
    calls = 0

    def fail_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("fresh unavailable cache should be reused briefly")

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fail_get)

    article = fetch_clean_article(config, item)

    assert article["cache_status"] == "hit"
    assert article["access_status"] == "unavailable"
    assert calls == 0


def test_read_article_endpoint_retries_too_short_open_cache(monkeypatch, tmp_path):
    config, item = _config(tmp_path)
    init_db(config.db_path)
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
            "excerpt": "广告短句",
            "text": "广告短句",
            "content_html": "<p>广告短句</p>",
            "access_status": "open",
            "access_label": "",
            "language": "zh",
            "fetched_at": "2026-06-03T00:00:00Z",
        },
    )

    class Response:
        url = "https://example.com/posts/model-launch"
        text = """
        <html><body><article>
          <h1>Fresh clean title</h1>
          <p>The retried article body has enough substance about the model launch, product details, and user impact to replace the stale short cache.</p>
        </article></body></html>
        """

        def raise_for_status(self):
            return None

    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)

    article = fetch_clean_article(config, item)

    assert article["cache_status"] == "miss"
    assert calls == 1
    assert "retried article body" in article["text"]


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

    async def fake_answer_question(config, question, items, conversation_messages=None, system_prompt=None, provider=None):
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

    async def fake_answer_question(config, question, items, conversation_messages=None, system_prompt=None, provider=None):
        captured["item"] = items[0]
        return {"answer": "ok", "title": "正文上下文", "citations": [], "model": config.ai_model}

    monkeypatch.setattr("server.ai_radar_api.article_reader._http_get", fake_get)
    monkeypatch.setattr("server.ai_radar_api.main.load_latest_items_with_source", fake_load_latest_items_with_source)
    monkeypatch.setattr("server.ai_radar_api.main.answer_question", fake_answer_question)

    res = client.post("/api/ask", json={"question": "这篇文章说了什么？", "scope": "today", "item_id": identity})

    assert res.status_code == 200
    assert captured["item"]["article_text"] == "Fresh article body should replace stale unavailable cache for Ask AI context."
