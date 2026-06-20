# Scoring System Improvement Plan

Date: 2026-06-19
Scope: AI relevance scoring, Bole Picks ranking, event clustering, audit tooling
Status: Draft for review

## 1. Goal

Improve the current scoring system from a usable rule-based AI news filter into a
more reliable, inspectable ranking pipeline.

The target is not to add a heavy LLM classifier into the default GitHub Actions
path. The target is to keep the system cheap, deterministic, testable, and
suitable for static-site generation, while improving:

- AI relevance recall and precision.
- Score resolution.
- Separation between topic relevance, source trust, and reading priority.
- Bole Picks ranking quality.
- Event clustering accuracy.
- Auditability and regression protection.

## 2. Current Assessment

The current system is a good lightweight explainable filter, but not yet a robust
importance-ranking system.

Strengths:

- `scripts/ai_relevance.py` emits inspectable fields such as `ai_score`,
  `ai_label`, `ai_signals`, `ai_relevance_reason`, and `ai_noise`.
- The default path is deterministic and cheap enough for GitHub Actions.
- The scoring rules already include source priors, AI terms, tech context, and
  noise suppression.
- Bole Picks adds a reader-facing ranking layer using AI score, source signals,
  source diversity, event merging, and recency.

Main weaknesses:

- Many kept items cluster around `0.65-0.69`, so the score has weak ranking
  resolution.
- `ai_score` mixes AI topical relevance with source trust.
- `scripts/ai_relevance.py` currently includes the full URL in scoring text,
  which can create false positives from URL paths or query strings.
- Chinese/mixed AI terms have recall gaps, for example `VLA`, `世界模型`,
  `Agent时代`, `桌面 Agent`, `智能体平台`, and model/product names that are
  important but not always obvious.
- Bole event clustering currently relies too much on coarse keys such as model
  names.
- Multi-source evidence is heuristic and can over-count duplicates from the same
  upstream source.

## 3. Design Direction

Split the scoring pipeline into three concepts:

1. `ai_relevance_score`
   Measures whether the item is actually about AI, models, agents, AI
   infrastructure, AI products, AI research, or AI industry.

2. `source_trust_score`
   Measures how much confidence the system has in the source as an information
   channel.

3. `priority_score`
   Measures how worth-reading the item is for Bole Picks and top lists.

Keep `ai_score` during migration for compatibility. Initially it can remain an
alias to the old score or to `ai_relevance_score`, but the plan should explicitly
migrate readers and tests to the clearer fields.

## 4. Phase 0: Baseline Audit And Golden Set

Before changing scoring logic, create a reproducible baseline.

Tasks:

- Extend or add an audit report that summarizes:
  - raw item count
  - kept item count
  - rejected item count
  - score buckets
  - source-level keep rate
  - review-band candidates
  - high-scoring rejected samples
  - low-confidence kept samples
- Create a manually reviewed golden fixture, for example:
  - `tests/fixtures/ai_relevance_golden.json`
- The fixture should include:
  - obvious AI positives
  - Chinese AI positives
  - mixed Chinese/English AI positives
  - agent/model false positives from non-AI business contexts
  - official-source items
  - aggregator duplicates
  - URL-noise examples
  - review-band examples

Success criteria:

- A baseline report exists before any scoring behavior changes.
- Golden-set tests can fail when recall or precision regresses.
- The baseline records current known weaknesses instead of hiding them.

Suggested commands:

```bash
python3 -m pytest -q tests/test_ai_relevance.py tests/test_topic_filter.py
python3 -m pytest -q
python scripts/audit_ai_relevance.py --data-dir data --output reports/ai-relevance-audit/baseline-2026-06-19.md
```

## 5. Phase 1: Fix URL Scoring Leakage

Problem:

`score_ai_relevance()` currently scores text built from title, source, site name,
and full URL. Full URL paths and query strings can contain unrelated AI-looking
tokens.

Plan:

- Replace full URL scoring with host-only or controlled URL signals.
- Keep useful source identity from domain names.
- Do not let path/query fragments directly trigger AI relevance.
- Add tests for:
  - Google News or redirect URLs containing noisy encoded paths.
  - A trusted AI domain where host identity should still help.
  - A non-AI article whose URL path includes misleading `ai`, `agent`, or
    `model`.

Success criteria:

- Host identity can contribute source context.
- URL path/query cannot by itself push an unrelated article over the AI
  threshold.

## 6. Phase 2: Split Relevance, Trust, And Priority

Problem:

One score currently carries too many meanings.

Plan:

- Add structured fields:
  - `ai_relevance_score`
  - `source_trust_score`
  - `priority_score`
  - `score_version`
- Keep compatibility fields:
  - `ai_score`
  - `ai_label`
  - `ai_relevance_reason`
  - `ai_signals`
  - `ai_noise`
- Update payload metadata from `ai_relevance_scoring_v0_4` to a new version once
  behavior changes.
- Keep the public filter threshold based on relevance, not source trust.

Success criteria:

- A low-trust source with a very AI-specific story can still be kept.
- A trusted source does not automatically make a weakly related story look
  strongly AI-related.
- Bole Picks can rank by `priority_score` without redefining AI relevance.

