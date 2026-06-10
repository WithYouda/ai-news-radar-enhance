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
    assert "./assets/styles.css?v=reader-images-0605" in html
    assert "./assets/config.js?v=info-arch-0602" in html
    assert "./assets/api-client.js?v=frontend-arch-0610" in html
    assert "./assets/app.js?v=reader-cache-0610" in html


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
    api_js = (ROOT / "assets/api-client.js").read_text(encoding="utf-8")
    assert 'id="askAiSheet"' in html
    assert 'id="askAiInput"' in html
    assert "openAskAi" in js
    assert "submitAskAi" in js
    assert "无法连接 AI 后端" in api_js


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


def test_news_data_fetches_bypass_browser_cache():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    api_js = (ROOT / "assets/api-client.js").read_text(encoding="utf-8")
    assert "fetchFreshJson" in js
    assert 'cache: "no-store"' in api_js
    assert "fetch(`./data/latest-24h.json?t=${Date.now()}`)" not in js


def test_news_update_workflow_runs_every_30_minutes_off_peak():
    workflow = (ROOT / ".github/workflows/update-news.yml").read_text(encoding="utf-8")
    assert 'cron: "17,47 * * * *"' in workflow


def test_ask_ai_contract_renders_markdown_and_reuses_loaded_conversation_id():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "renderMarkdown" in js
    assert "bubble.innerHTML = renderMarkdown(text)" in js
    assert "md-list-number" in js
    assert "state.activeConversationId" in js
    assert "conversation_id: state.activeConversationId" in js
    assert ".ask-ai-bubble h1" in css
    assert ".ask-ai-bubble code" in css


def test_ask_ai_message_actions_contract_matches_chat_product_controls():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'id="askAiQuoteBar"' in html
    assert "appendAskMessageActions" in js
    assert "editAskMessage" in js
    assert "deleteAskMessage" in js
    assert "regenerateAskMessage" in js
    assert "copyAskMessage" in js
    assert "ask-ai-action-icon" in js
    assert "aria-label" in js
    assert 'messageActionButton("重生成"' not in js
    assert 'messageActionButton("复制"' not in js
    assert 'messageActionButton("删除"' not in js
    assert "handleAskSelection" in js
    assert "handleAskLongPress" in js
    assert "setAskQuote" in js
    assert "clearAskQuote" in js
    assert ".ask-ai-message-actions" in css
    assert ".ask-ai-action-icon" in css
    assert ".ask-ai-quote-bar" in css
    assert ".ask-ai-quote-float" in css
    assert ".ask-ai-edit-box" in css
    assert "-webkit-touch-callout: none" in css


def test_ask_ai_streaming_setting_and_stream_submit_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'id="askStreamingToggle"' in html
    assert "ask_streaming_enabled" in js
    assert "state.askStreamingEnabled" in js
    assert "submitAskAiStream" in js
    assert 'apiStream("/api/ask/stream"' in js
    assert 'askStreamingToggleEl.addEventListener("change"' in js
    assert "state.askStreamingEnabled = Boolean(askStreamingToggleEl.checked)" in js


def test_ask_ai_streaming_error_event_is_handled_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    stream_fn = js[js.index("async function submitAskAiStream") : js.index("function setSettingsStatus")]
    assert 'event.type === "error"' in stream_fn
    assert "event.payload?.message" in stream_fn


def test_ask_ai_quote_is_sent_with_question_and_can_be_cleared():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    submit_js = js[js.index("async function submitAskAi()") : js.index("function setSettingsStatus")]
    assert "buildAskQuestionText(question)" in submit_js
    assert "clearAskQuote()" in submit_js
    assert "引用内容：" in js


def test_ask_ai_clears_input_immediately_after_queuing_message():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    submit_js = js[js.index("async function submitAskAi()") : js.index("function setSettingsStatus")]
    loading_index = submit_js.index("renderAskLoading(question)")
    clear_index = submit_js.index("askAiInputEl.value = \"\"")
    fetch_index = submit_js.index("const payload = await apiFetch(\"/api/ask\"")
    assert loading_index < clear_index < fetch_index


def test_ask_ai_visual_contract_feels_like_refined_chat_product():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "--ask-panel-bg: #fffdf8" in css
    assert "--ask-user-bg: #126a73" in css
    assert "--ask-ai-bg: #ffffff" in css
    assert "backdrop-filter" in css
    assert "flex-direction: row-reverse" not in css
    assert 'content: "你"' not in css
    assert ".ask-ai-message.user::before" not in css
    assert ".ask-ai-message.ai .ask-ai-bubble::before" not in css
    assert ".ask-ai-message.user .ask-ai-bubble::before" not in css


def test_ask_ai_history_delete_updates_list_without_loading_flash():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "removeAskHistoryRow(conversationId)" in js
    assert "await loadAskHistory(true)" not in js


def test_settings_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'id="settingsView"' in html
    assert 'id="adminPasswordInput"' in html
    assert 'id="askSystemPromptInput"' in html
    assert "loginAdmin" in js
    assert "saveSettings" in js
    assert "ask_system_prompt" in js


