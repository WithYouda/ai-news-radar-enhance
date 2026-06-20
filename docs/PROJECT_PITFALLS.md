# Project Pitfalls

Read this file before planning or writing code in this repository. If a task
touches one of these areas, explicitly check the prevention notes before editing.
After drafting tests and again after implementation, check whether the tests are
overfit to the suspected bug; add adversarial and corner-case coverage for
nearby failure modes before moving on.

## 2026-06-19: Full URL Text Inflated AI Relevance Scores

Symptoms:

- Non-AI items could be kept in the AI Signal view because their URL path or
  query string contained terms such as `openai`, `gpt`, `agent`, `model`, or
  `ai`.
- Broad business stories such as insurance-agent or business-model articles
  could receive AI signals from URL fragments instead of article/source text.

Root causes:

- `score_ai_relevance()` built its scoring text from title, source, site name,
  and the full URL.
- URL paths, redirect payloads, tracking parameters, and encoded aggregator
  links are not reliable article semantics.

Prevention:

- Score only the URL host as source identity; do not score URL path, query, or
  fragment text.
- Keep compatibility fields such as `ai_score`, but prefer explicit
  `ai_relevance_score`, `source_trust_score`, and `priority_score` in new
  contracts.
- Cover URL-noise false positives, useful host identity, credential/port host
  parsing, and non-AI `agent`/`model` contexts before changing scoring.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_ai_relevance.py tests/test_audit_ai_relevance.py tests/test_update_news_outputs.py
  ```

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

## 2026-06-10: Update Workflow Freshness Was Treated As Guaranteed

Symptoms:

- `data/latest-24h.json` sometimes lagged several hours even though
  `.github/workflows/update-news.yml` was scheduled twice per hour.
- A push-triggered `Update AI News Snapshot` run could finish in about 90
  seconds, while scheduled runs still had multi-hour gaps.

Root causes:

- GitHub Actions `schedule` is not a freshness SLA. GitHub documents that
  scheduled workflows can be delayed during high load and queued jobs can be
  dropped.
- Recent run history showed scheduled run gaps of multiple hours despite the
  cron expression being `17,47 * * * *`.
- A single failed or cancelled update run leaves Pages serving the previous
  generated data until the next successful run and Pages deployment.

Prevention:

- For user-visible freshness guarantees, do not rely only on GitHub Actions
  `schedule`; use an external cron/monitor or the VPS to trigger
  `workflow_dispatch`/repository updates when `generated_at` is stale.
- After push-triggered updates, check both `Update AI News Snapshot` and the
  following Pages deployment, then compare local and public
  `data/latest-24h.json` `generated_at` values.
- Keep an explicit stale-data alert path based on `generated_at`, not just
  successful workflow history.

## 2026-06-10: Feedparser URL Parsing Bypassed Request Timeouts

Symptoms:

- `Update data` normally completed in about 1-2 minutes, but one run stayed in
  that step until the workflow-level 15 minute timeout cancelled it.
- Logs showed no source-level progress after startup, making the stuck source
  hard to identify from GitHub output alone.

Root causes:

- `fetch_iris()` called `feedparser.parse(feed_url)`, which lets feedparser
  perform its own network request without the repository's `requests` timeout
  and session settings.
- Built-in sources run serially in `collect_all()`, so one unbounded source can
  block all later sources and prevent JSON publication.

Prevention:

- Never pass a URL directly to `feedparser.parse()` in production fetchers.
  Fetch with `session.get(..., timeout=...)` or `requests.get(..., timeout=...)`
  first, then parse response bytes.
- Add tests that prove subfeeds are fetched with explicit timeouts and that one
  timed-out subfeed does not prevent later subfeeds from being processed.
- When adding a source, check all network calls with `rg -n
  "feedparser\\.parse|requests\\.|session\\." scripts/update_news.py` and make
  sure every external request has a bounded timeout.

## 2026-06-11: X Status Pages Were Treated Like Fetchable Articles

Symptoms:

- Follow Builders / X items could show only the collected post title in the
  news list.
- Opening the clean reader for an `x.com/.../status/...` URL tried to fetch the
  X web page, which commonly returns a JavaScript/login/error shell instead of
  readable article HTML.
- Cached X fallback entries could keep showing `暂时无法清洗原文` even when the
  project already had enough public post text in the news item itself.

Root causes:

- The reader treated X status URLs like ordinary article pages.
- The X post text collected from public feeds or X API-style records lives on
  the news item, not in fetchable `x.com` HTML.

Prevention:

- For X/Twitter status URLs, prefer existing public item text as the clean
  article body before attempting any web fetch.
- Do not apply the X status fallback to non-status X pages such as profiles.
- When changing X reader behavior, cover direct X status fallback, stale X error
  shell cache replacement, fresh unavailable X fallback replacement, and
  non-status X URLs.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_ai_backend_article_reader.py -k "x_status or x_error_shell or x_unavailable or profile_page"
  ```

