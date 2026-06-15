# Pending User Verification

This file tracks changes that passed agent-side checks but still need a later
user-visible confirmation because the user cannot reproduce or observe the
scenario yet.

When the user says a change is temporarily unverifiable, append an entry here.
Do not store secrets, cookies, tokens, private feed contents, or `.env` values.

Each entry should include:

- Date
- Area
- What changed or what was claimed
- Agent-side evidence already collected
- Why user-side verification is blocked
- Next user-visible check
- Status

## Open

### 2026-06-12: WeChat clean-reader images

- Area: Backend clean article reader for `mp.weixin.qq.com` pages.
- Change: Preserve WeChat CDN images and emit `referrerpolicy="no-referrer"` so
  the browser does not send the AI News Radar page as the image referrer.
- Agent-side evidence:
  - Regression command passed:
    `python3 -m pytest -q tests/test_ai_backend_article_reader.py -k "upgrades_cached_wechat or weixin or wechat_cdn"`.
  - Full backend deployment verification passed on VPS: article reader and DB
    tests passed, Python compile checks passed, PM2 restarted, and health checks
    returned `{"ok":true}`.
  - Real-image probe on a public WeChat article showed that loading the same
    `mmbiz.qpic.cn` image with the AI News Radar page as referrer returned the
    anti-hotlink placeholder, while loading it with no referrer returned the
    larger real image.
- User-side verification blocked: the user currently does not see a WeChat
  article in the app/feed to open and inspect.
- Next user-visible check: when a `mp.weixin.qq.com` article appears, open it in
  the clean reader and confirm inline images show the article images instead of
  the `此图片来自微信公众平台，未经允许不可引用` placeholder.
- Status: Pending user confirmation.

## Resolved
