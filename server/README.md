# AI News Radar API

This directory contains the optional FastAPI backend for the enhanced personal reader.
GitHub Pages can still serve the static reader without this service; configure it when
you want authenticated settings, verification, and Ask AI.

## Local Run

```bash
python3 -m venv .venv-server
source .venv-server/bin/activate
pip install -r server/requirements.txt

RADAR_ADMIN_PASSWORD=change-me \
RADAR_SESSION_SECRET=change-me-long-random-value \
AI_BASE_URL=https://api.example.com/v1 \
AI_API_KEY=sk-placeholder \
AI_MODEL=gpt-4.1-mini \
AI_API_FORMAT=chat_completions \
uvicorn server.ai_radar_api.main:app --host 127.0.0.1 --port 8090
```

Health check:

```bash
curl http://127.0.0.1:8090/health
```

Expected response:

```json
{"ok": true}
```

## Environment

Copy `server/.env.example` into the environment used by your process manager. Do not
commit real passwords, API keys, cookies, tokens, or private feed content.

Required for production:

```text
RADAR_PUBLIC_BASE_URL=https://withyouda.github.io/ai-news-radar-enhance
RADAR_ALLOWED_ORIGINS=https://withyouda.github.io
RADAR_ADMIN_PASSWORD=<strong password>
RADAR_SESSION_SECRET=<long random value>
AI_BASE_URL=<OpenAI-compatible base URL>
AI_API_KEY=<provider API key>
AI_MODEL=<model name>
AI_API_FORMAT=chat_completions
```

`AI_API_FORMAT` supports:

- `chat_completions`: calls `{AI_BASE_URL}/chat/completions`.
- `responses`: calls `{AI_BASE_URL}/responses`.

## PM2

```bash
pm2 start ".venv-server/bin/uvicorn" --name ai-news-radar-api -- server.ai_radar_api.main:app --host 127.0.0.1 --port 8090
pm2 save
```

## Reverse Proxy

Expose the API through HTTPS:

```text
Public HTTPS -> 127.0.0.1:8090
```

Then set `assets/config.js` on the static site:

```javascript
window.AI_NEWS_RADAR_CONFIG = {
  apiBaseUrl: "https://<server-domain>",
};
```
