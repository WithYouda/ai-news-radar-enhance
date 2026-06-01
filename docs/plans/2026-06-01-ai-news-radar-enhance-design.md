# AI News Radar Enhance Design

Date: 2026-06-01

## 1. Product Goal

Build a personal AI information-flow reader on top of AI News Radar.

The product should keep the existing desktop reader stable while making the
mobile experience much more useful for daily reading. GitHub Actions continues
to collect and publish public news data. GitHub Pages serves the static reader.
This VPS runs the dynamic AI backend for question answering, classification,
fact verification, source scoring, settings, and future manual overrides.

The target user for V1 is one person: the repository owner. Multi-user SaaS,
registration, billing, shared teams, and public community features are out of
scope.

## 2. Standard Development Process

Use a practical software workflow:

1. Requirements: confirm goals, constraints, and user choices.
2. Design: write this document before feature implementation.
3. Implementation plan: split the design into small testable tasks.
4. Development: implement task by task with focused tests.
5. Verification: run local checks and manual UI checks before claiming done.
6. Deployment: push to GitHub, configure Actions/Pages/server environment, then
   verify the deployed behavior.
7. Iteration: use real reading experience to tune taxonomy, prompts, scoring,
   and source rules.

For this project, design decisions are user-owned. The implementation can make
engineering choices when they follow this document and existing repo patterns.

## 3. V1 Non-Goals

- Do not rewrite the whole product as a native Android app in V1.
- Do not break or redesign the current desktop layout.
- Do not require a domain name before the product can be tested.
- Do not put model API keys, passwords, tokens, cookies, or private OPML files
  in the static front end or public repository.
- Do not publish private source-derived data to public GitHub Pages.
- Do not implement registration, user roles, billing, team sharing, or public
  source-rating communities.
- Do not deep-verify every low-value item by default.

## 4. Deployment Model

Use Scheme B.

```text
GitHub Actions
  -> fetches sources
  -> generates public data/*.json
  -> commits snapshots

GitHub Pages
  -> serves index.html, assets/*, data/*.json
  -> stores no secrets
  -> remains the public/static reader

VPS AI backend
  -> exposes HTTPS API
  -> stores secrets in environment variables
  -> stores settings and verification state in SQLite
  -> fetches GitHub Pages JSON and original pages when needed
```

The front end should read the backend base URL from a small config file or
front-end constant, for example:

```text
AI_API_BASE_URL=https://<server-ip-or-domain>
```

Because GitHub Pages is HTTPS, browser calls to the backend must also use HTTPS.
For an IP-only backend, the hard requirement is a browser-trusted certificate
valid for that endpoint. If that blocks deployment, use a temporary free tunnel
or a cheap domain as a fallback.

## 5. Mobile Information Architecture

V1 mobile bottom navigation:

```text
今日 | 分类 | 核验 | 设置
```

Global floating assistant:

```text
问 AI
```

`问 AI` is not a separate bottom-nav page. It is a contextual assistant layer
available from all main pages.

The mobile-first product model:

- `今日`: daily reading hub, including Bole Picks, top stories, verified/low-risk
  highlights, and important category summaries.
- `分类`: topic-oriented browsing with seven top-level categories and editable
  second-level rules.
- `核验`: trust and verification workspace, including low-confidence items,
  deep-verification queue, source authority scores, and official-source coverage.
- `设置`: private admin controls for backend URL, taxonomy/rule editing,
  verification defaults, model provider config status, and login/logout.
- `问 AI`: ask questions about the current page, selected item, category, or all
  recent data.

Desktop should keep the current layout unless a later design explicitly changes
it. Mobile CSS and JS should be responsive and scoped so desktop behavior remains
stable.

## 6. Today Page

`今日` is the default mobile screen.

It should prioritize:

1. Bole Picks: the highest-signal items for immediate reading.
2. Verified highlights: items with strong official/first-hand support.
3. Category digest: one compact summary per active top-level category.
4. Latest stream: recent items, still searchable and filterable.

Each card should support:

- Open original link.
- Ask AI about this item.
- Show authority score and short reason when available.
- Trigger deep verification.
- Show category and subcategory.

The current desktop `伯乐精选` and signal stream can remain. Mobile can present
the same data with a different layout.

## 7. Category Taxonomy

The home page uses seven top-level categories:

1. 模型与产品
2. Agent 与工作流
3. 开发者工具
4. 开源与项目
5. 研究与评测
6. 公司与行业
7. 算力与基础设施

Second-level categories:

