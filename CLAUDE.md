# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Before You Start

Read these first (they hold context not derivable from code):

- `skills/ai-news-radar/SKILL.md` — source-intake workflow, safety rules, product direction
- `docs/SOURCE_COVERAGE.md` — before changing source strategy
- `README.md` — current usage and commands (Chinese), `server/README.md` — backend

Requires **Python 3.11** (the backend and tooling use `datetime.UTC`; 3.10 fails).

## Common Commands

```bash
# Install
pip install -r requirements.txt          # static-site generator deps
pip install -r requirements-dev.txt       # everything + pytest, fastapi, server deps

# Tests (run from repo root; conftest.py adds root to sys.path)
python -m pytest -q                        # full suite
python -m pytest -q tests/test_ai_backend_db.py            # single file
python -m pytest -q tests/test_topic_filter.py -k agentmail # single test by keyword

# Generate the public snapshot (writes data/*.json)
python scripts/update_news.py --output-dir data --window-hours 24
python scripts/update_news.py --output-dir data --window-hours 24 --rss-opml feeds/follow.opml --rss-max-feeds 10

# Serve the static site
python -m http.server 8080                 # then open http://localhost:8080

# Run the backend (env vars are required, see below)
RADAR_ADMIN_PASSWORD=change-me RADAR_SESSION_SECRET=change-me-long \
AI_BASE_URL=https://api.example.com/v1 AI_API_KEY=sk-x AI_MODEL=gpt-4.1-mini \
uvicorn server.ai_radar_api.main:app --host 127.0.0.1 --port 8090

# Fast validation gate (use before commits / handoff)
python -m py_compile scripts/update_news.py
python -m py_compile server/ai_radar_api/*.py
node --check assets/app.js
node --check sw.js
git diff --check
```

`pytest` uses a custom ASGI test client (`tests/conftest.py` monkeypatches
`fastapi.testclient.TestClient` and runs `anyio.to_thread.run_sync` inline) — no
running server or network is needed for backend tests.

## Architecture

Two independent layers. The static reader works alone; the FastAPI backend is an
**optional** enhancement, never a prerequisite.

### Layer 1 — Static reader (no server)

- **`scripts/update_news.py`** (the data pipeline): fetches all sources
  concurrently, scores AI relevance, translates EN→ZH titles, and writes
  `data/*.json`. Built-in sources are registered in `BUILT_IN_SOURCE_TASKS`
  (`SourceTask(site_id, name, fetch_fn)`); each fetcher is `fetch_<source>(session, now) -> list[RawItem]`.
  OPML/RSS sources come in via `--rss-opml`. Optional secret-backed adapters:
  AgentMail email digest and X API search (both off by default).
- **AI relevance** lives in `scripts/ai_relevance.py` (`score_ai_relevance`,
  `add_ai_relevance_fields`, versioned by `AI_RELEVANCE_SCORE_VERSION`). Golden
  fixtures: `tests/fixtures/ai_relevance_golden.json`.
- **Output `data/*.json`** (committed by CI, large — do not hand-edit):
  `latest-24h.json` (AI-strong signal view), `latest-24h-all.json` (all sources),
  `archive.json` (rolling history), `source-status.json` (per-source health),
  `waytoagi-7d.json`, `title-zh-cache.json` (translation cache).
- **Frontend**: `index.html` + `assets/app.js` (~6k lines, single global `state`
  object, vanilla JS), `assets/styles.css`, `sw.js` (PWA), `manifest.webmanifest`.
  `assets/api-client.js` exposes `window.AI_NEWS_RADAR_API` (`apiFetch`/`fetchFreshJson`);
  `assets/config.js` sets `window.AI_NEWS_RADAR_CONFIG.apiBaseUrl`. With no
  backend configured, the UI degrades to a plain static radar.

### Layer 2 — FastAPI backend (`server/ai_radar_api/`)

App factory `create_app()` in `main.py` wires everything; `main:app` is the
ASGI entrypoint. Config is env-driven via `AppConfig.from_env()` (`config.py`).
State is **SQLite** (`db.py` holds the full schema in `SCHEMA`; `init_db` also
does ad-hoc column migrations via `pragma table_info`).

Modules and what they own:

- `auth.py` + `routers/auth.py` — admin login, signed session cookie (`radar_session`)
- `classifier.py` — rule-based taxonomy classification; `taxonomy.py` seeds categories
- `verification.py` — source authority scoring + deep verification (`/api/verification/...`)
- `assistant.py` + `provider.py` — Ask AI; `AIProvider` calls an OpenAI-compatible
  endpoint, format switched by `AI_API_FORMAT` (`chat_completions` vs `responses`),
  supports SSE streaming (`/api/ask/stream`)
- `conversations.py` — Ask AI chat history (edit/regenerate/delete messages)
- `article_reader.py` — clean-article extraction + cache (`article_cache` table)
- `ai_profiles.py` + `routers/ai_profiles.py` — multiple AI provider profiles
  (keys encrypted with `RADAR_ENCRYPTION_KEY`)
- `personalization.py` + `routers/personalization.py` — personalized "伯乐/Bole"
  scoring; draft→confirm profile flow, feedback log
- `radar_data.py` — loads items the backend reasons over; **`item_identity()`**
  (sha1 of normalized URL) is the canonical cross-table item key

Protected routes depend on `require_session`; `/health`, `/api/taxonomy`, and
`/api/read/{item_id}` are public.

### CI / deploy

`.github/workflows/update-news.yml` runs the pipeline twice hourly on `master`,
commits only the whitelisted `data/*.json` files. Private OPML is injected via the
base64 secret `FOLLOW_OPML_B64` (falls back to `feeds/follow.example.opml`).
`data/email-digest.json` is published only when `EMAIL_DIGEST_PUBLISH=1`.
GitHub Pages serves the static site; the backend is deployed separately (PM2 +
HTTPS reverse proxy to `127.0.0.1:8090`).

### Required backend env (production)

`RADAR_PUBLIC_BASE_URL`, `RADAR_ALLOWED_ORIGINS` (CORS), `RADAR_ADMIN_PASSWORD`,
`RADAR_SESSION_SECRET`, `RADAR_DB_PATH`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`,
`AI_API_FORMAT`. See `server/.env.example`.

## Project Conventions & Boundaries

- **Two-layer product**: a curated default view for ordinary AI enthusiasts; an
  advanced layer (custom OPML, source health, maintainer controls) behind it.
  Prefer better defaults and source quality over adding reader-facing choices.
- **Adding sources**: prefer official RSS/Atom/OPML. Add a built-in fetcher only
  when useful to most public visitors; run `scripts/evaluate_source_overlap.py`
  first, then register in `BUILT_IN_SOURCE_TASKS` and update `docs/SOURCE_COVERAGE.md`.
  Custom scrapers only for stable, public, high-signal sources.
- **Never commit secrets**: `feeds/follow.opml`, `.env`, API keys, cookies,
  tokens, admin passwords, private newsletter/email bodies, or locally generated
  `data/*.json`. The public repo must stay runnable without secrets.
- AgentMail / X API / private newsletters are optional, secret-backed, and
  **off by default**; keep their bodies out of public `data/*.json`.
