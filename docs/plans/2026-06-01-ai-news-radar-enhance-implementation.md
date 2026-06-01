# AI News Radar Enhance Implementation Plan

> **Execution Skill:** Use `superpowers:subagent-driven-development` (same session) or `superpowers:executing-plans` (separate session) to implement this plan task-by-task.

**Goal:** Build the approved Scheme B personal AI reader: GitHub Pages remains the static reader, this VPS runs a FastAPI AI backend, and the mobile UI adds `今日 / 分类 / 核验 / 设置` plus a global `问 AI` assistant.

**Architecture:** Add a small authenticated FastAPI service with SQLite for taxonomy, classification, verification, settings, sessions, and AI answers. The static front end keeps the current desktop layout, progressively enhances mobile views, and falls back to existing public `data/*.json` when the backend is unavailable.

**Tech Stack:** Existing static HTML/CSS/JS, Python 3.11, FastAPI, SQLite, requests/httpx, pytest, GitHub Actions, GitHub Pages, PM2 or systemd, HTTPS reverse proxy.

---

## Ground Rules

- Do not commit `feeds/follow.opml`, `.env`, API keys, cookies, tokens, or private source data.
- Do not commit generated `data/*.json` unless the task explicitly updates the public data schema.
- Keep desktop behavior stable. Mobile changes should be gated by responsive CSS and view state.
- Write failing tests first for Python/backend behavior.
- For front-end structure, use static contract tests plus `node --check assets/app.js`.
- Commit after each task or small group of tightly related steps.

## Task 1: Add Backend Dependency And Config Foundation

**Files:**
- Create: `server/requirements.txt`
- Create: `server/ai_radar_api/__init__.py`
- Create: `server/ai_radar_api/config.py`
- Modify: `requirements-dev.txt`
- Test: `tests/test_ai_backend_config.py`

**Step 1: Write the failing config test**

```python
from pathlib import Path

from server.ai_radar_api.config import AppConfig


def test_config_reads_openai_compatible_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RADAR_PUBLIC_BASE_URL", "https://withyouda.github.io/ai-news-radar-enhance")
    monkeypatch.setenv("RADAR_ALLOWED_ORIGINS", "https://withyouda.github.io,https://example.com")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "secret-pass")
    monkeypatch.setenv("RADAR_SESSION_SECRET", "session-secret")
    monkeypatch.setenv("RADAR_DB_PATH", str(tmp_path / "radar.db"))
    monkeypatch.setenv("AI_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setenv("AI_MODEL", "test-model")

    config = AppConfig.from_env()

    assert config.public_base_url == "https://withyouda.github.io/ai-news-radar-enhance"
    assert config.allowed_origins == ["https://withyouda.github.io", "https://example.com"]
    assert config.admin_password == "secret-pass"
    assert config.session_secret == "session-secret"
    assert config.db_path == Path(tmp_path / "radar.db")
    assert config.ai_base_url == "https://api.example.com/v1"
    assert config.ai_api_key == "sk-test"
    assert config.ai_model == "test-model"


def test_config_has_safe_defaults(monkeypatch):
    for key in [
        "RADAR_PUBLIC_BASE_URL",
        "RADAR_ALLOWED_ORIGINS",
        "RADAR_ADMIN_PASSWORD",
        "RADAR_SESSION_SECRET",
        "RADAR_DB_PATH",
        "AI_BASE_URL",
        "AI_API_KEY",
        "AI_MODEL",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = AppConfig.from_env()

    assert config.public_base_url == "https://withyouda.github.io/ai-news-radar-enhance"
    assert config.allowed_origins == ["https://withyouda.github.io"]
    assert config.db_path.as_posix().endswith("server/data/radar.db")
    assert config.ai_model == "gpt-4.1-mini"
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_config.py -q
```

Expected: FAIL because `server.ai_radar_api.config` does not exist.

**Step 3: Add backend requirements**

Create `server/requirements.txt`:

```text
fastapi
uvicorn[standard]
httpx
pydantic
```

Modify `requirements-dev.txt`:

```text
-r requirements.txt
-r server/requirements.txt
pytest==8.3.4
PyYAML==6.0.2
```

