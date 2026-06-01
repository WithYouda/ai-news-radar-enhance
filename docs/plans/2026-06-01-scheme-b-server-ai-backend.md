# Scheme B Server AI Backend Implementation Plan

> **Execution Skill:** Use `superpowers:subagent-driven-development` (same session) or `superpowers:executing-plans` (separate session) to implement this plan task-by-task.

**Goal:** Build a self-owned AI News Radar setup where GitHub Pages serves the customized news reader, GitHub Actions refreshes public feed data, and this server runs the AI question-answering backend.

**Architecture:** Keep the public reader static and cheap: GitHub Actions generates `data/*.json`, then GitHub Pages serves `index.html`, `assets/*`, and `data/*`. Add a small server-side AI API on this VPS; the browser sends questions to the server, the server fetches the latest radar JSON, builds a bounded context, calls the configured model provider, and returns cited answers. Secrets stay in GitHub Secrets or server environment variables, never in the repository or front-end JavaScript.

**Tech Stack:** Existing static HTML/CSS/JS, existing Python news generator, GitHub Actions, GitHub Pages, Python FastAPI backend, uvicorn, PM2 or systemd process management, Nginx reverse proxy, OpenAI-compatible model provider configuration via environment variables.

---

## Current State

- New repository: `https://github.com/WithYouda/ai-news-radar-enhance`
- Branch: `master`
- GitHub Pages target: `https://withyouda.github.io/ai-news-radar-enhance/`
- Local 8080 static server has been stopped through PM2.
- Local `data/*.json` modifications are not important and do not need to be pushed.
- The pushed repository contains an initial root commit because the original local clone was shallow and could not be pushed as-is.

## Recommended Scheme B

Use this split:

```text
GitHub Actions
  -> scheduled fetch and data generation
  -> commits public data/*.json

GitHub Pages
  -> serves the customized reader
  -> no secrets
  -> can be installed later as PWA/TWA

This VPS
  -> runs AI Q&A backend
  -> stores model API key in environment variables
  -> rate limits and authenticates users
  -> fetches GitHub Pages JSON as public context
```

This avoids running the whole site on the VPS. The VPS is only needed for dynamic AI work.

## Safety Rules

- Do not commit `feeds/follow.opml`.
- Do not commit `.env`, API keys, cookies, tokens, inbox IDs, or private emails.
- Do not publish `data/email-digest.json` on public Pages unless the output is intentionally public.
- Do not put an AI API key, access token, or private passcode in `assets/app.js`.
- CORS is not authentication. The AI API needs rate limiting and either a login/session cookie, Basic Auth, or another server-side access control.
- Public GitHub Pages data should be treated as public. If a source is private, keep its full content on the server side.

## Task 1: Configure GitHub Pages and Actions

**Files:**
- Modify: `.github/workflows/update-news.yml`
- Modify: `index.html`
- Optional: `README.md`

**Step 1: Enable Pages**

In GitHub:

```text
Settings -> Pages
Source: Deploy from a branch
Branch: master
Folder: /root
```

Expected page:

```text
https://withyouda.github.io/ai-news-radar-enhance/
```

**Step 2: Enable Actions**

In GitHub:

```text
Actions -> Update AI News Snapshot -> Run workflow
```

Expected: the workflow updates and commits `data/latest-24h.json`, `data/latest-24h-all.json`, `data/archive.json`, `data/source-status.json`, `data/waytoagi-7d.json`, and `data/title-zh-cache.json`.

**Step 3: Reduce cron if needed**

For a personal radar, change the current 30-minute schedule:

```yaml
schedule:
  - cron: "0 * * * *"
```

Expected: the workflow runs hourly instead of every 30 minutes.

**Step 4: Update public site metadata**

In `index.html`, update:

```html
<link rel="canonical" href="https://withyouda.github.io/ai-news-radar-enhance/" />
<meta property="og:url" content="https://withyouda.github.io/ai-news-radar-enhance/" />
```

Expected: social previews and canonical URL point to the new site.

**Step 5: Validate**

Run locally after dependency setup:

```bash
python -m py_compile scripts/update_news.py
node --check assets/app.js
git diff --check
```

Expected: all commands pass.

## Task 2: Customize Public Information Sources

**Files:**
- Create locally only: `feeds/follow.opml`
- Do not commit: `feeds/follow.opml`
- Reference: `feeds/follow.example.opml`
- Reference: `docs/SOURCE_COVERAGE.md`

**Step 1: Create local OPML**

```bash
cp feeds/follow.example.opml feeds/follow.opml
```

Add public RSS/Atom sources first. Prefer official feeds, stable public feeds, and low-noise AI/product/research sources.

