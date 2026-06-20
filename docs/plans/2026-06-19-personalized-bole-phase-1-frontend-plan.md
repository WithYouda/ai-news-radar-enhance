# Personalized Bole Phase 1 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first visible 伯乐画像工作台 frontend slice, wired to the authenticated personalization API, while preserving the static fallback.

**Architecture:** Keep the current no-build static frontend. Add hidden overlay markup in `index.html`, local state and API wiring in `assets/app.js`, and responsive styling in `assets/styles.css`. The workbench exposes `兴趣校准`, `阅读偏好`, and `画像草稿`. Every calibration question has quick-choice chips plus a free-text field. The workbench stores draft profile data only after an explicit user action, then confirms it through the backend before showing it as active.

**Tech Stack:** HTML, vanilla JavaScript, CSS, Python static contract tests, Node syntax checks, local `http.server`, Chromium visual verification.

---

## Pitfall Checks

- `Mobile View Switching Can Unhide Overlay Panels`: `#boleWorkbench` must start with `hidden` and must not use `data-mobile-view`.
- `Frontend Client Split Broke Mobile/PWA Runtime`: keep all new runtime code in `assets/app.js`, keep the existing fallback API client, and bump `index.html` cache-busting query strings for changed JS/CSS.
- UI concision iron law: do not show internal implementation text such as first-login rules, confirmation mechanics, or progress labels like `1/4`.
- Customization iron law: every personalization question must expose a readable
  free-text path in the app, not only preset tags.

## Files

- Modify `tests/test_mobile_frontend_contract.py`: add frontend contract tests for the hidden overlay, concise copy, API routes, fallback behavior, and pure profile draft builder.
- Modify `index.html`: add a `为你推荐` entry button, settings personalization controls, and hidden `#boleWorkbench` overlay outside all `[data-mobile-view]` containers.
- Modify `assets/app.js`: add personalization state, draft builder helpers, API load/save/skip/reset/disable actions, workbench render/open/close handlers, and login-time loading.
- Modify `assets/styles.css`: add desktop horizontal workbench and mobile compact horizontal flow styles.
- Modify `tests/test_mobile_frontend_contract.py`: update JS/CSS cache-bust expectations after implementation.

## Task 1: Frontend Contract Tests

**Files:**
- Modify: `tests/test_mobile_frontend_contract.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_personalized_bole_workbench_starts_hidden_and_not_mobile_view():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="boleWorkbench"' in html
    assert 'id="boleWorkbench" class="bole-workbench" hidden' in html
    assert 'id="boleWorkbench" class="bole-workbench" data-mobile-view' not in html
    assert "兴趣校准" in html
    assert "阅读偏好" in html
    assert "画像草稿" in html
    assert "AI 访谈" not in html
    assert "首次登录" not in html
    assert "确认前不保存" not in html
    assert "1/4" not in html
```

Add a fourth test for calibration question inputs:

```python
def test_bole_calibration_questions_have_quick_choices_and_free_text():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-bole-question-id="attention_goal"' in html
    assert 'data-bole-question-id="negative_preferences"' in html
    assert 'data-bole-question-id="ai_domains"' in html
    assert 'data-bole-question-id="deep_reading_policy"' in html
    assert 'data-bole-question-id="reading_depth"' in html
    assert html.count("data-bole-question-id") >= 5
    assert html.count("data-bole-choice") >= 20
    assert html.count("data-bole-free-text") >= 5
```

Add a second test for API wiring:

```python
def test_personalized_bole_frontend_wires_authenticated_api_without_static_breakage():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "loadPersonalization" in js
    assert "openBoleWorkbench" in js
    assert "buildBoleProfileDraft" in js
    assert 'apiFetch("/api/personalization")' in js
    assert 'apiFetch("/api/personalization/draft"' in js
    assert 'apiFetch("/api/personalization/confirm"' in js
    assert 'apiFetch("/api/personalization/skip"' in js
    assert 'apiFetch("/api/personalization/reset"' in js
    assert 'apiFetch("/api/personalization/disable"' in js
    assert "if (!apiBaseUrl)" in js
```

Add a third test for pure draft normalization with a Node VM slice:

```python
def test_personalized_bole_profile_draft_builder_dedupes_and_handles_empty_inputs():
    # Extract parseBoleTerms/buildBoleProfileDraft and assert duplicate labels collapse,
    # empty inputs still produce a valid profile object, and negative interests keep
    # separate weights from positive interests.
```

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "personalized_bole or cache_busted"
```

Expected: tests fail because markup, functions, and cache-bust strings are not implemented yet.

## Task 2: Markup And Cache Bust

**Files:**
- Modify: `index.html`
- Modify: `tests/test_mobile_frontend_contract.py`

- [ ] **Step 1: Add hidden workbench and entry points**

Add a compact entry button near 伯乐精选 and a settings section:

```html
<button id="boleWorkbenchOpen" class="icon-pill bole-entry-button" type="button">为你推荐</button>
```

Add a hidden overlay after the existing source dialogs and before reader/Ask AI sheets:

```html
<section id="boleWorkbench" class="bole-workbench" hidden aria-label="伯乐画像工作台">
  ...