**Step 4: Implement config**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _csv(value: str) -> list[str]:
    return [part.strip().rstrip("/") for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class AppConfig:
    public_base_url: str
    allowed_origins: list[str]
    admin_password: str
    session_secret: str
    db_path: Path
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    max_context_items: int = 40
    deep_verify_top_n: int = 3

    @classmethod
    def from_env(cls) -> "AppConfig":
        public_base_url = os.getenv(
            "RADAR_PUBLIC_BASE_URL",
            "https://withyouda.github.io/ai-news-radar-enhance",
        ).rstrip("/")
        allowed_origins = _csv(os.getenv("RADAR_ALLOWED_ORIGINS", "https://withyouda.github.io"))
        return cls(
            public_base_url=public_base_url,
            allowed_origins=allowed_origins,
            admin_password=os.getenv("RADAR_ADMIN_PASSWORD", ""),
            session_secret=os.getenv("RADAR_SESSION_SECRET", ""),
            db_path=Path(os.getenv("RADAR_DB_PATH", "server/data/radar.db")),
            ai_base_url=os.getenv("AI_BASE_URL", "").rstrip("/"),
            ai_api_key=os.getenv("AI_API_KEY", ""),
            ai_model=os.getenv("AI_MODEL", "gpt-4.1-mini"),
            max_context_items=int(os.getenv("RADAR_MAX_CONTEXT_ITEMS", "40")),
            deep_verify_top_n=int(os.getenv("RADAR_DEEP_VERIFY_TOP_N", "3")),
        )
```

**Step 5: Run test to verify it passes**

Run:

```bash
pytest tests/test_ai_backend_config.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/requirements.txt server/ai_radar_api/__init__.py server/ai_radar_api/config.py requirements-dev.txt tests/test_ai_backend_config.py
git commit -m "feat: add ai backend config"
```

## Task 2: Add SQLite Schema And Default Taxonomy Storage

**Files:**
- Create: `server/ai_radar_api/db.py`
- Create: `server/ai_radar_api/taxonomy.py`
- Test: `tests/test_ai_backend_db.py`
- Test: `tests/test_ai_backend_taxonomy.py`

**Step 1: Write the failing database test**

```python
import sqlite3

from server.ai_radar_api.db import connect_db, init_db


def test_init_db_creates_required_tables(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }

    assert {
        "settings",
        "sessions",
        "taxonomy_categories",
        "item_classifications",
        "verification_results",
        "source_scores",
    }.issubset(tables)


def test_connect_db_uses_row_factory(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    with connect_db(db_path) as conn:
        conn.execute("insert into settings(key, value_json, updated_at) values (?, ?, ?)", ("x", "1", "now"))
        row = conn.execute("select key from settings where key = ?", ("x",)).fetchone()
    assert row["key"] == "x"
```

**Step 2: Write the failing taxonomy test**

```python
from server.ai_radar_api.db import init_db
from server.ai_radar_api.taxonomy import DEFAULT_TAXONOMY, list_taxonomy, seed_default_taxonomy


def test_seed_default_taxonomy_contains_seven_top_level_categories(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)
    seed_default_taxonomy(db_path)

    taxonomy = list_taxonomy(db_path)

    assert [row["label"] for row in taxonomy if row["parent_id"] is None] == [
        "模型与产品",
        "Agent 与工作流",
        "开发者工具",
        "开源与项目",
        "研究与评测",
        "公司与行业",
        "算力与基础设施",
    ]
    assert any(row["label"] == "MCP / 插件生态" for row in taxonomy)
    assert DEFAULT_TAXONOMY[0]["children"][0]["label"] == "模型发布"
```

**Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ai_backend_db.py tests/test_ai_backend_taxonomy.py -q
```

Expected: FAIL because modules do not exist.

**Step 4: Implement `db.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
create table if not exists settings (
  key text primary key,
  value_json text not null,
  updated_at text not null
);

create table if not exists sessions (
  session_id_hash text primary key,
  expires_at text not null,
  created_at text not null
);

create table if not exists taxonomy_categories (
  id text primary key,
  label text not null,
  parent_id text,
  priority integer not null default 0,
  enabled integer not null default 1,
  rule_hints_json text not null default '[]',
  updated_at text not null
);

create table if not exists item_classifications (
  item_id text primary key,
  url text not null,
  title_hash text not null,
  top_category text not null,
  sub_category text,
  confidence real not null,
  reason text not null,
  taxonomy_version text not null,
  model text not null,
  manual_override_json text,
  classified_at text not null
);

create table if not exists verification_results (
  item_id text primary key,
  url text not null,
  status text not null,
  authority_score integer not null,
  authority_reason text not null,
  evidence_json text not null,
  deep_verified integer not null default 0,
  manual_score integer,
  manual_note text,
  model text not null,
  verified_at text not null
);

create table if not exists source_scores (
  source_id text primary key,
  source_name text not null,
  base_score integer not null default 50,
  ai_score integer,
  manual_score integer,
  reason text,
  updated_at text not null
);
"""


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect_db(db_path) as conn:
        conn.executescript(SCHEMA)
```

**Step 5: Implement `taxonomy.py`**

Implement `DEFAULT_TAXONOMY` exactly from the design document, plus:

```python
def seed_default_taxonomy(db_path: str | Path) -> None:
    ...


def list_taxonomy(db_path: str | Path) -> list[dict]:
    ...
```

Use deterministic ids such as `models-products`, `models-products/model-release`.

**Step 6: Run tests**

Run:

```bash
pytest tests/test_ai_backend_db.py tests/test_ai_backend_taxonomy.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add server/ai_radar_api/db.py server/ai_radar_api/taxonomy.py tests/test_ai_backend_db.py tests/test_ai_backend_taxonomy.py
git commit -m "feat: add backend sqlite taxonomy storage"
```

## Task 3: Add FastAPI App, CORS, Health, Login, And Session Cookies

**Files:**
- Create: `server/ai_radar_api/auth.py`
- Create: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_auth.py`

**Step 1: Write failing auth tests**

```python
from fastapi.testclient import TestClient

from server.ai_radar_api.config import AppConfig
from server.ai_radar_api.main import create_app


def make_client(tmp_path, password="pass"):
    config = AppConfig(
        public_base_url="https://withyouda.github.io/ai-news-radar-enhance",
        allowed_origins=["https://withyouda.github.io"],
        admin_password=password,
        session_secret="test-session-secret",
        db_path=tmp_path / "radar.db",
        ai_base_url="https://api.example.com/v1",
        ai_api_key="sk-test",
        ai_model="test-model",
    )
    return TestClient(create_app(config))


def test_health_is_public(tmp_path):
    client = make_client(tmp_path)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_login_rejects_wrong_password(tmp_path):
    client = make_client(tmp_path)
    res = client.post("/api/auth/login", json={"password": "wrong"})
    assert res.status_code == 401


def test_login_sets_secure_httponly_cookie(tmp_path):
    client = make_client(tmp_path)
    res = client.post("/api/auth/login", json={"password": "pass"})
    assert res.status_code == 200
    cookie = res.headers["set-cookie"]
    assert "radar_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=none" in cookie
    assert "Secure" in cookie


def test_me_requires_session(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/me").status_code == 401
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_auth.py -q
```

Expected: FAIL because app/auth modules are incomplete.

**Step 3: Implement auth helpers**

In `auth.py`, implement:

```python
def create_session(config: AppConfig) -> str: ...
def hash_session(session_id: str, secret: str) -> str: ...
def store_session(db_path: Path, session_id: str, secret: str, ttl_hours: int = 24 * 14) -> None: ...
def validate_session(db_path: Path, session_id: str, secret: str) -> bool: ...
def delete_session(db_path: Path, session_id: str, secret: str) -> None: ...
```

Use `secrets.token_urlsafe(32)` and `hmac`/`hashlib.sha256`. Store only hashed
session ids.

**Step 4: Implement `main.py`**

Create `create_app(config: AppConfig | None = None) -> FastAPI`.

Required behavior:

- initialize DB and seed taxonomy
- add `CORSMiddleware` with `allow_origins=config.allowed_origins`
- set `allow_credentials=True`
- public `GET /health`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`

Cookie settings:

```python
response.set_cookie(
    "radar_session",
    session_id,
    httponly=True,
    secure=True,
    samesite="none",
    max_age=14 * 24 * 60 * 60,
)
```

**Step 5: Run tests**

Run:

```bash
pytest tests/test_ai_backend_auth.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/ai_radar_api/auth.py server/ai_radar_api/main.py tests/test_ai_backend_auth.py
git commit -m "feat: add authenticated ai backend app"
```

## Task 4: Add Radar Data Loader And Context Builder

**Files:**
- Create: `server/ai_radar_api/radar_data.py`
- Test: `tests/test_ai_backend_radar_data.py`

**Step 1: Write failing tests**

```python
from server.ai_radar_api.radar_data import build_context, item_identity, merge_item_metadata


def test_item_identity_prefers_stable_url():
    a = item_identity({"title": "A", "url": "https://example.com/a?utm_source=x"})
    b = item_identity({"title": "Different", "url": "https://example.com/a"})
    assert a == b


def test_build_context_limits_and_cites_items():
    items = [
        {"title": "OpenAI ships model", "url": "https://example.com/a", "ai_score": 0.9, "site_name": "OpenAI"},
        {"title": "Low signal", "url": "https://example.com/b", "ai_score": 0.1, "site_name": "Blog"},
    ]
    context = build_context(items, question="OpenAI?", max_items=1)
    assert "[1] OpenAI ships model" in context
    assert "https://example.com/a" in context
    assert "Low signal" not in context


def test_merge_item_metadata_adds_classification_and_verification():
    item = {"title": "A", "url": "https://example.com/a"}
    merged = merge_item_metadata(
        item,
        classification={"top_category": "模型与产品", "sub_category": "模型发布"},
        verification={"authority_score": 88, "status": "verified"},
    )
    assert merged["top_category"] == "模型与产品"
    assert merged["sub_category"] == "模型发布"
    assert merged["authority_score"] == 88
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_radar_data.py -q
```

Expected: FAIL.

**Step 3: Implement radar data helpers**

Implement:

```python
def normalize_public_url(url: str) -> str: ...
def item_identity(item: dict) -> str: ...
def fetch_public_json(config: AppConfig, path: str) -> dict: ...
def load_latest_items(config: AppConfig, mode: str = "ai") -> list[dict]: ...
def build_context(items: list[dict], question: str, max_items: int = 40) -> str: ...
def merge_item_metadata(item: dict, classification: dict | None, verification: dict | None) -> dict: ...
```

Ranking for context:

1. title/source text matches question keywords
2. higher `ai_score`
3. newer `published_at` / `first_seen_at`

**Step 4: Run tests**

Run:

```bash
pytest tests/test_ai_backend_radar_data.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add server/ai_radar_api/radar_data.py tests/test_ai_backend_radar_data.py
git commit -m "feat: add radar context builder"
```

## Task 5: Add Rule-Based Classification Service

**Files:**
- Create: `server/ai_radar_api/classifier.py`
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_classifier.py`

**Step 1: Write failing classifier tests**

```python
from server.ai_radar_api.classifier import classify_item
from server.ai_radar_api.taxonomy import DEFAULT_TAXONOMY


def test_classifies_model_release():
    result = classify_item(
        {"title": "OpenAI releases GPT-5 API and pricing", "source": "OpenAI News"},
        DEFAULT_TAXONOMY,
    )
    assert result["top_category"] == "模型与产品"
    assert result["sub_category"] in {"模型发布", "API / 平台更新", "价格 / 访问权限"}
    assert result["confidence"] >= 0.6


def test_classifies_mcp_agent_workflow():
    result = classify_item(
        {"title": "New MCP plugin lets agents call browser tools", "source": "GitHub"},
        DEFAULT_TAXONOMY,
    )
    assert result["top_category"] == "Agent 与工作流"
    assert result["sub_category"] == "MCP / 插件生态"


def test_falls_back_to_developer_tools():
    result = classify_item(
        {"title": "New SDK adds tracing and monitoring for RAG apps", "source": "Blog"},
        DEFAULT_TAXONOMY,
    )
    assert result["top_category"] == "开发者工具"
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_classifier.py -q
```

Expected: FAIL.

**Step 3: Implement deterministic V1 classifier**

Implement `classify_item(item, taxonomy)` with simple weighted keyword rules.
Return:

```python
{
    "top_category": "...",
    "sub_category": "...",
    "confidence": 0.0,
    "reason": "matched keywords: ...",
    "model": "rules-v1",
}
```

This is the local fallback. Later tasks can add AI classification for ambiguous
items, but V1 must work without model calls.

**Step 4: Add API endpoint**

In `main.py`, add authenticated:

```text
POST /api/classify
```

Request:

```json
{"items": [{"title": "...", "url": "..."}]}
```

Response:

```json
{"items": [{"item_id": "...", "top_category": "...", "sub_category": "..."}]}
```

Store results in `item_classifications`.

**Step 5: Run tests**

Run:

```bash
pytest tests/test_ai_backend_classifier.py tests/test_ai_backend_auth.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/ai_radar_api/classifier.py server/ai_radar_api/main.py tests/test_ai_backend_classifier.py
git commit -m "feat: add taxonomy classifier"
```

## Task 6: Add Verification And Authority Scoring

**Files:**
- Create: `server/ai_radar_api/verification.py`
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_verification.py`

**Step 1: Write failing verification tests**

```python
from server.ai_radar_api.verification import score_authority, verify_from_page_text


def test_official_source_scores_high():
    result = score_authority(
        item={"site_name": "Official AI Updates", "source": "OpenAI News", "url": "https://openai.com/news/test"},
        page_text="OpenAI announced a new API update in its official changelog.",
        evidence_links=["https://openai.com/news/test"],
        deep=False,
    )
    assert result["authority_score"] >= 85
    assert result["status"] == "verified"


def test_third_party_with_primary_links_scores_medium_high():
    result = score_authority(
        item={"site_name": "Example Blog", "source": "AI", "url": "https://blog.example/a"},
        page_text="This report cites the OpenAI announcement and GitHub release.",
        evidence_links=["https://openai.com/news/a", "https://github.com/org/repo/releases/tag/v1"],
        deep=False,
    )
    assert 70 <= result["authority_score"] <= 84


def test_summary_without_evidence_scores_low():
    result = score_authority(
        item={"site_name": "Aggregator", "source": "Hot", "url": "https://example.com/a"},
        page_text="People say a new model may be coming soon.",
        evidence_links=[],
        deep=False,
    )
    assert result["authority_score"] < 50


def test_verify_from_page_text_extracts_primary_links():
    result = verify_from_page_text(
        {"title": "A", "url": "https://example.com/a"},
        '<a href="https://openai.com/news/a">official post</a>',
        deep=False,
    )
    assert "https://openai.com/news/a" in result["evidence_links"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_verification.py -q
```

Expected: FAIL.

**Step 3: Implement verification helpers**

Implement:

```python
PRIMARY_DOMAINS = (
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "ai.googleblog.com",
    "huggingface.co",
    "github.com",
    "arxiv.org",
    "paperswithcode.com",
    "nvidia.com",
    "microsoft.com",
)

def extract_links(html: str) -> list[str]: ...
def is_primary_evidence(url: str) -> bool: ...
def score_authority(item: dict, page_text: str, evidence_links: list[str], deep: bool) -> dict: ...
def verify_from_page_text(item: dict, html: str, deep: bool = False) -> dict: ...
def fetch_and_verify(item: dict, timeout_seconds: int = 12, deep: bool = False) -> dict: ...
```

Use simple deterministic scoring first. AI explanation can be added later through
the provider path.

**Step 4: Add API endpoints**

In `main.py`, add authenticated:

```text
GET  /api/verification/items
POST /api/verification/{item_id}/verify
POST /api/verification/{item_id}/deep-verify
```

The deep endpoint sets `deep_verified=1`.

**Step 5: Run tests**

Run:

```bash
pytest tests/test_ai_backend_verification.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/ai_radar_api/verification.py server/ai_radar_api/main.py tests/test_ai_backend_verification.py
git commit -m "feat: add authority verification"
```

## Task 7: Add OpenAI-Compatible Provider And Ask Endpoint

**Files:**
- Create: `server/ai_radar_api/provider.py`
- Create: `server/ai_radar_api/assistant.py`
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_assistant.py`

**Step 1: Write failing assistant tests**

```python
from server.ai_radar_api.assistant import build_ask_messages


def test_build_ask_messages_requires_citations():
    messages = build_ask_messages(
        question="总结今天最重要的两条",
        context="[1] OpenAI ships model | OpenAI | https://example.com/a",
    )
    text = "\n".join(m["content"] for m in messages)
    assert "引用" in text
    assert "不知道" in text or "不足" in text
    assert "https://example.com/a" in text


def test_build_ask_messages_keeps_user_question():
    messages = build_ask_messages("这条有一手来源吗？", "[1] A | Source | https://a.com")
    assert messages[-1]["role"] == "user"
    assert "这条有一手来源吗" in messages[-1]["content"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_assistant.py -q
```

Expected: FAIL.

**Step 3: Implement provider**

Implement:

```python
class AIProvider:
    def __init__(self, config: AppConfig): ...
    async def chat(self, messages: list[dict], temperature: float = 0.2) -> str: ...
```

Call:

```text
POST {AI_BASE_URL}/chat/completions
Authorization: Bearer {AI_API_KEY}
```

Body:

```json
{
  "model": "...",
  "messages": [...],
  "temperature": 0.2
}
```

If `AI_BASE_URL` or `AI_API_KEY` is missing, raise a clear 503-style error.

**Step 4: Implement assistant**

Implement:

```python
def build_ask_messages(question: str, context: str) -> list[dict]: ...
async def answer_question(config: AppConfig, question: str, items: list[dict], provider: AIProvider | None = None) -> dict: ...
```

Answer response shape:

```json
{
  "answer": "...",
  "citations": [{"title": "...", "url": "..."}],
  "model": "..."
}
```

**Step 5: Add endpoint**

In `main.py`, add authenticated:

```text
POST /api/ask
```

Request:

```json
{
  "question": "总结今天最重要的 5 条",
  "scope": "today",
  "item_id": null,
  "category": null
}
```

Response:

```json
{
  "answer": "...",
  "citations": [...]
}
```

**Step 6: Run tests**

Run:

```bash
pytest tests/test_ai_backend_assistant.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add server/ai_radar_api/provider.py server/ai_radar_api/assistant.py server/ai_radar_api/main.py tests/test_ai_backend_assistant.py
git commit -m "feat: add ai assistant endpoint"
```

## Task 8: Add Backend Settings And Deep Verification Policy

**Files:**
- Create: `server/ai_radar_api/settings.py`
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_settings.py`

**Step 1: Write failing settings test**

```python
from server.ai_radar_api.db import init_db
from server.ai_radar_api.settings import get_settings, update_settings


def test_settings_default_deep_verification_is_limited(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    settings = get_settings(db_path)

    assert settings["deep_verification_enabled"] is False
    assert settings["deep_verification_scope"] == "bole_picks_and_topic_top_n"
    assert settings["deep_verification_top_n"] == 3


def test_update_settings_persists_values(tmp_path):
    db_path = tmp_path / "radar.db"
    init_db(db_path)

    update_settings(db_path, {"deep_verification_enabled": True, "deep_verification_top_n": 2})
    settings = get_settings(db_path)

    assert settings["deep_verification_enabled"] is True
    assert settings["deep_verification_top_n"] == 2
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_backend_settings.py -q
```

Expected: FAIL.

**Step 3: Implement settings**

Implement JSON settings stored in the `settings` table.

Default:

```python
DEFAULT_SETTINGS = {
    "deep_verification_enabled": False,
    "deep_verification_scope": "bole_picks_and_topic_top_n",
    "deep_verification_top_n": 3,
    "mobile_default_view": "today",
}
```

**Step 4: Add settings API**

In `main.py`, add authenticated:

```text
GET /api/settings
PUT /api/settings
```

Validate that `deep_verification_scope` can only be
`bole_picks_and_topic_top_n` in V1.

**Step 5: Run tests**

Run:

```bash
pytest tests/test_ai_backend_settings.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/ai_radar_api/settings.py server/ai_radar_api/main.py tests/test_ai_backend_settings.py
git commit -m "feat: add backend settings"
```

## Task 9: Add Front-End Backend Config And API Client

**Files:**
- Create: `assets/config.js`
- Modify: `index.html`
- Modify: `assets/app.js`
- Test: `tests/test_frontend_static_contract.py`

**Step 1: Write failing static contract test**

```python
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
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_frontend_static_contract.py -q
```

Expected: FAIL.

**Step 3: Add config file**

Create `assets/config.js`:

```javascript
window.AI_NEWS_RADAR_CONFIG = {
  apiBaseUrl: "",
};
```

This file contains no secrets. On GitHub Pages, set the public backend URL here
when the backend is ready.

**Step 4: Load config before app**

In `index.html`, add before `assets/app.js`:

```html
<script src="./assets/config.js?v=ai-backend-0601"></script>
```

**Step 5: Add API client helpers**

In `assets/app.js`, add near the top:

```javascript
const appConfig = window.AI_NEWS_RADAR_CONFIG || {};
const apiBaseUrl = String(appConfig.apiBaseUrl || "").replace(/\/$/, "");

async function apiFetch(path, options = {}) {
  if (!apiBaseUrl) throw new Error("AI 后端未配置");
  const res = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `API 请求失败: ${res.status}`);
  }
  return res.json();
}
```

**Step 6: Run checks**

Run:

```bash
pytest tests/test_frontend_static_contract.py -q
node --check assets/app.js
```

Expected: PASS.

**Step 7: Commit**

```bash
git add assets/config.js index.html assets/app.js tests/test_frontend_static_contract.py
git commit -m "feat: add frontend ai backend client"
```

## Task 10: Add Mobile App Shell Navigation

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Write failing mobile shell test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_nav_and_ask_entry_exist():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="mobileBottomNav"' in html
    assert 'data-view="today"' in html
    assert 'data-view="categories"' in html
    assert 'data-view="verification"' in html
    assert 'data-view="settings"' in html
    assert 'id="askAiButton"' in html


def test_mobile_css_is_scoped_to_small_screens():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert ".mobile-bottom-nav" in css
    assert "@media (max-width: 760px)" in css
    assert "padding-bottom" in css
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
```

Expected: FAIL.

**Step 3: Add mobile nav markup**

Before `</body>` in `index.html`:

```html
<nav id="mobileBottomNav" class="mobile-bottom-nav" aria-label="移动端主导航">
  <button type="button" class="mobile-nav-btn active" data-view="today">今日</button>
  <button type="button" class="mobile-nav-btn" data-view="categories">分类</button>
  <button type="button" class="mobile-nav-btn" data-view="verification">核验</button>
  <button type="button" class="mobile-nav-btn" data-view="settings">设置</button>
</nav>
<button id="askAiButton" class="ask-ai-fab" type="button">问 AI</button>
```

**Step 4: Add view state**

In `assets/app.js`, add:

```javascript
state.mobileView = "today";

function setMobileView(view) {
  state.mobileView = view;
  document.querySelectorAll("[data-mobile-view]").forEach((el) => {
    el.hidden = el.dataset.mobileView !== view;
  });
  document.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
}
```

Hook all `.mobile-nav-btn` click events.

**Step 5: Add mobile-only CSS**

In `assets/styles.css`, add outside media query:

```css
.mobile-bottom-nav,
.ask-ai-fab {
  display: none;
}
```

Inside `@media (max-width: 760px)`:

```css
.shell {
  padding-bottom: 96px;
}

.mobile-bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.96);
}

.mobile-nav-btn {
  min-height: 56px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
}

.mobile-nav-btn.active {
  color: var(--accent);
  font-weight: 800;
}

.ask-ai-fab {
  position: fixed;
  right: 14px;
  bottom: 72px;
  z-index: 31;
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  border: 1px solid rgba(18, 106, 115, 0.4);
  border-radius: 999px;
  padding: 0 14px;
  color: #fff;
  background: var(--accent);
  box-shadow: 0 8px 22px rgba(23, 23, 23, 0.16);
}
```

**Step 6: Run checks**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
node --check assets/app.js
```

Expected: PASS.

**Step 7: Commit**

```bash
git add index.html assets/app.js assets/styles.css tests/test_mobile_frontend_contract.py
git commit -m "feat: add mobile app shell"
```

## Task 11: Add Category View With Dynamic Taxonomy

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Extend failing contract test**

Add:

```python
def test_category_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'data-mobile-view="categories"' in html
    assert 'id="categoryView"' in html
    assert "loadTaxonomy" in js
    assert "renderCategoryView" in js
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
```

Expected: FAIL.

**Step 3: Add category container**

Add an unframed section inside `.shell`:

```html
<section id="categoryView" class="mobile-view-panel" data-mobile-view="categories" hidden>
  <div class="mobile-section-head">
    <h2>分类</h2>
    <span id="categoryMeta">加载中...</span>
  </div>
  <div id="categoryGrid" class="category-grid"></div>
  <div id="categoryDetail" class="category-detail"></div>
</section>
```

**Step 4: Add taxonomy loading**

In `assets/app.js`, add fallback taxonomy matching the design. Then:

```javascript
async function loadTaxonomy() {
  if (!apiBaseUrl) return fallbackTaxonomy;
  try {
    const payload = await apiFetch("/api/taxonomy");
    return payload.categories || fallbackTaxonomy;
  } catch (_) {
    return fallbackTaxonomy;
  }
}
```

**Step 5: Render only active subcategories**

Implement:

```javascript
function itemCategory(item) {
  return item.top_category || item.ai_label || "";
}

function renderCategoryView(taxonomy, items) {
  ...
}
```

Top-level cards show count. Subcategories render only when at least one item
matches that subcategory.

**Step 6: Run checks**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
node --check assets/app.js
```

Expected: PASS.

**Step 7: Commit**

```bash
git add index.html assets/app.js assets/styles.css tests/test_mobile_frontend_contract.py
git commit -m "feat: add mobile category view"
```

## Task 12: Add Verification Page UI

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Extend failing contract test**

```python
def test_verification_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'data-mobile-view="verification"' in html
    assert 'id="verificationView"' in html
    assert "loadVerificationSummary" in js
    assert "renderVerificationView" in js
    assert "deepVerifyItem" in js
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
```

Expected: FAIL.

**Step 3: Add verification markup**

```html
<section id="verificationView" class="mobile-view-panel" data-mobile-view="verification" hidden>
  <div class="mobile-section-head">
    <h2>核验</h2>
    <span id="verificationMeta">未连接后端</span>
  </div>
  <div id="verificationSummary" class="verification-summary"></div>
  <div id="verificationList" class="verification-list"></div>
</section>
```

**Step 4: Add front-end functions**

Implement:

```javascript
async function loadVerificationSummary() {
  if (!apiBaseUrl) return { items: [], unavailable: true };
  return apiFetch("/api/verification/items");
}

async function deepVerifyItem(itemId) {
  return apiFetch(`/api/verification/${encodeURIComponent(itemId)}/deep-verify`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

function renderVerificationView(payload) {
  ...
}
```

Show sections:

- 待核验
- 低可信
- 深度核验队列
- 第三方信源评分
- 一手来源覆盖

**Step 5: Add per-card deep verification action**

In `renderItemNode`, add a compact action button:

```javascript
const verifyBtn = document.createElement("button");
verifyBtn.type = "button";
verifyBtn.className = "card-action verify-action";
verifyBtn.textContent = "深度核验";
verifyBtn.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  deepVerifyItem(item.item_id || itemIdentity(item));
});
node.appendChild(verifyBtn);
```

**Step 6: Run checks**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
node --check assets/app.js
```

Expected: PASS.

**Step 7: Commit**

```bash
git add index.html assets/app.js assets/styles.css tests/test_mobile_frontend_contract.py
git commit -m "feat: add verification workspace"
```

## Task 13: Add Global Ask AI Sheet

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Extend failing contract test**

```python
def test_ask_ai_sheet_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'id="askAiSheet"' in html
    assert 'id="askAiInput"' in html
    assert "openAskAi" in js
    assert "submitAskAi" in js
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
```

Expected: FAIL.

**Step 3: Add sheet markup**

```html
<section id="askAiSheet" class="ask-ai-sheet" hidden aria-label="问 AI">
  <div class="ask-ai-panel">
    <div class="ask-ai-head">
      <h2>问 AI</h2>
      <button id="askAiClose" type="button">关闭</button>
    </div>
    <div id="askAiContext" class="ask-ai-context">今日</div>
    <textarea id="askAiInput" rows="3" placeholder="问今天的信息流..."></textarea>
    <button id="askAiSubmit" type="button">发送</button>
    <div id="askAiAnswer" class="ask-ai-answer"></div>
  </div>
</section>
```

**Step 4: Add JS behavior**

Implement:

```javascript
function currentAskScope() {
  return { scope: state.mobileView || "today" };
}

function openAskAi(extraContext = {}) {
  ...
}

async function submitAskAi() {
  const question = askAiInputEl.value.trim();
  if (!question) return;
  const payload = await apiFetch("/api/ask", {
    method: "POST",
    body: JSON.stringify({ question, ...currentAskScope() }),
  });
  renderAskAnswer(payload);
}
```

Answers must show citations as clickable links when returned.

**Step 5: Add CSS**

Use a bottom sheet on mobile and a right-side panel on desktop if visible. Keep
the sheet outside cards.

**Step 6: Run checks**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
node --check assets/app.js
```

Expected: PASS.

**Step 7: Commit**

```bash
git add index.html assets/app.js assets/styles.css tests/test_mobile_frontend_contract.py
git commit -m "feat: add ask ai sheet"
```

## Task 14: Add Settings/Login UI

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Extend failing contract test**

```python
def test_settings_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'id="settingsView"' in html
    assert 'id="adminPasswordInput"' in html
    assert "loginAdmin" in js
    assert "saveSettings" in js
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
```

Expected: FAIL.

**Step 3: Add settings markup**

```html
<section id="settingsView" class="mobile-view-panel" data-mobile-view="settings" hidden>
  <div class="mobile-section-head">
    <h2>设置</h2>
    <span id="settingsStatus">未登录</span>
  </div>
  <div class="settings-panel">
    <input id="adminPasswordInput" type="password" placeholder="管理员密码" />
    <button id="loginButton" type="button">登录</button>
    <label class="settings-toggle">
      <input id="deepVerificationToggle" type="checkbox" />
      <span>默认深度核验伯乐精选与分类 Top N</span>
    </label>
    <label class="field">
      <span>Top N</span>
      <input id="deepVerificationTopN" type="number" min="1" max="10" value="3" />
    </label>
    <button id="saveSettingsButton" type="button">保存设置</button>
  </div>
</section>
```

**Step 4: Add JS behavior**

Implement:

```javascript
async function loginAdmin() { ... }
async function loadSettings() { ... }
async function saveSettings() { ... }
```

Use `/api/auth/login`, `/api/me`, `/api/settings`.

**Step 5: Run checks**

Run:

```bash
pytest tests/test_mobile_frontend_contract.py -q
node --check assets/app.js
```

Expected: PASS.

**Step 6: Commit**

```bash
git add index.html assets/app.js assets/styles.css tests/test_mobile_frontend_contract.py
git commit -m "feat: add mobile settings login"
```

## Task 15: Add PWA Installability

**Files:**
- Create: `manifest.webmanifest`
- Create: `sw.js`
- Modify: `index.html`
- Test: `tests/test_pwa_contract.py`

**Step 1: Write failing PWA test**

```python
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
```

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_pwa_contract.py -q
```

Expected: FAIL.

**Step 3: Add manifest**

```json
{
  "name": "AI News Radar",
  "short_name": "AI Radar",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "background_color": "#f6f6f2",
  "theme_color": "#126a73",
  "icons": [
    {
      "src": "./assets/logo.svg",
      "sizes": "any",
      "type": "image/svg+xml"
    }
  ]
}
```

**Step 4: Add minimal service worker**

```javascript
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
```

Keep caching minimal in V1 to avoid stale news bugs.

**Step 5: Link it**

In `index.html`:

```html
<link rel="manifest" href="./manifest.webmanifest" />
<script>
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(() => {});
    });
  }
</script>
```

**Step 6: Run checks**

Run:

```bash
pytest tests/test_pwa_contract.py -q
node --check sw.js
```

Expected: PASS.

**Step 7: Commit**

```bash
git add manifest.webmanifest sw.js index.html tests/test_pwa_contract.py
git commit -m "feat: add pwa install support"
```

## Task 16: Add Server Runbook And Deployment Config

**Files:**
- Create: `server/README.md`
- Create: `server/.env.example`
- Optional create: `server/pm2.ecosystem.config.cjs`
- Modify: `README.md`
- Modify: `index.html`
- Modify: `.github/workflows/update-news.yml`

**Step 1: Write deployment notes**

`server/.env.example`:

```text
RADAR_PUBLIC_BASE_URL=https://withyouda.github.io/ai-news-radar-enhance
RADAR_ALLOWED_ORIGINS=https://withyouda.github.io
RADAR_ADMIN_PASSWORD=change-me
RADAR_SESSION_SECRET=change-me-long-random-value
RADAR_DB_PATH=server/data/radar.db
RADAR_MAX_CONTEXT_ITEMS=40
RADAR_DEEP_VERIFY_TOP_N=3
AI_BASE_URL=
AI_API_KEY=
AI_MODEL=
```

`server/README.md` should include:

```bash
python3 -m venv .venv-server
source .venv-server/bin/activate
pip install -r server/requirements.txt
uvicorn server.ai_radar_api.main:app --host 127.0.0.1 --port 8090
```

PM2 option:

```bash
pm2 start ".venv-server/bin/uvicorn" --name ai-news-radar-api -- server.ai_radar_api.main:app --host 127.0.0.1 --port 8090
pm2 save
```

Reverse proxy requirement:

```text
Public HTTPS -> 127.0.0.1:8090
```

**Step 2: Update public metadata**

In `index.html`, update:

```html
<link rel="canonical" href="https://withyouda.github.io/ai-news-radar-enhance/" />
<meta property="og:url" content="https://withyouda.github.io/ai-news-radar-enhance/" />
```

**Step 3: Reduce Action schedule if desired**

In `.github/workflows/update-news.yml`, change:

```yaml
schedule:
  - cron: "0 * * * *"
```

**Step 4: Document GitHub settings**

In `README.md`, add a short personal deployment section:

```text
Pages:
Settings -> Pages -> Deploy from branch -> master / root

Secrets:
FOLLOW_OPML_B64

Variables:
RSS_MAX_FEEDS=10
```

**Step 5: Run checks**

Run:

```bash
python -m py_compile scripts/update_news.py
node --check assets/app.js
git diff --check
```

Expected: PASS.

**Step 6: Commit**

```bash
git add server/README.md server/.env.example README.md index.html .github/workflows/update-news.yml
git commit -m "docs: add enhanced deployment runbook"
```

## Task 17: End-To-End Local Verification

**Files:**
- No required source changes unless verification finds bugs.

**Step 1: Install dependencies**

Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Expected: dependencies install successfully.

**Step 2: Run Python tests**

Run:

```bash
pytest -q
```

Expected: PASS.

**Step 3: Run syntax checks**

Run:

```bash
python -m py_compile scripts/update_news.py
python -m py_compile server/ai_radar_api/*.py
node --check assets/app.js
node --check sw.js
git diff --check
```

Expected: PASS.

**Step 4: Run backend locally**

Run:

```bash
RADAR_ADMIN_PASSWORD=local-pass \
RADAR_SESSION_SECRET=local-session-secret \
AI_BASE_URL=https://api.example.com/v1 \
AI_API_KEY=sk-placeholder \
AI_MODEL=test-model \
uvicorn server.ai_radar_api.main:app --host 127.0.0.1 --port 8090
```

Expected:

```text
http://127.0.0.1:8090/health
```

returns:

```json
{"ok": true}
```

**Step 5: Run static site locally**

In another shell:

```bash
python -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080
```

Expected:

- Desktop layout still works.
- Mobile width shows bottom nav.
- `问 AI` opens the sheet.
- `分类` and `核验` do not break when backend is unavailable.

**Step 6: Commit any verification fixes**

If verification required fixes:

```bash
git add <fixed-files>
git commit -m "fix: stabilize enhanced reader verification"
```

## Task 18: Production Deployment

**Files:**
- Modify only if production verification reveals config/doc issues.

**Step 1: Push branch**

Run:

```bash
git status --short
git push
```

Expected: only intentional source/doc changes are pushed. Generated `data/*.json`
changes remain uncommitted unless deliberately refreshed.

**Step 2: Configure GitHub Pages**

In GitHub:

```text
Settings -> Pages
Source: Deploy from a branch
Branch: master
Folder: /root
```

Expected:

```text
https://withyouda.github.io/ai-news-radar-enhance/
```

**Step 3: Configure GitHub Actions**

Secrets:

```text
FOLLOW_OPML_B64
```

Variables:

```text
RSS_MAX_FEEDS=10
```

Run:

```text
Actions -> Update AI News Snapshot -> Run workflow
```

Expected: workflow completes and commits public `data/*.json`.

**Step 4: Deploy AI backend on VPS**

Install and run:

```bash
python3 -m venv .venv-server
source .venv-server/bin/activate
pip install -r server/requirements.txt
pm2 start ".venv-server/bin/uvicorn" --name ai-news-radar-api -- server.ai_radar_api.main:app --host 127.0.0.1 --port 8090
pm2 save
```

Set environment variables through the chosen process manager or shell profile.

**Step 5: Add HTTPS reverse proxy**

Required:

```text
https://<server-ip-or-domain> -> http://127.0.0.1:8090
```

Validation:

```bash
curl -I https://<server-ip-or-domain>/health
```

Expected:

```text
HTTP/2 200
```

or another successful 200 response.

**Step 6: Configure frontend backend URL**

In `assets/config.js`:

```javascript
window.AI_NEWS_RADAR_CONFIG = {
  apiBaseUrl: "https://<server-ip-or-domain>",
};
```

Commit and push:

```bash
git add assets/config.js
git commit -m "chore: configure ai backend url"
git push
```

**Step 7: Verify deployed reader**

On phone:

- Open GitHub Pages URL.
- Add to home screen if PWA prompt is available.
- Login in `设置`.
- Open `问 AI`.
- Ask: `总结今天最重要的 5 条，并标出一手来源。`
- Open `核验`, trigger one `深度核验`.

Expected:

- No mixed-content error.
- Login cookie works across GitHub Pages and backend.
- AI answer returns citations.
- Deep verification result is cached and visible.