## 2026-06-12: WeChat Hotlinked Images Rendered As Anti-Leech Placeholders

Symptoms:

- Clean reader output for `mp.weixin.qq.com` articles showed many image blocks
  as `此图片来自微信公共号，未经允许不可引用`.

Root causes:

- The backend preserved `mmbiz.qpic.cn` image URLs in clean article HTML.
- Browsers then loaded those WeChat CDN images from the AI News Radar origin,
  where WeChat returns an anti-hotlink placeholder instead of the real image.

Prevention:

- For `mp.weixin.qq.com` pages, keep `mmbiz.qpic.cn` images but emit
  `referrerpolicy="no-referrer"` so the browser does not send the AI News Radar
  page as the image request referrer.
- Apply the attribute only to WeChat article pages; do not change the same CDN
  URLs when they appear on ordinary pages.
- Upgrade cached WeChat clean HTML on read so previously cached articles do not
  keep returning image tags without the referrer policy.
- Cover lazy `data-src`, direct `src`, cache hits, and a non-WeChat page that
  should still follow normal image rules.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_ai_backend_article_reader.py -k "upgrades_cached_wechat or weixin or wechat_cdn"
  ```

## 2026-06-12: Mobile View Switching Can Unhide Overlay Panels

Symptoms:

- A drawer or modal intended to start hidden can appear on first load.
- The opened overlay intercepts clicks on the underlying homepage controls.

Root causes:

- Overlay markup was given `data-mobile-view="today"`.
- `setMobileView()` controls all `[data-mobile-view]` nodes by assigning their
  `hidden` property, so it can override an overlay's default `hidden` state.

Prevention:

- Do not put `data-mobile-view` on modal, drawer, sheet, or overlay containers
  whose visibility is controlled by their own open/close buttons.
- Add a static contract for any new overlay that must remain hidden at startup.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py::test_homepage_uses_compact_header_and_data_drawer
  ```

## 2026-06-18: Source Sticky Headers Were Replaced By A Floating Clone

Symptoms:

- In AI 信号流, an expanded source title changed appearance while scrolling.
- The source title appeared to pop out instead of the original row staying fixed
  above its news items.

Root causes:

- The frontend added a separate `active-source-bar` fixed element that copied the
  source title instead of letting the original `.source-group-head` stick.
- `.list-wrap` used `overflow: hidden`, which can keep native sticky children
  constrained by the wrapper instead of the viewport.

Prevention:

- Keep source-title persistence as native CSS sticky on `.source-group-head`;
  do not add a fixed cloned source bar for this interaction.
- Keep the AI signal-flow wrapper from clipping sticky source headers.
- Bump the changed frontend asset query in `index.html` whenever this behavior
  changes so PWA/mobile caches do not mix old and new interaction code.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "cache_busted or native_source_header_sticky or source_header_sticks"
  ```

## 2026-06-18: Collapsing An Expanded Source Lost The Reader's Place

Symptoms:

- After expanding a source group, scrolling deep into its items, and clicking
  the sticky source title's `收起` action, the viewport stayed at the old scroll
  offset instead of returning to the collapsed source header.
- The reader could land on later content and lose track of which source had just
  been collapsed.

Root causes:

- The source toggle deleted the expanded source key and re-rendered the full
  list, but did not preserve the collapsed source as a scroll anchor.
- Removing many expanded items changes document height while the browser keeps
  the previous `scrollY`, so the visible content shifts past the source.

Prevention:

- Route source collapse through a helper that deletes the expanded key, renders
  the compact list, and then scrolls the same source header back to the top.
- Keep expand behavior separate from collapse behavior; expanding should not
  force a scroll jump.
- Bump the changed `assets/app.js` query in `index.html` whenever this
  interaction changes.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "cache_busted or collapsing_source or native_source_header_sticky or source_header_sticks"
  ```

## 2026-06-19: Site Group Expansion Lost Large-Source Context

Symptoms:

- In AI 信号流, large source groups such as Buzzing used a full-width footer
  button like `展开 Buzzing 全部 42 个来源`.
- After expanding a large source group, the site title scrolled away, so readers
  scanning many child sources lost the large-source context.
- Collapsing the expanded site group after scrolling deep could leave the reader
  below the collapsed site's header.

Root causes:

- Site-level expansion used a footer `site-show-more` button instead of the same
  header-right toggle pattern used by source groups.
- Only `.source-group-head` was native sticky; `.site-group-head` was static.
- Site collapse deleted the expanded site key and re-rendered without preserving
  the collapsed site header as the scroll anchor.

Prevention:

- Keep site-level expand/collapse controls inside `.site-group-head`; do not
  reintroduce footer `site-show-more` controls.
