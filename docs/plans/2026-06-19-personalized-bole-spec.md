# Personalized Bole Framework Spec

Date: 2026-06-19

Related design: `docs/plans/2026-06-19-personalized-bole-design.md`

## Purpose

This spec gives development a stable frame for the personalized **伯乐** system
without freezing every implementation detail up front. It defines product
invariants, phase boundaries, data ownership, integration points, and acceptance
criteria. Phase-level implementation plans may refine fields, prompts, routes,
and UI micro-interactions as long as they do not violate this spec.

## Product Invariants

These are non-negotiable unless this spec is explicitly revised:

- 伯乐 must learn from the user. It must not pretend to know interests before
  the user gives explicit or behavioral signals.
- AI-generated profile changes are drafts until the user confirms them.
- Every interest-calibration question must offer both quick-choice options and a
  free-text answer. Free text is first-class input and must not be constrained
  by the preset choices.
- The user can skip personalization, reopen it later, edit it, reset it, or
  disable it.
- Personal data, feedback, API tokens, and deep-read history stay private in the
  backend. Public `data/*.json` remains non-personal.
- The static site still works without the backend or personalization APIs.
- Any user-customizable capability must have a readable in-app setting.
- UI copy must stay concise and user-facing. Do not expose implementation rules
  or internal labels as visible text.
- Desktop and mobile may use different layouts, but they must share the same
  mental model and section names.
- UI/layout work requires visual companion before implementation and desktop plus
  mobile browser verification after implementation.
- Behavior changes require tests first, including regression and neighboring
  adversarial coverage.

## Existing Pitfall Checks

This feature touches several recorded pitfalls:

- **Mobile View Switching Can Unhide Overlay Panels**: the first-use workbench is
  an overlay/sheet/modal. It must not use `data-mobile-view` or any mobile view
  mechanism that can unhide it accidentally.
- **Frontend Client Split Broke Mobile/PWA Runtime**: frontend changes must keep
  stale mobile cached HTML compatible, preserve synchronous globals used by
  render paths, and bump cache-busting query strings when shipped.
- **X Status Pages Were Treated Like Fetchable Articles**: X integration must not
  assume `x.com` status pages are readable article pages. Prefer API/public feed
  item text for X posts.
- **Clean Article Fallback Cache Retried Immediately** and **Clean Article Cache
  Hit Was Behind News Item Lookup**: deep-read work must remain cache-first and
  must not turn repeated opens into repeated fetches.
- **Full URL Text Inflated AI Relevance Scores**: personalization and ranking
  must not score full URL paths/query strings as semantic interest signals.

If a future implementation exposes a new production/user-visible failure, add a
new entry to `docs/PROJECT_PITFALLS.md` with a regression test or verification
command.

## Scope Model

### Phase 1: Profile Workbench Foundation

Build the minimum user-confirmed profile loop:

- First-use workbench can open after login or first personalization entry.
- User can answer short interest-calibration questions using quick options,
  free text, or both.
- User can bypass the question flow and directly add custom interests,
  dislikes, source preferences, or reading preferences.
- App creates a profile draft.
- User can save, skip, edit, reset, disable, and reopen from `为你推荐` or
  settings.
- Static frontend fallback remains unchanged when the backend is unavailable.

Phase 1 may use rule-generated drafts before model-generated drafts if that
reduces risk. It must still preserve the same user-facing flow.

### Phase 2: Personalized Ranking And Feedback

Use the confirmed profile to reorder recommendations:

- Apply positive interests, negative interests, source preferences, and simple
  behavior preferences to ranking.
- Add feedback controls that are readable and reversible.
- Feedback may tune session ranking immediately, but persistent profile changes
  must be drafted and confirmed.
- Recommendation explanations must be short and derived from real ranking signals.

### Phase 3: AI Conversation Memory

Add a stronger learning loop:

- AI can ask follow-up questions.
- AI can infer candidate topics from quick choices, free-text answers, and
  follow-up conversation.
- AI can propose profile edits from repeated feedback or explicit chat.
- The app records enough context to explain why a draft changed.
- The user still confirms before active profile mutation.

### Phase 4: Deep Reading And Verification

Use body text only when it is worth the cost:

- Deep-read items that strongly match the profile or are likely high-value.
- Summaries include concise key facts, why it matters, and uncertainty.
- Important outputs use multi-pass or multi-model cross-checking where practical.
- Fact-checks cite available source material and mark uncertainty.
- Deep reading is cache-first, budget-aware, optional, and does not make browser
  automation a default production dependency.

