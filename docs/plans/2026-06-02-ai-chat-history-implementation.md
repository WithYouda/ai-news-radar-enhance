# AI Chat History Implementation Plan

> **Execution Skill:** Use `superpowers:subagent-driven-development` (same session) or `superpowers:executing-plans` (separate session) to implement this plan task-by-task.

**Goal:** Persist Ask AI conversation history and show it globally with system labels.

**Architecture:** Store each successful Ask AI turn in SQLite and expose authenticated history APIs. The frontend keeps the existing Ask AI sheet but adds a compact global history panel that can load stored answers back into the sheet.

**Tech Stack:** FastAPI, SQLite, vanilla JavaScript, pytest.

---

### Task 1: Database Schema

**Files:**
- Modify: `server/ai_radar_api/db.py`
- Test: `tests/test_ai_backend_db.py`

**Step 1: Write the failing test**

Assert `init_db()` creates an `ask_conversations` table.

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ai_backend_db.py::test_init_db_creates_required_tables -q`

**Step 3: Write minimal implementation**

Add `ask_conversations` to the SQLite schema with JSON text columns for scope, labels, and citations.

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_ai_backend_db.py::test_init_db_creates_required_tables -q`

### Task 2: Conversation Storage Module

**Files:**
- Create: `server/ai_radar_api/conversations.py`
- Test: `tests/test_ai_backend_conversations.py`

**Step 1: Write failing tests**

Cover storing a conversation, listing recent conversations, and reading one conversation.

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ai_backend_conversations.py -q`

**Step 3: Write minimal implementation**

Implement `build_ask_labels()`, `store_ask_conversation()`, `list_ask_conversations()`, and `get_ask_conversation()`.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ai_backend_conversations.py -q`

### Task 3: Ask API Persistence and History Endpoints

**Files:**
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_ask_api.py`

**Step 1: Write failing tests**

Assert `/api/ask` persists successful answers and `/api/ask/history` returns them with labels.

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ai_backend_ask_api.py -q`

**Step 3: Write minimal implementation**

Persist successful ask responses and add authenticated history endpoints.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ai_backend_ask_api.py -q`

### Task 4: Mobile History UI

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Write failing contract tests**

Assert the Ask AI sheet contains a history button/list container and the frontend references `/api/ask/history`.

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_mobile_frontend_contract.py -q`

**Step 3: Write minimal implementation**

Add a history button and panel to the Ask AI sheet, fetch recent history, render labels and previews, and allow selecting a stored answer.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mobile_frontend_contract.py -q`

### Task 5: Verification

Run:

```bash
.venv/bin/python -m pytest -q
node --check assets/app.js
git diff --check
```

Expected: all checks pass.
