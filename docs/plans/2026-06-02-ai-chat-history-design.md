# AI Chat History Design

## Goal

Add persistent, globally visible Ask AI conversation history with automatic context labels.

## Scope

This change stores successful Ask AI turns in the backend database and exposes them to the mobile UI as a global history view. It does not fetch article bodies or add full-text article retrieval; that remains a separate follow-up.

## Data Model

The backend stores one row per Ask AI turn in SQLite. Each row keeps the question, answer, citations, scope metadata, labels, model, context source, context item count, and timestamps.

Labels are system-generated in the first version:

- Page scope labels: `今日`, `分类`, `单篇新闻`, `核验`, `设置`
- Detail labels: `分类: <name>`, `新闻: <title>`
- Intent labels: `推荐`, `核验`, `追问`

User-defined labels are intentionally deferred.

## API

- `POST /api/ask` continues to answer a question and now persists the successful turn.
- `GET /api/ask/history` returns recent global Ask AI turns.
- `GET /api/ask/history/{conversation_id}` returns one stored turn.

All history endpoints require the existing authenticated session.

## UI

The mobile app adds a global history entry in the Ask AI sheet. The history list shows question, answer preview, time, and labels. Selecting a record opens the stored answer and citations in the same sheet.

## Failure Behavior

AI provider failures are not stored as successful history rows. If storage fails after a successful AI answer, the API still returns the answer and includes a non-fatal `history_saved: false` diagnostic.