### Phase 5: Recommendation-First Home

Make personalized recommendations a first-class product surface:

- User can set `为你推荐` as the homepage.
- Public Signal view stays available.
- First-time and anonymous users still get a useful public default.

## Data Ownership And Boundaries

### Public Data

Public generated files remain non-personal:

- `data/latest-24h.json`
- `data/latest-24h-all.json`
- `data/archive.json`
- `data/source-status.json`

They may include public scoring fields such as AI relevance and priority score,
but must not include user profile, feedback, private source settings, tokens, or
deep-read private history.

### Private Backend Data

Backend SQLite owns:

- Active personalization profile.
- Pending profile drafts.
- Recommendation feedback.
- User settings for personalization and homepage preference.
- X API settings metadata and encrypted/secret-backed token state.
- Deep-read summaries, verification outputs, and cache metadata.

Exact table names and JSON column shapes can be chosen during implementation,
but every private record must have enough timestamp/version metadata for safe
editing, rollback, and debugging.

## Profile Contract

The active profile should be expressible as structured data with these concepts:

- Positive interests with weights.
- Negative interests with weights.
- Preferred and downweighted sources.
- AI behavior preferences such as summary depth and verification strictness.
- Structured calibration answers, including selected quick choices and original
  free-text answers when they informed the profile.
- Version and confirmation metadata.

The exact field names are flexible. Implementers should prefer names that match
the surrounding backend style and are easy to expose through sanitized APIs.

## Draft Contract

Drafts represent AI or rule-generated suggestions that are not yet active.

Required states:

- `not_started`
- `skipped`
- `draft_pending`
- `confirmed`

The implementation may add more states later, but these states must remain
representable. Drafts must preserve enough evidence for the user or developer to
understand why the suggested change exists.

## Calibration Question Bank Contract

The question bank is part of 伯乐's product behavior. It must be broad enough to
cover the AI field, but the UI must keep the first run short and readable. The
first-run workbench must show five core questions.

Each question must define:

- A concise user-facing title.
- A stable question id.
- A set of quick-choice options.
- A free-text answer field.
- The profile fields it can influence.
- Optional follow-up topics that AI can ask when the answer is ambiguous or
  strongly focused.

Required first-run questions:

- `attention_goal`: whether the user wants useful tools, model capability
  changes, developer integration, research learning, industry impact, or
  business signals.
- `negative_preferences`: funding-only posts, marketing posts, duplicate
  reposts, vague opinions, overly academic items, and shallow summaries.
- `ai_domains`: Agent, multimodal, code AI, open models, local deployment, RAG
  or knowledge bases, AI search, robotics, AI hardware, safety, and regulation.
- `deep_reading_policy`: rank higher only, read body on high match, summarize,
  fact-check, or wait until the user opens the item.
- `reading_depth`: quick scan, standard summary, deep analysis, engineering
  details, or fact-check first.

The broader question bank must also cover content-type follow-ups such as model
releases, product updates, developer tools, open-source projects, papers,
benchmarks, funding/M&A, policy, incidents, pricing, and application cases.

Free-text answers have priority when building drafts. If free text conflicts
with quick-choice selections, the draft must preserve both as evidence and ask
the user to confirm the resulting interpretation before activation.

## Feedback Contract

Feedback must capture:

- Item identity.
- Feedback action.
- Optional user-provided reason.
- Timestamp.
- Whether the action changed only session ranking or created a persistent draft.

Allowed action names can be refined later. The first implementation should keep
the set small enough to be obvious in the UI.

## API Shape

This spec does not freeze exact route names, but the backend must expose these
capabilities through authenticated APIs:

- Read active personalization status.
- Read and save profile drafts.
- Confirm or discard a draft.
- Reset or disable personalization.
- Record item feedback.
- Fetch personalized recommendation ordering or ranking annotations.
- Read and update personalization-related settings.
- Read sanitized X integration settings and update them without exposing secrets.

API responses must separate:

- `active_profile`: user-confirmed data.
- `draft_profile`: pending AI/user edits.
- `recommendation_annotations`: explainable ranking hints.
- `capabilities`: backend feature availability and disabled/fallback states.

The frontend must handle missing or unavailable APIs by falling back to the
public static experience.

## UI Specification

### Workbench

The workbench has three conceptual sections:

- `兴趣校准`
- `阅读偏好`
- `画像草稿`

