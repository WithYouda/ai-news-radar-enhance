# Personalized Bole Design

Date: 2026-06-19

## Status

Accepted as the current product direction after visual companion review. This
document records the agreed requirements before implementation planning.

## Goal

Make **伯乐** the product's core personalized AI news assistant, not only a
global scoring rule. 伯乐 should learn what the user cares about, remember what
the user dislikes, explain how recommendations change, and help the user read
high-value items deeply.

The public feed can still work as a default Signal view, but signed-in users
should be able to make personalized recommendations their primary experience in
a later phase.

## Confirmed Requirements

### User Interest Learning

- 伯乐 must not assume it already knows the user's interests.
- The app needs an AI conversation/workbench that asks questions and turns the
  answers into an interest profile.
- The user may not know which categories they want, so fixed topic tags are only
  seeds. AI can propose dynamic topics from the conversation.
- Interest calibration must use a curated question bank that covers the AI
  field broadly, while only showing a short, focused set of questions in the UI.
- Every question must support both quick-choice options and free text. Free text
  is not an "other" escape hatch; it is a first-class answer path and can extend,
  override, or contradict selected options.
- User-written answers must be preserved as draft evidence so 伯乐 can explain
  why it proposed a profile change.
- The profile must support positive interests, negative interests, source
  preferences, and AI behavior preferences.
- AI may propose profile changes after chat or feedback, but changes must be
  user-confirmed before becoming active.

### Calibration Question Bank

The question bank should cover AI broadly without turning onboarding into a long
survey. The first-run workbench should show five core questions, and AI can ask
follow-ups only where the user's answers show interest or ambiguity.

Baseline question areas:

- `关注目标`: useful tools, model capability changes, developer integration,
  research learning, industry impact, business signals.
- `AI 方向`: Agent, multimodal, code AI, open models, local deployment, RAG /
  knowledge bases, AI search, robotics, AI hardware, safety and regulation.
- `内容类型`: model releases, product updates, developer tools, open-source
  projects, papers, benchmarks, funding/M&A, policy, incidents, pricing, cases.
- `负偏好`: funding-only posts, marketing posts, duplicated reposts, vague
  opinions, overly academic items, shallow summaries.
- `处理方式`: rank higher only, read body on high match, summarize, fact-check,
  wait until the user opens the item.
- `阅读深度`: quick scan, standard summary, deep analysis, engineering details,
  fact-check first.

Each question should include concise quick options plus a free-input field. The
initial five questions are: priority goal/content value, negative preferences,
AI domains, high-match handling, and reading depth. The underlying bank must be
broad enough for AI to follow up into subtopics such as Agent
products/frameworks, local deployment/quantization/hardware, content-type
preferences, or industry-specific applications.

### Feedback And Recommendation Correction

- Users need readable controls to say an item is more relevant, less relevant,
  not interested, or worth seeing more often.
- Feedback should update a pending profile draft or recommendation weights, not
  silently mutate the user profile.
- The user must be able to review, edit, undo, reset, or disable personalization.
- Recommendation explanations should be short and useful, for example "because
  you follow Agent productization", not a long debug report.

### Deep Reading And Verification

- If title/source signals strongly match the user's profile, 伯乐 may fetch or
  read the article body for deeper understanding.
- Deep reading should produce a concise summary, key facts, and why the item is
  recommended.
- Important summaries should be checked by multiple AI passes or models where
  practical.
- High-risk claims should trigger a factual verification pass that cites source
  material and marks uncertainty instead of inventing certainty.
- Deep reading must be cache-first, budget-aware, and optional; it must not make
  the public static feed depend on heavy browser automation.

### X API And User Customization

- X content is not a public default dependency.
- Users may opt into their own X API integration and choose tracked accounts,
  search terms, limits, and behavior inside the app.
- Any X API option must be visible, readable, editable, reversible, and disabled
  by default.
- Secrets and tokens must stay server-side or in deployment secrets. They must
  never be committed or shown back in full.

### First-Use Workbench

- On first login or first use of personalization, the app should actively open
  **伯乐画像工作台**.
- The user can skip the workbench and continue with public/default recommendations.
- Skipping is not permanent. The user can reopen the workbench from `为你推荐` or
  settings.
- The workbench should let users reach a useful first profile quickly, then
  refine it over time through chat and feedback.

## UI Direction

### Shared Mental Model

Desktop and mobile must use the same section titles and interaction model:

- `兴趣校准`
- `阅读偏好`
- `画像草稿`

