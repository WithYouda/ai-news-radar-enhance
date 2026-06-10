# Project Pitfalls

Read this file before planning or writing code in this repository. If a task
touches one of these areas, explicitly check the prevention notes before editing.

## 2026-06-10: Frontend Client Split Broke Mobile/PWA Runtime

Symptoms:

- Mobile/PWA showed `更新时间` stuck at loading.
- `AI 信号流` did not render.
- Clicking reader actions quickly failed with the clean-article fallback error.

Root causes:

- `assets/app.js` was changed to depend on `window.AI_NEWS_RADAR_API` from the new
  `assets/api-client.js`, but mobile/PWA/browser cache can run a new app bundle
  with older HTML or a missing newly split script.
- `apiBaseUrl` was moved into the `api-client.js` closure while `app.js` still
  used `apiBaseUrl` synchronously in many places, including `renderItemNode`.
  That caused a `ReferenceError` during `renderList()`, aborting initial render
  before `updatedAtEl` and the news list were updated.
- The first split did not bump the `app.js` cache-busting query, increasing the
  chance of mixed cached frontend assets.

Prevention:

- Before moving any frontend global/helper out of `assets/app.js`, run
  `rg -n "<name>" assets/app.js assets/*.js tests` and prove every consumer still
  has access to it.
- For split frontend scripts, keep a compatibility fallback in `app.js` unless
  the old HTML and new JS cannot be mixed in production/PWA caches.
- Bump the changed script URL in `index.html` every time a shipped JS file changes
  behavior.
- Add a regression test for stale/mobile cached HTML compatibility. At minimum,
  assert that `app.js` still has any synchronous globals used by reader controls
  and render paths.
- Do not trust `curl` of HTML/JS alone as a functional proof. Also verify the
  runtime data path that failed, for example:

  ```bash
  node --check assets/app.js
  python3 -m pytest -q tests/test_frontend_static_contract.py tests/test_mobile_frontend_contract.py
  python3 -m pytest -q
  curl -fsSL "https://withyouda.github.io/ai-news-radar-enhance/" | rg "assets/app.js"
  curl -fsSL "https://withyouda.github.io/ai-news-radar-enhance/assets/app.js?v=<current-version>" | rg "apiBaseUrl|fetchFreshJson"
  ```

## 2026-06-10: GitHub Actions Can Move Remote After A Push

Symptoms:

- A source push triggers `Update AI News Snapshot`.
- The workflow can commit generated `data/*.json` snapshots after the source
  commit, so local `master` becomes behind `origin/master`.

Prevention:

- After triggering or watching `update-news.yml`, run:

  ```bash
  git fetch origin master
  git rev-list --left-right --count HEAD...origin/master
  ```

- If remote is ahead and the worktree is safe, fast-forward with:

  ```bash
  git pull --ff-only origin master
  ```

- Re-run relevant verification after pulling generated data.
