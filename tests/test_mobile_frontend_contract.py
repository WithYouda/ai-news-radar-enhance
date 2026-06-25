import subprocess
import re
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _nav_buttons(html: str, nav_id: str):
    start = html.index(f'id="{nav_id}"')
    end = html.index("</nav>", start)
    nav = html[start:end]
    return re.findall(r'<button[^>]*data-view="([^"]+)"[^>]*>([^<]+)</button>', nav)


def test_mobile_nav_and_ask_entry_exist():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="mobileBottomNav"' in html
    assert 'data-view="today"' in html
    assert 'data-view="categories"' in html
    assert 'data-view="verification"' in html
    assert 'data-view="settings"' in html
    assert 'id="askAiButton"' in html


def test_desktop_navigation_exposes_every_mobile_view_without_hiding_itself():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert 'id="desktopViewNav"' in html
    assert 'id="desktopAskAiButton"' in html
    assert 'class="desktop-view-strip" data-mobile-view' not in html
    assert 'class="desktop-view-nav" data-mobile-view' not in html
    assert 'class="desktop-ask-button" data-mobile-view' not in html
    for view in ("today", "categories", "verification", "settings"):
        assert f'class="desktop-view-btn' in html
        assert f'data-view="{view}"' in html
    assert "desktopViewButtons" in js
    assert "desktopAskAiButtonEl" in js
    assert "desktopViewButtons.forEach" in js
    assert 'btn.classList.toggle("active", btn.dataset.view === view)' in js
    assert 'desktopAskAiButtonEl.addEventListener("click"' in js
    assert ".desktop-view-strip" in css
    assert ".desktop-view-nav" in css
    assert ".desktop-view-btn" in css
    assert ".desktop-ask-button" in css
    assert ".desktop-view-strip {\n    display: none;" in css


def test_desktop_and_mobile_main_navigation_stay_in_sync():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    desktop_buttons = _nav_buttons(html, "desktopViewNav")
    mobile_buttons = _nav_buttons(html, "mobileBottomNav")
    assert desktop_buttons == mobile_buttons


def test_mobile_settings_view_hides_ask_ai_fab_to_keep_form_clear():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert 'id="askAiButton" class="ask-ai-fab"' in html
    assert "document.body.dataset.activeMobileView = view;" in js
    mobile_css = css[css.index("@media (max-width: 760px)") :]
    assert 'body[data-active-mobile-view="settings"] .ask-ai-fab' in mobile_css
    settings_rule = mobile_css[
        mobile_css.index('body[data-active-mobile-view="settings"] .ask-ai-fab') :
    ]
    assert "display: none;" in settings_rule[:160]
    assert ".desktop-ask-button" in css


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
    assert "./assets/styles.css?v=personalized-bole-feedback-multitag-0624" in html
    assert "./assets/config.js?v=info-arch-0602" in html
    assert "./assets/api-client.js?v=frontend-arch-0610" in html
    assert "./assets/app.js?v=personalized-bole-feedback-multitag-0624" in html


def test_static_news_render_does_not_wait_for_optional_backend_data():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    init = js[js.index("async function init()") : js.index('searchInputEl.addEventListener("input"', js.index("async function init()"))]

    assert "const [newsResult, waytoagiResult, statusResult]" in init
    assert "Promise.allSettled([\n    loadNewsData(),\n    loadWaytoagiData(),\n    loadSourceStatusData()," in init
    assert "loadTaxonomy()" not in init[init.index("Promise.allSettled([") : init.index("]);", init.index("Promise.allSettled(["))]
    assert "loadVerificationSummary()" not in init[init.index("Promise.allSettled([") : init.index("]);", init.index("Promise.allSettled(["))]
    render_list_index = init.index("renderList();")
    taxonomy_index = init.index("loadOptionalBackendData();")
    assert render_list_index < taxonomy_index


def test_ai_config_dialog_starts_hidden_and_not_mobile_view():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    dialog = html[html.index('id="aiConfigDialog"') : html.index('id="boleWorkbench"')]

    assert 'id="aiConfigDialog" class="ai-config-dialog" hidden' in html
    assert 'id="aiConfigDialog" class="ai-config-dialog" data-mobile-view' not in html
    assert 'role="dialog" aria-modal="true"' in dialog
    assert "连接模型" in dialog
    assert "名称" in dialog
    assert 'id="aiConfigNameInput" type="text" placeholder="默认 AI"' in dialog
    assert 'id="aiConfigNameInput" type="text" value=' not in dialog
    assert "Base URL" in dialog
    assert 'id="aiConfigBaseUrlInput" type="url" placeholder="https://api.openai.com/v1"' in dialog
    assert 'id="aiConfigBaseUrlInput" type="url" value=' not in dialog
    assert "模型" in dialog
    assert 'id="aiConfigModelInput" type="text" placeholder="gpt5.5"' in dialog
    assert 'id="aiConfigModelInput" type="text" value=' not in dialog
    assert "API Key" in dialog
    assert "请求头 JSON" in dialog
    assert "超时秒数" in dialog
    assert 'id="aiConfigAdvancedPanel" class="ai-config-advanced-panel" hidden' in dialog


def test_ai_config_dialog_actions_match_confirmed_preview():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    dialog = html[html.index('id="aiConfigDialog"') : html.index('id="boleWorkbench"')]

    assert "可跳过进入画像工作台。" in dialog
    assert dialog.index('id="aiConfigSkipButton"') < dialog.index('id="aiConfigStatus"')
    assert dialog.index('id="aiConfigStatus"') < dialog.index('id="aiConfigTestButton"')
    assert dialog.index('id="aiConfigTestButton"') < dialog.index('id="aiConfigSaveButton"')
    assert 'id="aiConfigTestButton" class="ai-config-secondary-button" type="button">测试</button>' in dialog
    assert 'id="aiConfigSaveButton" class="ai-config-secondary-button" type="button">保存并继续</button>' in dialog
    assert "保存并继续" in dialog

    save_rule = css[
        css.index(".ai-config-secondary-button {") :
        css.index(".ai-config-ghost-button", css.index(".ai-config-secondary-button {"))
    ]
    assert "color: var(--accent);" in save_rule
    assert "background: var(--surface-soft);" in save_rule
    assert "background: var(--accent);" not in save_rule
    assert "background: #111" not in save_rule
    assert "background: #000" not in save_rule


def test_ai_config_dialog_advanced_layout_stays_aligned_on_desktop_and_mobile():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    desktop_rule = css[
        css.index(".ai-config-advanced-panel {") :
        css.index(".ai-config-advanced-panel[hidden]")
    ]
    desktop_input_rule = css[
        css.index(".ai-config-advanced-panel .field textarea,") :
        css.index(".ai-config-actions", css.index(".ai-config-advanced-panel .field textarea,"))
    ]
    mobile_css = css[css.index("@media (max-width: 760px)") :]
    mobile_advanced_rule = mobile_css[
        mobile_css.index(".ai-config-form-grid,") :
        mobile_css.index(".ai-config-actions", mobile_css.index(".ai-config-form-grid,"))
    ]
    mobile_actions_rule = mobile_css[
        mobile_css.index(".ai-config-actions {") :
        mobile_css.index(".ai-config-action-right", mobile_css.index(".ai-config-actions {"))
    ]

    assert "grid-template-columns: minmax(0, 1fr) 150px;" in desktop_rule
    assert "align-items: stretch;" in desktop_rule
    assert "min-height: 120px;" in desktop_input_rule
    assert "grid-template-columns: 1fr;" in mobile_advanced_rule
    assert "grid-template-columns: auto minmax(0, 1fr) auto auto;" in mobile_actions_rule
    assert "calc(18px + env(safe-area-inset-bottom))" in mobile_css


def test_ai_config_frontend_wires_existing_ai_profile_api_before_bole_workbench():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert "aiConfigSkipped" in js
    assert "aiConfigProfileId" in js
    assert "hasSavedAiConfigProfile" in js
    assert "shouldPromptForAiConfigBeforeBole" in js
    assert "openAiConfigDialog" in js
    assert "closeAiConfigDialog" in js
    assert "openBolePersonalizationEntry" in js
    assert "aiConfigProfilePayload" in js
    assert "saveAiConfigAndContinue" in js
    assert "testAiConfigConnection" in js
    assert 'apiFetch("/api/ai-profiles"' in js
    assert 'apiFetch(`/api/ai-profiles/${encodeURIComponent(profileId)}`' in js
    assert 'apiFetch(`/api/ai-profiles/${encodeURIComponent(profile.id)}/test`' in js
    assert "state.aiConfigProfileId = profile.id" in js
    assert "const profileId = state.aiConfigProfileId;" in js
    assert "openBolePersonalizationEntry({ auto: Boolean(options.autoOpen) })" in js
    assert "openBoleWorkbench();" in js[js.index("function skipAiConfigDialog") : js.index("async function saveAiConfigAndContinue")]
    assert ".ai-config-dialog" in css
    assert ".ai-config-advanced-panel" in css
    assert ".ai-config-dialog-open" in css


def test_ai_config_prompt_only_for_first_bole_entry_without_saved_profile():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function hasSavedAiConfigProfile");
        const end = js.indexOf("function aiProviderOptions", start);
        if (start < 0 || end < 0) {{
          throw new Error("missing AI config prompt helper slice");
        }}
        function evaluate(apiBaseUrl, aiProfiles, personalizationStatus, skipped) {{
          const sandbox = {{
            apiBaseUrl,
            state: {{
              aiProfiles,
              personalizationStatus,
              aiConfigSkipped: skipped,
            }},
            result: null,
          }};
          vm.createContext(sandbox);
          vm.runInContext(js.slice(start, end) + `
            result = shouldPromptForAiConfigBeforeBole();
          `, sandbox);
          return sandbox.result;
        }}
        const cases = {{
          staticFallback: evaluate("", [], {{ state: "not_started" }}, false),
          envOnlyFirstUse: evaluate("https://api.example.com", [{{ id: "env", readonly: true, has_api_key: true }}], {{ state: "not_started" }}, false),
          savedProfile: evaluate("https://api.example.com", [{{ id: "custom", readonly: false, has_api_key: true }}], {{ state: "not_started" }}, false),
          skippedThisSession: evaluate("https://api.example.com", [{{ id: "env", readonly: true }}], {{ state: "not_started" }}, true),
          alreadyConfirmed: evaluate("https://api.example.com", [{{ id: "env", readonly: true }}], {{ state: "confirmed" }}, false),
        }};
        if (cases.staticFallback !== false) throw new Error("static frontend should open workbench directly");
        if (cases.envOnlyFirstUse !== true) throw new Error("env-only first use should prompt for user AI config");
        if (cases.savedProfile !== false) throw new Error("saved custom AI profile should skip prompt");
        if (cases.skippedThisSession !== false) throw new Error("session skip should enter workbench directly");
        if (cases.alreadyConfirmed !== false) throw new Error("confirmed personalization should not show first-use prompt");
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_personalized_bole_workbench_starts_hidden_and_not_mobile_view():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    workbench = html[html.index('id="boleWorkbench"') : html.index('id="readerSheet"')]

    assert 'id="boleWorkbench"' in html
    assert 'id="boleWorkbench" class="bole-workbench" hidden' in html
    assert 'id="boleWorkbench" class="bole-workbench" data-mobile-view' not in html
    assert 'id="boleWorkbenchOpen"' in html
    assert 'id="boleSettingsOpen"' in html
    assert "兴趣校准" in html
    assert "阅读偏好" in html
    assert "画像草稿" in html
    assert "AI 访谈" not in html
    assert "推荐预览" not in html
    assert "确认保存" not in html
    assert "首次登录" not in html
    assert "确认前不保存" not in html
    assert "1/4" not in html
    assert "伯乐判断" not in workbench
    assert "接下来我会追问" not in workbench
    assert "每条都来自刚刚的选择或输入" not in workbench
    assert "确认后用于为你推荐" not in workbench
    assert "登录后使用伯乐画像" not in workbench
    assert "后端未配置" not in workbench
    assert "生成草稿" not in workbench
    assert "继续校准" not in workbench


