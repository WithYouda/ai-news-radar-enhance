# AI News Radar Agent Notes

## Scope

This repo powers the public AI News Radar static site and Scout Skill source workflow.
Use it for high-signal AI/tech news aggregation, OPML-based custom feeds,
GitHub Actions refresh jobs, and GitHub Pages publishing.

## Working Rules

- Iron law: before planning or writing code, read `docs/PROJECT_PITFALLS.md`
  and explicitly check the current task against the recorded pitfalls. If a
  change causes or fixes a production/user-visible failure, add a concise entry
  to that file in the same change. Do not call work complete until the relevant
  pitfall has a regression test or a documented verification command.
- Iron law: after drafting tests and again after implementation, review whether
  the tests are too narrowly tailored to the assumed bug. Add adversarial and
  corner-case coverage for adjacent failure modes before moving on.
- Iron law: agents run verification commands, local preview servers, and local
  browser checks themselves whenever permissions allow. Do not ask the user to
  run commands for validation; the user should only need to open provided links,
  inspect previews/screenshots, or report visible behavior. If sandbox,
  credentials, network, or OS permissions prevent an agent-side command, state
  the exact blocker and request approval or user-side verification.
- Keep changes small and reviewable.
- Search the repo before changing source fetchers or output schemas.
- Do not commit private feeds, secrets, tokens, cookies, or `.env` values.
- Do not commit `feeds/follow.opml`; use `feeds/follow.example.opml` as the public template.
- When the user says a change is temporarily unverifiable, append it to
  `docs/PENDING_USER_VERIFICATION.md` with agent-side evidence and the next
  user-visible check.
- Iron law: for any UI design or layout change, offer and use the visual
  companion workflow before implementation so the user can inspect mockups or
  previews instead of judging from text alone.
- Iron law: visual companion previews for production UI must be production-faithful
  and fully interactive for the workflow being reviewed. Do not show a static,
  partial, or semi-interactive mockup when the real feature depends on tabs,
  choices, side panels, deletion, save/continue/skip actions, animation, or
  responsive state. Before presenting a preview, agents must click through the
  same controls a user will rely on and verify that visible state updates match
  the intended production behavior.
- Iron law: visual companion previews must be drawn on top of the already
  implemented UI surface unless the user explicitly asks for a large redesign.
  If the user asks for a dialog, drawer, feedback control, or interaction inside
  an existing page, simulate the real surrounding page, layout constraints,
  entry points, row/card clicks, and motion. Do not invent detached panels,
  reserve large empty space for collapsed controls, add redundant buttons for an
  action that the current UI already supports, or replace established interaction
  patterns without explicit approval.
- Iron law: reader-facing UI and visual companion mockups must stay concise.
  Do not add filler explanations, duplicated guidance, or decorative text that
  does not help the user make a decision or complete the workflow. Responsive
  variants of the same feature must use consistent section titles and mental
  models across desktop and mobile, while adapting layout density to the screen.
  Do not expose implementation rules or internal flow labels such as "first
  login auto popup", "not saved until confirmed", or "1/4" as visible UI copy
  unless that exact text directly helps the reader act at that moment.
- Iron law: UI design must stay elegant, simple, and faithful to the user's
  stated intent. Do not add new visible elements, labels, panels, controls,
  decorative details, or explanatory copy that the user did not explicitly ask
  for or clearly imply. If the intent is ambiguous, ask a concise clarification
  instead of inventing extra UI.
- Iron law: for reader-facing icons and visual assets, search for suitable
  mature assets first and prefer the project's existing icon system or proven
  open-source icon libraries. Only hand-draw icons or visual elements when the
  user explicitly asks for custom drawing or no suitable mature asset can be
  found.
- Iron law: do not blindly mirror every user idea as implementation. Treat user
  ideas as product input, evaluate whether they solve the real workflow, and
  give practical pushback or a better recommendation when appropriate. During
  planning, actively ask whether a simpler, clearer, or more durable approach
  exists. After the user confirms a direction, execute it decisively; stop to
  re-evaluate only when implementation reveals a material constraint or risk
  that was not visible during planning.
- Iron law: any user-customizable capability must have a corresponding
  reader-facing, highly readable setting inside the app. Do not add hidden-only
  customization through environment variables, code constants, undocumented
  JSON, or maintainer-only files when the feature is meant for user choice.
  Advanced options such as enabling X API, choosing tracked X accounts, tuning
  recommendation interests, source preferences, or AI behavior must be visible,
  explainable, editable, and reversible in the app UI, with clear disabled and
  fallback states.
- Prefer stable public RSS/Atom/OPML sources before adding custom scrapers.
- Keep the reader-facing product simple: default to a curated AI-focused view, hide noisy or advanced source details behind existing filters/docs.

## Source Strategy

Read `docs/SOURCE_COVERAGE.md` before adding or removing sources.

Default source priority:

1. Official RSS/Atom feeds and OPML collections.
2. Stable public JSON APIs or static pages with timestamps.
3. Curated newsletters or changelogs with public feeds.
4. Manual/custom adapters only when the source is high-signal and stable.

Avoid account-bound timelines, broad personal social feeds, login-gated pages,
and fragile bridges unless the user explicitly accepts the maintenance cost.

## Common Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m py_compile scripts/update_news.py
python -m pytest -q
python scripts/update_news.py --output-dir data --window-hours 24 --rss-opml feeds/follow.opml
python -m http.server 8080
```

For agent workflows, read `skills/ai-news-radar/SKILL.md`.