Desktop may show multiple sections side by side. Mobile should show the current
section first and keep the flow short. Do not make the mobile version a long
vertical copy of desktop.

`兴趣校准` must render each visible question with quick choices and a free-input
field. `阅读偏好` covers recommendation posture, summary depth, deep-reading
trigger, and fact-check strictness. `画像草稿` shows what will change and includes
save, continue-calibration, and skip actions.

### First-Use Behavior

When personalization has not been started, the app may actively open the
workbench after login or first entry into personalization. The user can skip.
Skip must be reversible through a visible entry point.

Implementation note: do not expose internal rules such as "first login auto
popup" in user-facing copy. The UI should communicate through action labels and
state, not explanatory implementation text.

### Entry Points

At minimum:

- `为你推荐` can open or reopen the workbench.
- Settings can open personalization controls.
- Feedback controls can lead to a profile draft when enough signal exists.

### Copy And Layout Rules

- Keep visible text short and action-oriented.
- Do not show filler onboarding explanations.
- Do not show internal progress labels such as `1/4` unless a future visual
  review proves they improve clarity.
- Do not add cards inside cards or decorative content that does not serve the
  workflow.
- Desktop and mobile titles must stay consistent for the same conceptual section.

## X Integration

Direct X API is optional and user-owned:

- Disabled by default.
- Configured only through readable app settings.
- Tracks user-selected accounts/search terms/limits.
- Shows cost/rate-limit or disabled/fallback states.
- Stores secrets only server-side or in deployment secrets.
- Never shows full tokens back to the frontend.

Default public coverage may continue to rely on public generated feeds such as
Follow Builders.

## Deep Reading And Verification

Deep reading is an enhancement to recommendations, not a requirement for the
basic feed:

- Trigger from high profile match, user action, or high-value ranking.
- Reuse existing clean article cache and reader safety constraints.
- Prefer item text for X posts instead of fetching `x.com` HTML.
- Do not bypass paywalls, login walls, subscriptions, or source terms.
- Cache summaries and verification outputs with source/version metadata.
- Mark unavailable, restricted, or uncertain states explicitly.

Future implementation plans can decide the model/provider path. The spec only
requires that summaries and checks are traceable, bounded, and reversible.

## Testing Strategy

Each implementation slice must start with failing tests where feasible.

Required test classes:

- Backend profile/draft API tests.
- Backend feedback recording tests.
- Ranking tests for positive and negative interests.
- Static fallback tests when personalization APIs are unavailable.
- Frontend contract tests for first-use workbench markup and hidden startup
  state.
- Mobile/PWA cache compatibility tests for frontend asset changes.
- X integration default-off and secret-safety tests.
- Deep-read cache and unavailable/restricted fallback tests.

For UI slices:

- Use visual companion before implementation.
- Use Playwright or an equivalent local browser check after implementation.
- Verify desktop and mobile.
- Delete temporary screenshots after validation.

## Acceptance Gates

No phase is complete until:

- Relevant tests pass.
- `node --check assets/app.js` passes if frontend JS changed.
- Python compile checks pass for changed backend/scripts.
- `git diff --check` passes.
- Local preview/server checks are run by the agent.
- Frontend asset cache busts are updated when shipped behavior changes.
- Backend/API/DB/runtime changes are deployed to the server and PM2 is restarted
  when the change is meant to run there.

## Spec Evolution Rules

This spec is intentionally a framework, not a frozen blueprint.

Allowed during implementation:

- Add route names, schemas, table definitions, prompt templates, and exact UI
  states for the current slice.
- Replace a suggested approach with a simpler one if it preserves the product
  invariants and passes tests.
- Split a phase into smaller implementation plans.
- Add new acceptance checks when a new risk appears.
- Append slice-specific details after the slice design is validated, instead of
  guessing all future details before code teaches us the right shape.

Not allowed without revising this spec:

- Silent AI mutation of active user profile.
- Hidden-only user customization.
- Making personalization mandatory.
- Publishing private profile or token data to public `data/*.json`.
- Treating X web pages as generally readable article bodies.
- Skipping mobile visual verification for UI changes.
- Adding long explanatory copy that violates the UI concision rule.

## First Development Slice Recommendation

Start with Phase 1 only:

- Backend profile status and draft persistence.
- Frontend workbench shell with skip/reopen/save states.
- No deep reading.
- No X API UI beyond documenting the future settings area.
- No recommendation-first homepage switch yet.

This slice is small enough to verify end to end and large enough to establish
the core contract that later phases will build on.
