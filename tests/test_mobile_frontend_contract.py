from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_nav_and_ask_entry_exist():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="mobileBottomNav"' in html
    assert 'data-view="today"' in html
    assert 'data-view="categories"' in html
    assert 'data-view="verification"' in html
    assert 'data-view="settings"' in html
    assert 'id="askAiButton"' in html


def test_mobile_css_is_scoped_to_small_screens():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert ".mobile-bottom-nav" in css
    assert "@media (max-width: 760px)" in css
    assert "padding-bottom" in css


def test_hidden_mobile_sections_cannot_be_overridden_by_component_css():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "[hidden]" in css
    assert "display: none !important" in css


def test_mobile_fix_assets_are_cache_busted():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "./assets/styles.css?v=ask-chat-a6" in html
    assert "./assets/config.js?v=info-arch-0602" in html
    assert "./assets/app.js?v=ask-chat-a6" in html


def test_category_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'data-mobile-view="categories"' in html
    assert 'id="categoryView"' in html
    assert "loadTaxonomy" in js
    assert "renderCategoryView" in js


def test_category_cards_open_news_collection_and_scope_ask_ai():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "categoryFilter" in js
    assert "renderCategoryResultList" in js
    assert "category-news-list" in js
    assert "scope.category = state.categoryFilter" in js
    assert ".category-card.active" in css


def test_bole_picks_explain_selection_criteria():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "为什么精选" in html
    assert "bole-explainer" in js
    assert "多源命中" in js
    assert "官方源" in js
    assert "AI 分" in js


def test_verification_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'data-mobile-view="verification"' in html
    assert 'id="verificationView"' in html
    assert "loadVerificationSummary" in js
    assert "renderVerificationView" in js
    assert "deepVerifyItem" in js


def test_ask_ai_sheet_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'id="askAiSheet"' in html
    assert 'id="askAiInput"' in html
    assert "openAskAi" in js
    assert "submitAskAi" in js
    assert "无法连接 AI 后端" in js


def test_ask_ai_global_history_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'id="askAiMessagesButton"' in html
    assert 'id="askAiHistoryButton"' in html
    assert 'id="askAiHistoryList"' in html
    assert "/api/ask/history" in js
    assert "renderAskHistory" in js
    assert "toggleAskHistory" in js
    assert "deleteAskHistoryItem" in js
    assert ".ask-ai-history-item" in css
    assert ".ask-ai-history-delete" in css


def test_ask_ai_uses_chat_layout_with_bottom_composer():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'class="ask-ai-thread"' in html
    assert 'class="ask-ai-composer"' in html
    assert 'aria-label="发送"' in html
    assert '>发送<' not in html
    assert "grid-template-rows: auto auto minmax(0, 1fr) auto;" in css
    assert ".ask-ai-message.user" in css
    assert ".ask-ai-message.ai" in css
    assert ".ask-ai-send-icon" in css
    assert "renderAskConversation" in js


def test_ask_ai_sheet_locks_background_and_uses_compact_mobile_padding():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "body.ask-ai-open" in css
    assert "overflow: hidden;" in css
    assert "padding: 16px 14px 88px" not in css
    assert "askAiInputEl.value = payload.question" not in js


def test_ask_ai_continues_thread_and_hides_final_link_recommendations():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "appendAskMessage" in js
    assert "renderAskLoading(question)" in js
    assert "renderAskConversation({ answer: \"正在整理上下文...\" }, questionText)" not in js
    assert "appendAskCitations" not in js
    assert ".ask-ai-citations" not in css


def test_ask_ai_contract_renders_markdown_and_reuses_loaded_conversation_id():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "renderMarkdown" in js
    assert "bubble.innerHTML = renderMarkdown(text)" in js
    assert "state.activeConversationId" in js
    assert "conversation_id: state.activeConversationId" in js
    assert ".ask-ai-bubble h1" in css
    assert ".ask-ai-bubble code" in css


def test_ask_ai_history_delete_updates_list_without_loading_flash():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "removeAskHistoryRow(conversationId)" in js
    assert "await loadAskHistory(true)" not in js


def test_settings_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'id="settingsView"' in html
    assert 'id="adminPasswordInput"' in html
    assert "loginAdmin" in js
    assert "saveSettings" in js


def test_verify_action_is_mobile_scoped():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert ".card-action {\n  display: none;" in css
    assert "@media (max-width: 760px)" in css
    assert ".card-action {\n    display: inline-flex;" in css


def test_deep_verify_preserves_item_metadata_in_verification_payload():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "const verifiedItem = { ...item, ...result }" in js
    assert "items: [verifiedItem" in js