def test_verify_action_is_mobile_scoped():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert ".card-actions {\n  display: none;" in css
    assert "@media (max-width: 760px)" in css
    assert ".card-actions {\n    display: inline-flex;" in css


def test_clean_reader_contract_exists_for_news_cards():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'id="readerSheet"' in html
    assert 'id="readerBody"' in html
    assert 'id="readerTranslateButton"' in html
    assert 'id="readerAccessBadge"' in html
    assert 'class="reader-ask-fab"' in html
    assert "openReader(item)" in js
    assert "loadCleanArticle" in js
    assert "translateReaderArticle" in js
    assert "Translator.create" in js
    assert "Translator.availability" in js
    assert "requestCleanTextTranslation" in js
    assert "translate.google.com" not in js
    assert "cleanedTextForTranslation" in js
    assert "/api/translate" in js
    assert "&u=" not in js[js.index("async function translateReaderArticle") : js.index("async function loadCleanArticle")]
    assert 'translate="yes"' in html
    assert "/api/read/" in js
    assert "sha1Hex" in js
    assert "reader-action" in js
    assert ".reader-sheet" in css
    assert ".reader-article" in css
    assert ".reader-ask-fab" in css
    assert ".reader-access-badge" in css
    assert ".reader-close" in css and "white-space: nowrap" in css
    assert "body.reader-open" in css
    assert ".reader-article img" in css
    assert "max-width: 100%" in css
    assert ".reader-article figure" in css
    assert ".reader-article pre" in css
    assert "overflow-x: auto" in css
    assert ".reader-article pre code" in css
    assert ".reader-article code" in css


def test_clean_reader_reuses_session_cache_and_inflight_request_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    state_block = js[js.index("const state = {") : js.index("const statsEl = document.getElementById")]
    load_fn = js[js.index("async function loadCleanArticle") : js.index("async function openReader")]
    open_fn = js[js.index("async function openReader") : js.index("function bindReaderLink")]

    assert "readerArticleCache: new Map()" in state_block
    assert "readerArticleRequests: new Map()" in state_block
    assert "readerArticleKey: \"\"" in state_block
    assert "state.readerArticleCache.has(id)" in load_fn
    assert "state.readerArticleRequests.has(id)" in load_fn
    assert "state.readerArticleRequests.set(id, request)" in load_fn
    assert "state.readerArticleCache.set(id, article)" in load_fn
    assert "state.readerArticleRequests.delete(id)" in load_fn
    assert "state.readerArticleKey = id" in open_fn
    assert "state.readerArticleCache.has(id)" in open_fn
    assert "renderReaderLoading(item)" in open_fn
    assert "state.readerArticleKey !== id" in open_fn


def test_news_cards_render_optional_item_thumbnail():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'class="card-thumb"' in html
    assert "function itemImageUrl" in js
    assert "item.image_url" in js
    assert "thumbEl.src = thumbUrl" in js
    assert ".news-card.has-thumb .news-card-content" in css
    assert "aspect-ratio: 4 / 3;" in css


def test_ask_ai_sheet_supports_smooth_drag_to_dismiss():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'class="ask-ai-panel"' in html
    assert "askAiPanelEl" in js
    assert "handleAskPanelDragStart" in js
    assert "handleAskPanelDragMove" in js
    assert "handleAskPanelDragEnd" in js
    assert "ASK_DRAG_CLOSE_THRESHOLD" in js
    assert "closeAskAi()" in js[js.index("function handleAskPanelDragEnd") :]
    assert "--ask-drag-y" in css
    assert ".ask-ai-panel.dragging" in css
    assert "transform: translate3d(0, calc(var(--ask-open-y) + var(--ask-drag-y)), 0)" in css
    assert ".ask-ai-sheet.open" in css
    assert ".ask-ai-sheet.empty-thread .ask-ai-body" in css


def test_ask_ai_drag_contract_uses_top_drag_zone_without_blocking_chat_scroll():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'class="ask-ai-head sheet-drag-zone"' in html
    assert 'class="ask-ai-tools sheet-drag-zone"' in html
    assert "const ASK_DRAG_ACTIVATION_PX" in js
    assert "startScrollTop" in js[js.index("function handleAskPanelDragStart") : js.index("function handleAskPanelDragEnd")]
    assert "delta < ASK_DRAG_ACTIVATION_PX" in js
    assert ".ask-ai-head,\n.ask-ai-tools {\n  touch-action: none;" in css
    assert ".ask-ai-thread,\n.ask-ai-history-list {\n  min-height: 0;\n  overflow: auto;\n  touch-action: pan-y;" in css
    assert ".ask-ai-sheet.empty-thread .ask-ai-body" in css
    assert "askAiSheetEl.classList.add(\"empty-thread\")" in js


def test_reader_sheet_supports_drag_to_dismiss_and_floating_ask():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "readerPanelEl" in js
    assert "handleReaderPanelDragStart" in js
    assert "READER_DRAG_CLOSE_THRESHOLD" in js
    assert "closeReader()" in js[js.index("function handleReaderPanelDragEnd") :]
    assert "--reader-drag-y" in css
    assert ".reader-panel.dragging" in css
    assert "transform: translate3d(0, var(--reader-drag-y), 0)" in css
    assert ".reader-ask-fab" in css