```text
模型与产品:
  模型发布
  产品功能
  API / 平台更新
  多模态能力
  价格 / 访问权限
  安全 / 策略更新

Agent 与工作流:
  Agent 框架
  工具调用 / Function Calling
  MCP / 插件生态
  浏览器 / 电脑控制
  多 Agent 协作
  自动化工作流

开发者工具:
  IDE / 编程助手
  SDK / API 工具
  RAG / 数据工具
  部署 / 运维
  评测 / 监控
  安全 / 权限

开源与项目:
  开源模型
  开源工具
  GitHub 项目
  框架 / 库
  数据集
  Demo / 应用样例

研究与评测:
  论文
  Benchmark
  模型评测
  技术报告
  对齐 / 安全研究
  机器人 / 具身智能

公司与行业:
  融资 / 收购
  合作 / 生态
  商业化
  监管 / 政策
  组织 / 人才
  市场采用

算力与基础设施:
  GPU / 芯片
  推理服务
  训练基础设施
  云平台
  数据中心 / 能源
  本地模型 / 边缘设备
```

Second-level categories should only be shown when they have content for the
current time window.

The taxonomy must not be hardcoded as the only source of truth. Store it in the
server database so the user can edit:

- category labels
- second-level labels
- keyword/rule hints
- priority
- enabled/disabled state
- future manual overrides

The static front end can cache the latest taxonomy from the server and fall back
to a bundled default when the backend is unavailable.

## 8. Classification Model

Classification should combine rule-based hints and AI classification.

V1 behavior:

- Use the server taxonomy as the source of truth.
- Use simple keyword/source hints first where they are obvious.
- Use AI classification for ambiguous items or batch enrichment.
- Store classification results in SQLite to avoid reclassifying the same item on
  every page load.
- Preserve the original item data from `data/*.json`; classification should add
  metadata, not replace source content.

Each classified item should be able to store:

```text
item_id
url
title
top_category
sub_category
confidence
reason
classified_at
model
taxonomy_version
manual_override
```

## 9. Verification And Authority Scoring

The product should prefer first-hand and authoritative information.

V1 authority score:

```text
0-100 score
short AI explanation
verification status
evidence links
manual override fields reserved for later
```

Default verification should be lightweight:

- Fetch the original article/page when possible.
- Check whether it is official or first-hand.
- Check whether it cites official sources, papers, docs, GitHub releases,
  company announcements, changelogs, filings, or other primary material.
- Penalize pure reposts, vague summaries, missing links, or unclear provenance.
- Store the result in SQLite.

Authority scoring is mainly for third-party sources and aggregator items.
Official sources can receive a high base score, but should still expose why they
are treated as first-hand.

Suggested score bands:

```text
85-100: first-hand or official source, strong evidence
70-84: credible third-party report with clear primary-source links
50-69: useful but partly indirect or weakly sourced
30-49: low confidence, mostly summary or unclear provenance
0-29: rumor, unsupported, misleading, or failed verification
```

Manual scoring UI is deferred. The data model should reserve:

```text
manual_score
manual_note
manual_updated_at
```

## 10. Deep Verification Policy

Deep verification means active search/cross-checking beyond the original page.

V1 default:

- Per-card `深度核验` button is the primary trigger.
- Settings can enable default deep verification.
- If default deep verification is enabled, apply it only to:
  - Bole Picks
  - each active topic's Top N items
- Do not deep-verify every low-value/all-mode item by default.

Deep verification should:

- Search or fetch official/primary sources when possible.
- Compare claims against primary material.
- Produce a concise conclusion, evidence links, and uncertainty.
- Cache results.
- Mark failed fetches and rate-limit errors clearly.

## 11. Verification Page

`核验` is a first-class mobile page.

Sections:

- Pending: items not yet verified.
- Low confidence: items with weak authority scores or failed verification.
- Deep queue: items waiting for or undergoing deep verification.
- Source scores: authority score trends for third-party sources.
- Primary coverage: which items have official/paper/GitHub/docs evidence.

The page is for daily trust management, not just debugging. It should help answer:

- Which news should I be careful about?
- Which third-party sources are reliable today?
- Which important items deserve deep verification?
- Where did the AI find primary evidence?

## 12. Global AI Assistant

`问 AI` opens as a mobile-friendly sheet or panel from any page.

Supported contexts:

- Current item
- Current category
- Today's Bole Picks
- All 24h signal items
- Verification page state

Example questions:

```text
总结今天最重要的 5 条
这条新闻有一手来源吗？
这个模型发布和之前有什么区别？
只看开发者工具，今天有什么值得试？
把低可信消息列出来
```

The assistant should always cite the item URLs or evidence URLs used in the
answer. It should say when context is insufficient instead of inventing facts.

## 13. Backend Architecture

Use FastAPI + SQLite.

Suggested modules:

