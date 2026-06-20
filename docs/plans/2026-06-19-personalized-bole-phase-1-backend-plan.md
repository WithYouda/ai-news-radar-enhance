# Personalized Bole Phase 1 Backend Plan

Date: 2026-06-19

## Scope

Implement only the backend foundation for personalized 伯乐 profiles:

- Private SQLite persistence for active profile, draft profile, and status.
- Authenticated API routes for status, draft save, confirmation, skip, reset,
  and disable.
- No frontend workbench UI in this slice.
- No ranking changes, X API settings UI, deep reading, or homepage switch.

## Files

- Create `server/ai_radar_api/personalization.py`
  - Owns profile defaults, validation, status shaping, and SQLite operations.
- Create `server/ai_radar_api/routers/personalization.py`
  - Owns authenticated FastAPI routes.
- Modify `server/ai_radar_api/db.py`
  - Adds tables for personalization state and drafts.
- Modify `server/ai_radar_api/main.py`
  - Registers the personalization router.
- Add `tests/test_ai_backend_personalization.py`
  - Covers storage behavior and API behavior.

## TDD Steps

1. Write tests for default status and authentication.
2. Run those tests and verify they fail because the route/module does not exist.
3. Add the minimal schema, module, and router for default status.
4. Run focused tests until green.
5. Add tests for draft save and confirmation.
6. Run and watch them fail.
7. Implement draft persistence and confirmation.
8. Add adversarial tests for invalid draft shape, disabled state, and reset.
9. Implement the minimal validation/state transitions.
10. Run focused tests, backend compile checks, related backend tests, and
    `git diff --check`.

## Constraints

- Do not expose personalization data through public `data/*.json`.
- Do not add secrets or tokens.
- Keep every API authenticated.
- Preserve static frontend fallback by not requiring these APIs for existing
  reader paths.
- If UI is added later, use visual companion first and test mobile overlay
  startup behavior.
