# AI Provider Reader Actions Implementation Plan

> **Execution Skill:** Use `superpowers:subagent-driven-development` (same session) or `superpowers:executing-plans` (separate session) to implement this plan task-by-task.

**Goal:** Add encrypted AI provider profiles, configurable translation and reading-assistant providers, translation/original toggling, article summary, and article fact checking from the clean reader.

**Architecture:** Store provider profiles and usage selections in the existing SQLite-backed settings system, encrypt sensitive provider fields with a runtime master key, and refactor AI calls so translation and reading-assistant tasks can choose a provider profile. The static frontend adds mobile-first settings controls and reader toolbar actions that call the existing Ask AI flow for summary and fact checking.

**Tech Stack:** Python 3.11, FastAPI, SQLite, httpx, pytest, static HTML/CSS/JS, Node syntax check, PM2 runtime env.

---

## Ground Rules

- Use `test-driven-development` for each behavior change.
- Do not commit secrets, `.env`, cookies, private OPML, or generated `data/*.json`.
- Do not expose decrypted API keys or sensitive headers to the frontend.
- Do not push, restart, or deploy until the user explicitly agrees.
- Keep the mobile UI compact and app-like.
- Keep summary, Ask AI, and fact check on one reading-assistant provider.
- Keep fact check V1 scoped to the clean article plus existing Radar context.

## Task 1: Add Provider Profile Storage And Encryption

**Files:**
- Modify: `server/ai_radar_api/db.py`
- Create: `server/ai_radar_api/ai_profiles.py`
- Modify: `server/ai_radar_api/config.py`
- Test: `tests/test_ai_backend_ai_profiles.py`

**Step 1: Write failing encryption/storage tests**

Add tests:

```python
def test_profile_secrets_are_encrypted_and_sanitized(tmp_path):
    config = _config(tmp_path, encryption_key="test-fernet-key")
    saved = save_ai_profile(config, {
        "name": "Translation AI",
        "type": "chat_completions",
        "base_url": "https://api.example.com/v1",
        "model": "gpt-4.1-mini",
        "api_key": "sk-secret",
        "headers_json": '{"X-Test":"secret-header"}',
        "timeout_seconds": 45,
    })

    raw = _raw_profile_row(config.db_path, saved["id"])
    assert "sk-secret" not in raw["api_key_encrypted"]
    assert "secret-header" not in raw["headers_encrypted"]

    public = list_ai_profiles(config)
    assert public[0]["has_api_key"] is True
    assert "api_key" not in public[0]
    assert "headers_json" not in public[0]
```

Add tests:

```python
def test_missing_encryption_key_rejects_new_secret(tmp_path):
    config = _config(tmp_path, encryption_key="")
    with pytest.raises(ValueError, match="RADAR_ENCRYPTION_KEY"):
        save_ai_profile(config, {"name": "Bad", "api_key": "sk-secret"})
```

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_ai_profiles.py
```

Expected: FAIL because `ai_profiles.py` does not exist.

**Step 3: Implement schema and encryption**

Add table:

```sql
create table if not exists ai_provider_profiles (
  id text primary key,
  name text not null,
  type text not null,
  base_url text not null,
  model text not null,
  api_key_encrypted text not null default '',
  headers_encrypted text not null default '',
  timeout_seconds integer not null default 45,
  enabled integer not null default 1,
  created_at text not null,
  updated_at text not null
);
```

Add `AppConfig.encryption_key`.

Implement in `ai_profiles.py`:

- `save_ai_profile(config, values)`
- `list_ai_profiles(config)`
- `get_ai_profile_for_use(config, profile_id)`
- `delete_ai_profile(config, profile_id)`
- `encrypt_secret(config, value)`
- `decrypt_secret(config, value)`
- `sanitize_profile(row)`

Use `cryptography.fernet.Fernet` if already acceptable as a dependency. If
adding the dependency is too heavy, use AES-GCM from `cryptography`. Add the
chosen dependency to `server/requirements.txt` and `requirements-dev.txt`.

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_ai_profiles.py
```

Expected: PASS.

## Task 2: Add AI Profile API Routes

**Files:**
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_ai_profiles_api.py`

**Step 1: Write failing API tests**

Add tests for authenticated routes:

```python
def test_ai_profile_api_never_returns_plaintext_key(client):
    login(client)
    res = client.post("/api/ai-profiles", json={
        "name": "Reader AI",
        "type": "chat_completions",
        "base_url": "https://api.example.com/v1",
        "model": "gpt-4.1-mini",
        "api_key": "sk-secret",
        "headers_json": '{"X-Test":"secret"}',
        "timeout_seconds": 45,
    })
    assert res.status_code == 200
    assert "sk-secret" not in res.text
    assert "secret" not in res.text
    assert res.json()["has_api_key"] is True