**Step 2: Test locally**

```bash
python scripts/update_news.py --output-dir data --window-hours 24 --rss-opml feeds/follow.opml --rss-max-feeds 10
```

Expected: `data/source-status.json` shows OPML status under `rss_opml`.

**Step 3: Encode OPML for GitHub Secrets**

Linux:

```bash
base64 -w0 feeds/follow.opml
```

macOS:

```bash
base64 < feeds/follow.opml | pbcopy
```

Add the result as repository secret:

```text
FOLLOW_OPML_B64
```

**Step 4: Configure feed cap**

Add repository variable:

```text
RSS_MAX_FEEDS=10
```

Increase only after `data/source-status.json` confirms source quality.

## Task 3: Add Server AI Backend

**Files:**
- Create: `server/ai_radar_api/main.py`
- Create: `server/ai_radar_api/context.py`
- Create: `server/ai_radar_api/provider.py`
- Create: `server/ai_radar_api/security.py`
- Create: `server/requirements.txt`
- Create: `server/README.md`
- Test: `tests/test_ai_backend_context.py`
- Test: `tests/test_ai_backend_security.py`

**Backend endpoints:**

```text
GET  /health
POST /api/ask
```

**Environment variables:**

```text
RADAR_PUBLIC_BASE_URL=https://withyouda.github.io/ai-news-radar-enhance
AI_PROVIDER_BASE_URL=
AI_API_KEY=
AI_MODEL=
RADAR_ALLOWED_ORIGINS=https://withyouda.github.io
RADAR_ACCESS_PASSWORD=
RADAR_MAX_CONTEXT_ITEMS=40
RADAR_REQUESTS_PER_MINUTE=10
```

**Step 1: Write context builder test**

Test that the server can fetch or receive radar JSON and select a bounded context:

```python
def test_context_builder_keeps_most_relevant_items():
    items = [
        {"title": "OpenAI ships model update", "url": "https://example.com/a", "ai_score": 0.9},
        {"title": "Low relevance item", "url": "https://example.com/b", "ai_score": 0.2},
    ]
    context = build_context(items, question="OpenAI update?", max_items=1)
    assert "OpenAI ships model update" in context
    assert "Low relevance item" not in context
```

Run:

```bash
pytest tests/test_ai_backend_context.py -q
```

Expected before implementation: fail because `build_context` does not exist.

**Step 2: Implement `server/ai_radar_api/context.py`**

Implement:

```python
def build_context(items: list[dict], question: str, max_items: int = 40) -> str:
    ranked = sorted(items, key=lambda x: float(x.get("ai_score") or 0), reverse=True)
    selected = ranked[:max_items]
    lines = []
    for idx, item in enumerate(selected, 1):
        lines.append(
            f"[{idx}] {item.get('title')} | {item.get('site_name')} | "
            f"{item.get('published_at')} | {item.get('url')}"
        )
    return "\n".join(lines)
```

Run:

```bash
pytest tests/test_ai_backend_context.py -q
```

Expected: pass.

**Step 3: Write security tests**

Test that unauthenticated requests are rejected and allowed origins are enforced.

Run:

```bash
pytest tests/test_ai_backend_security.py -q
```

Expected before implementation: fail.

**Step 4: Implement FastAPI backend**

Create `server/ai_radar_api/main.py` with:

- `/health` returning `{ "ok": true }`
- `/api/ask` accepting `{ "question": "..." }`
- fetches `RADAR_PUBLIC_BASE_URL/data/latest-24h.json`
- builds context
- calls provider abstraction
- returns:

```json
{
  "answer": "...",
  "sources": [
    {"title": "...", "url": "..."}
  ]
}
```

Keep provider-specific code in `provider.py`.

**Step 5: Add provider abstraction**

Create `server/ai_radar_api/provider.py` with an OpenAI-compatible HTTP client:

```python
def answer_with_context(question: str, context: str) -> dict:
    ...
```

Do not hardcode model names or keys. Read from environment variables.

**Step 6: Add server requirements**

`server/requirements.txt`:

```text
fastapi
uvicorn[standard]
httpx
python-dotenv
pytest
```