def test_personalized_bole_workbench_uses_serial_b2_stage_layout():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    workbench = html[html.index('id="boleWorkbench"') : html.index('id="readerSheet"')]

    assert 'class="bole-stage-tabs"' in workbench
    assert 'data-bole-stage="calibration">兴趣校准' in workbench
    assert 'data-bole-stage="preferences">阅读偏好' in workbench
    assert 'data-bole-stage="draft">画像草稿' in workbench
    assert 'class="bole-stage-track"' in workbench
    assert 'data-bole-stage-panel="calibration"' in workbench
    assert 'data-bole-stage-panel="preferences"' in workbench
    assert 'data-bole-stage-panel="draft"' in workbench
    assert 'class="bole-workbench-grid"' not in workbench
    assert 'class="bole-workbench-section' not in workbench
    assert ".bole-stage-track" in css
    assert ".bole-dialogue" in css
    assert ".bole-profile-rail" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(280px, 316px);" in css
    assert "transition: transform 380ms cubic-bezier(0.16, 1, 0.3, 1);" in css
    assert ".bole-dialogue-turns.is-transitioning .bole-turn-deck-card.two" in css
    assert "@keyframes bole-card-exit" in css
    assert "@keyframes bole-deck-rise-two" in css


def test_bole_interest_and_reading_questions_are_separate_with_single_ai_input():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    workbench = html[html.index('id="boleWorkbench"') : html.index('id="readerSheet"')]

    assert workbench.count("data-bole-chat-input") == 1
    assert "data-bole-free-text" not in workbench
    assert "<textarea" not in workbench
    assert "const BOLE_PROFILE_QUESTIONS" in js
    question_bank = js[js.index("const BOLE_PROFILE_QUESTIONS") : js.index("function parseBoleTerms")]
    question_ids = re.findall(r'id: "([^"]+)"', question_bank)
    assert question_ids[:5] == [
        "attention_goal",
        "negative_preferences",
        "ai_domains",
        "deep_reading_policy",
        "reading_depth",
    ]

    expected_stages = {
        "attention_goal": "interest",
        "ai_domains": "interest",
        "negative_preferences": "interest",
        "deep_reading_policy": "reading",
        "reading_depth": "reading",
    }
    for question_id, stage in expected_stages.items():
        marker = f'id: "{question_id}"'
        assert marker in question_bank
        entry_start = question_bank.index(marker)
        entry_end = question_bank.index("\n  }", entry_start)
        entry = question_bank[entry_start:entry_end]
        assert f'stage: "{stage}"' in entry
        assert "choices: [" in entry
        assert len(re.findall(r'"[^"]+"', entry[entry.index("choices: [") : entry.index("]", entry.index("choices: ["))])) >= 3
    interest_bank = question_bank[
        question_bank.index('id: "attention_goal"') : question_bank.index('id: "deep_reading_policy"')
    ]
    assert "deep_reading_policy" not in interest_bank
    assert "reading_depth" not in interest_bank


def test_bole_mobile_workbench_uses_compact_stage_flow_not_long_form():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    workbench = html[html.index('id="boleWorkbench"') : html.index('id="readerSheet"')]
    mobile_css = css[css.index("@media (max-width: 760px)") :]

    assert 'class="bole-stage-tabs"' in workbench
    assert 'data-bole-stage="calibration">兴趣校准' in workbench
    assert 'data-bole-stage="preferences">阅读偏好' in workbench
    assert 'data-bole-stage="draft">画像草稿' in workbench
    assert "scroll-snap-type: x mandatory;" not in mobile_css
    assert ".bole-stage-track" in mobile_css
    assert ".bole-stage-panel" in mobile_css
    assert ".bole-dialogue" in mobile_css
    assert ".bole-profile-rail" in mobile_css
    assert "grid-auto-flow: column;" in mobile_css
    assert workbench.count("data-bole-chat-input") == 1
    assert workbench.count("data-bole-question-id") <= 1


def test_personalized_bole_frontend_wires_authenticated_api_without_static_breakage():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert "personalizationStatus" in js
    assert "boleStage" in js
    assert "boleAnswers" in js
    assert "boleShownQuestionIds" in js
    assert "boleConfirmedQuestionIds" in js
    assert "boleAnswerInterpretations" in js
    assert "boleQuestionTransitionTimer" in js
    assert "loadPersonalization" in js
    assert "openBoleWorkbench" in js
    assert "closeBoleWorkbench" in js
    assert "setBoleStage" in js
    assert "renderBoleConversation" in js
    assert "renderBoleRecognizedProfile" in js
    assert "transitionBoleQuestion" in js
    assert "primaryBoleActionLabel" in js
    assert "interpretBoleInput" in js
    assert "buildBoleConversationContext" in js
    assert "buildBoleProfileDraft" in js
    assert "buildBoleDraftEvidence" in js
    assert 'apiFetch("/api/personalization")' in js
    assert 'apiFetch("/api/personalization/interpret"' in js
    assert 'apiFetch("/api/personalization/draft"' in js
    assert 'apiFetch("/api/personalization/confirm"' in js
    assert 'apiFetch("/api/personalization/skip"' in js
    assert 'apiFetch("/api/personalization/reset"' in js
    assert 'apiFetch("/api/personalization/disable"' in js
    assert "if (!apiBaseUrl)" in js
    assert "loadPersonalization({ autoOpen: true })" in js
    assert ".bole-workbench" in css
    assert ".bole-stage-track" in css
    assert ".bole-dialogue" in css
    assert ".bole-profile-rail" in css