## 7. Phase 3: Improve Keyword And Rule Coverage

Plan:

- Expand AI signal dictionaries for:
  - Chinese terms: `智能体`, `多模态`, `世界模型`, `推理模型`, `开源模型`,
    `具身智能`, `AI 编程`, `AI 搜索`
  - mixed terms: `VLA`, `RAG`, `MCP`, `Agent SDK`, `AI coding`,
    `desktop agent`
  - product/model style terms when paired with context.
- Add stronger context rules for broad terms:
  - `agent`
  - `model`
  - `assistant`
  - `automation`
- Add explicit false-positive tests for non-AI meanings:
  - insurance agent
  - real estate agent
  - business model
  - fashion model
  - agency/news agency

Success criteria:

- Known misses like VLA/Agent-era/model-release style stories are easier to
  capture.
- Broad English words do not create large false-positive drift.

## 8. Phase 4: Improve Event Clustering

Problem:

Bole Picks event clustering is too coarse and can merge unrelated stories around
the same model/vendor name.

Plan:

- Replace model-name-only event keys with a normalized event key built from:
  - normalized title tokens
  - model/vendor/product entities
  - action words such as release, benchmark, acquisition, pricing, outage,
    policy
  - source/time window
- Keep clustering conservative at first.
- Prefer not merging over incorrectly merging unrelated stories.
- Add tests for:
  - two unrelated Gemini stories should not merge.
  - same story from multiple sources should merge.
  - same upstream source duplicated through multiple feeds should not count as
    independent corroboration.

Success criteria:

- Bole Picks still collapses real duplicates.
- Important unrelated stories do not disappear under one merged event.

## 9. Phase 5: Make Bole Picks A Priority Ranking Layer

Plan:

- Make Bole Picks use `priority_score`.
- Build priority from separate components:
  - AI relevance
  - source trust
  - independent source corroboration
  - official/source-of-record bonus
  - event freshness
  - HN/GitHub/AI HOT-style popularity where available
  - duplicate penalty
- Keep the visible explanation short:
  - why selected
  - source evidence
  - score components if useful
- Keep Top 10 as the default.

Success criteria:

- Bole Picks is no longer just "highest AI score".
- It surfaces important, independently corroborated stories.
- It still includes official one-source releases when they are clearly
  high-value.

## 10. Phase 6: Review Band For Future Second Pass

Plan:

- Keep `0.45 <= ai_relevance_score < 0.65` as a review band.
- Do not publish review-band items into the default AI Signal view.
- Use the band for audit reports and possible future manual/LLM review.
- Keep LLM classification out of the default public update path unless
  separately approved.

Success criteria:

- The project can inspect likely misses without increasing public noise.
- Future heavier classification remains optional.

## 11. Phase 7: Rollout And Compatibility

Plan:

- Add tests first.
- Change scoring internals behind compatible output fields.
- Bump metadata:
  - `topic_filter=ai_relevance_scoring_v0_5`
- If frontend reads new fields, bump cache bust in `index.html`.
- Keep old fields until the UI and audit scripts are fully migrated.
- Update `docs/ROADMAP.md` after implementation to record what shipped.

Rollback strategy:

- Keep the old threshold and compatibility fields.
- If the new ranking behaves badly, the public AI filter can continue using
  old-compatible `ai_score` while `priority_score` is disabled or ignored.
- Keep changes small enough to revert phase by phase.

## 12. Required Tests

Before implementation:

```bash
python3 -m pytest -q tests/test_ai_relevance.py tests/test_topic_filter.py
```

After each scoring change:

```bash
python3 -m pytest -q tests/test_ai_relevance.py tests/test_topic_filter.py
python3 -m py_compile scripts/ai_relevance.py scripts/update_news.py
```

Before completion:

```bash
python3 -m pytest -q
git diff --check
```

If frontend display or Bole Picks UI fields change:

```bash
node --check assets/app.js
python3 -m pytest -q tests/test_mobile_frontend_contract.py tests/test_frontend_static_contract.py
```

If generated data format changes:

```bash
python scripts/update_news.py --output-dir /tmp/ai-news-radar-scoring-preview --window-hours 24 --rss-opml feeds/follow.opml
python scripts/audit_ai_relevance.py --data-dir /tmp/ai-news-radar-scoring-preview --output reports/ai-relevance-audit/v0.5-preview.md
```

## 13. Risks

- A meaningful scoring improvement needs a manually reviewed golden set. Without
  it, test coverage can accidentally preserve old mistakes.
- The current local data snapshot may not represent fresh production
  distribution.
- Better recall can increase noise unless false-positive tests are added at the
  same time.
- Event clustering mistakes are reader-visible because they can hide or merge
  stories.
- Frontend field changes can be affected by stale mobile/PWA caches, so cache
  busting and stale-HTML compatibility tests are required if UI code changes.

## 14. Proposed Implementation Order

1. Add audit/golden-set tests.
2. Fix URL scoring leakage.
3. Split score fields while preserving `ai_score`.
4. Expand keyword/context coverage.
5. Improve event clustering.
6. Move Bole Picks to `priority_score`.
7. Update docs and roadmap.
8. Run full verification.