**Step 7: Run backend locally**

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn ai_radar_api.main:app --host 127.0.0.1 --port 8090
```

Expected:

```bash
curl http://127.0.0.1:8090/health
```

returns:

```json
{"ok": true}
```

## Task 4: Deploy Backend on This VPS

**Files:**
- Create: `server/ecosystem.config.cjs`
- Create outside repo: `/etc/ai-news-radar-api.env` or PM2 secret environment
- Modify server Nginx config outside repo

**Step 1: Create PM2 config**

Use port `8090` for the backend to keep it separate from the old static server:

```js
module.exports = {
  apps: [
    {
      name: "ai-news-radar-api",
      cwd: "/home/xdp/ai-news-radar/server",
      script: ".venv/bin/uvicorn",
      args: "ai_radar_api.main:app --host 127.0.0.1 --port 8090",
      env: {
        RADAR_PUBLIC_BASE_URL: "https://withyouda.github.io/ai-news-radar-enhance"
      }
    }
  ]
};
```

Do not put `AI_API_KEY` in this committed file.

**Step 2: Start PM2**

```bash
cd server
pm2 start ecosystem.config.cjs
pm2 save
```

Expected:

```bash
pm2 list
```

shows `ai-news-radar-api` online.

**Step 3: Add Nginx reverse proxy**

Recommended public API route:

```text
https://your-domain.example/api/ask
```

Proxy to:

```text
http://127.0.0.1:8090
```

Nginx must provide HTTPS. GitHub Pages is HTTPS, so the browser will block plain HTTP API calls.

**Step 4: Validate from outside**

```bash
curl https://your-domain.example/health
```

Expected:

```json
{"ok": true}
```

## Task 5: Add Frontend AI Ask Panel

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Optional Create: `data/runtime-config.json`

**Step 1: Add runtime config**

Use a public non-secret config file:

```json
{
  "aiApiBaseUrl": "https://your-domain.example"
}
```

This file can be public because it contains no API key.

**Step 2: Add Ask UI**

Add a compact panel:

```html
<section class="ask-panel">
  <textarea id="askInput" placeholder="问今天的 AI 更新..."></textarea>
  <button id="askSubmit" type="button">问 AI</button>
  <div id="askAnswer"></div>
</section>
```

**Step 3: Implement request**

In `assets/app.js`, send:

```js
fetch(`${config.aiApiBaseUrl}/api/ask`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  credentials: "include",
  body: JSON.stringify({ question })
});
```

Do not include private keys or permanent access tokens in JavaScript.

**Step 4: Validate**

```bash
node --check assets/app.js
python -m http.server 8080
```

Expected: the page loads and the ask panel can reach the server API.

## Task 6: Mobile Reader and PWA

**Files:**
- Create: `manifest.webmanifest`
- Create: `sw.js`
- Modify: `index.html`
- Modify: `assets/styles.css`
- Modify: `assets/app.js`

**Step 1: Add PWA manifest**

Add:

```json
{
  "name": "AI News Radar Enhance",
  "short_name": "AI Radar",
  "start_url": "/ai-news-radar-enhance/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#111827",
  "icons": []
}
```

**Step 2: Add service worker**

Cache static shell files only. Do not aggressively cache `data/*.json`; news should stay fresh.

**Step 3: Mobile UI pass**

Prioritize:

- Today
- Bole Picks
- Ask AI
- Sources
- Settings

Avoid adding many reader-facing controls to the first screen.

## Task 7: Private Data Policy

**Files:**
- Modify: `README.md`
- Modify: `docs/SOURCE_COVERAGE.md`
- Optional Create: `docs/PRIVATE_DATA_POLICY.md`

**Rules:**

- Public Pages may show public feeds and non-sensitive OPML results.
- AgentMail metadata should stay private unless explicitly published.
- If a private newsletter or inbox is used, server-side AI may summarize it for the authenticated user, but public `data/*.json` should not include it.
- If private source summaries are needed, store them on the VPS and expose them only through authenticated API routes.

## Task 8: Final Verification

Run:

```bash
python -m py_compile scripts/update_news.py
python -m pytest -q
node --check assets/app.js
git diff --check
curl https://withyouda.github.io/ai-news-radar-enhance/data/latest-24h.json
curl https://your-domain.example/health
```

Expected:

- Python compile passes.
- Tests pass.
- Frontend syntax check passes.
- GitHub Pages data is reachable.
- Server AI backend health check returns ok.

## Suggested Execution Order

1. Configure GitHub Pages and Actions.
2. Update public URL metadata.
3. Add public OPML customization.
4. Build server AI backend.
5. Deploy server backend behind HTTPS.
6. Add frontend Ask AI panel.
7. Add mobile reader/PWA polish.
8. Decide later whether to package as TWA Android app.

## Open Decisions

- Domain for the AI backend: use existing server domain or create a subdomain such as `radar-api.example.com`.
- Authentication style: password session, Basic Auth, or private-only network access.
- AI provider: OpenAI-compatible endpoint, local model, or another hosted provider.
- Private source boundary: whether private newsletter summaries should ever appear in public JSON.
