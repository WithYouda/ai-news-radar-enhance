# Project Pitfalls

Read this file before planning or writing code in this repository. If a task
touches one of these areas, explicitly check the prevention notes before editing.
After drafting tests and again after implementation, check whether the tests are
overfit to the suspected bug; add adversarial and corner-case coverage for
nearby failure modes before moving on.

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

## 2026-06-10: Clean Article Fallback Cache Retried Immediately

Symptoms:

- Closing and reopening the reader could show `正在清洗原文...` again for the
  same article.
- Articles that returned `暂时无法清洗原文` could be refetched immediately instead
  of reusing the just-stored fallback.

Root causes:

- Backend `access_status=unavailable` cache entries were treated as always
  retryable, unlike short `access_status=open` entries that already had a retry
  delay.
- The frontend reader had no session-level article cache or in-flight request
  reuse, and it rendered the cleaning loading state before every API response,
  making even fast cache hits look like a fresh clean.

Prevention:

- For article-reader cache changes, test both fresh and stale entries for
  `open`, `restricted`, and `unavailable` statuses.
- Verify repeated opens by checking `cache_status`, `access_status`,
  `fetched_at`, and request counts; do not rely only on the loading text.
- Keep reader-side session cache and in-flight request reuse when changing
  `openReader()` / `loadCleanArticle()`.
- Bump the `assets/app.js` cache-busting query in `index.html` whenever reader
  runtime behavior changes.

## 2026-06-10: Clean Article Cache Hit Was Behind News Item Lookup

Symptoms:

- Reopening an already cleaned article after closing the PWA could eventually
  show `已缓存` but still feel slow.
- Backend cache hits still paid the cost of resolving the requested reader id by
  loading and scanning latest news JSON before checking `article_cache`.

Root causes:

- `/api/read/{item_id}` resolved the news item first and only then checked the
  article cache.
- `article_cache` used canonical URL-hash ids, while the frontend can request a
  generated feed `id`; there was no persistent alias table from requested ids to
  canonical article ids.

Prevention:

- Keep `/api/read` cache-first: direct canonical cache lookup, then alias lookup,
  then latest-news item lookup only as a miss fallback.
- Add regression tests that prove cached article hits do not call
  `load_latest_items`.
- Include adversarial tests for orphan aliases, unsafe stale cached URLs,
  unavailable fallback caches, and unknown uncached ids so the reader does not
  become an arbitrary URL fetcher.