- Use native CSS sticky for `.site-group-head` and offset `.source-group-head`
  below it instead of adding fixed cloned bars.
- Route site collapse through a helper that deletes the expanded site key,
  renders the compact list, and scrolls the same site header back to the top.
- Bump changed frontend asset queries in `index.html` whenever site/source group
  interaction behavior changes.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "cache_busted or site_toggle or collapsing_site or group_headers_stick or native_group_header_sticky"
  ```

## 2026-06-20: Bole Workbench Regressed Into A Long Form

Symptoms:

- 伯乐画像工作台 used four uneven desktop panels instead of the approved
  three-panel workbench.
- Interest calibration appeared as broad form inputs instead of one focused
  question card at a time.
- Mobile rendered the workbench as horizontally scrollable large sections,
  making it feel like a long form instead of a compact `校准 / 偏好 / 草稿`
  flow.

Root causes:

- The first frontend shell tests covered overlay visibility and API wiring, but
  did not pin the approved visual companion structure.
- Calibration answers were represented as two generic textareas instead of the
  five required questions with quick choices plus first-class free text.

Prevention:

- Keep the production workbench aligned with the accepted visual companion:
  desktop has exactly `兴趣校准`, `阅读偏好`, and `画像草稿`; mobile uses short
  tabs and one active question card.
- Every calibration question must retain both preset choices and free text.
- Do not reintroduce internal copy such as `AI 访谈`, `确认保存`, `首次登录`,
  `确认前不保存`, or `1/4`.
- Bump changed frontend asset queries in `index.html` for PWA/mobile cache
  compatibility.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "personalized_bole or bole_calibration or bole_mobile or cache_busted"
  ```

## 2026-06-20: Bole Interest Calibration Mixed Survey Fields With AI Dialogue

Symptoms:

- 兴趣校准页被做成多栏表单或多个输入框，而不是一个 AI 对话入口。
- 阅读偏好题混进兴趣校准，导致用户选完兴趣后右侧档案含有不属于兴趣领域的内容。
- 画像草稿或保存按钮在右侧栏下方被截断，工作台内不能滚动到可操作区域。
- 静态前端没有后端时无法打开工作台，导致本地视觉验证和用户预览被 API 分支挡住。

Root causes:

- 工作台 UI 没有按 `兴趣校准 -> 阅读偏好 -> 画像草稿` 的串行模型约束实现。
- 预设选项和自由输入被当成表单字段，而不是同一个 AI 对话空间中的回答来源。
- 右侧档案栏没有独立的内部滚动和固定操作区。
- `openBoleWorkbench()` 在 `apiBaseUrl` 缺失时直接返回，阻断了静态降级体验。

Prevention:

- 兴趣校准只保留一个对话输入框；预设选项属于当前 AI 问题，阅读偏好题必须在独立阶段。
- 右侧只展示已经识别的领域、规避内容和阅读偏好，操作按钮必须始终可见。
- 静态前端允许打开工作台；仅保存、生成草稿、确认等后端动作进入不可用状态。
- Bump changed frontend asset queries in `index.html` whenever this behavior changes.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "personalized_bole or bole_mobile or bole_interest or cache_busted"
  ```

## 2026-06-20: Bole Dialogue Answers Were Treated As Static Tags

Symptoms:

- 用户自由输入后，原文会立刻变成右侧标签，没有经过伯乐的总结提炼或追问。
- 预设选项点完后仍需要再点发送按钮，问题推进不自然。
- 回头编辑第二个兴趣问题时，后续已经完成的问题可能从对话里消失。
- 右侧档案栏在兴趣校准阶段混入阅读偏好，且条目不能直接删除。

Root causes:

- 前端只用 `boleAnswers` 是否有值来推断当前题，没有区分已经显示的问题、
  已确认的问题和正在编辑的问题。
- 自由输入通过 `parseBoleTerms(answer.text)` 直接进入画像标签，没有独立的
  AI interpret/本地降级提炼层。
- 右侧档案栏从完整草稿渲染，没有按当前阶段过滤兴趣、负偏好和阅读偏好。

Prevention:

- 保持 `shown question ids`、`confirmed question ids`、`active question id` 分离；
  编辑历史题不能删除后续题。
- 自由输入必须保留原文证据，只能把 `ai_labels` 或预设选项写入画像标签。
- 预设选项点击后自动延迟推进，连续点击要重置 timer。
- 右侧档案按当前阶段过滤，并给每个条目提供可逆删除。
- Bump changed frontend asset queries in `index.html` whenever this behavior
  changes.
- Regression command:

  ```bash
  python3 -m pytest -q tests/test_mobile_frontend_contract.py -k "bole_dialogue or bole_custom or bole_right_rail or bole_stage_actions or personalized_bole"
  ```
