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
    assert "./assets/styles.css?v=personalized-bole-dialogue-0620" in html
    assert "./assets/config.js?v=info-arch-0602" in html
    assert "./assets/api-client.js?v=frontend-arch-0610" in html
    assert "./assets/app.js?v=personalized-bole-dialogue-0620" in html


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
    assert "transition: transform 360ms cubic-bezier(0.2, 0.8, 0.2, 1);" in css


def test_bole_interest_and_reading_questions_are_separate_with_single_ai_input():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    workbench = html[html.index('id="boleWorkbench"') : html.index('id="readerSheet"')]

    assert workbench.count("data-bole-chat-input") == 1
    assert "data-bole-free-text" not in workbench
    assert "<textarea" not in workbench
    assert "const BOLE_PROFILE_QUESTIONS" in js
    question_bank = js[js.index("const BOLE_PROFILE_QUESTIONS") : js.index("function parseBoleTerms")]

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
    assert "boleAdvanceTimer" in js
    assert "loadPersonalization" in js
    assert "openBoleWorkbench" in js
    assert "closeBoleWorkbench" in js
    assert "setBoleStage" in js
    assert "renderBoleConversation" in js
    assert "renderBoleRecognizedProfile" in js
    assert "scheduleBoleAdvance" in js
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
            boleAdvanceTimer: null,
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
        if (sandbox.result.visible.join("|") !== "attention_goal|ai_domains|negative_preferences") {{
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
            boleAdvanceTimer: null,
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

    turn_rule = css[css.index(".bole-turn {") : css.index(".bole-turn.answered")]
    profile_rule = css[css.index(".bole-profile-card {") : css.index(".bole-profile-card.avoid")]
    assert "animation:" not in turn_rule
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


def test_bole_picks_explain_selection_criteria():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "为什么精选" in html
    assert "bole-explainer" in js
    assert "多源命中" in js
    assert "官方源" in js
    assert "AI 分" in js


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
    assert "loginAdmin" in js
    assert "saveSettings" in js
    assert "ask_system_prompt" in js


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


def test_deep_verify_preserves_item_metadata_in_verification_payload():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "const verifiedItem = { ...item, ...result }" in js
    assert "items: [verifiedItem" in js
