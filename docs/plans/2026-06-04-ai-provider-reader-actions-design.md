# AI Provider And Reader Actions Design

Date: 2026-06-04

## 1. Product Goal

Upgrade the clean reader and Ask AI layer so the user can configure multiple AI
providers, choose which provider handles translation and reading assistance,
toggle translated article text back to the original text, summarize a clean
article, and run a one-click article fact check.

This is a single-user admin feature for the existing deployed AI News Radar
product. It must keep the current mobile-first reading experience fast and keep
secrets out of the public static site and Git repository.

## 2. Decisions

- Translation and reading assistance use separate provider selections.
- Summary, Ask AI, and one-click fact check share the same reading-assistant AI
  provider.
- Translation can use either browser translation or a selected AI provider.
- Custom provider headers are entered as JSON text.
- API keys and custom headers are encrypted before storage.
- The frontend never receives decrypted API keys or sensitive headers.
- One-click fact checking in V1 uses only the clean article plus the existing AI
  News Radar news pool. It does not perform additional web search.

## 3. Non-Goals

- Do not build a full provider marketplace.
- Do not add multi-user roles or team-level secrets.
- Do not expose decrypted provider secrets through settings APIs.
- Do not claim all-web fact checking in V1.
- Do not bypass paywalls, login walls, or mandatory subscriptions.
- Do not rewrite the existing Ask AI conversation model.

## 4. Provider Profiles

Settings will store a list of AI provider profiles. Each profile is an admin
configured model endpoint.

```json
{
  "id": "uuid",
  "name": "OpenAI Compatible",
  "type": "chat_completions",
  "base_url": "https://api.example.com/v1",
  "model": "gpt-4.1-mini",
  "api_key_encrypted": "...",
  "headers_encrypted": "...",
  "timeout_seconds": 45,
  "enabled": true,
  "created_at": "2026-06-04T00:00:00Z",
  "updated_at": "2026-06-04T00:00:00Z"
}
```

Supported provider types in this phase:

- `chat_completions`
- `responses`

The settings API returns only a sanitized profile summary:

```json
{
  "id": "uuid",
  "name": "OpenAI Compatible",
  "type": "chat_completions",
  "base_url": "https://api.example.com/v1",
  "model": "gpt-4.1-mini",
  "has_api_key": true,
  "headers_preview": ["Authorization", "X-Custom-Header"],
  "timeout_seconds": 45,
  "enabled": true
}
```

## 5. Secret Encryption

Sensitive fields are encrypted at rest in SQLite:

- API key
- custom headers JSON

The backend uses `RADAR_ENCRYPTION_KEY` as the master encryption key. This key
must live in the server runtime environment, not in Git, the database, or the
frontend.

Rules:

- If `RADAR_ENCRYPTION_KEY` is missing, the backend refuses to save a profile
  containing a new API key or encrypted headers.
- Editing a profile with an empty API key keeps the previous encrypted key.
- Deleting a profile deletes the encrypted secret material.
- Settings responses never return decrypted values.
- Error logs and provider test errors must be redacted.

This protects against SQLite or backup disclosure. It does not protect secrets
if the server host, runtime environment, or backend process memory is fully
compromised.

## 6. Legacy Environment Provider

The existing environment-driven provider remains compatible:

- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL`
- `AI_API_FORMAT`

If no stored provider profiles exist, the backend exposes a read-only sanitized
profile called "Environment AI". Existing Ask AI behavior continues to work.

This environment profile cannot reveal or edit its API key through the UI.

## 7. Usage Settings

Settings gain two provider selections:

```json
{
  "translation_provider_mode": "browser",
  "translation_provider_id": "",
  "reading_assistant_provider_id": "env"
}
```

Translation modes:

- `browser`: use browser translation only.
- `ai`: use the selected AI provider.

Reading assistant uses one provider for:

- Ask AI
- article summary
- article fact check

## 8. Reader Toolbar

The reader toolbar should become:

```text
原文   翻译   总结   核验
```

The toolbar remains compact and mobile-first. Buttons should not wrap
vertically. The reader close button must stay horizontal.

## 9. Translation Toggle

The clean article reader keeps both the original clean article and the
translated text in frontend state.

Button states:

- `翻译`: original text is visible, no translation has been shown yet.
- `原文`: translated Chinese text is visible.
- `中文`: original text is visible and a cached translation exists.
- `翻译中`: request in progress.
- `翻译失败`: translation failed; original text remains visible.

Behavior:

1. First tap translates the clean article text.
2. After translation, the reader body displays Chinese text and caches it.
3. Tapping `原文` restores the original clean HTML/text.
4. Tapping `中文` restores the cached translation without another backend call.
5. Translation failure must not overwrite the original clean article.

If browser translation is selected, the app attempts the browser `Translator`
API only when available. The app must not automatically open Google Translate.

## 10. Article Summary

The reader toolbar gets a `总结` button.

Behavior:

1. Open the Ask AI sheet.
2. Set context to the current article.
3. Send a preset summary question automatically.
4. Store the result in the Ask AI conversation history.
5. Let the user continue asking follow-up questions in the same conversation.

Preset prompt:

```text
请用中文总结这篇文章：
1. 核心信息
2. 对 AI/科技行业的影响
3. 需要注意的不确定点
4. 如果正文信息不足，请明确说明
```

## 11. One-Click Fact Check

The reader toolbar gets a `核验` button.

Behavior:

1. Open the Ask AI sheet.
2. Set context to the current article.
3. Send a preset fact-check question automatically.
4. Store the result in the Ask AI conversation history.
5. Let the user continue asking follow-up questions in the same conversation.

V1 context:

- clean article title
- clean article text
- source, published time, original URL
- relevant items from the existing AI News Radar news pool
- existing classification or verification metadata when present

Preset prompt:

```text
请对这篇文章做基于当前雷达上下文的事实交叉核验：
1. 提取关键事实主张
2. 判断哪些主张能从当前文章或相关新闻上下文得到支持
3. 标记无法确认、可能夸大、来源不清、时间不清的问题
4. 不要编造证据；证据不足时明确说证据不足
5. 最后给出可信度：高/中/低，并说明原因
```

The UI and answer copy must not imply all-web verification.

## 12. Settings UI

The mobile settings screen gets these sections:

```text
登录

AI 配置
- profile list
- add/edit profile
- test connection
- delete profile

用途选择
- 翻译: 浏览器内置 / AI profile
- 阅读助手: AI profile

Ask AI 系统提示词

现有核验设置
```

Custom headers are edited as JSON text:

```json
{
  "X-Custom-Header": "value"
}
```

The UI should validate JSON before saving and show a short mobile-friendly
error. It should not display provider secrets after save.

## 13. Backend API Shape

New endpoints:

```text
GET    /api/ai-profiles
POST   /api/ai-profiles
PUT    /api/ai-profiles/{profile_id}
DELETE /api/ai-profiles/{profile_id}
POST   /api/ai-profiles/{profile_id}/test
```

Updated endpoints:

```text
GET /api/settings
PUT /api/settings
POST /api/translate
POST /api/ask
POST /api/ask/stream
```

`POST /api/translate` uses the translation provider settings.
`POST /api/ask` and `POST /api/ask/stream` use the reading-assistant provider.

## 14. Future Work

### All-Web Fact Checking

Later, add a separate all-web fact-check mode that can:

- search the web for evidence
- fetch candidate source pages
- compare article claims against external evidence
- cite evidence links
- clearly label all-web verification separately from Radar-context verification

### Stronger Article Fetching

Later, improve article fetching to read as many non-paywalled articles as
practically possible:

- improve Google News, RSS, and redirect resolution
- evaluate mature extraction libraries and browserless fallbacks
- add targeted retry strategies for transient network failures
- classify hard paywalls, login walls, and strong anti-bot pages as restricted
- do not bypass mandatory payment or login restrictions

### Stored Article Analysis

Later, cache article-level summary and fact-check results so repeat opens can
show previous analysis without another AI call.