def test_reader_drag_contract_allows_body_scroll_and_top_pull_to_close():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'class="reader-head sheet-drag-zone"' in html
    assert 'class="reader-toolbar sheet-drag-zone"' in html
    assert "const READER_DRAG_ACTIVATION_PX" in js
    assert "startScrollTop" in js[js.index("function handleReaderPanelDragStart") : js.index("function handleReaderPanelDragEnd")]
    assert "readerDragState.active" in js
    assert "delta < READER_DRAG_ACTIVATION_PX" in js
    assert ".reader-head,\n.reader-toolbar {\n  touch-action: none;" in css
    assert ".reader-article" in css and "touch-action: pan-y" in css
    assert "overscroll-behavior: contain" in css


def test_clean_reader_translation_button_and_cleaned_text_fallback_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    translate_fn = js[js.index("async function translateReaderArticle") : js.index("async function loadCleanArticle")]
    render_fn = js[js.index("function renderReaderArticle") : js.index("function cleanedTextForTranslation")]
    assert "isReaderTranslationAvailable(payload)" in render_fn
    assert "readerTranslateButtonEl.hidden = !isReaderTranslationAvailable(payload)" in render_fn
    assert "cleanedTextForTranslation()" in translate_fn
    assert "requestCleanTextTranslation" in translate_fn
    assert "translate.google.com" not in translate_fn
    assert "&u=" not in translate_fn


def test_reader_translation_toggle_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "readerOriginalHtml" in js
    assert "readerTranslatedHtml" in js
    assert "readerShowingTranslation" in js
    assert "showOriginalReaderArticle" in js
    assert "showTranslatedReaderArticle" in js
    assert 'readerTranslateButtonEl.textContent = "原文"' in js
    assert 'readerTranslateButtonEl.textContent = "中文"' in js
    translate_fn = js[js.index("async function translateReaderArticle") : js.index("async function loadCleanArticle")]
    assert "state.readerTranslatedHtml" in translate_fn
    assert "requestCleanTextTranslation" in translate_fn


def test_reader_ai_translation_waits_for_current_settings_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    translate_fn = js[js.index("async function translateReaderArticle") : js.index("async function loadCleanArticle")]
    ai_mode_index = translate_fn.index('state.translationProviderMode !== "ai"')
    save_index = translate_fn.index("await saveSettings()")
    request_index = translate_fn.index("requestCleanTextTranslation")
    assert ai_mode_index < save_index < request_index


def test_reader_summary_and_fact_check_actions_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'id="readerSummaryButton"' in html
    assert 'id="readerFactCheckButton"' in html
    assert "summarizeReaderArticle" in js
    assert "factCheckReaderArticle" in js
    assert "openAskAiForReaderArticle" in js
    assert "请用中文总结这篇文章" in js
    assert "基于当前雷达上下文的事实交叉核验" in js
    assert "readerSummaryButtonEl.addEventListener" in js
    assert "readerFactCheckButtonEl.addEventListener" in js
    assert ".reader-toolbar button" in css


def test_settings_ai_profiles_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert 'id="aiProfilesList"' in html
    assert 'id="aiProfileNameInput"' in html
    assert 'id="aiProfileHeadersInput"' in html
    assert 'id="translationProviderModeSelect"' in html
    assert 'id="translationProviderSelect"' in html
    assert 'id="readingAssistantProviderSelect"' in html
    assert "loadAiProfiles" in js
    assert "saveAiProfile" in js
    assert "testAiProfile" in js
    assert "deleteAiProfile" in js
    assert "/api/ai-profiles" in js
    assert "translation_provider_mode" in js
    assert "reading_assistant_provider_id" in js
    assert ".settings-section" in css
    assert ".ai-profile-row" in css


def test_provider_usage_controls_autosave_contract():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    translation_mode_listener = js[js.index('translationProviderModeSelectEl.addEventListener("change"') :]
    translation_select_listener = js[js.index('translationProviderSelectEl.addEventListener("change"') :]
    reading_select_listener = js[js.index('readingAssistantProviderSelectEl.addEventListener("change"') :]
    assert "saveSettings()" in translation_mode_listener.split("});", 1)[0]
    assert "saveSettings()" in translation_select_listener.split("});", 1)[0]
    assert "saveSettings()" in reading_select_listener.split("});", 1)[0]


def test_news_title_click_opens_clean_reader_instead_of_original_page():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "function bindReaderLink" in js
    assert "linkEl.removeAttribute(\"target\")" in js
    assert "event.preventDefault()" in js[js.index("function bindReaderLink") :]
    assert "bindReaderLink(titleEl, item)" in js[js.index("function renderItemNode") :]
    assert "bindReaderLink(link, item)" in js[js.index("function buildBoleTimelineRow") :]


def test_deep_verify_preserves_item_metadata_in_verification_payload():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "const verifiedItem = { ...item, ...result }" in js
    assert "items: [verifiedItem" in js