</section>
```

Do not add `data-mobile-view` to the overlay.

- [ ] **Step 2: Bump changed frontend assets**

Change the stylesheet and app script URLs to:

```html
./assets/styles.css?v=personalized-bole-workbench-0619
./assets/app.js?v=personalized-bole-workbench-0619
```

- [ ] **Step 3: Run focused markup tests**

Run:

```bash
python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "personalized_bole or cache_busted"
```

Expected: markup assertions pass, JS/CSS behavior assertions still fail until later tasks.

## Task 3: JavaScript State And API Flow

**Files:**
- Modify: `assets/app.js`

- [ ] **Step 1: Add personalization state and element handles**

Add state fields:

```javascript
personalizationStatus: null,
personalizationUnavailable: false,
boleDraftPreview: null,
```

Add DOM handles for workbench fields, buttons, and status text.

- [ ] **Step 2: Add pure draft helpers**

Add `parseBoleTerms()` and `buildBoleProfileDraft()` before API side-effect functions. The helper should:

- Split Chinese and English separators.
- Deduplicate labels.
- Merge selected quick choices with free-text answers.
- Preserve raw calibration evidence so the resulting draft can explain how the
  profile was inferred.
- Build `positive_interests`, `negative_interests`, `source_preferences`, and `behavior_preferences`.
- Return a valid empty profile if the user skips text input.

- [ ] **Step 3: Add API functions**

Add:

- `loadPersonalization(options = {})`
- `saveBoleDraft()`
- `confirmBoleProfile()`
- `skipBolePersonalization()`
- `resetBolePersonalization()`
- `disableBolePersonalization()`

All API functions must no-op or show a concise unavailable state when `apiBaseUrl` is empty.

- [ ] **Step 4: Connect login-time loading**

After `loadSettings()` confirms the session, call `loadPersonalization({ autoOpen: true })`. Auto-open only when backend says `state === "not_started"` and the user is authenticated.

- [ ] **Step 5: Run focused JS tests**

Run:

```bash
python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "personalized_bole or cache_busted"
node --check assets/app.js
```

Expected: all focused frontend contract tests pass and JS syntax is valid.

## Task 4: Responsive Styling

**Files:**
- Modify: `assets/styles.css`

- [ ] **Step 1: Add desktop styles**

Add a fixed overlay and a horizontal grid:

```css
.bole-workbench { position: fixed; inset: 0; ... }
.bole-workbench-grid { display: grid; grid-template-columns: 1.08fr .92fr .9fr; ... }
```

- [ ] **Step 2: Add mobile styles**

Inside `@media (max-width: 760px)`, make the workbench a compact sheet with horizontal section cards:

```css
.bole-workbench-grid {
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
}
.bole-workbench-section {
  min-width: min(82vw, 340px);
  scroll-snap-align: start;
}
```

- [ ] **Step 3: Run focused CSS tests**

Run:

```bash
python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "personalized_bole or mobile"
```

Expected: tests pass.

## Task 5: Verification

**Files:**
- No source edits unless verification finds a bug.

- [ ] **Step 1: Run focused checks**

Run:

```bash
python3 -m pytest -q tests/test_mobile_frontend_contract.py tests/test_frontend_static_contract.py
node --check assets/app.js
git diff --check
```

- [ ] **Step 2: Run full tests**

Run:

```bash
python3 -m pytest -q
```

- [ ] **Step 3: Browser verify locally**

Use local static server `http://localhost:8080/` and the local backend preview on `127.0.0.1:8090`. Verify with Chromium:

- Desktop: login with preview password, workbench auto-opens for `not_started`, skip closes, settings can reopen.
- Mobile: workbench stays hidden before login, opens as a compact horizontal sheet after login, no `data-mobile-view` switching reveals it accidentally.
- Static fallback: when backend is unavailable, the page still renders the public feed.

Save temporary screenshots under `/tmp/ai-news-radar-visual` only during verification, then delete them before final reporting.

## Self-Review

- Spec coverage: this plan covers Phase 1 frontend shell, authenticated profile status/draft/confirm/skip/reset/disable, static fallback, concise UI, mobile overlay pitfall, and cache bust. It intentionally does not cover ranking, feedback, X API settings, deep reading, or homepage switching.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: the frontend profile fields match the backend validator: `positive_interests`, `negative_interests`, `source_preferences`, and `behavior_preferences`.