```

Add tests for:

- list profiles
- update profile while keeping old key when API key is empty
- delete profile
- reject invalid headers JSON
- reject unauthorized access

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_ai_profiles_api.py
```

Expected: FAIL because routes do not exist.

**Step 3: Implement routes**

Add routes:

```text
GET    /api/ai-profiles
POST   /api/ai-profiles
PUT    /api/ai-profiles/{profile_id}
DELETE /api/ai-profiles/{profile_id}
POST   /api/ai-profiles/{profile_id}/test
```

All routes require `require_session`.

Test route sends a minimal prompt through the selected profile and returns:

```json
{"ok": true, "model": "..."}
```

On failure, return a redacted error.

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_ai_profiles_api.py
```

Expected: PASS.

## Task 3: Refactor AIProvider To Accept Profile Overrides

**Files:**
- Modify: `server/ai_radar_api/provider.py`
- Modify: `server/ai_radar_api/assistant.py`
- Test: `tests/test_ai_backend_provider_profiles.py`

**Step 1: Write failing provider tests**

Add tests:

```python
def test_ai_provider_uses_profile_base_url_key_model_and_headers(monkeypatch):
    profile = {
        "type": "chat_completions",
        "base_url": "https://profile.example/v1",
        "api_key": "sk-profile",
        "model": "profile-model",
        "headers": {"X-Extra": "value"},
        "timeout_seconds": 12,
    }
    provider = AIProvider(config, profile=profile)
    ...
```

Assert:

- URL uses profile base URL.
- Authorization uses profile key.
- model uses profile model.
- extra headers are included.
- config env provider still works with no profile.

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_provider_profiles.py
```

Expected: FAIL because `AIProvider` does not accept a profile.

**Step 3: Implement provider override**

Refactor `AIProvider.__init__`:

```python
def __init__(self, config: AppConfig, profile: dict | None = None):
    self.config = config
    self.profile = profile or {}
```

Resolve:

- API format from profile type or config format
- base URL from profile or config
- API key from profile or config
- model from profile or config
- headers from profile plus Authorization
- timeout from profile or default

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_provider_profiles.py
```

Expected: PASS.

## Task 4: Add Provider Usage Settings

**Files:**
- Modify: `server/ai_radar_api/settings.py`
- Modify: `server/ai_radar_api/main.py`
- Test: `tests/test_ai_backend_settings.py`

**Step 1: Write failing settings tests**

Add tests for defaults:

```python
def test_settings_default_provider_usage():
    settings = get_settings(db_path)
    assert settings["translation_provider_mode"] == "browser"
    assert settings["translation_provider_id"] == ""
    assert settings["reading_assistant_provider_id"] == "env"
```

Add validation tests:

- invalid translation mode rejected
- invalid provider id rejected when a stored profile is selected
- env profile remains valid

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_settings.py
```

Expected: FAIL because settings keys do not exist.

**Step 3: Implement settings keys**

Extend `DEFAULT_SETTINGS`:

```python
"translation_provider_mode": "browser",
"translation_provider_id": "",
"reading_assistant_provider_id": "env",
```

Validate supported values in `update_settings`.

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_settings.py
```

Expected: PASS.

## Task 5: Route Translation And Ask Through Selected Providers

**Files:**
- Modify: `server/ai_radar_api/main.py`
- Modify: `server/ai_radar_api/assistant.py`
- Modify: `server/ai_radar_api/ai_profiles.py`
- Test: `tests/test_ai_backend_ask_api.py`
- Test: `tests/test_ai_backend_translation_api.py`

**Step 1: Write failing tests**

Add tests:

```python
def test_translate_uses_selected_translation_profile(monkeypatch, tmp_path):
    ...
```

Assert translation uses the selected profile, not the reading assistant profile.

Add tests:

```python
def test_ask_uses_selected_reading_assistant_profile(monkeypatch, tmp_path):
    ...
```

Assert Ask AI receives the reading-assistant profile.

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_translation_api.py tests/test_ai_backend_ask_api.py
```

Expected: FAIL because routes still use the config environment provider.

**Step 3: Implement provider selection**

Add helpers:

- `selected_translation_profile(config)`
- `selected_reading_assistant_profile(config)`

Translation:

- if mode is `browser`, backend AI translate should reject with a clear error
  unless the frontend explicitly selected AI mode.
- if mode is `ai`, use selected translation profile.

Ask:

- use selected reading-assistant profile.
- summary and fact-check are regular Ask requests and need no special endpoint.

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_ai_backend_translation_api.py tests/test_ai_backend_ask_api.py
```

Expected: PASS.

## Task 6: Add Reader Translation Toggle State

**Files:**
- Modify: `assets/app.js`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Write failing frontend contract tests**

Add assertions that:

- reader state stores original HTML/text.
- reader state stores translated HTML/text.
- translate button can show `原文` and `中文`.
- translated text is reused without another `requestCleanTextTranslation` call.
- `translate.google.com` is not present.

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_mobile_frontend_contract.py::test_reader_translation_toggle_contract
```

Expected: FAIL because the toggle state does not exist.

**Step 3: Implement frontend toggle**

Add state fields:

```js
readerOriginalHtml
readerOriginalText
readerTranslatedHtml
readerShowingTranslation
```

Update:

- `renderReaderArticle`
- `translateReaderArticle`
- `renderTranslatedReaderArticle`

Button labels:

- `翻译`
- `翻译中`
- `原文`
- `中文`
- `翻译失败`

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_mobile_frontend_contract.py::test_reader_translation_toggle_contract
node --check assets/app.js
```

Expected: PASS.

## Task 7: Add Summary And Fact-Check Reader Actions

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Write failing frontend contract tests**

Add assertions that:

- `readerSummaryButton` exists.
- `readerFactCheckButton` exists.
- summary opens Ask AI with current article context.
- fact check opens Ask AI with current article context.
- summary prompt includes the approved summary prompt.
- fact-check prompt labels the scope as current Radar context.

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_mobile_frontend_contract.py::test_reader_summary_and_fact_check_actions_contract
```

Expected: FAIL because buttons and handlers do not exist.

**Step 3: Implement reader actions**

Add toolbar buttons:

```html
<button id="readerSummaryButton" type="button">总结</button>
<button id="readerFactCheckButton" type="button">核验</button>
```

Add JS helpers:

- `summarizeReaderArticle()`
- `factCheckReaderArticle()`
- `openAskAiForReaderArticle(question)`

Both helpers:

- close or keep reader according to current Ask AI behavior
- set `state.askScope = item`
- send the preset question automatically
- append to Ask AI conversation history

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_mobile_frontend_contract.py::test_reader_summary_and_fact_check_actions_contract
node --check assets/app.js
```

Expected: PASS.

## Task 8: Add Settings UI For Profiles And Usage

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/styles.css`
- Test: `tests/test_mobile_frontend_contract.py`

**Step 1: Write failing contract tests**

Add assertions that settings contains:

- AI profile list
- add/edit profile controls
- headers JSON textarea
- profile test button
- translation usage select
- reading assistant usage select
- no API key plaintext rendering contract

**Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_mobile_frontend_contract.py::test_settings_ai_profiles_contract
```

Expected: FAIL because controls do not exist.

**Step 3: Implement mobile-first settings UI**

Keep the settings screen utilitarian:

- compact sections
- no nested cards
- stable input widths
- textarea for headers JSON
- API key input placeholder says existing key is preserved when blank
- test connection button beside profile actions

Add JS:

- `loadAiProfiles()`
- `renderAiProfiles()`
- `saveAiProfile()`
- `deleteAiProfile()`
- `testAiProfile()`
- settings save/load integration for provider usage

**Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_mobile_frontend_contract.py::test_settings_ai_profiles_contract
node --check assets/app.js
```

Expected: PASS.

## Task 9: Full Verification

**Files:**
- All touched files

**Step 1: Run full backend/frontend checks**

Run:

```bash
.venv/bin/python -m pytest -q
node --check assets/app.js
.venv/bin/python -m py_compile server/ai_radar_api/article_reader.py server/ai_radar_api/assistant.py server/ai_radar_api/main.py server/ai_radar_api/db.py server/ai_radar_api/radar_data.py server/ai_radar_api/config.py server/ai_radar_api/provider.py server/ai_radar_api/settings.py server/ai_radar_api/ai_profiles.py
git diff --check
```

Expected:

- pytest passes
- JS syntax check passes
- py_compile passes
- diff check passes

**Step 2: Manual runtime checks before asking to push**

Check:

- settings login still works
- legacy env AI still works before adding profiles
- adding an AI profile does not return plaintext key
- translation mode browser does not call AI fallback automatically
- translation mode AI translates and toggles original/Chinese
- summary opens Ask AI and sends the summary prompt
- fact check opens Ask AI and sends the fact-check prompt
- Ask AI still handles normal questions

**Step 3: Report and ask for cloud approval**

Do not commit, push, or restart until the user explicitly agrees.

Report:

- changed files
- verification output
- any limitations
- ask: `是否同意推上云端`