```text
server/ai_radar_api/main.py
server/ai_radar_api/config.py
server/ai_radar_api/db.py
server/ai_radar_api/auth.py
server/ai_radar_api/radar_data.py
server/ai_radar_api/taxonomy.py
server/ai_radar_api/classifier.py
server/ai_radar_api/verification.py
server/ai_radar_api/assistant.py
server/ai_radar_api/provider.py
```

OpenAI-compatible provider configuration:

```text
AI_BASE_URL
AI_API_KEY
AI_MODEL
```

Other server environment variables:

```text
RADAR_PUBLIC_BASE_URL=https://withyouda.github.io/ai-news-radar-enhance
RADAR_ALLOWED_ORIGINS=https://withyouda.github.io
RADAR_ADMIN_PASSWORD=
RADAR_SESSION_SECRET=
RADAR_DB_PATH=server/data/radar.db
RADAR_MAX_CONTEXT_ITEMS=40
RADAR_DEEP_VERIFY_TOP_N=3
```

Initial API surface:

```text
GET  /health
POST /api/auth/login
POST /api/auth/logout
GET  /api/me
GET  /api/taxonomy
PUT  /api/taxonomy
POST /api/classify
GET  /api/verification/items
POST /api/verification/{item_id}/verify
POST /api/verification/{item_id}/deep-verify
POST /api/ask
GET  /api/settings
PUT  /api/settings
```

V1 can implement a smaller subset first, but the boundaries should follow this
shape.

## 14. Auth And Security

V1 is single-user.

Use simple password login:

- Admin password stored only in server environment variables.
- Login returns an HttpOnly session cookie.
- Session secret stored only in environment variables.
- CORS allows the GitHub Pages origin.
- Backend rejects unauthenticated mutation and ask/verify requests.
- Rate-limit AI endpoints.
- Do not log API keys, session cookies, private OPML, raw prompts containing
  private data, or full private-source content.

GitHub Pages is static and public. Treat every file published under `data/` as
public.

## 15. SQLite Storage Outline

Suggested tables:

```text
settings
  key
  value_json
  updated_at

sessions
  session_id_hash
  expires_at
  created_at

taxonomy_categories
  id
  label
  parent_id
  priority
  enabled
  rule_hints_json
  updated_at

item_classifications
  item_id
  url
  title_hash
  top_category
  sub_category
  confidence
  reason
  taxonomy_version
  model
  manual_override_json
  classified_at

verification_results
  item_id
  url
  status
  authority_score
  authority_reason
  evidence_json
  deep_verified
  manual_score
  manual_note
  model
  verified_at

source_scores
  source_id
  source_name
  base_score
  ai_score
  manual_score
  reason
  updated_at
```

Use migrations or explicit schema initialization so deployment can be repeated.

## 16. Front-End Design Constraints

Mobile:

- Bottom nav fixed to `今日 / 分类 / 核验 / 设置`.
- Floating `问 AI` stays reachable without covering core card actions.
- Cards should remain compact, readable, and finger-friendly.
- Category pages show top-level categories first, then only active second-level
  categories.
- Verification status should be visible but not make every card visually noisy.

Desktop:

- Existing desktop layout remains the baseline.
- New controls should be hidden, rearranged, or progressively enhanced on desktop
  unless explicitly designed.
- Do not replace the current desktop information density with a mobile-style app
  shell.

## 17. App Strategy

V1 should become a high-quality mobile web app first.

Fastest low-cost app path:

1. Make the mobile web reader work well.
2. Add PWA manifest and service worker.
3. Let the user install it to the phone home screen.
4. Later, wrap the PWA into Android through Trusted Web Activity if a Play Store
   style app is still needed.

Native Android should wait until the web UX and backend value are proven.

## 18. Acceptance Criteria

V1 design is implemented when:

- GitHub Pages still serves the existing radar data.
- Desktop layout is not visibly regressed.
- Mobile has the agreed bottom navigation.
- `今日` can show Bole Picks, category digest, and latest stream.
- `分类` uses seven top-level categories and dynamic second-level categories.
- Taxonomy/rules can be fetched from the server.
- `核验` shows verification states and source trust information.
- `问 AI` can answer using current radar context with citations.
- Backend stores settings, taxonomy, classifications, and verification results in
  SQLite.
- Secrets live only in GitHub Secrets or server environment variables.
- The implementation can run locally and be deployed to GitHub Pages + VPS.

## 19. Open Risks

- IP-only HTTPS may be harder than using a real domain. Validate certificate
  options early.
- AI classification and verification cost can grow. Cache aggressively and keep
  deep verification scoped.
- Original page fetching can fail because of blocking, dynamic pages, or paywalls.
  The UI must show uncertainty.
- Taxonomy quality will need real-world tuning after daily use.
- Public GitHub Pages must not receive private source content.