def test_bole_question_progression_requires_explicit_next_action_after_ready():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("const BOLE_PROFILE_QUESTIONS");
        const end = js.indexOf("function renderBoleWorkbench", start);
        if (start < 0 || end < 0) {{
          throw new Error("missing bole helper slice");
        }}
        const sandbox = {{
          state: {{
            boleStage: "calibration",
            boleAnswers: {{}},
            boleShownQuestionIds: new Set(["attention_goal"]),
            boleConfirmedQuestionIds: new Set(),
            boleAnswerInterpretations: {{}},
            boleActiveQuestionId: "attention_goal",
            boleQuestionTransitionTimer: null,
          }},
          setTimeout,
          clearTimeout,
          renderBoleWorkbench: () => {{}},
          syncBoleStage: () => {{}},
          renderBoleConversation: () => {{}},
          renderBoleDraftPreview: () => {{}},
          renderBoleRecommendationPreview: () => {{}},
          renderBoleRecognizedProfile: () => {{}},
          renderBoleSettingsStatus: () => {{}},
          syncBoleActionButtons: () => {{}},
          boleChatInputEl: null,
          boleDialogueTurnsEl: null,
          boleReadingTurnsEl: null,
          result: null,
        }};
        vm.createContext(sandbox);
        vm.runInContext(js.slice(start, end) + `
          mergeBoleAnswer("attention_goal", {{ choices: ["产品与工具"] }});
          const before = {{
            active: state.boleActiveQuestionId,
            ready: isBoleQuestionReady("attention_goal"),
            label: primaryBoleActionLabel("attention_goal"),
            shown: Array.from(state.boleShownQuestionIds),
          }};
          transitionBoleQuestion("ai_domains", {{ animate: false }});
          const after = {{
            active: state.boleActiveQuestionId,
            label: primaryBoleActionLabel("ai_domains"),
            shown: Array.from(state.boleShownQuestionIds),
          }};
          result = {{ before, after }};
        `, sandbox);
        if (sandbox.result.before.active !== "attention_goal") {{
          throw new Error("choice selection should not auto-advance active question");
        }}
        if (!sandbox.result.before.ready || sandbox.result.before.label !== "下一题") {{
          throw new Error(`ready question should show 下一题, got ${{sandbox.result.before.label}}`);
        }}
        if (sandbox.result.before.shown.includes("ai_domains")) {{
          throw new Error("next question should not be shown before explicit next action");
        }}
        if (sandbox.result.after.active !== "ai_domains") {{
          throw new Error("explicit next action should activate ai_domains");
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_last_question_ready_action_moves_to_next_stage_not_auto_advance():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("const BOLE_PROFILE_QUESTIONS");
        const end = js.indexOf("function renderBoleWorkbench", start);
        const sandbox = {{
          state: {{
            boleStage: "calibration",
            boleAnswers: {{}},
            boleShownQuestionIds: new Set(["attention_goal", "negative_preferences", "ai_domains"]),
            boleConfirmedQuestionIds: new Set(["attention_goal", "negative_preferences"]),
            boleAnswerInterpretations: {{}},
            boleActiveQuestionId: "ai_domains",
            boleQuestionTransitionTimer: null,
          }},
          setTimeout,
          clearTimeout,
          renderBoleWorkbench: () => {{}},
          syncBoleStage: () => {{}},
          renderBoleConversation: () => {{}},
          renderBoleDraftPreview: () => {{}},
          renderBoleRecommendationPreview: () => {{}},
          renderBoleRecognizedProfile: () => {{}},
          renderBoleSettingsStatus: () => {{}},
          syncBoleActionButtons: () => {{}},
          boleChatInputEl: null,
          boleDialogueTurnsEl: null,
          boleReadingTurnsEl: null,
          result: null,
        }};
        vm.createContext(sandbox);
        vm.runInContext(js.slice(start, end) + `
          mergeBoleAnswer("ai_domains", {{ choices: ["Agent"] }});
          const before = {{
            stage: state.boleStage,
            active: state.boleActiveQuestionId,
            label: primaryBoleActionLabel("ai_domains"),
          }};
          advanceBoleQuestionFrom("ai_domains", {{ animate: false }});
          result = {{
            before,
            afterStage: state.boleStage,
            afterActive: state.boleActiveQuestionId,
            shown: Array.from(state.boleShownQuestionIds),
          }};
        `, sandbox);
        if (sandbox.result.before.label !== "下一环节") {{
          throw new Error(`last question should show 下一环节, got ${{sandbox.result.before.label}}`);
        }}
        if (sandbox.result.before.stage !== "calibration" || sandbox.result.before.active !== "ai_domains") {{
          throw new Error("last question should stay active before explicit action");
        }}
        if (sandbox.result.afterStage !== "preferences" || sandbox.result.afterActive !== "deep_reading_policy") {{
          throw new Error(`expected preferences/deep_reading_policy, got ${{sandbox.result.afterStage}}/${{sandbox.result.afterActive}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_free_text_with_selected_choice_still_requires_interpretation():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("const BOLE_PROFILE_QUESTIONS");
        const end = js.indexOf("function renderBoleWorkbench", start);
        const sandbox = {{
          state: {{
            boleStage: "calibration",
            boleAnswers: {{}},
            boleShownQuestionIds: new Set(["attention_goal"]),
            boleConfirmedQuestionIds: new Set(),
            boleAnswerInterpretations: {{}},
            boleActiveQuestionId: "attention_goal",
            boleQuestionTransitionTimer: null,
          }},
          setTimeout,
          clearTimeout,
          result: null,
        }};
        vm.createContext(sandbox);
        vm.runInContext(js.slice(start, end) + `
          mergeBoleAnswer("attention_goal", {{
            choices: ["产品与工具"],
            text: "只看本地部署和量化，不想看泛泛工具盘点",
            ai_labels: [],
            ai_note: "",
          }});
          const before = {{
            ready: isBoleQuestionReady("attention_goal"),
            label: primaryBoleActionLabel("attention_goal"),
          }};
          mergeBoleAnswer("attention_goal", {{
            choices: ["产品与工具"],
            text: "只看本地部署和量化，不想看泛泛工具盘点",
            ai_labels: ["本地部署"],
            ai_note: "伯乐理解为：本地部署",
          }});
          result = {{
            before,
            afterReady: isBoleQuestionReady("attention_goal"),
            afterLabel: primaryBoleActionLabel("attention_goal"),
          }};
        `, sandbox);
        if (sandbox.result.before.ready || sandbox.result.before.label !== "确认回答") {{
          throw new Error(`free text with choices must wait for interpretation, got ${{sandbox.result.before.label}}`);
        }}
        if (!sandbox.result.afterReady || sandbox.result.afterLabel !== "下一题") {{
          throw new Error(`interpreted answer should become 下一题, got ${{sandbox.result.afterLabel}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_question_dot_or_answer_click_uses_card_transition():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert "transitionBoleQuestion(turn.dataset.boleQuestionId" in js
    assert "transitionBoleQuestion(nextQuestion.id" in js
    assert "bole-turn-deck-card one" in js
    assert "bole-turn-deck-card two" in js
    assert "is-transitioning" in js
    assert "exiting" in js
    assert ".bole-turn.exiting" in css
    assert ".bole-turn.entering" in css
    assert ".bole-dialogue-turns.is-transitioning" in css


def test_bole_choice_rerender_does_not_replay_card_enter_animation():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("const BOLE_PROFILE_QUESTIONS");
        const end = js.indexOf("function renderBoleWorkbench", start);
        const sandbox = {{
          state: {{
            boleStage: "calibration",
            boleAnswers: {{}},
            boleShownQuestionIds: new Set(["attention_goal"]),
            boleConfirmedQuestionIds: new Set(),
            boleAnswerInterpretations: {{}},
            boleActiveQuestionId: "attention_goal",
            boleQuestionTransitionTimer: null,
            boleEnteringQuestionId: "",
          }},
          escapeHtml: (value) => String(value || ""),
          result: null,
        }};
        vm.createContext(sandbox);
        vm.runInContext(js.slice(start, end) + `
          const question = boleQuestionById("attention_goal");
          mergeBoleAnswer("attention_goal", {{ choices: ["产品与工具"] }});
          const stable = renderBoleQuestionTurn(question);
          state.boleEnteringQuestionId = "attention_goal";
          const entering = renderBoleQuestionTurn(question);
          result = {{
            stableHasEntering: stable.includes("entering"),
            enteringHasEntering: entering.includes("entering"),
          }};
        `, sandbox);
        if (sandbox.result.stableHasEntering) {{
          throw new Error("ordinary choice rerender should not replay card enter animation");
        }}
        if (!sandbox.result.enteringHasEntering) {{
          throw new Error("real question transition should mark the next card as entering");
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_workbench_can_open_for_static_frontend_preview_without_backend():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    start = js.index("function openBoleWorkbench")
    end = js.index("function closeBoleWorkbench", start)
    body = js[start:end]
    branch_start = body.index("if (!apiBaseUrl)")
    unavailable_branch = body[branch_start : body.index("}", branch_start)]

    assert "return;" not in unavailable_branch
    assert "boleWorkbenchEl.hidden = false" in body
    assert "后端未配置" not in body
    assert "登录后使用伯乐画像" not in body


def test_bole_dialogue_progression_preserves_later_questions_when_editing():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("const BOLE_PROFILE_QUESTIONS");
        const end = js.indexOf("function renderBoleWorkbench", start);
        if (start < 0 || end < 0) {{
          throw new Error("missing bole helper slice");
        }}
        const sandbox = {{
          state: {{
            boleStage: "calibration",
            boleAnswers: {{}},
            boleShownQuestionIds: new Set(["attention_goal"]),
            boleConfirmedQuestionIds: new Set(),
            boleAnswerInterpretations: {{}},
            boleQuestionTransitionTimer: null,
          }},
          setTimeout,
          clearTimeout,
          result: null,
        }};
        vm.createContext(sandbox);
        vm.runInContext(js.slice(start, end) + `
          mergeBoleAnswer("attention_goal", {{ choices: ["产品与工具"] }});
          confirmBoleQuestion("attention_goal");
          mergeBoleAnswer("ai_domains", {{ choices: ["Agent"] }});
          confirmBoleQuestion("ai_domains");
          mergeBoleAnswer("negative_preferences", {{ choices: ["营销稿"] }});
          confirmBoleQuestion("negative_preferences");
          activateBoleQuestion("ai_domains");
          const visible = visibleBoleQuestionsForStage("calibration").map((item) => item.id);
          result = {{
            visible,
            confirmed: Array.from(state.boleConfirmedQuestionIds),
            active: activeBoleQuestion("calibration").id,
          }};
        `, sandbox);
        if (sandbox.result.visible.join("|") !== "attention_goal|negative_preferences|ai_domains") {{
          throw new Error(`editing a previous question hid later questions: ${{sandbox.result.visible.join("|")}}`);
        }}
        if (!sandbox.result.confirmed.includes("negative_preferences")) {{
          throw new Error("later confirmed question was lost during edit");
        }}
        if (sandbox.result.active !== "ai_domains") {{
          throw new Error(`expected ai_domains to reopen, got ${{sandbox.result.active}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_custom_input_uses_ai_interpretation_instead_of_raw_text_tags():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("const BOLE_PROFILE_QUESTIONS");
        const end = js.indexOf("function renderBoleWorkbench", start);
        const sandbox = {{
          state: {{
            boleStage: "calibration",
            boleAnswers: {{}},
            boleShownQuestionIds: new Set(["attention_goal"]),
            boleConfirmedQuestionIds: new Set(),
            boleAnswerInterpretations: {{}},
            boleQuestionTransitionTimer: null,
          }},
          setTimeout,
          clearTimeout,
          result: null,
        }};
        vm.createContext(sandbox);
        vm.runInContext(js.slice(start, end) + `
          const raw = "我更关心企业内部知识库真正落地，不想看空泛观点";
          mergeBoleAnswer("attention_goal", {{
            text: raw,
            ai_labels: ["企业知识库落地", "规避空泛观点"],
            ai_note: "更偏向企业内部知识库场景。",
            follow_up: "你更想看产品实践还是工程方案？",
          }});
          const answer = normalizeBoleAnswer(state.boleAnswers.attention_goal);
          result = {{
            text: answer.text,
            labels: boleAnswerLabels(answer),
            context: buildBoleConversationContext("ai_domains"),
          }};
        `, sandbox);
        if (sandbox.result.text !== "我更关心企业内部知识库真正落地，不想看空泛观点") {{
          throw new Error("raw custom answer was not preserved");
        }}
        if (sandbox.result.labels.join("|") !== "企业知识库落地|规避空泛观点") {{
          throw new Error(`raw text leaked into profile tags: ${{sandbox.result.labels.join("|")}}`);
        }}
        const context = JSON.stringify(sandbox.result.context);
        if (!context.includes("企业内部知识库真正落地") || !context.includes("企业知识库落地")) {{
          throw new Error("conversation context should include raw answer and AI labels");
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_right_rail_filters_by_stage_and_supports_removing_choices():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert "boleProfileSectionsForStage" in js
    assert 'state.boleStage === "calibration"' in js
    assert 'state.boleStage === "preferences"' in js
    assert "data-bole-remove-question" in js
    assert "data-bole-remove-label" in js
    assert "removeBoleProfileLabel" in js
    assert "renderBoleProfileCards(readingLabels" not in js[js.index("function renderBoleRecognizedProfile") : js.index("function renderBoleDraftPreview")]
    assert ".bole-profile-remove" in css


def test_bole_stage_actions_are_minimal_and_contextual():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    workbench = html[html.index('id="boleWorkbench"') : html.index('id="readerSheet"')]

    assert 'id="boleDraftButton"' not in workbench
    assert "生成草稿" not in workbench
    assert "继续校准" not in workbench
    assert 'id="boleConfirmButton" class="bole-primary-button" type="button">保存</button>' in workbench
    assert "syncBoleActionButtons" in js
    assert 'boleConfirmButtonEl.textContent = state.boleStage === "draft" ? "保存画像" : "保存";' in js
    assert 'boleContinueButtonEl.hidden = state.boleStage === "draft";' in js
    assert 'boleSkipButtonEl.hidden = !isFirstUseStage || state.boleStage === "draft";' in js


def test_bole_motion_is_stable_and_rail_scrollbar_is_compact():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    profile_rule = css[css.index(".bole-profile-card {") : css.index(".bole-profile-card.avoid")]
    assert ".bole-turn.entering" in css
    assert ".bole-turn.exiting" in css
    assert "@keyframes bole-card-enter" in css
    assert "@keyframes bole-card-exit" in css
    assert "animation:" not in profile_rule
    assert ".bole-profile-list::-webkit-scrollbar" in css
    rail_scrollbar = css[css.index(".bole-profile-list::-webkit-scrollbar") : css.index(".bole-profile-card", css.index(".bole-profile-list::-webkit-scrollbar"))]
    assert "width: 4px;" in rail_scrollbar
    assert "height: 4px;" in rail_scrollbar
    assert "@keyframes bole-rise" not in css
    assert "@keyframes bole-slide-in" not in css


def test_personalized_bole_profile_draft_builder_dedupes_and_handles_empty_inputs():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function parseBoleTerms");
        const end = js.indexOf("function renderBoleWorkbench", start);
        if (start < 0 || end < 0) {{
          throw new Error("missing bole profile draft helper slice");
        }}
        const code = js.slice(start, end)
          + "\\nresult = {{"
          + "\\n  empty: buildBoleProfileDraft({{ calibrationAnswers: {{}} }}),"
          + "\\n  mixed: buildBoleProfileDraft({{"
          + "\\n    calibrationAnswers: {{"
          + "\\n      attention_goal: {{ choices: ['模型发布', 'Agent 产品化'], text: '模型评测, Agent 产品化 / 开源工具', ai_labels: ['模型评测', '开源工具'] }},"
          + "\\n      negative_preferences: {{ choices: ['融资'], text: '融资；硬件八卦', ai_labels: ['硬件八卦'] }},"
          + "\\n      ai_domains: {{ choices: ['Agent 产品化'], text: 'RAG / 知识库，多模态', ai_labels: ['RAG / 知识库', '多模态'] }},"
          + "\\n      deep_reading_policy: {{ choices: ['高命中读正文'], text: '重大新闻先核验', ai_labels: ['重大新闻先核验'] }},"
          + "\\n      reading_depth: {{ choices: ['深入分析'], text: '工程细节', ai_labels: ['工程细节'] }}"
          + "\\n    }}"
          + "\\n  }}),"
          + "\\n  evidence: buildBoleDraftEvidence({{"
          + "\\n    calibrationAnswers: {{ attention_goal: {{ choices: ['工具链'], text: '本地部署' }} }}"
          + "\\n  }})"
          + "\\n}};";
        const sandbox = {{ result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        const empty = sandbox.result.empty;
        const mixed = sandbox.result.mixed;
        if (!Array.isArray(empty.positive_interests) || empty.positive_interests.length !== 0) {{
          throw new Error("empty positive interests should stay valid and empty");
        }}
        if (!Array.isArray(empty.negative_interests) || empty.negative_interests.length !== 0) {{
          throw new Error("empty negative interests should stay valid and empty");
        }}
        if (empty.behavior_preferences.summary_depth !== "standard") {{
          throw new Error("empty draft should keep standard summary default");
        }}
        const positiveLabels = mixed.positive_interests.map((item) => item.label);
        const negativeLabels = mixed.negative_interests.map((item) => item.label);
        if (positiveLabels.join("|") !== "模型发布|Agent 产品化|模型评测|开源工具|RAG / 知识库|多模态") {{
          throw new Error(`unexpected positive labels: ${{positiveLabels.join("|")}}`);
        }}
        if (negativeLabels.join("|") !== "融资|硬件八卦") {{
          throw new Error(`unexpected negative labels: ${{negativeLabels.join("|")}}`);
        }}
        if (mixed.positive_interests[0].weight !== 0.85 || mixed.negative_interests[0].weight !== 0.8) {{
          throw new Error("interest weights are not normalized as expected");
        }}
        if (mixed.behavior_preferences.summary_depth !== "deep") {{
          throw new Error("summary depth was not preserved");
        }}
        if (mixed.behavior_preferences.verification_strictness !== "strict") {{
          throw new Error("verification strictness was not preserved");
        }}
        if (mixed.behavior_preferences.deep_reading_policy[0] !== "高命中读正文") {{
          throw new Error("deep reading policy was not preserved");
        }}
        if (sandbox.result.evidence.calibration_answers.attention_goal.text !== "本地部署") {{
          throw new Error("calibration evidence should preserve free text");
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_homepage_uses_compact_header_and_data_drawer():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    assert "过去 24 小时值得看的 AI/科技更新" not in html
    assert 'id="dataDrawerButton"' in html
    assert 'id="dataDrawer"' in html
    assert 'id="dataDrawer" class="data-drawer" hidden' in html
    assert 'id="dataDrawer" class="data-drawer" data-mobile-view' not in html
    assert 'id="dataDrawerClose"' in html
    assert "openDataDrawer" in js
    assert "closeDataDrawer" in js
    assert ".updated-pill" in css
    assert ".data-drawer" in css


def test_signal_flow_has_source_sort_and_hidden_controls():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert 'id="sourceSortButton"' in html
    assert 'id="sourceHiddenButton"' in html
    assert 'id="sourceSortDialog"' in html
    assert 'id="sourceSortList"' in html
    assert 'id="sourceSortBlockButton"' in html
    assert 'id="sourceHiddenDialog"' in html
    assert "renderSourceSortDialog" in js
    assert "blockSelectedSourceGroups" in js
    assert "restoreHiddenSourcePreference" in js
    assert ".signal-flow-actions" in css
    assert ".source-sort-dialog" in css


def test_signal_flow_source_preferences_are_local_and_reversible():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    assert "SOURCE_PREF_STORAGE_KEY" in js
    assert "localStorage.getItem(SOURCE_PREF_STORAGE_KEY)" in js
    assert "localStorage.setItem(SOURCE_PREF_STORAGE_KEY" in js
    assert "hiddenSites" in js
    assert "hiddenSourcesBySite" in js
    assert "siteOrder" in js
    assert "sourceOrderBySite" in js
    assert "sourcePreferenceHiddenCount" in js


def test_signal_flow_groups_default_to_compact_expandable_sections():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    assert "SOURCE_GROUP_PREVIEW_COUNT = 2" in js
    assert "SOURCE_ITEM_PREVIEW_COUNT = 3" in js
    assert "expandedSites: new Set()" in js
    assert "expandedSourceGroups: new Set()" in js
    assert "source-toggle-action" in js
    assert "source-toggle-meta" in js
    assert "aria-expanded" in js
    assert "source-show-more" not in js
    assert "site-show-more" not in js


def test_signal_flow_site_toggle_lives_in_site_header_not_group_footer():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    function_start = js.index("function renderGroupedBySiteAndSource")
    function_end = js.index("function renderList", function_start)
    site_group_renderer = js[function_start:function_end]

    assert "siteSection.dataset.siteId = siteId" in site_group_renderer
    assert "site-toggle-meta" in site_group_renderer
    assert "site-toggle-action" in site_group_renderer
    assert "header.append(title, meta)" in site_group_renderer
    assert "meta.append(count, toggle)" in site_group_renderer
    assert "siteSection.appendChild(buildShowMoreButton(" not in site_group_renderer
    assert "state.expandedSites.add(siteId)" in site_group_renderer
    assert "collapseSiteGroup(siteId)" in site_group_renderer
    assert "toggle.setAttribute(\"aria-label\"" in site_group_renderer


def test_signal_flow_collapsing_site_returns_to_same_site_header():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    collapse_start = js.index("function collapseSiteGroup")
    collapse_end = js.index("function sourcePrefsHiddenSourceSet", collapse_start)
    collapse_code = js[collapse_start:collapse_end]
    function_start = js.index("function renderGroupedBySiteAndSource")
    function_end = js.index("function renderList", function_start)
    site_group_renderer = js[function_start:function_end]

    assert "collapseSiteGroup(siteId)" in site_group_renderer
    assert "state.expandedSites.delete(siteId)" in collapse_code
    assert "renderList()" in collapse_code
    assert "window.requestAnimationFrame" in collapse_code
    assert "findSiteGroupNode(siteId)" in collapse_code
    assert 'scrollIntoView({ behavior: "auto", block: "start" })' in collapse_code
    assert "state.expandedSites.add(siteId)" in site_group_renderer
    assert "scrollIntoView" not in site_group_renderer


def test_signal_flow_source_toggle_lives_in_source_header_not_group_footer():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    function_start = js.index("function buildSourceGroupNode")
    function_end = js.index("function groupBySource", function_start)
    source_group_builder = js[function_start:function_end]

    assert "header.append(title, meta)" in source_group_builder
    assert "meta.append(count, toggle)" in source_group_builder
    assert "section.appendChild(buildShowMoreButton(" not in source_group_builder
    assert "expandedSourceGroups.add(sourceKey)" in source_group_builder
    assert "collapseSourceGroup(sourceKey)" in source_group_builder
    assert "toggle.setAttribute(\"aria-label\"" in source_group_builder


def test_signal_flow_collapsing_source_returns_to_same_source_header():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    collapse_start = js.index("function collapseSourceGroup")
    collapse_end = js.index("function buildSourceGroupNode", collapse_start)
    collapse_code = js[collapse_start:collapse_end]
    function_start = js.index("function buildSourceGroupNode")
    function_end = js.index("function groupBySource", function_start)
    source_group_builder = js[function_start:function_end]

    assert "collapseSourceGroup(sourceKey)" in source_group_builder
    assert "state.expandedSourceGroups.delete(sourceKey)" in collapse_code
    assert "renderList()" in collapse_code
    assert "window.requestAnimationFrame" in collapse_code
    assert "findSourceGroupNode(sourceKey)" in collapse_code
    assert 'scrollIntoView({ behavior: "auto", block: "start" })' in collapse_code
    assert "state.expandedSourceGroups.add(sourceKey)" in source_group_builder
    assert "scrollIntoView" not in source_group_builder


def test_signal_flow_source_toggle_is_unboxed_text_action_with_mobile_fallback():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert ".source-toggle-action" in css
    assert ".source-toggle-meta" in css
    assert ".source-show-more" not in css
    assert ".site-toggle-action" in css
    assert ".site-toggle-meta" in css
    assert ".site-show-more" not in css
    assert ".source-toggle-action {\n  border: 0;" in css
    assert "background: transparent;" in css
    assert "text-decoration: underline;" in css
    assert ".site-toggle-action .site-toggle-label" in css
    assert ".source-toggle-action .source-toggle-label" in css
    assert "display: none;" in css


def test_signal_flow_group_headers_stick_while_scanning_expanded_items():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    list_wrap_start = css.index(".bole-picks-wrap,")
    list_wrap_end = css.index("}", list_wrap_start) + 1
    list_wrap_css = css[list_wrap_start:list_wrap_end]
    list_stack_start = css.index(".news-list,")
    list_stack_end = css.index(".site-group {", list_stack_start)
    list_stack_css = css[list_stack_start:list_stack_end]
    site_selector_start = css.index(".site-group-head {")
    site_selector_end = css.index(".source-group-head {", site_selector_start)
    site_header_css = css[site_selector_start:site_selector_end]
    selector_start = css.index(".source-group-head {")
    selector_end = css.index(".site-group-head h3,", selector_start)
    source_header_css = css[selector_start:selector_end]

    assert "overflow: hidden;" not in list_wrap_css
    assert ".list-wrap" in list_wrap_css
    assert "overflow: visible;" in list_wrap_css
    assert "display: block;" in list_stack_css
    assert "display: grid;" not in list_stack_css
    assert "position: sticky;" in site_header_css
    assert "top: 0;" in site_header_css
    assert "z-index:" in site_header_css
    assert "box-shadow:" in site_header_css
    assert "linear-gradient" in site_header_css
    assert "var(--surface)" in site_header_css
    assert "position: sticky;" in source_header_css
    assert "top: var(--site-group-sticky-offset);" in source_header_css
    assert "z-index:" in source_header_css
    assert "box-shadow:" in source_header_css
    assert "linear-gradient" in source_header_css
    assert "var(--surface)" in source_header_css


def test_signal_flow_uses_native_group_header_sticky_without_fixed_clone():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert "ensureActiveSourceBar" not in js
    assert "syncActiveSourceBar" not in js
    assert "scheduleActiveSourceBarSync" not in js
    assert "activeSourceBarEl" not in js
    assert "active-source-bar" not in js
    assert "activeSiteBar" not in js
    assert "active-site-bar" not in js
    assert "window.addEventListener(\"scroll\", scheduleActiveSourceBarSync" not in js
    assert "active-source-bar" not in css
    assert "active-site-bar" not in css


def test_source_sort_dialog_uses_real_four_point_grip_icons():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert "function renderDragGrip" in js
    assert "for (let i = 0; i < 4; i += 1)" in js
    assert "drag-grip" in js
    assert ".drag-grip" in css
    assert "grid-template-columns: repeat(2" in css
    assert ">拖<" not in js


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


def test_bole_picks_selection_criteria_copy_is_not_rendered_inline():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert "为什么精选" not in html
    assert "伯乐精选依据：" not in js
    assert "bole-explainer" not in js
    assert ".bole-explainer" not in css
    assert ".bole-picks-sub" not in css


def test_bole_picks_show_top_ten_candidates():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    picker_start = js.index("function pickBoleItems")
    picker_end = js.index("function boleReasonText", picker_start)
    picker = js[picker_start:picker_end]

    assert "const BOLE_PICK_LIMIT = 10" in js
    assert "picked.length < BOLE_PICK_LIMIT" in picker
    assert "picked.length < 8" not in picker


def test_bole_picks_limit_applies_when_more_than_ten_candidates_exist():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z' }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nresult = pickBoleItems(items).length;";
        const items = Array.from({{ length: 12 }}, (_, index) => ({{
          title: `Distinct AI model update ${{index}}`,
          site_name: "TechURLs",
          site_id: "techurls",
          source: `Source ${{index}}`,
          ai_score: 0.9,
          published_at: `2026-06-18T${{String(index).padStart(2, "0")}}:00:00Z`
        }}));
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result !== 10) {{
          throw new Error(`expected 10 picks, got ${{sandbox.result}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_prefers_priority_score_over_ai_score():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z' }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nresult = pickBoleItems(items)[0].item.title;";
        const items = [
          {{
            title: "High relevance but lower priority",
            site_name: "TechURLs",
            source: "Source A",
            ai_score: 0.95,
            priority_score: 0.70,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Lower relevance but higher priority",
            site_name: "Official AI Updates",
            source: "OpenAI News",
            ai_score: 0.80,
            priority_score: 0.98,
            published_at: "2026-06-18T09:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result !== "Lower relevance but higher priority") {{
          throw new Error(`expected priority_score winner, got ${{sandbox.result}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_confirmed_profile_promotes_matching_interests():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z', personalizationStatus: {{ state: 'confirmed', enabled: true, active_profile: {{ positive_interests: [{{ label: 'Agent' }}], negative_interests: [] }} }} }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nconst pick = pickBoleItems(items)[0];"
          + "\\nresult = {{ title: pick.item.title, reason: boleReasonText(pick), score: pick.score }};";
        const items = [
          {{
            title: "Generic AI market update",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.95,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Agent framework reaches production teams",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.82,
            published_at: "2026-06-18T09:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result.title !== "Agent framework reaches production teams") {{
          throw new Error(`expected Agent profile match first, got ${{sandbox.result.title}}`);
        }}
        if (!sandbox.result.reason.includes("符合您的画像：Agent")) {{
          throw new Error(`expected personalized reason, got ${{sandbox.result.reason}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_render_bole_picks_keeps_profile_priority_order():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("\\nfunction itemImageUrl", start);
        function createElement(tagName) {{
          return {{
            tagName,
            className: "",
            textContent: "",
            innerHTML: "",
            children: [],
            append(...nodes) {{ this.children.push(...nodes); }},
            appendChild(node) {{ this.children.push(node); return node; }}
          }};
        }}
        const items = [
          {{
            title: "Generic AI market update",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.95,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Agent framework reaches production teams",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.82,
            published_at: "2026-06-18T09:00:00Z"
          }}
        ];
        const root = createElement("div");
        const meta = createElement("div");
        const document = {{ createElement }};
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "function fmtNumber(value) {{ return String(value); }}\\n"
          + "function bindReaderLink() {{}}\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + "const bolePicksListEl = root;\\n"
          + "const bolePicksMetaEl = meta;\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z', itemsAi: items, personalizationStatus: {{ state: 'confirmed', enabled: true, active_profile: {{ positive_interests: [{{ label: 'Agent' }}], negative_interests: [] }} }} }};\\n"
          + js.slice(start, end)
          + "\\nrenderBolePicks();"
          + "\\nconst list = root.children.find((child) => child.className === 'bole-compact-list');"
          + "\\nresult = list.children.map((row) => row.children[1].children[1].textContent);"
          + "\\nmetaText = meta.textContent;";
        const sandbox = {{ document, items, root, meta, result: null, metaText: "" }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result[0] !== "Agent framework reaches production teams") {{
          throw new Error(`expected rendered Agent profile match first, got ${{sandbox.result[0]}}`);
        }}
        if (!sandbox.metaText.includes("按得分排序") || !sandbox.metaText.includes("已应用画像")) {{
          throw new Error(`expected personalized score-order meta text, got ${{sandbox.metaText}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_confirmed_profile_downranks_negative_interests_without_url_noise():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z', personalizationStatus: {{ state: 'confirmed', enabled: true, active_profile: {{ positive_interests: [{{ label: 'Agent' }}], negative_interests: [{{ label: '营销稿' }}] }} }} }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nresult = pickBoleItems(items).map((row) => ({{ title: row.item.title, score: row.score, reason: boleReasonText(row) }}));";
        const items = [
          {{
            title: "Agent vendor marketing roundup",
            title_zh: "Agent 厂商营销稿汇总",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.96,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Production Agent runtime adds local deployment controls",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.86,
            published_at: "2026-06-18T09:00:00Z"
          }},
          {{
            title: "Insurance market update",
            site_name: "Business Wire",
            source: "Source C",
            url: "https://example.com/agent-ai-launch",
            priority_score: 0.84,
            published_at: "2026-06-18T08:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result[0].title !== "Production Agent runtime adds local deployment controls") {{
          throw new Error(`expected non-marketing Agent item first, got ${{sandbox.result[0].title}}`);
        }}
        const urlNoise = sandbox.result.find((row) => row.title === "Insurance market update");
        if (urlNoise.reason.includes("符合您的画像")) {{
          throw new Error(`URL path should not create a profile match: ${{urlNoise.reason}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_confirmed_profile_applies_source_preferences_without_url_noise():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z', personalizationStatus: {{ state: 'confirmed', enabled: true, active_profile: {{ positive_interests: [], negative_interests: [], source_preferences: [{{ source: 'OpenAI News', weight: 0.9 }}, {{ source: 'Low Quality Wire', weight: -0.9 }}] }} }} }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nresult = pickBoleItems(items).map((row) => ({{ title: row.item.title, score: row.score, reason: boleReasonText(row) }}));";
        const items = [
          {{
            title: "Generic AI market update",
            site_name: "Generic Tech",
            source: "Daily Feed",
            priority_score: 0.94,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Official Agent SDK release notes",
            site_name: "OpenAI News",
            source: "Official Updates",
            priority_score: 0.82,
            published_at: "2026-06-18T09:00:00Z"
          }},
          {{
            title: "Speculative AI rumor roundup",
            site_name: "Low Quality Wire",
            source: "Low Quality Wire",
            priority_score: 0.98,
            published_at: "2026-06-18T08:00:00Z"
          }},
          {{
            title: "AI market brief",
            site_name: "Generic Tech",
            source: "Daily Feed",
            url: "https://example.com/openai-news/agent",
            priority_score: 0.83,
            published_at: "2026-06-18T07:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result[0].title !== "Official Agent SDK release notes") {{
          throw new Error(`expected preferred source first, got ${{sandbox.result[0].title}}`);
        }}
        if (!sandbox.result[0].reason.includes("符合您的来源偏好：OpenAI News")) {{
          throw new Error(`expected source preference reason, got ${{sandbox.result[0].reason}}`);
        }}
        const downranked = sandbox.result.find((row) => row.title === "Speculative AI rumor roundup");
        if (!downranked || !downranked.reason.includes("已按来源偏好降权：Low Quality Wire")) {{
          throw new Error(`expected source downrank reason, got ${{downranked && downranked.reason}}`);
        }}
        const urlNoise = sandbox.result.find((row) => row.title === "AI market brief");
        if (urlNoise.reason.includes("来源偏好")) {{
          throw new Error(`URL path should not trigger source preference: ${{urlNoise.reason}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_confirmed_profile_applies_reading_behavior_preferences_without_url_noise():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z', personalizationStatus: {{ state: 'confirmed', enabled: true, active_profile: {{ positive_interests: [], negative_interests: [], source_preferences: [], behavior_preferences: {{ summary_depth: 'deep', reading_depth: ['工程细节'] }} }} }} }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nresult = pickBoleItems(items).map((row) => ({{ title: row.item.title, score: row.score, reason: boleReasonText(row) }}));";
        const items = [
          {{
            title: "Generic AI market update",
            site_name: "Generic Tech",
            source: "Daily Feed",
            priority_score: 0.94,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Agent SDK adds API integration controls",
            summary: "Engineering teams can inspect workflow traces and deployment hooks.",
            ai_label: "developer_tooling",
            ai_signals: ["Agent SDK"],
            site_name: "Developer Blog",
            source: "Engineering",
            priority_score: 0.83,
            published_at: "2026-06-18T09:00:00Z"
          }},
          {{
            title: "AI market brief",
            site_name: "Generic Tech",
            source: "Daily Feed",
            url: "https://example.com/sdk/api/engineering",
            priority_score: 0.84,
            published_at: "2026-06-18T08:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result[0].title !== "Agent SDK adds API integration controls") {{
          throw new Error(`expected engineering-depth item first, got ${{sandbox.result[0].title}}`);
        }}
        if (!sandbox.result[0].reason.includes("符合阅读偏好：工程细节")) {{
          throw new Error(`expected behavior preference reason, got ${{sandbox.result[0].reason}}`);
        }}
        const urlNoise = sandbox.result.find((row) => row.title === "AI market brief");
        if (urlNoise.reason.includes("阅读偏好")) {{
          throw new Error(`URL path should not trigger behavior preference: ${{urlNoise.reason}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_ignore_draft_and_disabled_profiles():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const items = [
          {{
            title: "Generic AI market update",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.95,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Agent framework reaches production teams",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.82,
            published_at: "2026-06-18T09:00:00Z"
          }}
        ];
        const statuses = [
          {{
            state: "draft",
            enabled: true,
            draft_profile: {{ positive_interests: [{{ label: "Agent" }}], negative_interests: [] }}
          }},
          {{
            state: "confirmed",
            enabled: false,
            active_profile: {{ positive_interests: [{{ label: "Agent" }}], negative_interests: [] }}
          }}
        ];
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nresult = statuses.map((personalizationStatus) => {{"
          + "\\n  state.personalizationStatus = personalizationStatus;"
          + "\\n  const pick = pickBoleItems(items)[0];"
          + "\\n  return {{ title: pick.item.title, reason: boleReasonText(pick) }};"
          + "\\n}});";
        const sandbox = {{
          items,
          statuses,
          state: {{ generatedAt: "2026-06-19T00:00:00Z", personalizationStatus: null }},
          result: null
        }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        sandbox.result.forEach((row) => {{
          if (row.title !== "Generic AI market update") {{
            throw new Error(`inactive profile should not personalize ranking, got ${{row.title}}`);
          }}
          if (row.reason.includes("符合您的画像")) {{
            throw new Error(`inactive profile should not appear in reason: ${{row.reason}}`);
          }}
        }});
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_picks_rerender_after_confirmed_profile_status_changes():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    for name in (
        "loadPersonalization",
        "confirmBoleProfile",
        "skipBolePersonalization",
        "resetBolePersonalization",
        "disableBolePersonalization",
    ):
        match = re.search(rf"async function {name}\([^)]*\) \{{(?P<body>.*?)\n\}}", js, re.S)
        assert match, f"missing {name}()"
        body = match.group("body")
        assert "renderBolePicks();" in body, f"{name}() must refresh personalized Bole Picks"


def test_render_bole_picks_can_switch_between_score_and_time_order():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("\\nfunction itemImageUrl", start);
        function createElement(tagName) {{
          return {{
            tagName,
            className: "",
            textContent: "",
            _innerHTML: "",
            get innerHTML() {{ return this._innerHTML; }},
            set innerHTML(value) {{ this._innerHTML = value; this.children = []; }},
            dataset: {{}},
            children: [],
            append(...nodes) {{ this.children.push(...nodes); }},
            appendChild(node) {{ this.children.push(node); return node; }},
            setAttribute(name, value) {{ this[name] = value; }},
            addEventListener() {{}}
          }};
        }}
        const items = [
          {{
            id: "high-old",
            title: "High scoring older AI release",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.96,
            published_at: "2026-06-18T08:00:00Z"
          }},
          {{
            id: "fresh-low",
            title: "Fresh lower scoring AI update",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.72,
            published_at: "2026-06-18T12:00:00Z"
          }}
        ];
        const root = createElement("div");
        const meta = createElement("div");
        const document = {{ createElement }};
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "function fmtNumber(value) {{ return String(value); }}\\n"
          + "function bindReaderLink() {{}}\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + "const bolePicksListEl = root;\\n"
          + "const bolePicksMetaEl = meta;\\n"
          + "const boleSortPopoverEl = null;\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z', itemsAi: items, personalizationStatus: null, boleFeedbackByKey: new Map(), boleSortMode: 'score' }};\\n"
          + js.slice(start, end)
          + "\\nrenderBolePicks();"
          + "\\nconst byScore = root.children.find((child) => child.className === 'bole-compact-list').children.map((row) => row.children[1].children[1].textContent);"
          + "\\nconst scoreMeta = meta.textContent;"
          + "\\nsetBoleSortMode('time');"
          + "\\nconst byTime = root.children.find((child) => child.className === 'bole-compact-list').children.map((row) => row.children[1].children[1].textContent);"
          + "\\nconst timeMeta = meta.textContent;"
          + "\\nresult = {{ byScore, scoreMeta, byTime, timeMeta }};";
        const sandbox = {{ document, items, root, meta, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result.byScore[0] !== "High scoring older AI release") {{
          throw new Error(`expected score order first, got ${{sandbox.result.byScore[0]}}`);
        }}
        if (sandbox.result.byTime[0] !== "Fresh lower scoring AI update") {{
          throw new Error(`expected time order first, got ${{sandbox.result.byTime[0]}}`);
        }}
        if (!sandbox.result.scoreMeta.includes("按得分排序") || !sandbox.result.timeMeta.includes("按时间排序")) {{
          throw new Error(`unexpected meta text: ${{JSON.stringify(sandbox.result)}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_event_key_keeps_unrelated_same_model_stories_separate():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z' }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nconst ranked = items.map((item, index) => ({{ item, index, score: scorePercent(item) }}));"
          + "\\nresult = clusterBoleEvents(ranked).length;";
        const items = [
          {{
            title: "Gemini 2.5 Flash pricing cut reaches developers",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.90,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Gemini 2.5 Flash benchmark tops coding chart",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.89,
            published_at: "2026-06-18T09:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result !== 2) {{
          throw new Error(`expected two unrelated clusters, got ${{sandbox.result}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_event_key_merges_same_model_same_action_stories():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-19T00:00:00Z' }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nconst ranked = items.map((item, index) => ({{ item, index, score: scorePercent(item) }}));"
          + "\\nconst clusters = clusterBoleEvents(ranked);"
          + "\\nresult = {{ length: clusters.length, mergedCount: clusters[0].mergedCount }};";
        const items = [
          {{
            title: "Gemini 2.5 Flash pricing cut reaches developers",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.90,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            title: "Google cuts Gemini 2.5 Flash pricing for API users",
            site_name: "AI HOT",
            source: "Source B",
            priority_score: 0.91,
            published_at: "2026-06-18T09:00:00Z"
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result.length !== 1 || sandbox.result.mergedCount !== 2) {{
          throw new Error(`expected one merged pricing cluster, got ${{JSON.stringify(sandbox.result)}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


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
    assert 'id="boleConflictStrategySelect"' in html
    assert "画像冲突策略" in html
    assert 'value="ask">每次询问' in html
    assert 'value="last_decision">最后决断' in html
    assert "loginAdmin" in js
    assert "saveSettings" in js
    assert "ask_system_prompt" in js
    assert "bole_conflict_strategy" in js


def test_settings_view_adapts_to_desktop_wide_layout_and_mobile_single_column():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert 'class="settings-section settings-login-section"' in html
    assert 'class="settings-section settings-ai-section"' in html
    assert 'class="settings-section settings-usage-section"' in html
    assert 'class="settings-section settings-behavior-section"' in html
    assert 'class="settings-section settings-bole-section"' in html
    assert "max-width: 520px" not in css
    assert ".settings-panel {\n  width: 100%;" in css
    assert "align-content: start;" in css[css.index(".settings-section {") : css.index(".settings-login-section {")]
    assert "grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);" in css
    assert ".settings-login-section {\n  grid-column: 1 / -1;" in css
    assert ".settings-ai-section {\n  grid-row: span 3;" in css
    assert ".settings-ai-section .ai-profile-form {\n  grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert ".settings-panel {\n    grid-template-columns: 1fr;" in css
    assert ".settings-login-section,\n  .settings-ai-section {\n    grid-column: auto;\n    grid-row: auto;" in css
    assert ".settings-ai-section .ai-profile-form {\n    grid-template-columns: 1fr;" in css


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


def test_bole_feedback_surfaces_match_confirmed_overlay_design():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    reader = html[html.index('id="readerSheet"') : html.index('id="askAiSheet"')]
    header = html[html.index('class="bole-picks-head"') : html.index('id="bolePicksList"')]

    assert 'id="boleSortButton"' in header
    assert "排序" in header
    assert 'id="boleSortPopover" class="bole-sort-popover" hidden' in html
    assert 'id="boleSortPopover" class="bole-sort-popover" data-mobile-view' not in html
    assert 'data-bole-sort-mode="score"' in html
    assert 'data-bole-sort-mode="time"' in html
    assert 'id="boleFeedbackButton"' in header
    assert "最近反馈" in header
    assert 'id="boleWorkbenchOpen"' in header
    assert "画像" in header
    assert "为你推荐" not in header
    assert 'id="boleFeedbackDialog" class="bole-feedback-dialog" hidden' in html
    assert 'id="boleFeedbackDialog" class="bole-feedback-dialog" data-mobile-view' not in html
    assert 'id="boleTunePopover" class="bole-tune-popover" hidden' in html
    assert 'id="boleTunePopover" class="bole-tune-popover" data-mobile-view' not in html
    assert 'id="boleDraftSuggestionDialog" class="bole-draft-suggestion-dialog" hidden' in html
    assert 'id="readerFeedbackTrigger" class="reader-feedback-trigger"' in reader
    assert 'id="readerFeedbackPopover" class="reader-feedback-popover" hidden' in reader
    assert 'id="readerFeedbackPopover" class="reader-feedback-popover" data-mobile-view' not in html
    assert 'aria-controls="readerFeedbackPopover"' in reader
    assert 'class="lucide-icon"' in reader
    assert 'data-bole-feedback-action="more_like_this"' in reader
    assert 'data-bole-feedback-action="less_relevant"' in reader
    assert 'data-bole-feedback-action="not_interested"' in reader
    assert 'data-bole-feedback-action="more_relevant"' not in reader
    assert 'id="readerFeedback" class="reader-feedback"' not in reader
    assert "更相关" not in reader
    assert "多看类似" not in reader
    assert "感兴趣" in reader
    assert 'class="feedback-option positive"' in reader
    assert 'class="feedback-option negative"' in reader
    assert 'class="feedback-option negative strong"' in reader
    assert "feedback-glyph" not in reader
    assert "画像草稿已保存" not in html
    assert ".bole-feedback-dialog" in css
    assert ".bole-sort-popover" in css
    assert ".bole-tune-popover" in css
    assert ".reader-feedback-trigger" in css
    assert ".reader-feedback-popover" in css
    assert ".feedback-option.positive" in css
    assert ".feedback-option.negative" in css
    assert ".bole-draft-suggestion-dialog" in css


def test_bole_feedback_uses_dialogs_and_anchored_popover_not_inline_panels():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    row_builder = js[js.index("function buildBoleTimelineRow") : js.index("function renderBolePicks")]

    assert "openBoleSortPopover" in js
    assert "setBoleSortMode" in js
    assert "openBoleFeedbackDialog" in js
    assert "closeBoleFeedbackDialog" in js
    assert "openBoleTunePopover" in js
    assert "positionBoleTunePopover" in js
    assert "toggleReaderFeedbackPopover" in js
    assert "closeReaderFeedbackPopover" in js
    assert "getBoundingClientRect()" in js[js.index("function positionBoleTunePopover") :]
    assert "submitBoleFeedback" in js
    assert "undoBoleFeedback" in js
    assert "loadBoleFeedback" in js
    assert 'apiFetch("/api/personalization/feedback"' in js
    assert 'apiFetch(`/api/personalization/feedback/${encodeURIComponent(feedbackId)}`' in js
    assert 'className = "bole-row-tune-button"' in row_builder
    assert "body.append(meta, title, reason, tune)" in row_builder
    assert "link.append(time, body)" in row_builder
    assert "link.append(time, body, tune)" not in row_builder
    assert 'data-bole-feedback-action="less_relevant"' not in row_builder
    assert "阅读" not in row_builder
    assert "readerFeedbackTriggerEl.addEventListener" in js
    assert "readerFeedbackPopoverEl.addEventListener" in js
    assert "submitBoleFeedback(button.dataset.boleFeedbackAction, state.readerItem)" in js
    assert "closeReaderFeedbackPopover();" in js[js.index("async function submitBoleFeedback") :]
    assert "removeBoleSessionFeedback(localFeedback)" not in js[js.index("async function submitBoleFeedback") : js.index("async function undoBoleFeedback")]
    assert ".bole-tune-popover {\n  position: fixed;" in css
    assert ".bole-sort-popover {\n  position: absolute;" in css
    assert ".bole-feedback-dialog {\n  position: fixed;" in css
    assert ".reader-feedback-popover {\n  position: absolute;" in css
    assert ".bole-draft-suggestion-dialog {\n  position: fixed;" in css
    assert ".bole-row-feedback-panel" not in css
    assert ".bole-feedback-inline" not in css


def test_bole_feedback_draft_suggestion_merges_with_existing_profile_before_save():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "function mergeBoleProfilePatch" in js
    assert "function baseBoleProfileForSuggestion" in js
    assert "function currentBoleDraftProfile" in js

    save_body = js[js.index("async function saveBoleDraft") : js.index("async function confirmBoleProfile")]
    merge_body = js[js.index("function mergeDraftSuggestionIntoWorkbench") : js.index("function feedbackPayloadForItem")]
    assert "currentBoleDraftProfile()" in save_body
    assert "baseBoleProfileForSuggestion()" in merge_body

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function uniqueBoleProfileEntries");
        const end = js.indexOf("function closeBoleDraftSuggestionDialog", start);
        const code = js.slice(start, end)
          + "\\nresult = mergeBoleProfilePatch(base, patch);";
        const base = {{
          positive_interests: [{{ label: "Agent", weight: 0.85, source: "user" }}],
          negative_interests: [{{ label: "融资", weight: 0.8, source: "user" }}],
          source_preferences: [{{ source: "OpenAI News", weight: 0.7 }}],
          behavior_preferences: {{ summary_depth: "concise", verification_strictness: "standard" }}
        }};
        const patch = {{
          positive_interests: [{{ label: "Agent", weight: 0.65, source: "feedback" }}],
          negative_interests: [{{ label: "营销稿", weight: 0.75, source: "feedback" }}]
        }};
        const sandbox = {{ base, patch, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        const positive = sandbox.result.positive_interests.map((item) => item.label).join("|");
        const negative = sandbox.result.negative_interests.map((item) => item.label).join("|");
        if (positive !== "Agent") {{
          throw new Error(`expected deduped positive interests, got ${{positive}}`);
        }}
        if (negative !== "融资|营销稿") {{
          throw new Error(`expected merged negative interests, got ${{negative}}`);
        }}
        if (sandbox.result.source_preferences[0].source !== "OpenAI News") {{
          throw new Error("source preferences should be preserved");
        }}
        if (sandbox.result.behavior_preferences.summary_depth !== "concise") {{
          throw new Error("behavior preferences should be preserved");
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_profile_conflict_strategy_resolves_same_label_by_policy():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "function resolveBoleProfilePatchConflict" in js
    assert "function mergeBoleProfilePatch" in js
    assert "function applyBoleConflictDecision" in js

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function uniqueBoleProfileEntries");
        const end = js.indexOf("function closeBoleDraftSuggestionDialog", start);
        const code = js.slice(start, end)
          + "\\nconst askResult = resolveBoleProfilePatchConflict(basePositive, negativePatch, 'ask');"
          + "\\nconst lastNegative = mergeBoleProfilePatch(basePositive, negativePatch, {{ conflictStrategy: 'last_decision' }});"
          + "\\nconst lastPositive = mergeBoleProfilePatch(baseNegative, positivePatch, {{ conflictStrategy: 'last_decision' }});"
          + "\\nconst userPositive = applyBoleConflictDecision(basePositive, negativePatch, 'positive');"
          + "\\nconst userIgnore = applyBoleConflictDecision(basePositive, negativePatch, 'ignore');"
          + "\\nresult = {{ askResult, lastNegative, lastPositive, userPositive, userIgnore }};";
        const basePositive = {{
          positive_interests: [{{ label: "Agent", weight: 0.85, source: "user" }}],
          negative_interests: [{{ label: "融资", weight: 0.8, source: "user" }}]
        }};
        const baseNegative = {{
          positive_interests: [],
          negative_interests: [{{ label: "Agent", weight: 0.8, source: "user" }}]
        }};
        const negativePatch = {{ negative_interests: [{{ label: "Agent", weight: 0.75, source: "feedback" }}] }};
        const positivePatch = {{ positive_interests: [{{ label: "Agent", weight: 0.7, source: "feedback" }}] }};
        const sandbox = {{ basePositive, baseNegative, negativePatch, positivePatch, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        const result = sandbox.result;
        const askConflict = result.askResult.conflicts[0];
        if (!askConflict || askConflict.label !== "Agent" || askConflict.incoming !== "negative") {{
          throw new Error(`expected ask conflict for Agent negative patch: ${{JSON.stringify(result.askResult)}}`);
        }}
        if (result.askResult.profile.positive_interests.map((item) => item.label).join("|") !== "Agent") {{
          throw new Error("ask strategy should keep the existing profile until the user decides");
        }}
        if (result.askResult.profile.negative_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("ask strategy should not add the conflicting negative label before decision");
        }}
        if (result.lastNegative.positive_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("last_decision should remove Agent from positive interests");
        }}
        if (!result.lastNegative.negative_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("last_decision should add Agent to negative interests");
        }}
        if (!result.lastPositive.positive_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("last_decision should add Agent back to positive interests");
        }}
        if (result.lastPositive.negative_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("last_decision should remove Agent from negative interests");
        }}
        if (!result.userPositive.positive_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("positive user decision should keep Agent positive");
        }}
        if (result.userPositive.negative_interests.map((item) => item.label).includes("Agent")) {{
          throw new Error("positive user decision should not leave Agent negative");
        }}
        if (result.userIgnore.positive_interests.map((item) => item.label).join("|") !== "Agent") {{
          throw new Error("ignore decision should keep existing positive profile");
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_last_decision_conflict_path_persists_without_dialog():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    last_decision_branch = js[
        js.index('if (state.boleConflictStrategy === "last_decision")') :
        js.index("openBoleProfileConflictDialog", js.index('if (state.boleConflictStrategy === "last_decision")'))
    ]
    assert "openBoleProfileConflictDialog" not in last_decision_branch
    assert "applyResolvedBoleProfile(conflict.profile, { persist: true })" in last_decision_branch

    apply_resolved_body = js[
        js.index("async function applyResolvedBoleProfile") :
        js.index("function openBoleProfileConflictDialog")
    ]
    assert 'apiFetch("/api/personalization/draft"' in apply_resolved_body
    assert 'apiFetch("/api/personalization/confirm"' in apply_resolved_body
    # Static/offline guard: optimistic local render and the persist/apiBaseUrl
    # early return must come before any backend write, so a no-backend reader and
    # a non-persisting caller never hit personalization APIs.
    guard_index = apply_resolved_body.index("if (!options.persist || !apiBaseUrl) return;")
    assert guard_index < apply_resolved_body.index('apiFetch("/api/personalization/draft"')
    assert apply_resolved_body.index("renderBolePicks();") < guard_index


def test_bole_manual_conflict_decision_persists_selected_direction():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")

    handler_body = js[
        js.index("function handleBoleProfileConflictDecision") :
        js.index("function feedbackPayloadForItem")
    ]
    assert "applyBoleConflictDecision" in handler_body
    assert "applyResolvedBoleProfile(profile, { persist: true })" in handler_body
    ignore_branch = handler_body[
        handler_body.index('if (decision === "ignore")') :
        handler_body.index("const profile = applyBoleConflictDecision")
    ]
    assert "applyResolvedBoleProfile" not in ignore_branch


def test_bole_conflict_dialog_has_no_selected_pill_badge():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert 'id="boleProfileConflictDialog" class="bole-profile-conflict-dialog" hidden' in html
    assert "data-bole-conflict-decision=\"positive\"" in html
    assert "data-bole-conflict-decision=\"negative\"" in html
    assert "data-bole-conflict-decision=\"ignore\"" in html
    conflict_css = css[css.index(".bole-profile-conflict-dialog {") :]
    assert "已选" not in conflict_css
    assert "border-radius: 999px" not in conflict_css[: conflict_css.index(".bole-profile-conflict-result")]


def test_bole_conflict_dialog_mobile_layout_is_sheet_not_cramped_columns():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")

    assert 'id="boleProfileConflictDialog" class="bole-profile-conflict-dialog" hidden' in html
    assert 'id="boleProfileConflictDialog" class="bole-profile-conflict-dialog" data-mobile-view' not in html
    mobile_css = css[css.index("@media (max-width: 760px)") :]
    assert ".bole-profile-conflict-dialog {" in mobile_css
    assert ".bole-profile-conflict-panel {" in mobile_css
    assert ".bole-profile-conflict-sources," in mobile_css
    assert ".bole-profile-conflict-actions {" in mobile_css
    conflict_mobile = mobile_css[mobile_css.index(".bole-profile-conflict-dialog {") :]
    assert "place-items: end center;" in conflict_mobile[:260]
    assert "grid-template-columns: 1fr;" in conflict_mobile


def test_bole_mobile_tune_button_stays_beside_item_body_not_time_column():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    mobile_css = css[css.index("@media (max-width: 760px)") :]
    row_rule = mobile_css[
        mobile_css.index(".bole-compact-list .bole-row {") :
        mobile_css.index(".bole-compact-list .bole-row::before")
    ]
    time_rule = mobile_css[
        mobile_css.index(".bole-compact-list .bole-row-time {") :
        mobile_css.index(".bole-compact-list .bole-row-body")
    ]
    body_rule = mobile_css[
        mobile_css.index(".bole-compact-list .bole-row-body {") :
        mobile_css.index(".bole-compact-list .bole-row-tune-button")
    ]
    tune_rule = mobile_css[
        mobile_css.index(".bole-compact-list .bole-row-tune-button {") :
        mobile_css.index(".bole-lead-card", mobile_css.index(".bole-compact-list .bole-row-tune-button"))
    ]

    assert "grid-template-columns: 1fr;" in row_rule
    assert "grid-column: 1 / -1;" in time_rule
    assert "grid-column: 1;" in body_rule
    assert "position: absolute;" in tune_rule
    assert "top: 8px;" in tune_rule
    assert "right: 8px;" in tune_rule


def test_bole_session_feedback_promotes_and_downranks_without_url_path_noise():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nrecordBoleSessionFeedback({{ action: 'more_like_this', item: items[1] }});"
          + "\\nrecordBoleSessionFeedback({{ action: 'not_interested', item: items[2] }});"
          + "\\nresult = pickBoleItems(items).map((row) => ({{ title: row.item.title, score: row.score, reason: boleReasonText(row) }}));";
        const items = [
          {{
            id: "generic",
            title: "Generic AI market update",
            site_name: "TechURLs",
            source: "Source A",
            priority_score: 0.94,
            published_at: "2026-06-18T10:00:00Z"
          }},
          {{
            id: "agent-runtime",
            title: "Agent runtime reaches production teams",
            site_name: "TechURLs",
            source: "Source B",
            priority_score: 0.74,
            published_at: "2026-06-18T09:00:00Z"
          }},
          {{
            id: "insurance",
            title: "Insurance market update",
            site_name: "Business Wire",
            source: "Source C",
            url: "https://example.com/agent-ai-launch?topic=agent",
            priority_score: 0.90,
            published_at: "2026-06-18T08:00:00Z"
          }}
        ];
        const sandbox = {{
          items,
          state: {{
            generatedAt: "2026-06-19T00:00:00Z",
            personalizationStatus: null,
            boleFeedbackByKey: new Map()
          }},
          result: null
        }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result[0].title !== "Agent runtime reaches production teams") {{
          throw new Error(`expected positive feedback winner, got ${{sandbox.result[0].title}}`);
        }}
        const insurance = sandbox.result.find((row) => row.title === "Insurance market update");
        if (!insurance || !insurance.reason.includes("已按反馈降权")) {{
          throw new Error(`expected explicit feedback downrank, got ${{insurance && insurance.reason}}`);
        }}
        if (insurance.reason.includes("符合您的画像")) {{
          throw new Error(`URL path should not create a profile match: ${{insurance.reason}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_feedback_api_failure_keeps_session_feedback_visible():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("async function undoBoleFeedback", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const document = {{ createElement() {{ return {{ className: '', textContent: '', dataset: {{}}, append() {{}}, appendChild() {{}} }}; }} }};\\n"
          + "const boleFeedbackListEl = {{ innerHTML: '', appendChild() {{}} }};\\n"
          + "const bolePicksListEl = null;\\n"
          + "const bolePicksMetaEl = null;\\n"
          + "const readerFeedbackPopoverEl = null;\\n"
          + "const boleTunePopoverEl = null;\\n"
          + "function renderBolePicks() {{ picksRendered += 1; }}\\n"
          + "function openBoleDraftSuggestionDialog() {{ throw new Error('should not open draft suggestion'); }}\\n"
          + "const apiBaseUrl = 'https://api.example.test';\\n"
          + "async function apiFetch() {{ throw new Error('unauthorized'); }}\\n"
          + js.slice(start, end)
          + "\\nresultPromise = submitBoleFeedback('not_interested', item);";
        const item = {{
          id: "agent-story",
          title: "Agent story",
          site_name: "TechURLs",
          source: "Source A",
          priority_score: 0.7,
          published_at: "2026-06-18T10:00:00Z"
        }};
        const sandbox = {{
          item,
          state: {{ boleFeedbackItems: [], boleFeedbackByKey: new Map() }},
          picksRendered: 0,
          readerClosed: 0,
          tuneClosed: 0,
          resultPromise: null
        }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        sandbox.resultPromise.then((result) => {{
          if (!result || result.action !== "not_interested") {{
            throw new Error(`expected local feedback result, got ${{JSON.stringify(result)}}`);
          }}
          if (sandbox.state.boleFeedbackItems.length !== 1) {{
            throw new Error(`expected session feedback to remain visible, got ${{sandbox.state.boleFeedbackItems.length}}`);
          }}
        }});
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_feedback_undo_removes_local_and_failed_api_records():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function scorePercent", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const document = {{ createElement() {{ return {{ className: '', textContent: '', dataset: {{}}, append() {{}}, appendChild() {{}} }}; }} }};\\n"
          + "const boleFeedbackListEl = null;\\n"
          + "const bolePicksListEl = null;\\n"
          + "const bolePicksMetaEl = null;\\n"
          + "const apiBaseUrl = 'https://api.example.test';\\n"
          + "let deleteCalls = 0;\\n"
          + "async function apiFetch(path, options) {{ deleteCalls += 1; throw new Error('offline'); }}\\n"
          + "function renderBolePicks() {{ picksRendered += 1; }}\\n"
          + js.slice(start, end)
          + "\\n(async () => {{"
          + "\\n  const local = recordBoleSessionFeedback({{ action: 'not_interested', item, created_at: '2026-06-23T12:00:00Z' }});"
          + "\\n  state.boleFeedbackItems = [local];"
          + "\\n  await undoBoleFeedback(local.id);"
          + "\\n  const afterLocal = {{ id: local.id, length: state.boleFeedbackItems.length, byKey: state.boleFeedbackByKey.size, deleteCalls }};"
          + "\\n  const server = recordBoleSessionFeedback({{ id: 42, action: 'less_relevant', item, created_at: '2026-06-23T12:01:00Z' }});"
          + "\\n  state.boleFeedbackItems = [server];"
          + "\\n  await undoBoleFeedback('42');"
          + "\\n  result = {{ afterLocal, afterServer: {{ length: state.boleFeedbackItems.length, byKey: state.boleFeedbackByKey.size, deleteCalls }} }};"
          + "\\n}})();";
        const item = {{
          id: "agent-story",
          title: "Agent story",
          site_name: "TechURLs",
          source: "Source A",
          priority_score: 0.7,
          published_at: "2026-06-18T10:00:00Z"
        }};
        const sandbox = {{
          item,
          state: {{ boleFeedbackItems: [], boleFeedbackByKey: new Map(), boleFeedbackUndoTombstones: new Set() }},
          picksRendered: 0,
          result: null
        }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        setTimeout(() => {{
          const {{ afterLocal, afterServer }} = sandbox.result || {{}};
          if (!afterLocal?.id) {{
            throw new Error(`local feedback needs stable undo id, got ${{JSON.stringify(afterLocal)}}`);
          }}
          if (afterLocal.length !== 0 || afterLocal.byKey !== 0) {{
            throw new Error(`local undo did not remove feedback: ${{JSON.stringify(afterLocal)}}`);
          }}
          if (afterLocal.deleteCalls !== 0) {{
            throw new Error(`local undo should not call backend delete: ${{JSON.stringify(afterLocal)}}`);
          }}
          if (afterServer.length !== 0 || afterServer.byKey !== 0 || afterServer.deleteCalls !== 1) {{
            throw new Error(`failed API delete should stay undone in this session: ${{JSON.stringify(afterServer)}}`);
          }}
        }}, 0);
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_feedback_history_shows_time_target_filters_search_and_sorting():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    dialog = html[html.index('id="boleFeedbackDialog"') : html.index('id="boleTunePopover"')]

    assert 'id="boleFeedbackSearch"' in dialog
    assert 'id="boleFeedbackTopicFilter"' in dialog
    assert 'id="boleFeedbackActionFilter"' in dialog
    assert 'id="boleFeedbackSortSelect"' in dialog
    assert 'id="boleFeedbackActionOrder"' in dialog
    assert 'id="boleFeedbackDialog" class="bole-feedback-dialog" data-mobile-view' not in html
    assert "boleFeedbackVisibleItems" in js
    assert "boleFeedbackTargetLabel" in js
    assert "boleFeedbackTopicOptions" in js
    assert "formatBoleFeedbackTime" in js
    assert "setBoleFeedbackFilter" in js
    assert "moveBoleFeedbackActionOrder" in js
    assert ".bole-feedback-tools" in css
    assert ".bole-feedback-action-order" in css
    lucide_rule = css[css.index(".lucide-icon {") : css.index(".feedback-caret", css.index(".lucide-icon {"))]
    assert "overflow: visible;" in lucide_rule
    mobile_css = css[css.index("@media (max-width: 760px)") :]
    assert ".bole-feedback-tools" in mobile_css
    assert ".bole-feedback-panel" in mobile_css


def test_bole_feedback_positive_thumb_icons_have_svg_padding_against_clipping():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    reader = html[html.index('id="readerFeedbackPopover"') : html.index('data-bole-feedback-action="less_relevant"')]
    feedback_render = js[js.index("function renderBoleFeedbackList()") : js.index("function syncBoleFeedbackFilterControls()")]

    padded_thumb_svg = 'class="lucide-icon feedback-thumb-icon" viewBox="-1 -1 26 26"'
    assert padded_thumb_svg in reader
    assert padded_thumb_svg in feedback_render
    assert ".bole-feedback-row .mark .feedback-thumb-icon" in css
    assert ".feedback-option .mark .feedback-thumb-icon" in css


def test_bole_feedback_history_filtering_sorting_and_target_inference_ignores_url_noise():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function scorePercent", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + js.slice(start, end)
          + "\\nstate.boleFeedbackItems = feedback.map(recordBoleSessionFeedback);"
          + "\\nconst display = state.boleFeedbackItems.map((item) => ({{ action: item.action, target: boleFeedbackTargetLabel(item), time: formatBoleFeedbackTime(item.created_at) }}));"
          + "\\nconst topicOptions = boleFeedbackTopicOptions();"
          + "\\nstate.boleFeedbackFilters.query = 'code';"
          + "\\nconst searchTitles = boleFeedbackVisibleItems().map((item) => item.item.title);"
          + "\\nstate.boleFeedbackFilters.query = '';"
          + "\\nstate.boleFeedbackFilters.topic = 'Agent';"
          + "\\nconst topicTargets = boleFeedbackVisibleItems().map(boleFeedbackTargetLabel);"
          + "\\nstate.boleFeedbackFilters.topic = '';"
          + "\\nstate.boleFeedbackFilters.action = 'not_interested';"
          + "\\nconst actionLabels = boleFeedbackVisibleItems().map((item) => item.action);"
          + "\\nstate.boleFeedbackFilters.action = '';"
          + "\\nstate.boleFeedbackFilters.sort = 'topic';"
          + "\\nconst topicOrder = boleFeedbackVisibleItems().map(boleFeedbackTargetLabel);"
          + "\\nstate.boleFeedbackFilters.sort = 'action';"
          + "\\nstate.boleFeedbackFilters.actionOrder = ['not_interested', 'more_like_this', 'less_relevant'];"
          + "\\nconst actionOrder = boleFeedbackVisibleItems().map((item) => item.action);"
          + "\\nresult = {{ display, topicOptions, searchTitles, topicTargets, actionLabels, topicOrder, actionOrder }};";
        const feedback = [
          {{
            action: "less_relevant",
            created_at: "2026-06-23T12:00:00Z",
            item: {{
              id: "agent-runtime",
              title: "Agent runtime reaches production teams",
              summary: "Tool-use controls for agents",
              site_name: "OpenAI Developers",
              source: "Official",
              ai_signals: ["Agent", "官方更新"]
            }}
          }},
          {{
            action: "more_like_this",
            created_at: "2026-06-23T11:00:00Z",
            item: {{
              id: "code-ai",
              title: "Code AI benchmark tracks repository edits",
              summary: "Evaluation for coding agents",
              site_name: "GitHub",
              source: "Trending",
              ai_signals: ["Code AI"]
            }}
          }},
          {{
            action: "not_interested",
            created_at: "2026-06-23T10:00:00Z",
            item: {{
              id: "funding",
              title: "AI startup funding roundup",
              summary: "Late-stage financing news",
              site_name: "Business Wire",
              source: "Newswire",
              ai_signals: ["融资"]
            }}
          }},
          {{
            action: "less_relevant",
            created_at: "2026-06-23T09:00:00Z",
            item: {{
              id: "insurance",
              title: "Insurance market update",
              summary: "Agency channel news",
              site_name: "Business Wire",
              source: "Newswire",
              url: "https://example.com/agent-ai-launch?topic=agent"
            }}
          }}
        ];
        const sandbox = {{
          feedback,
          state: {{
            boleFeedbackItems: [],
            boleFeedbackByKey: new Map(),
            boleFeedbackUndoTombstones: new Set(),
            boleFeedbackFilters: {{
              query: "",
              topic: "",
              action: "",
              sort: "time",
              actionOrder: ["more_like_this", "less_relevant", "not_interested"]
            }}
          }},
          result: null
        }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        const result = sandbox.result;
        const agent = result.display.find((item) => item.action === "less_relevant" && item.target === "Agent");
    if (!agent || !agent.time.includes("06-23") || !agent.time.includes(":")) {{
      throw new Error(`expected target and time in display data: ${{JSON.stringify(result.display)}}`);
    }}
        const urlNoise = result.display.find((item) => item.action === "less_relevant" && item.target !== "Agent");
    if (!urlNoise || urlNoise.target !== "整条新闻") {{
      throw new Error(`URL path must not infer Agent target: ${{JSON.stringify(result.display)}}`);
    }}
    if (result.topicOptions.includes("这条新闻") || result.topicOptions.includes("整条新闻")) {{
      throw new Error(`generic item scope must not appear as a topic filter: ${{JSON.stringify(result.topicOptions)}}`);
    }}
        if (result.searchTitles.length !== 1 || !result.searchTitles[0].includes("Code AI")) {{
          throw new Error(`search failed: ${{JSON.stringify(result.searchTitles)}}`);
        }}
        if (result.topicTargets.length !== 1 || result.topicTargets[0] !== "Agent") {{
          throw new Error(`topic filter failed: ${{JSON.stringify(result.topicTargets)}}`);
        }}
        if (result.actionLabels.length !== 1 || result.actionLabels[0] !== "not_interested") {{
          throw new Error(`action filter failed: ${{JSON.stringify(result.actionLabels)}}`);
        }}
        if (result.topicOrder.slice(0, 3).join("|") !== "Agent|Code AI|融资") {{
          throw new Error(`topic sort should use pinyin/latin initials: ${{JSON.stringify(result.topicOrder)}}`);
        }}
        if (result.actionOrder[0] !== "not_interested") {{
          throw new Error(`custom action sort failed: ${{JSON.stringify(result.actionOrder)}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_feedback_target_uses_ai_entity_for_curated_hotlist_items():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function uniqueBolePickStrings", start);
        const code = "const state = {{ boleFeedbackByKey: new Map(), boleFeedbackUndoTombstones: new Set() }};\\n"
          + js.slice(start, end)
          + "\\nresult = boleFeedbackTargetLabel({{ action: 'more_like_this', item }});";
        const item = {{
          id: "zeli-openai-movie",
          title: "Amazon drops Sam Altman movie after announcing OpenAI partnership",
          title_en: "Amazon drops Sam Altman movie after announcing OpenAI partnership",
          title_zh: "亚马逊在宣布与OpenAI合作后，撤下萨姆·阿尔特曼的传记电影",
          summary: "",
          site_name: "Zeli",
          source: "Hacker News · 24h最热",
          ai_label: "curated_hotlist",
          ai_signals: ["zeli_24h_hot"],
          url: "https://example.com/path/agent-noise"
        }};
        const sandbox = {{ item, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result !== "OpenAI") {{
          throw new Error(`expected OpenAI target, got ${{sandbox.result}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_feedback_payload_keeps_primary_target_and_matched_targets():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function scorePercent", start);
        const code = "const state = {{ boleFeedbackByKey: new Map(), boleFeedbackUndoTombstones: new Set() }};\\n"
          + js.slice(start, end)
          + "\\nconst payload = feedbackPayloadForItem('more_like_this', item);"
          + "\\nconst searchable = boleFeedbackSearchText({{ action: 'more_like_this', item: {{ title: 'OpenAI partnership update', feedback_target: payload.item.feedback_target, matched_targets: payload.item.matched_targets }} }});"
          + "\\nresult = {{ target: payload.item.feedback_target, matched: payload.item.matched_targets, searchable }};";
        const item = {{
          id: "zeli-openai-movie",
          title: "Amazon drops Sam Altman movie after announcing OpenAI partnership",
          title_en: "Amazon drops Sam Altman movie after announcing OpenAI partnership",
          title_zh: "亚马逊在宣布与OpenAI合作后，撤下萨姆·阿尔特曼的传记电影",
          summary: "",
          site_name: "Zeli",
          source: "Hacker News · 24h最热",
          ai_label: "curated_hotlist",
          ai_signals: ["zeli_24h_hot"],
          url: "https://example.com/path/agent-noise"
        }};
        const sandbox = {{ item, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result.target !== "OpenAI") {{
          throw new Error(`expected primary target OpenAI, got ${{JSON.stringify(sandbox.result)}}`);
        }}
        const joined = (sandbox.result.matched || []).join("|");
        if (joined !== "OpenAI|Amazon") {{
          throw new Error(`expected multi-target context without URL noise, got ${{JSON.stringify(sandbox.result)}}`);
        }}
        if (!sandbox.result.searchable.includes("amazon")) {{
          throw new Error(`secondary target should be searchable: ${{JSON.stringify(sandbox.result)}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_bole_events_merge_same_english_title_despite_chinese_translation_variants_and_keep_target():
    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");
        const js = fs.readFileSync({str(ROOT / "assets/app.js")!r}, "utf8");
        const start = js.indexOf("function itemTitleText");
        const end = js.indexOf("function buildBoleLead", start);
        const code = "function fmtTime() {{ return ''; }}\\n"
          + "const state = {{ generatedAt: '2026-06-20T13:56:43Z', personalizationStatus: null, boleFeedbackByKey: new Map(), boleFeedbackUndoTombstones: new Set() }};\\n"
          + "const BOLE_PICK_LIMIT = 10;\\n"
          + js.slice(start, end)
          + "\\nconst picks = pickBoleItems(items);"
          + "\\nresult = picks.map((row) => ({{ title: row.item.title, mergedCount: row.mergedCount, target: boleFeedbackTargetLabel({{ action: 'more_like_this', item: row.item }}), payloadTarget: feedbackPayloadForItem('more_like_this', row.item).item.feedback_target, signals: row.sourceSignals }}));";
        const englishTitle = "Amazon drops Sam Altman movie after announcing OpenAI partnership";
        const items = [
          {{
            id: "newsnow-openai-movie",
            site_id: "newsnow",
            site_name: "NewsNow",
            source: "hackernews",
            title: englishTitle,
            title_original: englishTitle,
            title_en: englishTitle,
            title_zh: "亚马逊在宣布与 OpenAI 合作后放弃了山姆·奥特曼电影",
            published_at: "2026-06-19T21:40:15Z",
            priority_score: 0.71,
            ai_label: "ai_product_update",
            ai_signals: ["openai"]
          }},
          {{
            id: "zeli-openai-movie",
            site_id: "zeli",
            site_name: "Zeli",
            source: "Hacker News · 24h最热",
            title: englishTitle,
            title_original: englishTitle,
            title_en: englishTitle,
            title_zh: "亚马逊在宣布与OpenAI合作后，撤下萨姆·阿尔特曼的传记电影",
            published_at: "2026-06-19T20:03:16Z",
            priority_score: 0.71,
            ai_label: "curated_hotlist",
            ai_signals: ["zeli_24h_hot"]
          }}
        ];
        const sandbox = {{ items, result: null }};
        vm.createContext(sandbox);
        vm.runInContext(code, sandbox);
        if (sandbox.result.length !== 1) {{
          throw new Error(`expected one merged event, got ${{JSON.stringify(sandbox.result)}}`);
        }}
        if (sandbox.result[0].mergedCount !== 2 || sandbox.result[0].target !== "OpenAI" || sandbox.result[0].payloadTarget !== "OpenAI") {{
          throw new Error(`expected merged OpenAI target, got ${{JSON.stringify(sandbox.result)}}`);
        }}
        """
    )

    subprocess.run(["node", "-e", script], check=True, cwd=ROOT)


def test_deep_verify_preserves_item_metadata_in_verification_payload():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "const verifiedItem = { ...item, ...result }" in js
    assert "items: [verifiedItem" in js