The layout may change by screen size, but section naming and user intent should
remain consistent.

### Desktop

- Use a horizontal workbench where the user can see the relationship between
  answers, profile draft, and recommendation preview.
- Keep controls close to the relevant section.
- Avoid long onboarding explanations. Let titles, examples, and actions carry
  the workflow.

### Mobile

- Do not squeeze the desktop workbench into a long vertical form.
- Show the current step first and keep later states compact.
- Keep primary actions visible near the bottom.
- Avoid internal progress labels such as `1/4` unless they directly help the
  user act at that moment.

### Interaction States To Cover

The design must account for these states on both desktop and mobile:

- Initial workbench open.
- User answers a calibration question through quick options, free text, or both.
- User bypasses question flow and directly adds a custom preference.
- AI asks a follow-up or prepares a profile draft.
- Profile draft is shown for review.
- Recommendation preview shows what will change.
- User saves the profile.
- User skips and sees a later entry point to start personalization.
- User reopens the workbench from recommendations or settings.

### Copy Rules

- Do not expose implementation rules as reader-facing UI text.
- Do not show filler explanations, duplicated guidance, decorative copy, or
  internal labels such as "first login auto popup", "not saved until confirmed",
  or `1/4` unless the exact phrase directly helps the user complete the current
  action.
- Keep visible text short, concrete, and action-oriented.

## Data Model Direction

### Profile

A future profile should include:

- User-confirmed interest topics with weights.
- User-confirmed negative topics with weights.
- Source preferences.
- AI behavior preferences, such as summary depth or verification strictness.
- Version, timestamps, and last-confirmed state.

### Drafts

AI-generated changes should be stored as drafts:

- `not_started`
- `skipped`
- `draft_pending`
- `confirmed`

Drafts allow AI to suggest changes without silently changing the active profile.

### Feedback

Feedback records should preserve:

- News item identity.
- User action.
- Optional reason.
- Timestamp.
- Whether it produced a profile draft or only adjusted session ranking.

## System Architecture Direction

- Public `data/*.json` remains public and non-personal.
- Private user profiles, feedback, settings, API tokens, and deep-read history
  belong in the backend SQLite database.
- The static frontend must degrade cleanly when no backend is configured.
- Personalized ranking should be an overlay on top of the existing public feed,
  not a replacement for source fetching.
- Any backend/API/DB/schema/runtime implementation requires server deployment
  and PM2 restart after validation.

## Implementation Phases

### Phase 1: Profile Workbench Foundation

- Add the first-use workbench UI and settings entry point.
- Store explicit user-confirmed profile data.
- Support skip, reopen, edit, reset, and disable states.
- Keep public static fallback intact.

### Phase 2: Personalized Ranking And Feedback

- Apply profile weights to recommendation ordering.
- Add simple feedback controls.
- Produce pending profile adjustments from repeated feedback.
- Show concise recommendation reasons.

### Phase 3: AI Conversation Memory

- Add chat-driven interest discovery.
- Let AI ask follow-up questions and propose profile drafts.
- Require user confirmation before saving changes.

### Phase 4: Deep Reading And Verification

- Deep-read high-match or high-value items.
- Summarize with citations or source references.
- Add multi-pass or multi-model cross-checking where practical.
- Add fact-check status and uncertainty labels.

### Phase 5: Recommendation-First Home

- Let users choose `为你推荐` as the homepage.
- Keep public Signal view available as a fallback and comparison layer.
- Avoid making personalization mandatory for casual users.

## Testing And Verification Requirements

Before implementation, create tests first for any behavior change.

Required coverage includes:

- First-use popup state without violating the mobile overlay pitfall.
- Skip, reopen, save, edit, reset, and disable flows.
- AI-proposed profile changes requiring user confirmation.
- Static frontend fallback when backend personalization is unavailable.
- Mobile/PWA stale cache compatibility for any frontend asset change.
- Desktop and mobile visual verification for workbench layouts.
- Secret safety for X API and other user-owned integrations.
- Regression tests for ranking behavior and neighboring edge cases.

For UI implementation, follow visual companion first, then use Playwright or an
equivalent browser check on desktop and mobile. Delete temporary screenshots
after verification.

## Open Decisions For Implementation Planning

- Exact backend schema names and API route shapes.
- Whether the first profile draft is generated locally from rules or through the
  configured AI provider.
- Which model or model pair is used for deep-read cross-checking.
- How aggressively to budget deep reads per day.
- Whether recommendation explanations are generated server-side or derived from
  structured ranking signals in the frontend.
