const appConfig = window.AI_NEWS_RADAR_CONFIG || {};
const apiBaseUrl = String(appConfig.apiBaseUrl || "").replace(/\/$/, "");

function createFallbackApiClient() {
  async function apiFetch(path, options = {}) {
    if (!apiBaseUrl) throw new Error("AI 后端未配置");
    let res;
    try {
      res = await fetch(`${apiBaseUrl}${path}`, {
        ...options,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
      });
    } catch (err) {
      throw new Error("无法连接 AI 后端，请刷新页面或检查后端 tunnel 是否在线。");
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `API 请求失败: ${res.status}`);
    }
    return res.json();
  }

  async function fetchFreshJson(url, errorLabel) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${errorLabel}: ${res.status}`);
    return res.json();
  }

  return {
    apiFetch,
    fetchFreshJson,
  };
}

const { apiFetch, fetchFreshJson } = window.AI_NEWS_RADAR_API || createFallbackApiClient();

const READER_SUMMARY_PROMPT = `请用中文总结这篇文章：
1. 核心信息
2. 对 AI/科技行业的影响
3. 需要注意的不确定点
4. 如果正文信息不足，请明确说明`;

const READER_FACT_CHECK_PROMPT = `请对这篇文章做基于当前雷达上下文的事实交叉核验：
1. 提取关键事实主张
2. 判断哪些主张能从当前文章或相关新闻上下文得到支持
3. 标记无法确认、可能夸大、来源不清、时间不清的问题
4. 不要编造证据；证据不足时明确说证据不足
5. 最后给出可信度：高/中/低，并说明原因`;

const SOURCE_PREF_STORAGE_KEY = "aiNewsRadar.sourcePrefs.v1";
const SOURCE_GROUP_PREVIEW_COUNT = 2;
const SOURCE_ITEM_PREVIEW_COUNT = 3;
const BOLE_PICK_LIMIT = 10;

function emptySourcePrefs() {
  return {
    siteOrder: [],
    hiddenSites: [],
    sourceOrderBySite: {},
    hiddenSourcesBySite: {},
  };
}

function uniqueStrings(values) {
  return Array.from(new Set((Array.isArray(values) ? values : []).map((value) => String(value || "").trim()).filter(Boolean)));
}

function sanitizeSourcePrefs(raw) {
  const defaults = emptySourcePrefs();
  const prefs = raw && typeof raw === "object" ? raw : {};
  const sourceOrderBySite = {};
  const hiddenSourcesBySite = {};
  Object.entries(prefs.sourceOrderBySite || {}).forEach(([siteId, sources]) => {
    sourceOrderBySite[String(siteId)] = uniqueStrings(sources);
  });
  Object.entries(prefs.hiddenSourcesBySite || {}).forEach(([siteId, sources]) => {
    hiddenSourcesBySite[String(siteId)] = uniqueStrings(sources);
  });
  return {
    ...defaults,
    siteOrder: uniqueStrings(prefs.siteOrder),
    hiddenSites: uniqueStrings(prefs.hiddenSites),
    sourceOrderBySite,
    hiddenSourcesBySite,
  };
}

function loadSourcePrefs() {
  try {
    if (!window.localStorage) return emptySourcePrefs();
    const raw = window.localStorage.getItem(SOURCE_PREF_STORAGE_KEY);
    if (!raw) return emptySourcePrefs();
    return sanitizeSourcePrefs(JSON.parse(raw));
  } catch (_) {
    return emptySourcePrefs();
  }
}

function saveSourcePrefs() {
  state.sourcePrefs = sanitizeSourcePrefs(state.sourcePrefs);
  try {
    if (window.localStorage) window.localStorage.setItem(SOURCE_PREF_STORAGE_KEY, JSON.stringify(state.sourcePrefs));
  } catch (_) {
    // Local preferences are best-effort only.
  }
}

const state = {
  itemsAi: [],
  itemsAll: [],
  itemsAllRaw: [],
  statsAi: [],
  totalAi: 0,
  totalRaw: 0,
  totalAllMode: 0,
  allDedup: true,
  allDataLoaded: false,
  allDataUrl: "data/latest-24h-all.json",
  allDataPromise: null,
  siteFilter: "",
  query: "",
  mode: "ai",
  waytoagiMode: "today",
  mobileView: "today",
  categoryFilter: "",
  expandedSites: new Set(),
  expandedSourceGroups: new Set(),
  sourceSortExpandedSites: new Set(),
  sourceSortSelection: new Set(),
  sourcePointerDrag: null,
  sourcePrefs: loadSourcePrefs(),
  taxonomy: [],
  verificationPayload: null,
  askContext: {},
  askQuote: "",
  askStreamingEnabled: false,
  activeConversationId: null,
  askHistoryLoaded: false,
  askHistoryVisible: false,
  readerItem: null,
  readerArticle: null,
  readerArticleKey: "",
  readerArticleCache: new Map(),
  readerArticleRequests: new Map(),
  readerOriginalHtml: "",
  readerOriginalText: "",
  readerTranslatedHtml: "",
  readerShowingTranslation: false,
  aiProfiles: [],
  personalizationStatus: null,
  personalizationUnavailable: false,
  boleConflictStrategy: "ask",
  aiConfigSkipped: false,
  aiConfigProfileId: "",
  boleSortMode: "score",
  boleFeedbackItems: [],
  boleFeedbackByKey: new Map(),
  boleFeedbackUndoTombstones: new Set(),
  boleFeedbackFilters: {
    query: "",
    topic: "",
    action: "",
    sort: "time",
    actionOrder: ["more_like_this", "less_relevant", "not_interested"],
  },
  boleTuneItem: null,
  bolePendingDraftSuggestion: null,
  bolePendingProfileConflict: null,
  boleDraftPreview: null,
  boleStage: "calibration",
  boleAnswers: {},
  boleShownQuestionIds: new Set(["attention_goal"]),
  boleConfirmedQuestionIds: new Set(),
  boleAnswerInterpretations: {},
  boleActiveQuestionId: "attention_goal",
  boleQuestionTransitionTimer: null,
  boleTransitionStage: "",
  boleEnteringQuestionId: "",
  translationProviderMode: "browser",
  translationProviderId: "",
  readingAssistantProviderId: "env",
  waytoagiData: null,
  sourceStatus: null,
  generatedAt: null,
};

const statsEl = document.getElementById("stats");
const siteSelectEl = document.getElementById("siteSelect");
const sitePillsEl = document.getElementById("sitePills");
const newsListEl = document.getElementById("newsList");
const updatedAtEl = document.getElementById("updatedAt");
const searchInputEl = document.getElementById("searchInput");
const resultCountEl = document.getElementById("resultCount");
const listTitleEl = document.getElementById("listTitle");
const itemTpl = document.getElementById("itemTpl");
const modeAiBtnEl = document.getElementById("modeAiBtn");
const modeAllBtnEl = document.getElementById("modeAllBtn");
const modeHintEl = document.getElementById("modeHint");
const allDedupeWrapEl = document.getElementById("allDedupeWrap");
const allDedupeToggleEl = document.getElementById("allDedupeToggle");
const allDedupeLabelEl = document.getElementById("allDedupeLabel");
const advancedSummaryEl = document.getElementById("advancedSummary");
const sourceHealthEl = document.getElementById("sourceHealth");
const dataDrawerButtonEl = document.getElementById("dataDrawerButton");
const dataDrawerEl = document.getElementById("dataDrawer");
const dataDrawerCloseEl = document.getElementById("dataDrawerClose");
const dataDrawerMetaEl = document.getElementById("dataDrawerMeta");

const waytoagiUpdatedAtEl = document.getElementById("waytoagiUpdatedAt");
const waytoagiMetaEl = document.getElementById("waytoagiMeta");
const waytoagiListEl = document.getElementById("waytoagiList");
const waytoagiTodayBtnEl = document.getElementById("waytoagiTodayBtn");
const waytoagi7dBtnEl = document.getElementById("waytoagi7dBtn");
const coverageStripEl = document.getElementById("coverageStrip");
const bolePicksListEl = document.getElementById("bolePicksList");
const bolePicksMetaEl = document.getElementById("bolePicksMeta");
const boleSortButtonEl = document.getElementById("boleSortButton");
const boleSortPopoverEl = document.getElementById("boleSortPopover");
const boleFeedbackButtonEl = document.getElementById("boleFeedbackButton");
const boleFeedbackDialogEl = document.getElementById("boleFeedbackDialog");
const boleFeedbackCloseEl = document.getElementById("boleFeedbackClose");
const boleFeedbackListEl = document.getElementById("boleFeedbackList");
const boleFeedbackCountEl = document.getElementById("boleFeedbackCount");
const boleFeedbackSearchEl = document.getElementById("boleFeedbackSearch");
const boleFeedbackTopicFilterEl = document.getElementById("boleFeedbackTopicFilter");
const boleFeedbackActionFilterEl = document.getElementById("boleFeedbackActionFilter");
const boleFeedbackSortSelectEl = document.getElementById("boleFeedbackSortSelect");
const boleFeedbackActionOrderEl = document.getElementById("boleFeedbackActionOrder");
const boleTunePopoverEl = document.getElementById("boleTunePopover");
const boleDraftSuggestionDialogEl = document.getElementById("boleDraftSuggestionDialog");
const boleDraftSuggestionBodyEl = document.getElementById("boleDraftSuggestionBody");
const boleDraftSuggestionCloseEl = document.getElementById("boleDraftSuggestionClose");
const boleDraftSuggestionDismissEl = document.getElementById("boleDraftSuggestionDismiss");
const boleDraftSuggestionSaveEl = document.getElementById("boleDraftSuggestionSave");
const boleProfileConflictDialogEl = document.getElementById("boleProfileConflictDialog");
const boleProfileConflictCloseEl = document.getElementById("boleProfileConflictClose");
const boleProfileConflictLabelEl = document.getElementById("boleProfileConflictLabel");
const boleProfileConflictPolicyEl = document.getElementById("boleProfileConflictPolicy");
const boleProfileConflictExistingTitleEl = document.getElementById("boleProfileConflictExistingTitle");
const boleProfileConflictExistingSourceEl = document.getElementById("boleProfileConflictExistingSource");
const boleProfileConflictIncomingTitleEl = document.getElementById("boleProfileConflictIncomingTitle");
const boleProfileConflictIncomingSourceEl = document.getElementById("boleProfileConflictIncomingSource");
const sourceSortButtonEl = document.getElementById("sourceSortButton");
const sourceHiddenButtonEl = document.getElementById("sourceHiddenButton");
const sourceHiddenCountEl = document.getElementById("sourceHiddenCount");
const sourceSortDialogEl = document.getElementById("sourceSortDialog");
const sourceSortListEl = document.getElementById("sourceSortList");
const sourceSortBlockButtonEl = document.getElementById("sourceSortBlockButton");
const sourceSortCloseEl = document.getElementById("sourceSortClose");
const sourceHiddenDialogEl = document.getElementById("sourceHiddenDialog");
const sourceHiddenListEl = document.getElementById("sourceHiddenList");
const sourceHiddenCloseEl = document.getElementById("sourceHiddenClose");
const askAiButtonEl = document.getElementById("askAiButton");
const desktopAskAiButtonEl = document.getElementById("desktopAskAiButton");
const desktopViewButtons = document.querySelectorAll(".desktop-view-btn");
const categoryMetaEl = document.getElementById("categoryMeta");
const categoryGridEl = document.getElementById("categoryGrid");
const categoryDetailEl = document.getElementById("categoryDetail");
const verificationMetaEl = document.getElementById("verificationMeta");
const verificationSummaryEl = document.getElementById("verificationSummary");
const verificationListEl = document.getElementById("verificationList");
const askAiSheetEl = document.getElementById("askAiSheet");
const askAiPanelEl = askAiSheetEl?.querySelector(".ask-ai-panel");
const askAiCloseEl = document.getElementById("askAiClose");
const askAiContextEl = document.getElementById("askAiContext");
const askAiMessagesButtonEl = document.getElementById("askAiMessagesButton");
const askAiHistoryButtonEl = document.getElementById("askAiHistoryButton");
const askAiHistoryListEl = document.getElementById("askAiHistoryList");
const askAiInputEl = document.getElementById("askAiInput");
const askAiSubmitEl = document.getElementById("askAiSubmit");
const askAiAnswerEl = document.getElementById("askAiAnswer");
const askAiQuoteBarEl = document.getElementById("askAiQuoteBar");
const settingsStatusEl = document.getElementById("settingsStatus");
const adminPasswordInputEl = document.getElementById("adminPasswordInput");
const loginButtonEl = document.getElementById("loginButton");
const deepVerificationToggleEl = document.getElementById("deepVerificationToggle");
const deepVerificationTopNEl = document.getElementById("deepVerificationTopN");
const askStreamingToggleEl = document.getElementById("askStreamingToggle");
const askSystemPromptInputEl = document.getElementById("askSystemPromptInput");
const saveSettingsButtonEl = document.getElementById("saveSettingsButton");
const boleConflictStrategySelectEl = document.getElementById("boleConflictStrategySelect");
const aiProfilesMetaEl = document.getElementById("aiProfilesMeta");
const aiProfilesListEl = document.getElementById("aiProfilesList");
const aiProfileIdInputEl = document.getElementById("aiProfileIdInput");
const aiProfileNameInputEl = document.getElementById("aiProfileNameInput");
const aiProfileTypeSelectEl = document.getElementById("aiProfileTypeSelect");
const aiProfileBaseUrlInputEl = document.getElementById("aiProfileBaseUrlInput");
const aiProfileModelInputEl = document.getElementById("aiProfileModelInput");
const aiProfileApiKeyInputEl = document.getElementById("aiProfileApiKeyInput");
const aiProfileHeadersInputEl = document.getElementById("aiProfileHeadersInput");
const aiProfileTimeoutInputEl = document.getElementById("aiProfileTimeoutInput");
const saveAiProfileButtonEl = document.getElementById("saveAiProfileButton");
const testAiProfileButtonEl = document.getElementById("testAiProfileButton");
const resetAiProfileFormButtonEl = document.getElementById("resetAiProfileFormButton");
const aiConfigDialogEl = document.getElementById("aiConfigDialog");
const aiConfigPanelEl = aiConfigDialogEl?.querySelector(".ai-config-panel");
const aiConfigHeadStatusEl = document.getElementById("aiConfigHeadStatus");
const aiConfigNameInputEl = document.getElementById("aiConfigNameInput");
const aiConfigTypeSelectEl = document.getElementById("aiConfigTypeSelect");
const aiConfigBaseUrlInputEl = document.getElementById("aiConfigBaseUrlInput");
const aiConfigModelInputEl = document.getElementById("aiConfigModelInput");
const aiConfigApiKeyInputEl = document.getElementById("aiConfigApiKeyInput");
const aiConfigAdvancedToggleEl = document.getElementById("aiConfigAdvancedToggle");
const aiConfigAdvancedStateEl = document.getElementById("aiConfigAdvancedState");
const aiConfigAdvancedPanelEl = document.getElementById("aiConfigAdvancedPanel");
const aiConfigHeadersInputEl = document.getElementById("aiConfigHeadersInput");
const aiConfigTimeoutInputEl = document.getElementById("aiConfigTimeoutInput");
const aiConfigSkipButtonEl = document.getElementById("aiConfigSkipButton");
const aiConfigStatusEl = document.getElementById("aiConfigStatus");
const aiConfigTestButtonEl = document.getElementById("aiConfigTestButton");
const aiConfigSaveButtonEl = document.getElementById("aiConfigSaveButton");
const boleWorkbenchOpenEl = document.getElementById("boleWorkbenchOpen");
const boleSettingsOpenEl = document.getElementById("boleSettingsOpen");
const boleSettingsStatusEl = document.getElementById("boleSettingsStatus");
const boleDisableButtonEl = document.getElementById("boleDisableButton");
const boleResetButtonEl = document.getElementById("boleResetButton");
const boleWorkbenchEl = document.getElementById("boleWorkbench");
const boleWorkbenchCloseEl = document.getElementById("boleWorkbenchClose");
const boleStageTrackEl = document.getElementById("boleStageTrack");
const boleStagePanels = Array.from(document.querySelectorAll("[data-bole-stage-panel]"));
const boleStageButtons = Array.from(document.querySelectorAll("[data-bole-stage]"));
const boleDialogueTurnsEl = document.getElementById("boleDialogueTurns");
const boleReadingTurnsEl = document.getElementById("boleReadingTurns");
const boleQuestionDotGroups = Array.from(document.querySelectorAll("[data-bole-question-dots]"));
const boleChatFormEl = document.getElementById("boleChatForm");
const boleChatInputEl = document.getElementById("boleChatInput");
const boleChatSendEl = document.getElementById("boleChatSend");
const boleRecognizedProfileEl = document.getElementById("boleRecognizedProfile");
const boleProfileRailTitleEl = document.getElementById("boleProfileRailTitle");
const boleProfileRailHintEl = document.getElementById("boleProfileRailHint");
const bolePreferenceButtons = Array.from(document.querySelectorAll("[data-bole-preference]"));
const boleContinueButtonEl = document.getElementById("boleContinueButton");
const boleDraftButtonEl = document.getElementById("boleDraftButton");
const boleDraftPreviewEl = document.getElementById("boleDraftPreview");
const boleRecommendationPreviewEl = document.getElementById("boleRecommendationPreview");
const boleConfirmButtonEl = document.getElementById("boleConfirmButton");
const boleSkipButtonEl = document.getElementById("boleSkipButton");
const boleWorkbenchStatusEl = document.getElementById("boleWorkbenchStatus");
const translationProviderModeSelectEl = document.getElementById("translationProviderModeSelect");
const translationProviderSelectEl = document.getElementById("translationProviderSelect");
const readingAssistantProviderSelectEl = document.getElementById("readingAssistantProviderSelect");
const readerSheetEl = document.getElementById("readerSheet");
const readerPanelEl = readerSheetEl?.querySelector(".reader-panel");
const readerCloseEl = document.getElementById("readerClose");
const readerTitleEl = document.getElementById("readerTitle");
const readerSourceEl = document.getElementById("readerSource");
const readerBodyEl = document.getElementById("readerBody");
const readerOriginalLinkEl = document.getElementById("readerOriginalLink");
const readerAskButtonEl = document.getElementById("readerAskButton");
const readerTranslateButtonEl = document.getElementById("readerTranslateButton");
const readerSummaryButtonEl = document.getElementById("readerSummaryButton");
const readerFactCheckButtonEl = document.getElementById("readerFactCheckButton");
const readerFeedbackTriggerEl = document.getElementById("readerFeedbackTrigger");
const readerFeedbackPopoverEl = document.getElementById("readerFeedbackPopover");
const readerAccessBadgeEl = document.getElementById("readerAccessBadge");
const ASK_DRAG_ACTIVATION_PX = 8;
const ASK_DRAG_CLOSE_THRESHOLD = 132;
const READER_DRAG_ACTIVATION_PX = 8;
const READER_DRAG_CLOSE_THRESHOLD = 128;
let askDragState = null;
let readerDragState = null;
let askCloseTimer = null;
let readerCloseTimer = null;

const SOURCE_KINDS = {
  official_ai: { label: "官方", tone: "official" },
  aibreakfast: { label: "日报", tone: "newsletter" },
  followbuilders: { label: "Builders/X", tone: "builders" },
  xapi: { label: "X API", tone: "builders" },
  techurls: { label: "聚合", tone: "aggregate" },
  buzzing: { label: "聚合", tone: "aggregate" },
  iris: { label: "聚合", tone: "aggregate" },
  bestblogs: { label: "博客", tone: "blogs" },
  tophub: { label: "聚合", tone: "aggregate" },
  zeli: { label: "聚合", tone: "aggregate" },
  aihubtoday: { label: "AI站点", tone: "aihub" },
  aibase: { label: "AI站点", tone: "aihub" },
  newsnow: { label: "聚合", tone: "aggregate" },
};

const fallbackTaxonomy = [
  {
    id: "models-products",
    label: "模型与产品",
    children: [
      { id: "models-products/model-release", label: "模型发布" },
      { id: "models-products/product-features", label: "产品功能" },
      { id: "models-products/api-platform", label: "API / 平台更新" },
      { id: "models-products/multimodal", label: "多模态能力" },
      { id: "models-products/pricing-access", label: "价格 / 访问权限" },
      { id: "models-products/safety-policy", label: "安全 / 策略更新" },
    ],
  },
  {
    id: "agents-workflows",
    label: "Agent 与工作流",
    children: [
      { id: "agents-workflows/agent-frameworks", label: "Agent 框架" },
      { id: "agents-workflows/tool-calling", label: "工具调用 / Function Calling" },
      { id: "agents-workflows/mcp-plugins", label: "MCP / 插件生态" },
      { id: "agents-workflows/browser-computer-control", label: "浏览器 / 电脑控制" },
      { id: "agents-workflows/multi-agent", label: "多 Agent 协作" },
      { id: "agents-workflows/automation", label: "自动化工作流" },
    ],
  },
  {
    id: "developer-tools",
    label: "开发者工具",
    children: [
      { id: "developer-tools/ide-coding-assistants", label: "IDE / 编程助手" },
      { id: "developer-tools/sdk-api-tools", label: "SDK / API 工具" },
      { id: "developer-tools/rag-data-tools", label: "RAG / 数据工具" },
      { id: "developer-tools/deploy-ops", label: "部署 / 运维" },
      { id: "developer-tools/eval-monitoring", label: "评测 / 监控" },
      { id: "developer-tools/security-permissions", label: "安全 / 权限" },
    ],
  },
  {
    id: "open-source-projects",
    label: "开源与项目",
    children: [
      { id: "open-source-projects/open-models", label: "开源模型" },
      { id: "open-source-projects/open-tools", label: "开源工具" },
      { id: "open-source-projects/github-projects", label: "GitHub 项目" },
      { id: "open-source-projects/frameworks-libraries", label: "框架 / 库" },
      { id: "open-source-projects/datasets", label: "数据集" },
      { id: "open-source-projects/demos-apps", label: "Demo / 应用样例" },
    ],
  },
  {
    id: "research-evaluation",
    label: "研究与评测",
    children: [
      { id: "research-evaluation/papers", label: "论文" },
      { id: "research-evaluation/benchmarks", label: "Benchmark" },
      { id: "research-evaluation/model-evaluation", label: "模型评测" },
      { id: "research-evaluation/technical-reports", label: "技术报告" },
      { id: "research-evaluation/alignment-safety", label: "对齐 / 安全研究" },
      { id: "research-evaluation/robotics-embodied-ai", label: "机器人 / 具身智能" },
    ],
  },
  {
    id: "company-industry",
    label: "公司与行业",
    children: [
      { id: "company-industry/funding-acquisitions", label: "融资 / 收购" },
      { id: "company-industry/partnership-ecosystem", label: "合作 / 生态" },
      { id: "company-industry/commercialization", label: "商业化" },
      { id: "company-industry/regulation-policy", label: "监管 / 政策" },
      { id: "company-industry/org-talent", label: "组织 / 人才" },
      { id: "company-industry/market-adoption", label: "市场采用" },
    ],
  },
  {
    id: "compute-infrastructure",
    label: "算力与基础设施",
    children: [
      { id: "compute-infrastructure/gpu-chips", label: "GPU / 芯片" },
      { id: "compute-infrastructure/inference-services", label: "推理服务" },
      { id: "compute-infrastructure/training-infra", label: "训练基础设施" },
      { id: "compute-infrastructure/cloud-platforms", label: "云平台" },
      { id: "compute-infrastructure/data-center-energy", label: "数据中心 / 能源" },
      { id: "compute-infrastructure/local-edge-models", label: "本地模型 / 边缘设备" },
    ],
  },
];

const legacyCategoryMap = {
  ai_general: { top: "模型与产品", sub: "产品功能" },
  model_release: { top: "模型与产品", sub: "模型发布" },
  agent_workflow: { top: "Agent 与工作流", sub: "Agent 框架" },
  ai_product_update: { top: "模型与产品", sub: "产品功能" },
  developer_tool: { top: "开发者工具", sub: "SDK / API 工具" },
  developer_tooling: { top: "开发者工具", sub: "SDK / API 工具" },
  infrastructure: { top: "算力与基础设施", sub: "推理服务" },
  ai_tech: { top: "研究与评测", sub: "技术报告" },
};

function fmtNumber(n) {
  return new Intl.NumberFormat("zh-CN").format(n || 0);
}

function setMobileView(view) {
  state.mobileView = view;
  document.body.dataset.activeMobileView = view;
  document.querySelectorAll("[data-mobile-view]").forEach((el) => {
    el.hidden = el.dataset.mobileView !== view;
  });
  document.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  desktopViewButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
}

function currentAskScope() {
  const scope = { scope: state.mobileView || "today", ...state.askContext };
  if (state.mobileView === "categories" && state.categoryFilter) {
    scope.category = state.categoryFilter;
  }
  return scope;
}

function askScopeLabel(scope) {
  const labels = {
    today: "今日",
    categories: "分类",
    verification: "核验",
    settings: "设置",
  };
  return labels[scope] || "今日";
}

function askContextLabel(scope) {
  if (scope.item_title) return `新闻 · ${scope.item_title}`;
  if (scope.category) return `分类 · ${scope.category}`;
  return askScopeLabel(scope.scope);
}

function openAskAi(extraContext = {}) {
  if (!askAiSheetEl) return;
  if (askCloseTimer) window.clearTimeout(askCloseTimer);
  state.askContext = extraContext;
  state.activeConversationId = null;
  const scope = currentAskScope();
  if (askAiContextEl) askAiContextEl.textContent = askContextLabel(scope);
  if (askAiAnswerEl) {
    askAiAnswerEl.innerHTML = "";
    askAiAnswerEl.hidden = false;
    if (!apiBaseUrl) askAiAnswerEl.textContent = "AI 后端未配置。";
  }
  setAskPanelView("messages");
  askAiSheetEl.classList.add("empty-thread");
  askAiSheetEl.classList.remove("open");
  askAiSheetEl.hidden = false;
  resetAskPanelDrag();
  document.body.classList.add("ask-ai-open");
  window.requestAnimationFrame(() => askAiSheetEl.classList.add("open"));
  if (askAiInputEl) askAiInputEl.focus();
}

function finishCloseAskAi() {
  if (!askAiSheetEl) return;
  resetAskPanelDrag();
  askAiSheetEl.classList.remove("open", "empty-thread");
  askAiSheetEl.hidden = true;
  document.body.classList.remove("ask-ai-open");
}

function closeAskAi() {
  if (!askAiSheetEl) return;
  if (askCloseTimer) window.clearTimeout(askCloseTimer);
  if (askAiSheetEl.hidden || !askAiPanelEl) {
    finishCloseAskAi();
    return;
  }
  askAiPanelEl.classList.remove("dragging");
  askAiPanelEl.classList.add("settling");
  askAiPanelEl.style.setProperty("--ask-drag-y", "100vh");
  askAiSheetEl.style.setProperty("--ask-backdrop-opacity", "0");
  askAiSheetEl.classList.remove("open");
  document.body.classList.remove("ask-ai-open");
  askCloseTimer = window.setTimeout(finishCloseAskAi, 220);
}

function resetAskPanelDrag() {
  askDragState = null;
  if (!askAiPanelEl) return;
  askAiPanelEl.classList.remove("dragging", "settling");
  askAiPanelEl.style.setProperty("--ask-drag-y", "0px");
  askAiSheetEl?.style.setProperty("--ask-backdrop-opacity", "1");
}

function canStartAskPanelDrag(event) {
  if (event.button !== undefined && event.button !== 0) return false;
  const blocked = event.target.closest?.(
    ".ask-ai-thread, .ask-ai-history-list, .ask-ai-composer, textarea, input, button, a, .ask-ai-message-actions"
  );
  return !blocked && Boolean(event.target.closest?.(".sheet-drag-zone, .ask-ai-panel"));
}

function handleAskPanelDragStart(event) {
  if (!askAiPanelEl || !canStartAskPanelDrag(event)) return;
  const scrollEl = event.target.closest?.(".ask-ai-thread, .ask-ai-history-list");
  askDragState = {
    pointerId: event.pointerId,
    startY: event.clientY,
    startScrollTop: scrollEl?.scrollTop || 0,
    currentY: 0,
    active: false,
  };
  askAiPanelEl.classList.remove("settling");
}

function handleAskPanelDragMove(event) {
  if (!askDragState || event.pointerId !== askDragState.pointerId || !askAiPanelEl) return;
  const delta = Math.max(0, event.clientY - askDragState.startY);
  if (!askDragState.active) {
    if (delta < ASK_DRAG_ACTIVATION_PX) return;
    askDragState.active = true;
    askAiPanelEl.setPointerCapture?.(event.pointerId);
    askAiPanelEl.classList.add("dragging");
  }
  askDragState.currentY = delta;
  askAiPanelEl.style.setProperty("--ask-drag-y", `${delta}px`);
  askAiSheetEl?.style.setProperty("--ask-backdrop-opacity", String(Math.max(0.28, 1 - delta / 420)));
  event.preventDefault();
}

function handleAskPanelDragEnd(event) {
  if (!askDragState || event.pointerId !== askDragState.pointerId || !askAiPanelEl) return;
  const shouldClose = askDragState.currentY >= ASK_DRAG_CLOSE_THRESHOLD;
  if (askDragState.active) askAiPanelEl.releasePointerCapture?.(event.pointerId);
  askAiPanelEl.classList.remove("dragging");
  askAiPanelEl.classList.add("settling");
  if (shouldClose) {
    closeAskAi();
    return;
  }
  askAiPanelEl.style.setProperty("--ask-drag-y", "0px");
  askAiSheetEl?.style.setProperty("--ask-backdrop-opacity", "1");
  askDragState = null;
}

function finishCloseReader() {
  if (!readerSheetEl) return;
  resetReaderPanelDrag();
  readerSheetEl.hidden = true;
  document.body.classList.remove("reader-open");
}

function resetReaderPanelDrag() {
  readerDragState = null;
  if (!readerPanelEl) return;
  readerPanelEl.classList.remove("dragging", "settling");
  readerPanelEl.style.setProperty("--reader-drag-y", "0px");
}

function canStartReaderPanelDrag(event) {
  if (event.button !== undefined && event.button !== 0) return false;
  if (event.target.closest?.("textarea, input, button, a")) return false;
  if (event.target.closest?.(".reader-article")) {
    return !readerBodyEl || readerBodyEl.scrollTop <= 0;
  }
  return true;
}

function handleReaderPanelDragStart(event) {
  if (!readerPanelEl || !canStartReaderPanelDrag(event)) return;
  const scrollEl = event.target.closest?.(".reader-article");
  readerDragState = {
    pointerId: event.pointerId,
    startY: event.clientY,
    startScrollTop: scrollEl?.scrollTop || 0,
    currentY: 0,
    active: false,
  };
  readerPanelEl.classList.remove("settling");
}

function handleReaderPanelDragMove(event) {
  if (!readerDragState || event.pointerId !== readerDragState.pointerId || !readerPanelEl) return;
  const delta = Math.max(0, event.clientY - readerDragState.startY);
  if (readerDragState.startScrollTop > 0) return;
  if (!readerDragState.active) {
    if (delta < READER_DRAG_ACTIVATION_PX) return;
    readerDragState.active = true;
    readerPanelEl.setPointerCapture?.(event.pointerId);
    readerPanelEl.classList.add("dragging");
  }
  readerDragState.currentY = delta;
  readerPanelEl.style.setProperty("--reader-drag-y", `${delta}px`);
  event.preventDefault();
}

function handleReaderPanelDragEnd(event) {
  if (!readerDragState || event.pointerId !== readerDragState.pointerId || !readerPanelEl) return;
  const shouldClose = readerDragState.currentY >= READER_DRAG_CLOSE_THRESHOLD;
  if (readerDragState.active) readerPanelEl.releasePointerCapture?.(event.pointerId);
  readerPanelEl.classList.remove("dragging");
  readerPanelEl.classList.add("settling");
  if (shouldClose) {
    closeReader();
    return;
  }
  readerPanelEl.style.setProperty("--reader-drag-y", "0px");
  readerDragState = null;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function renderMarkdown(text) {
  const blocks = [];
  const source = String(text || "");
  const parts = source.split(/```/);
  parts.forEach((part, index) => {
    if (index % 2 === 1) {
      const code = part.replace(/^[a-zA-Z0-9_-]+\n/, "");
      blocks.push(`<pre><code>${escapeHtml(code.trim())}</code></pre>`);
      return;
    }
    const lines = part.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    let listItems = [];
    let listType = "ul";
    const flushList = () => {
      if (!listItems.length) return;
      const itemsHtml = listItems.map((item) => {
        const marker = item.marker ? `<span class="md-list-number">${escapeHtml(item.marker)}</span>` : "";
        return `<li>${marker}<span>${renderInlineMarkdown(item.text)}</span></li>`;
      }).join("");
      blocks.push(`<${listType} class="ask-ai-md-list">${itemsHtml}</${listType}>`);
      listItems = [];
    };
    lines.forEach((line) => {
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      const bullet = line.match(/^[-*+]\s+(.+)$/);
      const ordered = line.match(/^(\d+[.)])\s+(.+)$/);
      if (heading) {
        flushList();
        const level = Math.min(heading[1].length, 3);
        blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      } else if (bullet || ordered) {
        const nextType = ordered ? "ol" : "ul";
        if (listItems.length && listType !== nextType) flushList();
        listType = nextType;
        listItems.push(ordered ? { marker: ordered[1], text: ordered[2] } : { marker: "•", text: bullet[1] });
      } else {
        flushList();
        blocks.push(`<p>${renderInlineMarkdown(line)}</p>`);
      }
    });
    flushList();
  });
  return blocks.join("") || "<p>没有返回答案。</p>";
}

function askHistoryRow(conversationId) {
  return Array.from(askAiHistoryListEl?.querySelectorAll(".ask-ai-history-item") || [])
    .find((row) => row.dataset.conversationId === conversationId) || null;
}

function askMessageId(row) {
  const value = Number(row?.dataset.messageId || 0);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function strTrim(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function askActionIcon(action) {
  const icons = {
    edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l10.5-10.5-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/></svg>',
    delete: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M7 7l1 13h8l1-13"/><path d="M9 7V4h6v3"/></svg>',
    regenerate: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.5 10A7 7 0 0 0 6.2 7.8"/><path d="M5.5 14a7 7 0 0 0 12.3 2.2"/></svg>',
    copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 8h10v12H8z"/><path d="M6 16H4V4h12v2"/></svg>',
    cancel: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12"/><path d="M18 6 6 18"/></svg>',
    save: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 13l4 4L19 7"/></svg>',
  };
  return `<span class="ask-ai-action-icon ask-ai-action-${action}">${icons[action] || ""}</span>`;
}

function messageActionButton(action, label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ask-ai-message-action";
  button.dataset.action = action;
  button.setAttribute("aria-label", label);
  button.title = label;
  button.innerHTML = askActionIcon(action);
  return button;
}

function appendAskMessageActions(row, role, text, options = {}) {
  if (!row || options.pending || !options.messageId) return;
  const actions = document.createElement("div");
  actions.className = "ask-ai-message-actions";
  if (role === "user") {
    actions.append(
      messageActionButton("edit", "编辑"),
      messageActionButton("delete", "删除"),
    );
  } else {
    actions.append(
      messageActionButton("regenerate", "重新生成"),
      messageActionButton("copy", "复制"),
      messageActionButton("delete", "删除"),
    );
  }
  actions.addEventListener("click", (event) => {
    const button = event.target.closest(".ask-ai-message-action");
    if (!button) return;
    const action = button.dataset.action;
    if (action === "edit") editAskMessage(row);
    if (action === "delete") deleteAskMessage(row);
    if (action === "regenerate") regenerateAskMessage(row);
    if (action === "copy") copyAskMessage(text, button);
  });
  row.appendChild(actions);
}

function appendAskMessage(role, text, options = {}) {
  if (!askAiAnswerEl) return null;
  askAiSheetEl?.classList.remove("empty-thread");
  const row = document.createElement("div");
  row.className = `ask-ai-message ${role}`;
  if (options.pending) row.classList.add("pending");
  if (options.messageId) row.dataset.messageId = String(options.messageId);
  row.askMessageText = text;
  const bubble = document.createElement("div");
  bubble.className = "ask-ai-bubble";
  bubble.innerHTML = renderMarkdown(text);
  row.appendChild(bubble);
  appendAskMessageActions(row, role, text, options);
  askAiAnswerEl.appendChild(row);
  askAiAnswerEl.scrollTop = askAiAnswerEl.scrollHeight;
  return row;
}

function renderAskConversation(payload, questionText = "") {
  if (!askAiAnswerEl) return;
  askAiAnswerEl.hidden = false;
  askAiAnswerEl.innerHTML = "";
  if (Array.isArray(payload?.messages)) {
    const messages = payload.messages;
    messages.forEach((message) => {
      appendAskMessage(message.role === "assistant" ? "ai" : "user", message.content || "", {
        messageId: message.id,
      });
    });
    askAiAnswerEl.scrollTop = askAiAnswerEl.scrollHeight;
    return;
  }
  const question = questionText || payload?.question || "";
  if (question) {
    appendAskMessage("user", question);
  }
  appendAskMessage("ai", payload?.answer || "没有返回答案。");
  askAiAnswerEl.scrollTop = askAiAnswerEl.scrollHeight;
}

function renderAskLoading(questionText) {
  if (!askAiAnswerEl) return;
  askAiAnswerEl.hidden = false;
  appendAskMessage("user", questionText);
  return appendAskMessage("ai", "正在整理上下文...", { pending: true });
}

function renderAskAnswer(payload) {
  const pending = askAiAnswerEl?.querySelector(".ask-ai-message.pending");
  if (pending) pending.remove();
  if (Array.isArray(payload?.messages) && payload.messages.length) {
    renderAskConversation(payload);
    return;
  }
  appendAskMessage("ai", payload?.answer || "没有返回答案。");
}

function setAskQuote(text) {
  const quote = strTrim(text).slice(0, 500);
  state.askQuote = quote;
  renderAskQuoteBar();
  if (askAiInputEl) askAiInputEl.focus();
}

function clearAskQuote() {
  state.askQuote = "";
  renderAskQuoteBar();
}

function renderAskQuoteBar() {
  if (!askAiQuoteBarEl) return;
  askAiQuoteBarEl.innerHTML = "";
  if (!state.askQuote) {
    askAiQuoteBarEl.hidden = true;
    return;
  }
  askAiQuoteBarEl.hidden = false;
  const label = document.createElement("span");
  label.textContent = "引用";
  const text = document.createElement("p");
  text.textContent = state.askQuote;
  const close = document.createElement("button");
  close.type = "button";
  close.setAttribute("aria-label", "删除引用");
  close.textContent = "×";
  close.addEventListener("click", clearAskQuote);
  askAiQuoteBarEl.append(label, text, close);
}

function buildAskQuestionText(question) {
  const base = strTrim(question);
  if (!state.askQuote) return base;
  const quoted = state.askQuote
    .split(/\n+/)
    .map((line) => `> ${line.trim()}`)
    .join("\n");
  return `引用内容：\n${quoted}\n\n${base}`;
}

function askRequestBody(question) {
  return { question, conversation_id: state.activeConversationId, ...currentAskScope() };
}

function updateStreamingBubble(row, text) {
  const bubble = row?.querySelector(".ask-ai-bubble");
  if (!bubble) return;
  bubble.innerHTML = renderMarkdown(text || "正在整理上下文...");
  askAiAnswerEl.scrollTop = askAiAnswerEl.scrollHeight;
}

function parseSseBlock(block) {
  const event = { type: "message", data: "" };
  block.split(/\n/).forEach((line) => {
    if (line.startsWith("event:")) event.type = line.slice(6).trim();
    if (line.startsWith("data:")) event.data += line.slice(5).trim();
  });
  if (!event.data) return null;
  try {
    return { type: event.type, payload: JSON.parse(event.data) };
  } catch (err) {
    return null;
  }
}

async function apiStream(path, body, onEvent) {
  const res = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const text = await res.text();
    throw new Error(text || `API 请求失败: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\n\n/);
    buffer = blocks.pop() || "";
    blocks.forEach((block) => {
      const event = parseSseBlock(block);
      if (event) onEvent(event);
    });
  }
  const tail = parseSseBlock(buffer);
  if (tail) onEvent(tail);
}

function removeAskQuoteFloat() {
  document.querySelector(".ask-ai-quote-float")?.remove();
}

function selectedAskText() {
  const selection = window.getSelection?.();
  if (!selection || selection.isCollapsed) return null;
  const text = strTrim(selection.toString());
  if (!text) return null;
  const range = selection.rangeCount ? selection.getRangeAt(0) : null;
  const node = range?.commonAncestorContainer;
  const element = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
  const bubble = element?.closest?.(".ask-ai-message.ai .ask-ai-bubble");
  return bubble ? { text, range } : null;
}

function showAskQuoteFloat(text, rect) {
  removeAskQuoteFloat();
  const quoteText = strTrim(text);
  if (!quoteText) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ask-ai-quote-float";
  button.textContent = "引用";
  button.style.left = `${Math.min(window.innerWidth - 74, Math.max(12, rect.left))}px`;
  button.style.top = `${Math.max(12, rect.bottom + 8)}px`;
  button.addEventListener("click", () => {
    setAskQuote(quoteText);
    window.getSelection?.().removeAllRanges();
    removeAskQuoteFloat();
  });
  document.body.appendChild(button);
}

function handleAskSelection() {
  const selected = selectedAskText();
  if (!selected) {
    removeAskQuoteFloat();
    return;
  }
  showAskQuoteFloat(selected.text, selected.range.getBoundingClientRect());
}

let askLongPressTimer = null;

function clearAskLongPress() {
  if (askLongPressTimer) {
    window.clearTimeout(askLongPressTimer);
    askLongPressTimer = null;
  }
}

function handleAskLongPress(event) {
  const bubble = event.target.closest?.(".ask-ai-message.ai .ask-ai-bubble");
  if (!bubble || event.pointerType === "mouse") return;
  clearAskLongPress();
  const point = { x: event.clientX, y: event.clientY };
  askLongPressTimer = window.setTimeout(() => {
    const selected = selectedAskText();
    if (selected) {
      showAskQuoteFloat(selected.text, selected.range.getBoundingClientRect());
      return;
    }
    const rect = { left: point.x, bottom: point.y + 6 };
    showAskQuoteFloat(bubble.textContent || "", rect);
  }, 420);
}

async function copyAskMessage(text, button) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const input = document.createElement("textarea");
      input.value = text;
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    if (button) {
      button.classList.add("copied");
      button.setAttribute("aria-label", "已复制");
      button.title = "已复制";
      window.setTimeout(() => {
        button.classList.remove("copied");
        button.setAttribute("aria-label", "复制");
        button.title = "复制";
      }, 900);
    }
  } catch (err) {
    if (button) {
      button.setAttribute("aria-label", "复制失败");
      button.title = "复制失败";
    }
  }
}

async function editAskMessage(row) {
  const messageId = askMessageId(row);
  if (!messageId || !state.activeConversationId) return;
  const bubble = row.querySelector(".ask-ai-bubble");
  if (!bubble) return;
  const original = row.askMessageText || bubble.textContent || "";
  row.classList.add("editing");
  bubble.innerHTML = "";
  const editor = document.createElement("textarea");
  editor.className = "ask-ai-edit-box";
  editor.value = original;
  const controls = document.createElement("div");
  controls.className = "ask-ai-edit-actions";
  const cancel = messageActionButton("cancel", "取消");
  const save = messageActionButton("save", "保存");
  controls.append(cancel, save);
  bubble.append(editor, controls);
  editor.focus();
  cancel.addEventListener("click", () => {
    row.classList.remove("editing");
    bubble.innerHTML = renderMarkdown(original);
  });
  save.addEventListener("click", async () => {
    const content = editor.value.trim();
    if (!content) return;
    save.disabled = true;
    const payload = await apiFetch(`/api/ask/history/${state.activeConversationId}/messages/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    });
    state.askHistoryLoaded = false;
    renderAskConversation(payload);
  });
}

async function deleteAskMessage(row) {
  const messageId = askMessageId(row);
  if (!messageId || !state.activeConversationId) return;
  row.classList.add("pending");
  const payload = await apiFetch(`/api/ask/history/${state.activeConversationId}/messages/${messageId}`, {
    method: "DELETE",
  });
  state.askHistoryLoaded = false;
  renderAskConversation(payload);
}

async function regenerateAskMessage(row) {
  const messageId = askMessageId(row);
  if (!messageId || !state.activeConversationId) return;
  const bubble = row.querySelector(".ask-ai-bubble");
  row.classList.add("pending");
  if (bubble) bubble.innerHTML = renderMarkdown("正在重新生成...");
  const payload = await apiFetch(`/api/ask/history/${state.activeConversationId}/messages/${messageId}/regenerate`, {
    method: "POST",
  });
  state.askHistoryLoaded = false;
  renderAskConversation(payload);
}

function renderAskHistory(payload) {
  if (!askAiHistoryListEl) return;
  askAiHistoryListEl.innerHTML = "";
  const items = Array.isArray(payload?.items) ? payload.items : [];
  const head = document.createElement("div");
  head.className = "ask-ai-history-head";
  const title = document.createElement("strong");
  title.textContent = "最近对话";
  const count = document.createElement("span");
  count.textContent = `${items.length} 条`;
  head.append(title, count);
  askAiHistoryListEl.appendChild(head);
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "ask-ai-history-empty";
    empty.textContent = "暂无对话记录。";
    askAiHistoryListEl.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const itemEl = document.createElement("div");
    itemEl.className = "ask-ai-history-item";
    itemEl.dataset.conversationId = item.conversation_id || "";

    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = "ask-ai-history-open";

    const question = document.createElement("span");
    question.className = "ask-ai-history-question";
    question.textContent = item.title || "未命名对话";
    openButton.appendChild(question);

    const preview = document.createElement("span");
    preview.className = "ask-ai-history-preview";
    preview.textContent = item.answer_preview || "";
    openButton.appendChild(preview);

    const labels = document.createElement("span");
    labels.className = "ask-ai-history-labels";
    (Array.isArray(item.labels) ? item.labels : []).forEach((label) => {
      const pill = document.createElement("span");
      pill.textContent = label;
      labels.appendChild(pill);
    });
    openButton.appendChild(labels);

    const meta = document.createElement("span");
    meta.className = "ask-ai-history-meta";
    const createdAt = item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : "";
    meta.textContent = createdAt;
    openButton.appendChild(meta);

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "ask-ai-history-delete";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", () => deleteAskHistoryItem(item.conversation_id));

    openButton.addEventListener("click", () => loadAskHistoryDetail(item.conversation_id));
    itemEl.append(openButton, deleteButton);
    askAiHistoryListEl.appendChild(itemEl);
  });
}

async function loadAskHistory(force = false) {
  if (!askAiHistoryListEl) return;
  if (!apiBaseUrl) {
    askAiHistoryListEl.textContent = "AI 后端未配置。";
    return;
  }
  if (state.askHistoryLoaded && !force) return;
  askAiHistoryListEl.textContent = "正在加载历史...";
  try {
    const payload = await apiFetch("/api/ask/history");
    renderAskHistory(payload);
    state.askHistoryLoaded = true;
  } catch (err) {
    askAiHistoryListEl.textContent = err.message || "历史记录加载失败。";
  }
}

async function loadAskHistoryDetail(conversationId) {
  if (!conversationId) return;
  setAskPanelView("messages");
  if (askAiAnswerEl) {
    askAiAnswerEl.hidden = false;
    askAiAnswerEl.textContent = "正在加载历史对话...";
  }
  try {
    const payload = await apiFetch(`/api/ask/history/${conversationId}`);
    state.activeConversationId = payload.conversation_id || conversationId;
    if (askAiInputEl) askAiInputEl.value = "";
    if (askAiContextEl) {
      askAiContextEl.textContent = Array.isArray(payload.labels) && payload.labels.length ? payload.labels.join(" · ") : "历史";
    }
    renderAskConversation(payload);
  } catch (err) {
    if (askAiAnswerEl) askAiAnswerEl.textContent = err.message || "历史对话加载失败。";
  }
}

function removeAskHistoryRow(conversationId) {
  const row = askHistoryRow(conversationId);
  if (row) row.remove();
  const rows = askAiHistoryListEl?.querySelectorAll(".ask-ai-history-item") || [];
  const count = askAiHistoryListEl?.querySelector(".ask-ai-history-head span");
  if (count) count.textContent = `${rows.length} 条`;
  if (!rows.length && askAiHistoryListEl && !askAiHistoryListEl.querySelector(".ask-ai-history-empty")) {
    const empty = document.createElement("div");
    empty.className = "ask-ai-history-empty";
    empty.textContent = "暂无对话记录。";
    askAiHistoryListEl.appendChild(empty);
  }
}

async function deleteAskHistoryItem(conversationId) {
  if (!conversationId) return;
  const deleteButton = askHistoryRow(conversationId)?.querySelector(".ask-ai-history-delete");
  if (deleteButton) deleteButton.disabled = true;
  try {
    await apiFetch(`/api/ask/history/${conversationId}`, { method: "DELETE" });
    removeAskHistoryRow(conversationId);
    if (state.activeConversationId === conversationId) {
      state.activeConversationId = null;
      if (askAiAnswerEl) askAiAnswerEl.innerHTML = "";
    }
  } catch (err) {
    if (deleteButton) deleteButton.disabled = false;
    if (askAiHistoryListEl) askAiHistoryListEl.textContent = err.message || "删除失败。";
  }
}

function setAskPanelView(view) {
  const isHistory = view === "history";
  state.askHistoryVisible = isHistory;
  if (isHistory) askAiSheetEl?.classList.remove("empty-thread");
  if (askAiHistoryListEl) askAiHistoryListEl.hidden = !isHistory;
  if (askAiAnswerEl) askAiAnswerEl.hidden = isHistory;
  if (askAiHistoryButtonEl) askAiHistoryButtonEl.classList.toggle("active", isHistory);
  if (askAiMessagesButtonEl) askAiMessagesButtonEl.classList.toggle("active", !isHistory);
  if (isHistory) loadAskHistory();
}

function toggleAskHistory() {
  setAskPanelView(state.askHistoryVisible ? "messages" : "history");
}

async function submitAskAi() {
  if (!askAiInputEl || !askAiSubmitEl || !askAiAnswerEl) return;
  let question = askAiInputEl.value.trim();
  if (!question) return;
  question = buildAskQuestionText(question);
  if (!apiBaseUrl) {
    askAiAnswerEl.textContent = "AI 后端未配置。";
    return;
  }
  askAiSubmitEl.disabled = true;
  setAskPanelView("messages");
  const pendingRow = renderAskLoading(question);
  askAiInputEl.value = "";
  clearAskQuote();
  try {
    if (state.askStreamingEnabled) {
      await submitAskAiStream(question, pendingRow);
      return;
    }
    const payload = await apiFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify(askRequestBody(question)),
    });
    state.activeConversationId = payload?.conversation_id || state.activeConversationId;
    renderAskAnswer(payload);
    if (payload?.history_saved) {
      state.askHistoryLoaded = false;
      if (state.askHistoryVisible) loadAskHistory(true);
    }
  } catch (err) {
    const pending = askAiAnswerEl.querySelector(".ask-ai-message.pending");
    if (pending) pending.remove();
    appendAskMessage("ai", err.message || "请求失败。");
  } finally {
    askAiSubmitEl.disabled = false;
  }
}

async function submitAskPresetQuestion(questionText) {
  if (!askAiAnswerEl) return;
  const question = strTrim(questionText);
  if (!question) return;
  if (!apiBaseUrl) {
    askAiAnswerEl.textContent = "AI 后端未配置。";
    return;
  }
  if (askAiSubmitEl) askAiSubmitEl.disabled = true;
  setAskPanelView("messages");
  const pendingRow = renderAskLoading(question);
  clearAskQuote();
  try {
    if (state.askStreamingEnabled) {
      await submitAskAiStream(question, pendingRow);
      return;
    }
    const payload = await apiFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify(askRequestBody(question)),
    });
    state.activeConversationId = payload?.conversation_id || state.activeConversationId;
    renderAskAnswer(payload);
    if (payload?.history_saved) {
      state.askHistoryLoaded = false;
      if (state.askHistoryVisible) loadAskHistory(true);
    }
  } catch (err) {
    const pending = askAiAnswerEl.querySelector(".ask-ai-message.pending");
    if (pending) pending.remove();
    appendAskMessage("ai", err.message || "请求失败。");
  } finally {
    if (askAiSubmitEl) askAiSubmitEl.disabled = false;
  }
}

async function submitAskAiStream(question, pendingRow) {
  let streamedText = "";
  let donePayload = null;
  try {
    await apiStream("/api/ask/stream", askRequestBody(question), (event) => {
      if (event.type === "delta") {
        streamedText += String(event.payload?.text || "");
        updateStreamingBubble(pendingRow, streamedText);
      }
      if (event.type === "error") {
        throw new Error(event.payload?.message || "流式输出失败");
      }
      if (event.type === "done") {
        donePayload = event.payload;
      }
    });
  } catch (err) {
    const payload = await apiFetch("/api/ask", {
      method: "POST",
      body: JSON.stringify(askRequestBody(question)),
    });
    state.activeConversationId = payload?.conversation_id || state.activeConversationId;
    renderAskAnswer(payload);
    if (payload?.history_saved) state.askHistoryLoaded = false;
    return;
  }
  if (donePayload) {
    state.activeConversationId = donePayload?.conversation_id || state.activeConversationId;
    renderAskConversation(donePayload);
    if (donePayload?.history_saved) state.askHistoryLoaded = false;
  }
}

const BOLE_PROFILE_QUESTIONS = [
  {
    id: "attention_goal",
    stage: "interest",
    title: "您最想优先看到哪类 AI 新闻？",
    prompt: "",
    placeholder: "自由输入",
    choices: ["产品与工具", "模型能力", "开发者集成", "研究学习", "行业影响", "商业信号"],
  },
  {
    id: "negative_preferences",
    stage: "interest",
    title: "哪些内容您通常不想看？",
    prompt: "",
    placeholder: "自由输入",
    choices: ["纯融资快讯", "营销稿", "重复转载", "空泛观点", "过度学术", "浅层汇总"],
  },
  {
    id: "ai_domains",
    stage: "interest",
    title: "您更关注哪些 AI 方向？",
    prompt: "",
    placeholder: "自由输入",
    choices: ["Agent", "Code AI", "多模态", "开源模型", "本地部署", "RAG / 知识库", "AI 搜索"],
  },
  {
    id: "deep_reading_policy",
    stage: "reading",
    title: "高命中新闻默认怎么处理？",
    prompt: "",
    placeholder: "自由输入",
    multiple: false,
    choices: ["只提高排序", "自动读正文并摘要", "先核验再推荐", "打开文章时再处理"],
  },
  {
    id: "reading_depth",
    stage: "reading",
    title: "您偏好的阅读深度是什么？",
    prompt: "",
    placeholder: "自由输入",
    multiple: false,
    choices: ["快速扫读", "标准摘要", "深度分析", "工程细节", "先做核验"],
  },
];

const BOLE_STAGE_ORDER = ["calibration", "preferences", "draft"];
const BOLE_QUESTION_TRANSITION_MS = 380;

function parseBoleTerms(text) {
  const protectedText = String(text || "").replace(/RAG\s*\/\s*知识库/gi, "RAG__BOLE_SLASH__知识库");
  const parts = protectedText.split(/[\n,，、;；/|]+/).map((part) => part.replace(/RAG__BOLE_SLASH__知识库/g, "RAG / 知识库"));
  return uniqueBoleLabels(parts);
}

function normalizeBoleLabel(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function uniqueBoleLabels(values) {
  const seen = new Set();
  const labels = [];
  (Array.isArray(values) ? values : []).forEach((value) => {
    const label = normalizeBoleLabel(value);
    if (!label || seen.has(label)) return;
    seen.add(label);
    labels.push(label);
  });
  return labels;
}

function normalizeBoleAnswer(rawAnswer) {
  const answer = rawAnswer && typeof rawAnswer === "object" ? rawAnswer : {};
  return {
    choices: uniqueBoleLabels(Array.isArray(answer.choices) ? answer.choices : []),
    text: normalizeBoleLabel(answer.text || ""),
    ai_labels: uniqueBoleLabels(Array.isArray(answer.ai_labels) ? answer.ai_labels : []),
    ai_note: normalizeBoleLabel(answer.ai_note || ""),
    follow_up: normalizeBoleLabel(answer.follow_up || ""),
    source: normalizeBoleLabel(answer.source || ""),
  };
}

function normalizeBoleCalibrationAnswers(rawAnswers) {
  const answers = rawAnswers && typeof rawAnswers === "object" ? rawAnswers : {};
  return {
    attention_goal: normalizeBoleAnswer(answers.attention_goal),
    negative_preferences: normalizeBoleAnswer(answers.negative_preferences),
    ai_domains: normalizeBoleAnswer(answers.ai_domains),
    deep_reading_policy: normalizeBoleAnswer(answers.deep_reading_policy),
    reading_depth: normalizeBoleAnswer(answers.reading_depth),
  };
}

function boleAnswerLabels(answer) {
  return uniqueBoleLabels([...(answer?.choices || []), ...(answer?.ai_labels || [])]);
}

function inferBoleSummaryDepth(readingDepthLabels, preferenceValues = {}) {
  if (preferenceValues.summary_depth) return preferenceValues.summary_depth;
  const text = uniqueBoleLabels(readingDepthLabels).join(" ");
  if (/深入|工程|deep/i.test(text)) return "deep";
  if (/快速|扫读|短|quick|concise/i.test(text)) return "concise";
  return "standard";
}

function inferBoleVerificationStrictness(policyLabels, readingDepthLabels, preferenceValues = {}) {
  if (preferenceValues.verification_strictness) return preferenceValues.verification_strictness;
  const text = uniqueBoleLabels([...policyLabels, ...readingDepthLabels]).join(" ");
  return /核验|事实|严格|fact|verify/i.test(text) ? "strict" : "standard";
}

function buildBoleProfileDraft(options = {}) {
  const answers = normalizeBoleCalibrationAnswers(options.calibrationAnswers);
  const preferenceValues = options.preferenceValues && typeof options.preferenceValues === "object" ? options.preferenceValues : {};
  const policyLabels = boleAnswerLabels(answers.deep_reading_policy);
  const readingDepthLabels = boleAnswerLabels(answers.reading_depth);
  const positiveLabels = uniqueBoleLabels([
    ...(Array.isArray(options.selectedInterests) ? options.selectedInterests : []),
    ...parseBoleTerms(options.positiveText),
    ...boleAnswerLabels(answers.attention_goal),
    ...boleAnswerLabels(answers.ai_domains),
  ]).slice(0, 12);
  const negativeLabels = uniqueBoleLabels([
    ...parseBoleTerms(options.negativeText),
    ...boleAnswerLabels(answers.negative_preferences),
  ]).slice(0, 12);
  const summaryDepth = options.summaryDepth || inferBoleSummaryDepth(readingDepthLabels, preferenceValues);
  const verificationStrictness =
    options.verificationStrictness || inferBoleVerificationStrictness(policyLabels, readingDepthLabels, preferenceValues);
  return {
    positive_interests: positiveLabels.map((label) => ({ label, weight: 0.85, source: "user" })),
    negative_interests: negativeLabels.map((label) => ({ label, weight: 0.8, source: "user" })),
    source_preferences: [],
    behavior_preferences: {
      summary_depth: summaryDepth,
      verification_strictness: verificationStrictness,
      deep_reading_policy: policyLabels,
      reading_depth: readingDepthLabels,
      recommendation_posture: preferenceValues.recommendation_posture || "practical",
      deep_reading_trigger: preferenceValues.deep_reading_trigger || "high_match",
      reading_cadence: preferenceValues.reading_cadence || "daily",
    },
  };
}

function buildBoleDraftEvidence(options = {}) {
  const answers = normalizeBoleCalibrationAnswers(options.calibrationAnswers);
  return {
    source: "workbench",
    calibration_answers: answers,
    conversation_context: buildBoleConversationContext(),
  };
}

function boleQuestionStageForUi(stage) {
  return stage === "preferences" ? "reading" : "interest";
}

function boleQuestionsForUiStage(stage) {
  if (stage === "draft") return [];
  return BOLE_PROFILE_QUESTIONS.filter((question) => question.stage === boleQuestionStageForUi(stage));
}

function boleQuestionById(questionId) {
  return BOLE_PROFILE_QUESTIONS.find((question) => question.id === questionId) || null;
}

function clearBoleQuestionTransitionTimer() {
  if (state.boleQuestionTransitionTimer) {
    clearTimeout(state.boleQuestionTransitionTimer);
    state.boleQuestionTransitionTimer = null;
  }
  if (state.boleTransitionStage) {
    questionContainerForStage(state.boleTransitionStage)?.classList.remove("is-transitioning");
    state.boleTransitionStage = "";
  }
}

function ensureBoleStageStarted(stage = state.boleStage) {
  const questions = boleQuestionsForUiStage(stage);
  if (!questions.length) return;
  const hasVisible = questions.some((question) => state.boleShownQuestionIds.has(question.id));
  if (hasVisible) return;
  state.boleShownQuestionIds.add(questions[0].id);
  if (stage === state.boleStage) state.boleActiveQuestionId = questions[0].id;
}

function visibleBoleQuestionsForStage(stage = state.boleStage) {
  ensureBoleStageStarted(stage);
  return boleQuestionsForUiStage(stage).filter((question) => {
    const answer = normalizeBoleAnswer(state.boleAnswers[question.id]);
    return (
      state.boleShownQuestionIds.has(question.id) ||
      state.boleConfirmedQuestionIds.has(question.id) ||
      boleAnswerLabels(answer).length > 0 ||
      Boolean(answer.text)
    );
  });
}

function activeBoleQuestion(stage = state.boleStage) {
  const visible = visibleBoleQuestionsForStage(stage);
  const active = visible.find((question) => question.id === state.boleActiveQuestionId);
  if (active) return active;
  return visible.find((question) => !state.boleConfirmedQuestionIds.has(question.id)) || visible[visible.length - 1] || null;
}

function mergeBoleAnswer(questionId, patch = {}) {
  const current = normalizeBoleAnswer(state.boleAnswers[questionId]);
  state.boleAnswers = {
    ...state.boleAnswers,
    [questionId]: {
      choices: patch.choices !== undefined ? uniqueBoleLabels(patch.choices) : current.choices,
      text: patch.text !== undefined ? normalizeBoleLabel(patch.text) : current.text,
      ai_labels: patch.ai_labels !== undefined ? uniqueBoleLabels(patch.ai_labels) : current.ai_labels,
      ai_note: patch.ai_note !== undefined ? normalizeBoleLabel(patch.ai_note) : current.ai_note,
      follow_up: patch.follow_up !== undefined ? normalizeBoleLabel(patch.follow_up) : current.follow_up,
      source: patch.source !== undefined ? normalizeBoleLabel(patch.source) : current.source,
    },
  };
  state.boleShownQuestionIds.add(questionId);
  if (patch.ai_labels !== undefined || patch.ai_note !== undefined || patch.follow_up !== undefined) {
    state.boleAnswerInterpretations[questionId] = {
      labels: uniqueBoleLabels(patch.ai_labels || []),
      note: normalizeBoleLabel(patch.ai_note || ""),
      follow_up: normalizeBoleLabel(patch.follow_up || ""),
    };
  }
}

function nextBoleQuestionAfter(questionId) {
  const question = boleQuestionById(questionId);
  if (!question) return null;
  const questions = BOLE_PROFILE_QUESTIONS.filter((item) => item.stage === question.stage);
  const index = questions.findIndex((item) => item.id === questionId);
  return index >= 0 ? questions[index + 1] || null : null;
}

function confirmBoleQuestion(questionId, options = {}) {
  const question = boleQuestionById(questionId);
  if (!question) return null;
  state.boleConfirmedQuestionIds.add(questionId);
  state.boleShownQuestionIds.add(questionId);
  const nextQuestion = nextBoleQuestionAfter(questionId);
  if (nextQuestion && options.revealNext !== false) {
    state.boleShownQuestionIds.add(nextQuestion.id);
    state.boleActiveQuestionId = nextQuestion.id;
  }
  return nextQuestion;
}

function activateBoleQuestion(questionId) {
  const question = boleQuestionById(questionId);
  if (!question) return;
  clearBoleQuestionTransitionTimer();
  state.boleStage = question.stage === "reading" ? "preferences" : "calibration";
  state.boleShownQuestionIds.add(questionId);
  state.boleActiveQuestionId = questionId;
  const enteringQuestionId = state.boleEnteringQuestionId;
  if (typeof renderBoleWorkbench === "function") renderBoleWorkbench();
  if (state.boleEnteringQuestionId === enteringQuestionId) state.boleEnteringQuestionId = "";
  if (typeof boleChatInputEl !== "undefined" && boleChatInputEl) {
    boleChatInputEl.focus();
    boleChatInputEl.setSelectionRange?.(boleChatInputEl.value.length, boleChatInputEl.value.length);
  }
}

function isBoleQuestionReady(questionId) {
  const answer = normalizeBoleAnswer(state.boleAnswers[questionId]);
  if (answer.text && answer.ai_note === "正在理解...") return false;
  if (answer.text && !answer.ai_labels.length) return false;
  return boleAnswerLabels(answer).length > 0;
}

function isLastBoleQuestionInStage(questionId) {
  const question = boleQuestionById(questionId);
  if (!question) return false;
  const questions = BOLE_PROFILE_QUESTIONS.filter((item) => item.stage === question.stage);
  return questions.findIndex((item) => item.id === questionId) === questions.length - 1;
}

function primaryBoleActionLabel(questionId = state.boleActiveQuestionId) {
  const answer = normalizeBoleAnswer(state.boleAnswers[questionId]);
  if (answer.ai_note === "正在理解...") return "理解中...";
  if (!isBoleQuestionReady(questionId)) return "确认回答";
  return isLastBoleQuestionInStage(questionId) ? "下一环节" : "下一题";
}

function questionContainerForStage(stage = state.boleStage) {
  return stage === "preferences" ? boleReadingTurnsEl : boleDialogueTurnsEl;
}

function finishBoleQuestionTransition(targetQuestionId, targetStage) {
  state.boleQuestionTransitionTimer = null;
  const stageForContainer = state.boleTransitionStage || state.boleStage;
  questionContainerForStage(stageForContainer)?.classList.remove("is-transitioning");
  state.boleTransitionStage = "";
  if (targetStage) {
    setBoleStage(targetStage, { animate: false });
    return;
  }
  state.boleEnteringQuestionId = targetQuestionId;
  activateBoleQuestion(targetQuestionId);
}

function transitionBoleQuestion(questionId, options = {}) {
  const question = boleQuestionById(questionId);
  if (!question) return;
  const targetStage = question.stage === "reading" ? "preferences" : "calibration";
  const currentContainer = questionContainerForStage(state.boleStage);
  const currentCard = currentContainer?.querySelector(`[data-bole-question-id="${state.boleActiveQuestionId}"]`);
  clearBoleQuestionTransitionTimer();
  state.boleShownQuestionIds.add(questionId);
  if (options.animate === false || !currentCard || state.boleStage !== targetStage || state.boleActiveQuestionId === questionId) {
    activateBoleQuestion(questionId);
    return;
  }
  currentContainer.classList.add("is-transitioning");
  currentCard.classList.add("exiting");
  state.boleTransitionStage = state.boleStage;
  state.boleQuestionTransitionTimer = setTimeout(() => finishBoleQuestionTransition(questionId), BOLE_QUESTION_TRANSITION_MS);
}

function advanceBoleQuestionFrom(questionId, options = {}) {
  const nextQuestion = confirmBoleQuestion(questionId, { revealNext: false });
  if (!nextQuestion) {
    if (state.boleStage === "calibration") setBoleStage("preferences", options);
    else if (state.boleStage === "preferences") setBoleStage("draft", options);
    else renderBoleWorkbench();
    return;
  }
  transitionBoleQuestion(nextQuestion.id, options);
}

function buildBoleConversationContext(currentQuestionId = "") {
  if (typeof BOLE_PROFILE_QUESTIONS === "undefined") return [];
  return BOLE_PROFILE_QUESTIONS.filter((question) => question.id !== currentQuestionId).map((question) => {
    const answer = normalizeBoleAnswer(state.boleAnswers[question.id]);
    return {
      question_id: question.id,
      question_title: question.title,
      stage: question.stage,
      choices: answer.choices,
      text: answer.text,
      ai_labels: answer.ai_labels,
      ai_note: answer.ai_note,
      follow_up: answer.follow_up,
    };
  }).filter((item) => item.choices.length || item.text || item.ai_labels.length);
}

function localBoleInterpretation(question, text, choices = []) {
  const sourceText = normalizeBoleLabel(text);
  const inferred = [];
  const haystack = sourceText.toLowerCase();
  if (/rag|知识库/.test(haystack)) inferred.push("RAG / 知识库");
  if (/agent|智能体/.test(haystack)) inferred.push("Agent");
  if (/code|编程|代码/.test(haystack)) inferred.push("Code AI");
  if (/本地|私有|部署|量化/.test(haystack)) inferred.push("本地部署");
  if (/多模态|图像|视频|语音/.test(haystack)) inferred.push("多模态");
  if (/工程|研发|开发|集成/.test(haystack)) inferred.push("工程与部署");
  if (/产品|工具|效率/.test(haystack)) inferred.push("产品与工具");
  if (/融资|资本/.test(haystack)) inferred.push("纯融资快讯");
  if (/营销|软文/.test(haystack)) inferred.push("营销稿");
  if (/空泛|观点/.test(haystack)) inferred.push("空泛观点");
  if (/核验|事实|可信/.test(haystack)) inferred.push("事实核验");
  if (/深入|深度|细节/.test(haystack)) inferred.push("深入分析");
  const labels = uniqueBoleLabels([...choices, ...inferred, ...parseBoleTerms(sourceText)]).slice(0, 5);
  return {
    labels,
    note: labels.length ? `伯乐理解为：${labels.join("、")}` : "",
    follow_up: question?.stage === "interest" ? "你更想看实践案例，还是底层能力变化？" : "这个偏好在高命中新闻里优先使用。",
    source: "local",
  };
}

async function interpretBoleInput(question, text, selectedChoices = []) {
  const fallback = localBoleInterpretation(question, text, selectedChoices);
  if (!apiBaseUrl) return fallback;
  try {
    const payload = await apiFetch("/api/personalization/interpret", {
      method: "POST",
      body: JSON.stringify({
        question_id: question.id,
        stage: state.boleStage,
        answer_text: normalizeBoleLabel(text),
        selected_choices: uniqueBoleLabels(selectedChoices),
        history: buildBoleConversationContext(question.id),
      }),
    });
    const labels = uniqueBoleLabels(payload?.labels || []);
    return {
      labels: labels.length ? labels : fallback.labels,
      note: normalizeBoleLabel(payload?.note || fallback.note),
      follow_up: normalizeBoleLabel(payload?.follow_up || fallback.follow_up),
      source: "ai",
    };
  } catch (_) {
    return fallback;
  }
}

function syncBoleStage() {
  const stage = BOLE_STAGE_ORDER.includes(state.boleStage) ? state.boleStage : "calibration";
  state.boleStage = stage;
  ensureBoleStageStarted(stage);
  if (boleWorkbenchEl) boleWorkbenchEl.dataset.boleStage = stage;
  if (boleStageTrackEl) {
    const stageIndex = Math.max(0, BOLE_STAGE_ORDER.indexOf(stage));
    boleStageTrackEl.style.transform = `translateX(-${stageIndex * 100}%)`;
  }
  boleStageButtons.forEach((button) => {
    const active = button.dataset.boleStage === stage;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  boleStagePanels.forEach((panel) => {
    const active = panel.dataset.boleStagePanel === stage;
    panel.classList.toggle("active", active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  });
  if (boleChatFormEl) boleChatFormEl.hidden = stage === "draft";
  if (boleChatInputEl) {
    const question = activeBoleQuestion(stage);
    boleChatInputEl.placeholder = question?.placeholder || "自由输入";
    boleChatInputEl.value = stage === "draft" ? "" : normalizeBoleAnswer(state.boleAnswers[question?.id]).text;
  }
}

function setBoleStage(stage, options = {}) {
  if (!BOLE_STAGE_ORDER.includes(stage)) return;
  clearBoleQuestionTransitionTimer();
  state.boleStage = stage;
  ensureBoleStageStarted(stage);
  if (stage !== "draft") {
    state.boleActiveQuestionId = activeBoleQuestion(stage)?.id || state.boleActiveQuestionId;
  }
  renderBoleWorkbench();
  if (stage !== "draft") boleChatInputEl?.focus();
}

function renderBoleChoiceButtons(question) {
  const answer = normalizeBoleAnswer(state.boleAnswers[question.id]);
  return question.choices
    .map((choice) => {
      const active = answer.choices.includes(choice);
      return `<button class="bole-seed-chip${active ? " active" : ""}" type="button" data-bole-question-choice="${escapeHtml(
        question.id,
      )}" data-bole-choice="${escapeHtml(choice)}">${escapeHtml(choice)}</button>`;
    })
    .join("");
}

function renderBoleQuestionTurn(question) {
  if (!question) return "";
  const answer = normalizeBoleAnswer(state.boleAnswers[question.id]);
  const labels = boleAnswerLabels(answer);
  const active = question.id === activeBoleQuestion(state.boleStage)?.id;
  const answered = !active && (state.boleConfirmedQuestionIds.has(question.id) || labels.length > 0 || Boolean(answer.text));
  const userLine = answer.text ? `<p class="bole-user-evidence">您说：${escapeHtml(answer.text)}</p>` : "";
  const interpretation = labels.length
    ? `<div class="bole-interpretation"><span>伯乐理解为</span><strong>${escapeHtml(labels.join("、"))}</strong></div>`
    : "";
  const followUp = answer.follow_up ? `<p>${escapeHtml(answer.follow_up)}</p>` : `<p>${escapeHtml(question.prompt)}</p>`;
  return `
    <article class="bole-turn bole-turn-ai${answered ? " answered" : ""}${
      active && state.boleEnteringQuestionId === question.id ? " entering" : ""
    }" data-bole-question-id="${escapeHtml(question.id)}">
      <h4>${escapeHtml(question.title)}</h4>
      ${active && question.prompt ? followUp : ""}
      ${userLine}
      ${interpretation}
      ${active ? `<div class="bole-seed-row" aria-label="预设选项">${renderBoleChoiceButtons(question)}</div>` : ""}
    </article>
  `;
}

function renderBoleQuestionDots(stage) {
  return boleQuestionsForUiStage(stage)
    .map((question, index) => {
      const active = question.id === state.boleActiveQuestionId && stage === state.boleStage;
      const done = isBoleQuestionReady(question.id);
      return `<button class="bole-question-dot${active ? " active" : ""}${done ? " done" : ""}" type="button" data-bole-question-dot="${escapeHtml(question.id)}" aria-label="${escapeHtml(question.title)}"></button>`;
    })
    .join("");
}

function renderBoleTurnDeck() {
  return '<div class="bole-turn-deck-card one"></div><div class="bole-turn-deck-card two"></div>';
}

function renderBoleConversation() {
  boleQuestionDotGroups.forEach((group) => {
    group.innerHTML = renderBoleQuestionDots(group.dataset.boleQuestionDots || "calibration");
  });
  if (boleDialogueTurnsEl) {
    const question = state.boleStage === "calibration" ? activeBoleQuestion("calibration") : activeBoleQuestion("calibration");
    boleDialogueTurnsEl.innerHTML = `${renderBoleTurnDeck()}${question ? renderBoleQuestionTurn(question) : ""}`;
  }
  if (boleReadingTurnsEl) {
    const question = activeBoleQuestion("preferences");
    boleReadingTurnsEl.innerHTML = `${renderBoleTurnDeck()}${question ? renderBoleQuestionTurn(question) : ""}`;
  }
}

function setBoleWorkbenchStatus(text) {
  if (boleWorkbenchStatusEl) boleWorkbenchStatusEl.textContent = text || "";
}

function boleStatusLabel() {
  if (!apiBaseUrl) return "未连接";
  if (state.personalizationUnavailable) return "暂不可用";
  const status = state.personalizationStatus;
  if (!status) return "未加载";
  if (status.state === "confirmed" && status.enabled) return "已启用";
  if (status.state === "confirmed" && !status.enabled) return "已停用";
  if (status.state === "draft_pending") return "有草稿";
  if (status.state === "skipped") return "已跳过";
  return "未设置";
}

function renderBoleSettingsStatus() {
  if (boleSettingsStatusEl) boleSettingsStatusEl.textContent = boleStatusLabel();
}

function syncBoleActionButtons() {
  const busy = false;
  const isFirstUseStage = !state.personalizationStatus || state.personalizationStatus.state === "not_started";
  if (boleConfirmButtonEl) {
    boleConfirmButtonEl.disabled = busy;
    boleConfirmButtonEl.textContent = state.boleStage === "draft" ? "保存画像" : "保存";
  }
  if (boleContinueButtonEl) boleContinueButtonEl.hidden = state.boleStage === "draft";
  if (boleSkipButtonEl) {
    boleSkipButtonEl.hidden = !isFirstUseStage || state.boleStage === "draft";
    boleSkipButtonEl.disabled = false;
  }
  const unavailable = !apiBaseUrl || state.personalizationUnavailable;
  if (boleDisableButtonEl) boleDisableButtonEl.disabled = unavailable || !state.personalizationStatus?.active_profile;
  if (boleResetButtonEl) boleResetButtonEl.disabled = unavailable || !state.personalizationStatus;
  if (boleChatSendEl && state.boleStage !== "draft") {
    const question = activeBoleQuestion(state.boleStage);
    const answer = normalizeBoleAnswer(state.boleAnswers[question?.id]);
    const hasInput = Boolean(answer.text || boleChatInputEl?.value.trim() || boleAnswerLabels(answer).length);
    boleChatSendEl.textContent = primaryBoleActionLabel(question?.id);
    boleChatSendEl.disabled = answer.ai_note === "正在理解..." || !hasInput;
  }
}

function collectBoleCalibrationAnswers() {
  const answers = {};
  BOLE_PROFILE_QUESTIONS.forEach((question) => {
    answers[question.id] = normalizeBoleAnswer(state.boleAnswers[question.id]);
  });
  return answers;
}

function collectBolePreferenceValues() {
  const values = {};
  bolePreferenceButtons.forEach((button) => {
    if (!button.classList.contains("active")) return;
    const key = button.dataset.bolePreference;
    if (!key) return;
    values[key] = button.dataset.boleValue || button.textContent.trim();
  });
  return values;
}

function collectBoleDraftInput() {
  return buildBoleProfileDraft({
    calibrationAnswers: collectBoleCalibrationAnswers(),
    preferenceValues: collectBolePreferenceValues(),
  });
}

function renderBoleInterestTags(items, emptyText) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return `<span class="bole-empty-chip">${escapeHtml(emptyText)}</span>`;
  return list
    .map((item) => {
      const label = typeof item === "string" ? item : item.label || item.source || "";
      return `<span class="bole-profile-chip">${escapeHtml(label)}</span>`;
    })
    .join("");
}

function renderBoleProfileCards(items, emptyText, options = {}) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return `<div class="bole-empty-state">${escapeHtml(emptyText)}</div>`;
  return list
    .map((item) => {
      const label = item.label || item.source || item;
      const questionId = item.questionId || "";
      return `
        <div class="bole-profile-card${options.avoid ? " avoid" : ""}">
          <strong>${escapeHtml(label)}</strong>
          ${
            questionId
              ? `<button class="bole-profile-remove" type="button" aria-label="移除 ${escapeHtml(label)}" data-bole-remove-question="${escapeHtml(questionId)}" data-bole-remove-label="${escapeHtml(label)}">×</button>`
              : ""
          }
        </div>
      `;
    })
    .join("");
}

function boleItemsFromQuestion(questionId, options = {}) {
  const answer = normalizeBoleAnswer(state.boleAnswers[questionId]);
  return boleAnswerLabels(answer).map((label) => ({ label, questionId, ...options }));
}

function boleProfileSectionsForStage(stage = state.boleStage) {
  if (stage === "preferences") {
    return [
      { title: "阅读偏好", items: [...boleItemsFromQuestion("deep_reading_policy"), ...boleItemsFromQuestion("reading_depth")] },
    ];
  }
  if (stage === "draft") {
    return [
      { title: "多看", items: [...boleItemsFromQuestion("attention_goal"), ...boleItemsFromQuestion("ai_domains")] },
      { title: "少看", items: boleItemsFromQuestion("negative_preferences", { avoid: true }), avoid: true },
      { title: "阅读偏好", items: [...boleItemsFromQuestion("deep_reading_policy"), ...boleItemsFromQuestion("reading_depth")] },
    ];
  }
  return [
    { title: "多看", items: [...boleItemsFromQuestion("attention_goal"), ...boleItemsFromQuestion("ai_domains")] },
    { title: "少看", items: boleItemsFromQuestion("negative_preferences", { avoid: true }), avoid: true },
  ];
}

function renderBoleRecognizedProfile() {
  if (!boleRecognizedProfileEl) return;
  if (boleProfileRailTitleEl) {
    if (state.boleStage === "preferences") boleProfileRailTitleEl.textContent = "阅读偏好";
    else if (state.boleStage === "draft") boleProfileRailTitleEl.textContent = "画像草稿";
    else boleProfileRailTitleEl.textContent = "已选兴趣";
  }
  const sections = boleProfileSectionsForStage(state.boleStage);
  const blocks = sections
    .filter((section) => section.items.length)
    .map((section) => `
      <div class="bole-profile-block">
        <span>${escapeHtml(section.title)}</span>
        ${renderBoleProfileCards(section.items, "", { avoid: section.avoid })}
      </div>
    `);
  const emptyText = state.boleStage === "preferences" ? "先设置阅读偏好" : state.boleStage === "draft" ? "完成前两步后显示画像" : "先回答兴趣问题";
  boleRecognizedProfileEl.innerHTML = blocks.join("") || `<div class="bole-empty-state">${escapeHtml(emptyText)}</div>`;
}

function removeBoleProfileLabel(questionId, label) {
  const answer = normalizeBoleAnswer(state.boleAnswers[questionId]);
  mergeBoleAnswer(questionId, {
    choices: answer.choices.filter((item) => item !== label),
    ai_labels: answer.ai_labels.filter((item) => item !== label),
  });
  state.boleDraftPreview = collectBoleDraftInput();
  renderBoleWorkbench();
}

function renderBoleDraftPreview(profile) {
  if (!boleDraftPreviewEl) return;
  if (!profile) {
    boleDraftPreviewEl.innerHTML = '<div class="bole-empty-state">回答后显示草稿</div>';
    return;
  }
  const readingLabels = uniqueBoleLabels([
    ...(profile.behavior_preferences?.deep_reading_policy || []),
    ...(profile.behavior_preferences?.reading_depth || []),
  ]);
  boleDraftPreviewEl.innerHTML = `
    <div class="bole-profile-block bole-draft-box">
      <span>多看</span>
      <div class="bole-chip-row">${renderBoleInterestTags(profile.positive_interests, "待添加")}</div>
    </div>
    <div class="bole-profile-block bole-draft-box">
      <span>少看</span>
      <div class="bole-chip-row">${renderBoleInterestTags(profile.negative_interests, "未设置")}</div>
    </div>
    <div class="bole-profile-block bole-draft-box">
      <span>阅读偏好</span>
      <div class="bole-chip-row">${readingLabels.length ? renderBoleInterestTags(readingLabels, "未设置") : '<span class="bole-empty-chip">未设置</span>'}</div>
    </div>
  `;
}

function renderBoleRecommendationPreview(profile) {
  if (boleRecommendationPreviewEl) boleRecommendationPreviewEl.innerHTML = "";
}

function renderBoleWorkbench() {
  const status = state.personalizationStatus || {};
  const profile = state.boleDraftPreview || status.draft_profile || status.active_profile || collectBoleDraftInput();
  syncBoleStage();
  renderBoleConversation();
  renderBoleDraftPreview(profile);
  renderBoleRecommendationPreview(profile);
  renderBoleRecognizedProfile(profile);
  renderBoleSettingsStatus();
  syncBoleActionButtons();
}

async function advanceBoleQuestion(text = "") {
  const question = activeBoleQuestion(state.boleStage);
  if (!question) return;
  if (isBoleQuestionReady(question.id)) {
    advanceBoleQuestionFrom(question.id);
    return;
  }
  const nextText = normalizeBoleLabel(text);
  if (!nextText) return;
  const answer = normalizeBoleAnswer(state.boleAnswers[question.id]);
  mergeBoleAnswer(question.id, { choices: answer.choices, text: nextText, ai_note: "正在理解..." });
  renderBoleWorkbench();
  const interpretation = await interpretBoleInput(question, nextText, answer.choices);
  mergeBoleAnswer(question.id, {
    choices: answer.choices,
    text: nextText,
    ai_labels: interpretation.labels,
    ai_note: interpretation.note,
    follow_up: interpretation.follow_up,
    source: interpretation.source,
  });
  state.boleDraftPreview = collectBoleDraftInput();
  renderBoleWorkbench();
}

function openBoleWorkbench() {
  if (!boleWorkbenchEl) return;
  if (!apiBaseUrl) {
    state.personalizationUnavailable = true;
  }
  renderBoleWorkbench();
  setBoleWorkbenchStatus("");
  boleWorkbenchEl.hidden = false;
  document.body.classList.add("bole-workbench-open");
  window.requestAnimationFrame(() => boleWorkbenchEl.classList.add("open"));
  if (state.boleStage !== "draft") boleChatInputEl?.focus();
}

function closeBoleWorkbench() {
  if (!boleWorkbenchEl) return;
  boleWorkbenchEl.classList.remove("open");
  boleWorkbenchEl.hidden = true;
  document.body.classList.remove("bole-workbench-open");
}

async function loadPersonalization(options = {}) {
  if (!apiBaseUrl) {
    state.personalizationUnavailable = true;
    renderBoleWorkbench();
    renderBolePicks();
    return null;
  }
  try {
    const payload = await apiFetch("/api/personalization");
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = payload.draft_profile || payload.active_profile || state.boleDraftPreview;
    loadBoleFeedback({ quiet: true });
    renderBoleWorkbench();
    renderBolePicks();
    if (options.autoOpen && payload.state === "not_started") openBolePersonalizationEntry({ auto: Boolean(options.autoOpen) });
    return payload;
  } catch (err) {
    state.personalizationUnavailable = true;
    renderBoleWorkbench();
    renderBolePicks();
    if (!options.quiet) setBoleWorkbenchStatus(err.message || "伯乐画像不可用");
    return null;
  }
}

async function saveBoleDraft(options = {}) {
  if (!apiBaseUrl) {
    state.personalizationUnavailable = true;
    renderBoleWorkbench();
    setBoleWorkbenchStatus("暂时无法保存");
    return false;
  }
  const profile = currentBoleDraftProfile();
  const evidence = buildBoleDraftEvidence({
    calibrationAnswers: collectBoleCalibrationAnswers(),
  });
  if (state.bolePendingDraftSuggestion) {
    evidence.feedback_suggestion = state.bolePendingDraftSuggestion.evidence || state.bolePendingDraftSuggestion;
  }
  evidence.positive_count = profile.positive_interests.length;
  evidence.negative_count = profile.negative_interests.length;
  state.boleDraftPreview = profile;
  renderBoleWorkbench();
  if (boleConfirmButtonEl) boleConfirmButtonEl.disabled = true;
  if (!options.silent) setBoleWorkbenchStatus("保存中...");
  try {
    const payload = await apiFetch("/api/personalization/draft", {
      method: "POST",
      body: JSON.stringify({
        profile,
        evidence,
      }),
    });
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = payload.draft_profile || profile;
    renderBoleWorkbench();
    if (!options.silent) setBoleWorkbenchStatus("");
    return true;
  } catch (err) {
    setBoleWorkbenchStatus(err.message || "草稿生成失败");
    return false;
  } finally {
    syncBoleActionButtons();
  }
}

async function confirmBoleProfile() {
  const saved = await saveBoleDraft({ silent: true });
  if (!saved) return;
  if (boleConfirmButtonEl) boleConfirmButtonEl.disabled = true;
  setBoleWorkbenchStatus("保存中...");
  try {
    const payload = await apiFetch("/api/personalization/confirm", { method: "POST" });
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = payload.active_profile || null;
    renderBoleWorkbench();
    renderBolePicks();
    setBoleWorkbenchStatus("");
    closeBoleWorkbench();
  } catch (err) {
    setBoleWorkbenchStatus(err.message || "保存失败");
  } finally {
    syncBoleActionButtons();
  }
}

async function skipBolePersonalization() {
  if (!apiBaseUrl) return;
  setBoleWorkbenchStatus("跳过中...");
  try {
    const payload = await apiFetch("/api/personalization/skip", { method: "POST" });
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = null;
    renderBoleWorkbench();
    renderBolePicks();
    closeBoleWorkbench();
  } catch (err) {
    setBoleWorkbenchStatus(err.message || "跳过失败");
  }
}

async function resetBolePersonalization() {
  if (!apiBaseUrl) {
    renderBoleWorkbench();
    return;
  }
  setSettingsStatus("重置伯乐画像中...");
  try {
    const payload = await apiFetch("/api/personalization/reset", { method: "POST" });
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = null;
    state.boleAnswers = {};
    state.boleShownQuestionIds = new Set(["attention_goal"]);
    state.boleConfirmedQuestionIds = new Set();
    state.boleAnswerInterpretations = {};
    state.boleActiveQuestionId = "attention_goal";
    clearBoleQuestionTransitionTimer();
    state.boleStage = "calibration";
    if (boleChatInputEl) boleChatInputEl.value = "";
    renderBoleWorkbench();
    renderBolePicks();
    setSettingsStatus("伯乐画像已重置");
  } catch (err) {
    setSettingsStatus(err.message || "重置失败");
  }
}

async function disableBolePersonalization() {
  if (!apiBaseUrl) {
    renderBoleWorkbench();
    return;
  }
  setSettingsStatus("停用伯乐画像中...");
  try {
    const payload = await apiFetch("/api/personalization/disable", { method: "POST" });
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = payload.active_profile || null;
    renderBoleWorkbench();
    renderBolePicks();
    setSettingsStatus("伯乐画像已停用");
  } catch (err) {
    setSettingsStatus(err.message || "停用失败");
  }
}

function setSettingsStatus(text) {
  if (settingsStatusEl) settingsStatusEl.textContent = text;
}

function setAiConfigStatus(text, tone = "") {
  if (aiConfigStatusEl) {
    aiConfigStatusEl.textContent = text || "";
    aiConfigStatusEl.classList.toggle("ok", tone === "ok");
    aiConfigStatusEl.classList.toggle("warn", tone === "warn");
  }
  if (aiConfigHeadStatusEl) {
    aiConfigHeadStatusEl.textContent = tone === "ok" ? "已连接" : "未连接";
  }
}

function hasSavedAiConfigProfile() {
  return (state.aiProfiles || []).some((profile) => profile && profile.id !== "env" && !profile.readonly);
}

function shouldPromptForAiConfigBeforeBole() {
  if (!apiBaseUrl || state.aiConfigSkipped) return false;
  const status = state.personalizationStatus || {};
  if (status.state && status.state !== "not_started") return false;
  return !hasSavedAiConfigProfile();
}

function resetAiConfigForm() {
  state.aiConfigProfileId = "";
  if (aiConfigNameInputEl) aiConfigNameInputEl.value = "";
  if (aiConfigTypeSelectEl) aiConfigTypeSelectEl.value = "chat_completions";
  if (aiConfigBaseUrlInputEl) aiConfigBaseUrlInputEl.value = "";
  if (aiConfigModelInputEl) aiConfigModelInputEl.value = "";
  if (aiConfigApiKeyInputEl) aiConfigApiKeyInputEl.value = "";
  if (aiConfigHeadersInputEl) aiConfigHeadersInputEl.value = "";
  if (aiConfigTimeoutInputEl) aiConfigTimeoutInputEl.value = "45";
}

function closeAiConfigDialog() {
  if (!aiConfigDialogEl) return;
  aiConfigDialogEl.classList.remove("open");
  aiConfigDialogEl.hidden = true;
  document.body.classList.remove("ai-config-dialog-open");
}

function openAiConfigDialog() {
  if (!aiConfigDialogEl) {
    openBoleWorkbench();
    return;
  }
  resetAiConfigForm();
  setAiConfigStatus("可跳过进入画像工作台。");
  aiConfigDialogEl.hidden = false;
  document.body.classList.add("ai-config-dialog-open");
  window.requestAnimationFrame(() => aiConfigDialogEl.classList.add("open"));
  aiConfigNameInputEl?.focus();
}

function skipAiConfigDialog() {
  state.aiConfigSkipped = true;
  closeAiConfigDialog();
  openBoleWorkbench();
}

function aiConfigProfilePayload() {
  const headersText = aiConfigHeadersInputEl?.value.trim() || "";
  if (headersText) JSON.parse(headersText);
  return {
    name: aiConfigNameInputEl?.value.trim() || "默认 AI",
    type: aiConfigTypeSelectEl?.value || "chat_completions",
    base_url: aiConfigBaseUrlInputEl?.value.trim() || "",
    model: aiConfigModelInputEl?.value.trim() || "",
    api_key: aiConfigApiKeyInputEl?.value || "",
    headers_json: headersText,
    timeout_seconds: Number(aiConfigTimeoutInputEl?.value || 45),
    enabled: true,
  };
}

async function saveReadingAssistantProvider(profileId) {
  if (!apiBaseUrl || !profileId) return;
  const topN = Math.max(1, Math.min(10, Number(deepVerificationTopNEl?.value || 3)));
  const translationMode = translationProviderModeSelectEl?.value || state.translationProviderMode || "browser";
  const payload = {
    deep_verification_enabled: Boolean(deepVerificationToggleEl?.checked),
    deep_verification_scope: "bole_picks_and_topic_top_n",
    deep_verification_top_n: topN,
    ask_streaming_enabled: Boolean(askStreamingToggleEl?.checked),
    ask_system_prompt: askSystemPromptInputEl?.value || "",
    translation_provider_mode: translationMode,
    translation_provider_id: translationMode === "ai" ? translationProviderSelectEl?.value || state.translationProviderId || "env" : "",
    reading_assistant_provider_id: profileId,
  };
  const settings = await apiFetch("/api/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  applySettings(settings);
}

async function saveAiConfigAndContinue() {
  if (!apiBaseUrl) {
    skipAiConfigDialog();
    return;
  }
  let payload;
  try {
    payload = aiConfigProfilePayload();
  } catch (_) {
    setAiConfigStatus("请求头 JSON 格式错误", "warn");
    return;
  }
  if (aiConfigSaveButtonEl) aiConfigSaveButtonEl.disabled = true;
  setAiConfigStatus("保存中...");
  try {
    const profileId = state.aiConfigProfileId;
    const profile = await apiFetch(profileId ? `/api/ai-profiles/${encodeURIComponent(profileId)}` : "/api/ai-profiles", {
      method: profileId ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    state.aiConfigProfileId = profile.id;
    state.aiProfiles = [profile, ...(state.aiProfiles || []).filter((item) => item.id !== "env" && item.id !== profile.id)];
    renderAiProfiles();
    await saveReadingAssistantProvider(profile.id);
    setAiConfigStatus("已保存", "ok");
    closeAiConfigDialog();
    openBoleWorkbench();
  } catch (err) {
    setAiConfigStatus(err.message || "AI 配置保存失败", "warn");
  } finally {
    if (aiConfigSaveButtonEl) aiConfigSaveButtonEl.disabled = false;
  }
}

async function testAiConfigConnection() {
  if (!apiBaseUrl) return;
  let payload;
  try {
    payload = aiConfigProfilePayload();
  } catch (_) {
    setAiConfigStatus("请求头 JSON 格式错误", "warn");
    return;
  }
  if (aiConfigTestButtonEl) aiConfigTestButtonEl.disabled = true;
  setAiConfigStatus("测试中...");
  try {
    const profile = await apiFetch("/api/ai-profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.aiConfigProfileId = profile.id;
    state.aiProfiles = [profile, ...(state.aiProfiles || []).filter((item) => item.id !== "env" && item.id !== profile.id)];
    renderAiProfiles();
    await apiFetch(`/api/ai-profiles/${encodeURIComponent(profile.id)}/test`, { method: "POST" });
    setAiConfigStatus("AI 连接正常", "ok");
  } catch (err) {
    setAiConfigStatus(err.message || "AI 连接失败", "warn");
  } finally {
    if (aiConfigTestButtonEl) aiConfigTestButtonEl.disabled = false;
  }
}

function openBolePersonalizationEntry(options = {}) {
  if (shouldPromptForAiConfigBeforeBole()) {
    openAiConfigDialog();
    return;
  }
  openBoleWorkbench();
}

function applySettings(settings) {
  if (!settings) return;
  if (deepVerificationToggleEl) {
    deepVerificationToggleEl.checked = Boolean(settings.deep_verification_enabled);
  }
  if (deepVerificationTopNEl) {
    deepVerificationTopNEl.value = String(settings.deep_verification_top_n || 3);
  }
  state.askStreamingEnabled = Boolean(settings.ask_streaming_enabled);
  if (askStreamingToggleEl) {
    askStreamingToggleEl.checked = state.askStreamingEnabled;
  }
  if (askSystemPromptInputEl) {
    askSystemPromptInputEl.value = String(settings.ask_system_prompt || "");
  }
  state.translationProviderMode = settings.translation_provider_mode || "browser";
  state.translationProviderId = settings.translation_provider_id || "";
  state.readingAssistantProviderId = settings.reading_assistant_provider_id || "env";
  state.boleConflictStrategy = settings.bole_conflict_strategy === "last_decision" ? "last_decision" : "ask";
  if (translationProviderModeSelectEl) translationProviderModeSelectEl.value = state.translationProviderMode;
  if (translationProviderSelectEl) translationProviderSelectEl.value = state.translationProviderId || "env";
  if (readingAssistantProviderSelectEl) readingAssistantProviderSelectEl.value = state.readingAssistantProviderId || "env";
  if (boleConflictStrategySelectEl) boleConflictStrategySelectEl.value = state.boleConflictStrategy;
  syncTranslationProviderMode();
}

function aiProviderOptions() {
  const envProfile = { id: "env", name: "环境变量 AI", readonly: true };
  const seen = new Set(["env"]);
  const storedProfiles = (state.aiProfiles || []).filter((profile) => {
    if (!profile?.id || seen.has(profile.id)) return false;
    seen.add(profile.id);
    return true;
  });
  return [envProfile, ...storedProfiles];
}

function syncTranslationProviderMode() {
  if (!translationProviderModeSelectEl || !translationProviderSelectEl) return;
  const useAi = translationProviderModeSelectEl.value === "ai";
  translationProviderSelectEl.disabled = !useAi;
  if (!useAi) {
    translationProviderSelectEl.value = "";
    return;
  }
  if (!translationProviderSelectEl.value) {
    translationProviderSelectEl.value = state.translationProviderId || "env";
  }
}

function renderProviderOptions() {
  const options = aiProviderOptions();
  [translationProviderSelectEl, readingAssistantProviderSelectEl].forEach((selectEl) => {
    if (!selectEl) return;
    const current = selectEl === translationProviderSelectEl ? state.translationProviderId || "env" : state.readingAssistantProviderId || "env";
    selectEl.innerHTML = options
      .map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name || profile.id)}</option>`)
      .join("");
    selectEl.value = current;
    if (!selectEl.value && options.length) selectEl.value = options[0].id;
  });
  syncTranslationProviderMode();
}

function resetAiProfileForm() {
  if (aiProfileIdInputEl) aiProfileIdInputEl.value = "";
  if (aiProfileNameInputEl) aiProfileNameInputEl.value = "";
  if (aiProfileTypeSelectEl) aiProfileTypeSelectEl.value = "chat_completions";
  if (aiProfileBaseUrlInputEl) aiProfileBaseUrlInputEl.value = "";
  if (aiProfileModelInputEl) aiProfileModelInputEl.value = "";
  if (aiProfileApiKeyInputEl) aiProfileApiKeyInputEl.value = "";
  if (aiProfileHeadersInputEl) aiProfileHeadersInputEl.value = "";
  if (aiProfileTimeoutInputEl) aiProfileTimeoutInputEl.value = "45";
}

function fillAiProfileForm(profile) {
  if (!profile || profile.readonly) return;
  if (aiProfileIdInputEl) aiProfileIdInputEl.value = profile.id || "";
  if (aiProfileNameInputEl) aiProfileNameInputEl.value = profile.name || "";
  if (aiProfileTypeSelectEl) aiProfileTypeSelectEl.value = profile.type || "chat_completions";
  if (aiProfileBaseUrlInputEl) aiProfileBaseUrlInputEl.value = profile.base_url || "";
  if (aiProfileModelInputEl) aiProfileModelInputEl.value = profile.model || "";
  if (aiProfileApiKeyInputEl) aiProfileApiKeyInputEl.value = "";
  if (aiProfileHeadersInputEl) aiProfileHeadersInputEl.value = "";
  if (aiProfileTimeoutInputEl) aiProfileTimeoutInputEl.value = String(profile.timeout_seconds || 45);
}

function renderAiProfiles() {
  if (aiProfilesMetaEl) aiProfilesMetaEl.textContent = `${state.aiProfiles.length} 个配置`;
  if (!aiProfilesListEl) return;
  aiProfilesListEl.innerHTML = "";
  state.aiProfiles.forEach((profile) => {
    const row = document.createElement("div");
    row.className = "ai-profile-row";
    row.dataset.profileId = profile.id;
    const meta = [profile.type, profile.model, profile.has_api_key ? "已保存 key" : "无 key"].filter(Boolean).join(" · ");
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(profile.name || profile.id)}</strong>
        <span>${escapeHtml(meta)}</span>
      </div>
      <div class="ai-profile-actions">
        <button type="button" data-action="edit" ${profile.readonly ? "disabled" : ""}>编辑</button>
        <button type="button" data-action="test">测试</button>
        <button type="button" data-action="delete" ${profile.readonly ? "disabled" : ""}>删除</button>
      </div>
    `;
    aiProfilesListEl.appendChild(row);
  });
  renderProviderOptions();
}

async function loadAiProfiles() {
  if (!apiBaseUrl) return;
  try {
    const payload = await apiFetch("/api/ai-profiles");
    state.aiProfiles = Array.isArray(payload.items) ? payload.items : [];
    renderAiProfiles();
  } catch (err) {
    if (aiProfilesMetaEl) aiProfilesMetaEl.textContent = "AI 配置加载失败";
  }
}

function aiProfilePayload() {
  const headersText = aiProfileHeadersInputEl?.value.trim() || "";
  if (headersText) JSON.parse(headersText);
  return {
    name: aiProfileNameInputEl?.value.trim() || "",
    type: aiProfileTypeSelectEl?.value || "chat_completions",
    base_url: aiProfileBaseUrlInputEl?.value.trim() || "",
    model: aiProfileModelInputEl?.value.trim() || "",
    api_key: aiProfileApiKeyInputEl?.value || "",
    headers_json: headersText,
    timeout_seconds: Number(aiProfileTimeoutInputEl?.value || 45),
    enabled: true,
  };
}

async function saveAiProfile() {
  if (!apiBaseUrl) return;
  const profileId = aiProfileIdInputEl?.value.trim();
  let payload;
  try {
    payload = aiProfilePayload();
  } catch (_) {
    setSettingsStatus("请求头 JSON 格式错误");
    return;
  }
  const path = profileId ? `/api/ai-profiles/${encodeURIComponent(profileId)}` : "/api/ai-profiles";
  const method = profileId ? "PUT" : "POST";
  if (saveAiProfileButtonEl) saveAiProfileButtonEl.disabled = true;
  setSettingsStatus("保存 AI 配置中...");
  try {
    await apiFetch(path, { method, body: JSON.stringify(payload) });
    resetAiProfileForm();
    await loadAiProfiles();
    setSettingsStatus("AI 配置已保存");
  } catch (err) {
    setSettingsStatus(err.message || "AI 配置保存失败");
  } finally {
    if (saveAiProfileButtonEl) saveAiProfileButtonEl.disabled = false;
  }
}

async function testAiProfile(profileId = aiProfileIdInputEl?.value.trim()) {
  if (!apiBaseUrl || !profileId) {
    setSettingsStatus("请先选择或保存 AI 配置");
    return;
  }
  if (testAiProfileButtonEl) testAiProfileButtonEl.disabled = true;
  setSettingsStatus("测试连接中...");
  try {
    await apiFetch(`/api/ai-profiles/${encodeURIComponent(profileId)}/test`, { method: "POST" });
    setSettingsStatus("AI 连接正常");
  } catch (err) {
    setSettingsStatus(err.message || "AI 连接失败");
  } finally {
    if (testAiProfileButtonEl) testAiProfileButtonEl.disabled = false;
  }
}

async function deleteAiProfile(profileId) {
  if (!apiBaseUrl || !profileId) return;
  setSettingsStatus("删除 AI 配置中...");
  try {
    await apiFetch(`/api/ai-profiles/${encodeURIComponent(profileId)}`, { method: "DELETE" });
    resetAiProfileForm();
    await loadAiProfiles();
    setSettingsStatus("AI 配置已删除");
  } catch (err) {
    setSettingsStatus(err.message || "删除失败");
  }
}

async function loginAdmin() {
  if (!adminPasswordInputEl) return;
  if (!apiBaseUrl) {
    setSettingsStatus("后端未配置");
    return;
  }
  const password = adminPasswordInputEl.value.trim();
  if (!password) {
    setSettingsStatus("请输入密码");
    return;
  }
  if (loginButtonEl) loginButtonEl.disabled = true;
  setSettingsStatus("登录中...");
  try {
    await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    adminPasswordInputEl.value = "";
    setSettingsStatus("已登录");
    await loadSettings();
  } catch (err) {
    setSettingsStatus(err.message || "登录失败");
  } finally {
    if (loginButtonEl) loginButtonEl.disabled = false;
  }
}

async function loadSettings() {
  if (!apiBaseUrl) {
    setSettingsStatus("后端未配置");
    return null;
  }
  try {
    await apiFetch("/api/me");
    const settings = await apiFetch("/api/settings");
    applySettings(settings);
    await loadAiProfiles();
    await loadPersonalization({ autoOpen: true });
    setSettingsStatus("已登录");
    return settings;
  } catch (_) {
    setSettingsStatus("未登录");
    return null;
  }
}

async function saveSettings() {
  if (!apiBaseUrl) {
    setSettingsStatus("后端未配置");
    return;
  }
  const topN = Math.max(1, Math.min(10, Number(deepVerificationTopNEl?.value || 3)));
  const translationMode = translationProviderModeSelectEl?.value || "browser";
  if (saveSettingsButtonEl) saveSettingsButtonEl.disabled = true;
  setSettingsStatus("保存中...");
  try {
    const settings = await apiFetch("/api/settings", {
      method: "PUT",
      body: JSON.stringify({
        deep_verification_enabled: Boolean(deepVerificationToggleEl?.checked),
        deep_verification_scope: "bole_picks_and_topic_top_n",
        deep_verification_top_n: topN,
        ask_streaming_enabled: Boolean(askStreamingToggleEl?.checked),
        ask_system_prompt: askSystemPromptInputEl?.value || "",
        translation_provider_mode: translationMode,
        translation_provider_id: translationMode === "ai" ? translationProviderSelectEl?.value || "env" : "",
        reading_assistant_provider_id: readingAssistantProviderSelectEl?.value || "env",
        bole_conflict_strategy: boleConflictStrategySelectEl?.value || "ask",
      }),
    });
    applySettings(settings);
    setSettingsStatus("已保存");
  } catch (err) {
    setSettingsStatus(err.message || "保存失败");
  } finally {
    if (saveSettingsButtonEl) saveSettingsButtonEl.disabled = false;
  }
}

function fmtTime(iso) {
  if (!iso) return "时间未知";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

function fmtDate(iso) {
  if (!iso) return "未知日期";
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

function setStats(payload) {
  const cards = [
    ["AI 信号", fmtNumber(payload.total_items)],
    ["站点数", fmtNumber(payload.site_count)],
    ["来源分组", fmtNumber(payload.source_count)],
    ["归档", fmtNumber(payload.archive_total || 0)]
  ];

  statsEl.innerHTML = "";
  cards.forEach(([k, v]) => {
    const node = document.createElement("div");
    node.className = "stat";
    node.innerHTML = `<div class="k">${k}</div><div class="v">${v}</div>`;
    statsEl.appendChild(node);
  });
}

function sourceKind(siteId) {
  return SOURCE_KINDS[siteId] || { label: "来源", tone: "default" };
}

function siteRows() {
  return Array.isArray(state.sourceStatus?.sites) ? state.sourceStatus.sites : [];
}

function siteRow(siteId) {
  return siteRows().find((site) => site.site_id === siteId) || null;
}

function renderCoverageCard(label, value, meta, tone = "") {
  const node = document.createElement("div");
  node.className = `coverage-card ${tone}`.trim();
  const labelEl = document.createElement("span");
  labelEl.className = "coverage-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.textContent = value;
  const metaEl = document.createElement("span");
  metaEl.className = "coverage-meta";
  metaEl.textContent = meta;
  node.append(labelEl, valueEl, metaEl);
  return node;
}

function renderCoverageStrip(errorMessage = "") {
  if (!coverageStripEl) return;
  coverageStripEl.innerHTML = "";

  const rows = siteRows();
  const failedSites = Array.isArray(state.sourceStatus?.failed_sites) ? state.sourceStatus.failed_sites : [];
  const rss = state.sourceStatus?.rss_opml || {};
  const agentmail = state.sourceStatus?.agentmail || {};
  const xApi = state.sourceStatus?.x_api || {};
  const allCount = Number(state.sourceStatus?.items_before_topic_filter || state.totalAllMode || state.itemsAll.length || 0);
  const coverageCount = Number(state.sourceStatus?.fetched_raw_items || state.totalRaw || allCount || 0);
  const officialCount = Number(siteRow("official_ai")?.item_count || 0);
  const newsletterCount = Number(siteRow("aibreakfast")?.item_count || 0);
  const buildersCount = Number(siteRow("followbuilders")?.item_count || 0);
  const totalSites = rows.length;
  const okSites = Number(state.sourceStatus?.successful_sites || 0);
  const opmlValue = rss.enabled ? `${fmtNumber(rss.ok_feeds || 0)}/${fmtNumber(rss.effective_feed_total || 0)}` : "OPML";
  const opmlMeta = rss.enabled ? "RSS示例/自定义订阅已接入" : "可用OPML批量接入RSS";
  const xApiLabel = xApi.enabled ? `X ${xApi.skipped ? "待窗口" : fmtNumber(xApi.item_count || 0)}` : "X待配置";
  const mailLabel = agentmail.enabled ? `Mail ${fmtNumber(agentmail.item_count || 0)}` : "Mail待配置";
  const advancedMeta = xApi.enabled || agentmail.enabled
    ? `额度保护 · ${xApiLabel} / ${mailLabel}`
    : "X API 与 AgentMail 默认关闭";

  const cards = [
    ["源健康", totalSites ? `${fmtNumber(okSites)}/${fmtNumber(totalSites)}` : "加载中", failedSites.length ? `${fmtNumber(failedSites.length)} 个失败源` : (errorMessage || "内置源正常"), failedSites.length ? "warn" : "ok"],
    ["今日覆盖池", `${fmtNumber(coverageCount)} 条`, allCount ? `全网抓取原始信号 · ${fmtNumber(allCount)} 条入池` : "全网抓取原始信号", "signal"],
    ["AI强相关", `${fmtNumber(state.totalAi)} 条`, "24小时强相关信号", "signal"],
    ["官方/日报源池", `${fmtNumber(officialCount + newsletterCount)} 条`, "官方节点 + AI Breakfast", "official"],
    ["Builders/X源池", `${fmtNumber(buildersCount)} 条`, "Follow Builders公开feed", "builders"],
    ["RSS/OPML扩展", opmlValue, opmlMeta, "private"],
    ["高级源", "X / Mail", advancedMeta, "private"],
  ];

  cards.forEach(([label, value, meta, tone]) => {
    coverageStripEl.appendChild(renderCoverageCard(label, value, meta, tone));
  });
}

function renderAdvancedSummary() {
  if (!advancedSummaryEl) return;
  const status = state.sourceStatus;
  const allCount = state.allDedup
    ? (state.totalAllMode || state.itemsAll.length)
    : (state.totalRaw || state.itemsAllRaw.length);
  if (!status) {
    advancedSummaryEl.textContent = `全量 ${fmtNumber(allCount)} 条`;
    return;
  }
  const sites = Array.isArray(status.sites) ? status.sites : [];
  const totalSites = sites.length;
  const okSites = Number(status.successful_sites || 0);
  advancedSummaryEl.textContent = `${fmtNumber(okSites)}/${fmtNumber(totalSites)} 源可用 · 全量 ${fmtNumber(allCount)} 条`;
}

function computeSiteStats(items) {
  const m = new Map();
  items.forEach((item) => {
    if (!m.has(item.site_id)) {
      m.set(item.site_id, { site_id: item.site_id, site_name: item.site_name, count: 0, raw_count: 0 });
    }
    const row = m.get(item.site_id);
    row.count += 1;
    row.raw_count += 1;
  });
  return Array.from(m.values()).sort((a, b) => b.count - a.count || a.site_name.localeCompare(b.site_name, "zh-CN"));
}

function currentSiteStats() {
  if (state.mode === "ai") return state.statsAi || [];
  return computeSiteStats(state.allDedup ? (state.itemsAll || []) : (state.itemsAllRaw || []));
}

function renderSiteFilters() {
  const stats = currentSiteStats();

  siteSelectEl.innerHTML = '<option value="">全部站点</option>';
  stats.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.site_id;
    const raw = s.raw_count ?? s.count;
    opt.textContent = `${s.site_name} (${s.count}/${raw})`;
    siteSelectEl.appendChild(opt);
  });
  siteSelectEl.value = state.siteFilter;

  sitePillsEl.innerHTML = "";
  const allPill = document.createElement("button");
  allPill.className = `pill ${state.siteFilter === "" ? "active" : ""}`;
  allPill.textContent = "全部";
  allPill.onclick = () => {
    state.siteFilter = "";
    renderSiteFilters();
    renderList();
  };
  sitePillsEl.appendChild(allPill);

  stats.forEach((s) => {
    const btn = document.createElement("button");
    btn.className = `pill ${state.siteFilter === s.site_id ? "active" : ""}`;
    const raw = s.raw_count ?? s.count;
    btn.textContent = `${s.site_name} ${s.count}/${raw}`;
    btn.onclick = () => {
      state.siteFilter = s.site_id;
      renderSiteFilters();
      renderList();
    };
    sitePillsEl.appendChild(btn);
  });
}

function renderModeSwitch() {
  modeAiBtnEl.classList.toggle("active", state.mode === "ai");
  modeAllBtnEl.classList.toggle("active", state.mode === "all");
  if (allDedupeWrapEl) allDedupeWrapEl.classList.toggle("show", state.mode === "all");
  if (allDedupeToggleEl) allDedupeToggleEl.checked = state.allDedup;
  if (allDedupeLabelEl) allDedupeLabelEl.textContent = state.allDedup ? "去重开" : "去重关";
  if (state.mode === "ai") {
    modeHintEl.textContent = `AI强相关 · ${fmtNumber(state.totalAi)} 条`;
    if (listTitleEl) listTitleEl.textContent = "AI 信号流";
  } else {
    const allCount = state.allDedup
      ? (state.totalAllMode || state.itemsAll.length)
      : (state.totalRaw || state.itemsAllRaw.length);
    modeHintEl.textContent = `全量 · ${state.allDedup ? "去重开" : "去重关"} · ${fmtNumber(allCount)} 条`;
    if (listTitleEl) listTitleEl.textContent = "全量更新";
  }
  renderAdvancedSummary();
}

function effectiveAllItems() {
  return state.allDedup ? state.itemsAll : state.itemsAllRaw;
}

function modeItems() {
  return state.mode === "all" ? effectiveAllItems() : state.itemsAi;
}

function normalizeTaxonomy(taxonomy) {
  if (!Array.isArray(taxonomy) || !taxonomy.length) return fallbackTaxonomy;
  if (taxonomy.some((row) => Array.isArray(row.children))) {
    return taxonomy.map((row) => ({
      id: row.id || row.label,
      label: row.label || row.id,
      children: Array.isArray(row.children) ? row.children : [],
    }));
  }

  const childrenByParent = new Map();
  taxonomy.forEach((row) => {
    if (!row.parent_id) return;
    if (!childrenByParent.has(row.parent_id)) childrenByParent.set(row.parent_id, []);
    childrenByParent.get(row.parent_id).push({ id: row.id, label: row.label });
  });
  return taxonomy
    .filter((row) => !row.parent_id)
    .map((row) => ({
      id: row.id,
      label: row.label,
      children: childrenByParent.get(row.id) || [],
    }));
}

async function loadTaxonomy() {
  if (!apiBaseUrl) return fallbackTaxonomy;
  try {
    const payload = await apiFetch("/api/taxonomy");
    return payload.categories || fallbackTaxonomy;
  } catch (_) {
    return fallbackTaxonomy;
  }
}

function itemCategory(item) {
  const direct = item.top_category || "";
  if (direct) return direct;
  const mapped = legacyCategoryMap[item.ai_label] || null;
  return mapped ? mapped.top : (item.ai_label || "");
}

function itemSubCategory(item) {
  const direct = item.sub_category || "";
  if (direct) return direct;
  const mapped = legacyCategoryMap[item.ai_label] || null;
  return mapped ? mapped.sub : "";
}

function renderCategoryView(taxonomy, items) {
  if (!categoryGridEl || !categoryDetailEl || !categoryMetaEl) return;
  const groups = normalizeTaxonomy(taxonomy);
  const rows = Array.isArray(items) ? items : [];
  const categoryRows = groups.map((category) => ({
    category,
    items: rows.filter((item) => itemCategory(item) === category.label),
  }));
  const firstAvailable = categoryRows.find((row) => row.items.length);
  if (!state.categoryFilter || !categoryRows.some((row) => row.category.label === state.categoryFilter && row.items.length)) {
    state.categoryFilter = firstAvailable?.category.label || "";
  }
  const selected = categoryRows.find((row) => row.category.label === state.categoryFilter) || firstAvailable;
  categoryGridEl.innerHTML = "";
  categoryDetailEl.innerHTML = "";
  categoryMetaEl.textContent = selected
    ? `${selected.category.label} · ${fmtNumber(selected.items.length)} 条`
    : `${fmtNumber(rows.length)} 条信号`;

  categoryRows.forEach(({ category, items: categoryItems }) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "category-card";
    card.classList.toggle("active", state.categoryFilter === category.label);
    card.dataset.category = category.label;
    const title = document.createElement("strong");
    title.textContent = category.label;
    const count = document.createElement("span");
    count.textContent = `${fmtNumber(categoryItems.length)} 条`;
    card.append(title, count);
    card.disabled = categoryItems.length === 0;
    categoryGridEl.appendChild(card);

    card.addEventListener("click", () => {
      state.categoryFilter = category.label;
      renderCategoryView(taxonomy, rows);
      categoryDetailEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  renderCategoryResultList(selected?.category || null, selected?.items || []);
}

function renderCategoryResultList(category, categoryItems) {
  categoryDetailEl.innerHTML = "";
  if (!category) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "当前没有可展示的分类新闻。";
    categoryDetailEl.appendChild(empty);
    return;
  }
  const detail = document.createElement("section");
  detail.className = "category-detail-group";
  const head = document.createElement("div");
  head.className = "category-detail-head";
  const heading = document.createElement("h3");
  heading.textContent = category.label;
  const meta = document.createElement("span");
  meta.textContent = `${fmtNumber(categoryItems.length)} 条新闻`;
  head.append(heading, meta);
  detail.appendChild(head);

  const childRows = (category.children || [])
    .map((child) => {
      const matched = categoryItems.filter((item) => itemSubCategory(item) === child.label);
      return { child, matched };
    })
    .filter((row) => row.matched.length);

  if (childRows.length) {
    const subWrap = document.createElement("div");
    subWrap.className = "subcategory-summary";
    childRows.forEach(({ child, matched }) => {
      const row = document.createElement("div");
      row.className = "subcategory-row";
      const name = document.createElement("span");
      name.textContent = child.label;
      const value = document.createElement("strong");
      value.textContent = fmtNumber(matched.length);
      row.append(name, value);
      subWrap.appendChild(row);
    });
    detail.appendChild(subWrap);
  }

  const list = document.createElement("div");
  list.className = "category-news-list";
  categoryItems.forEach((item) => {
    list.appendChild(renderItemNode(item));
  });
  detail.appendChild(list);
  categoryDetailEl.appendChild(detail);
}

function itemIdentity(item) {
  return item.item_id || item.id || item.url || itemTitleText(item);
}

function normalizePublicUrl(url) {
  try {
    const parsed = new URL(String(url || "").trim());
    if (!parsed.protocol || !parsed.host) return String(url || "").trim();
    const params = new URLSearchParams(parsed.search);
    Array.from(params.keys()).forEach((key) => {
      const lower = key.toLowerCase();
      if (lower.startsWith("utm_") || ["fbclid", "gclid", "igshid", "mc_cid", "mc_eid"].includes(lower)) {
        params.delete(key);
      }
    });
    parsed.protocol = parsed.protocol.toLowerCase();
    parsed.hostname = parsed.hostname.toLowerCase();
    parsed.hash = "";
    parsed.search = params.toString();
    if (parsed.pathname !== "/") parsed.pathname = parsed.pathname.replace(/\/+$/, "");
    return parsed.toString();
  } catch (_) {
    return String(url || "").trim();
  }
}

async function sha1Hex(text) {
  const encoder = new TextEncoder();
  const digest = await window.crypto.subtle.digest("SHA-1", encoder.encode(text));
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function readerItemId(item) {
  if (item.item_id || item.id) return item.item_id || item.id;
  const url = normalizePublicUrl(item.url || "");
  if (!url || !window.crypto?.subtle) return itemIdentity(item);
  return sha1Hex(url);
}

function closeReader() {
  if (!readerSheetEl) return;
  closeReaderFeedbackPopover();
  if (readerCloseTimer) window.clearTimeout(readerCloseTimer);
  if (readerSheetEl.hidden || !readerPanelEl) {
    finishCloseReader();
    return;
  }
  readerPanelEl.classList.remove("dragging");
  readerPanelEl.classList.add("settling");
  readerPanelEl.style.setProperty("--reader-drag-y", "100vh");
  document.body.classList.remove("reader-open");
  readerCloseTimer = window.setTimeout(finishCloseReader, 220);
}

function renderReaderLoading(item) {
  state.readerArticle = null;
  state.readerOriginalHtml = "";
  state.readerOriginalText = "";
  state.readerTranslatedHtml = "";
  state.readerShowingTranslation = false;
  if (readerTitleEl) readerTitleEl.textContent = itemTitleText(item);
  if (readerSourceEl) readerSourceEl.textContent = item.site_name || item.source || "AI News Radar";
  if (readerOriginalLinkEl) {
    readerOriginalLinkEl.href = item.url || "#";
    readerOriginalLinkEl.hidden = !item.url;
  }
  if (readerTranslateButtonEl) {
    readerTranslateButtonEl.hidden = true;
    readerTranslateButtonEl.disabled = false;
    readerTranslateButtonEl.textContent = "翻译";
  }
  if (readerAccessBadgeEl) {
    readerAccessBadgeEl.hidden = true;
    readerAccessBadgeEl.textContent = "";
  }
  if (readerBodyEl) {
    readerBodyEl.innerHTML = '<div class="reader-state">正在清洗原文...</div>';
    readerBodyEl.lang = "";
    readerBodyEl.setAttribute("translate", "yes");
  }
}

function isReaderTranslationAvailable(payload) {
  const language = String(payload?.language || "").trim().toLowerCase();
  if (payload?.translation_available === true) return true;
  if (payload?.translation_available === false) return false;
  return Boolean(language && !["unknown", "zh", "zh-cn", "zh-tw"].includes(language));
}

function renderReaderArticle(payload) {
  if (!readerBodyEl) return;
  state.readerArticle = payload;
  if (readerTitleEl) readerTitleEl.textContent = payload.title || itemTitleText(payload.item || {});
  if (readerSourceEl) {
    const meta = [payload.site_name, payload.published_at ? fmtTime(payload.published_at) : "", payload.cache_status === "hit" ? "已缓存" : "新抓取"]
      .filter(Boolean)
      .join(" · ");
    readerSourceEl.textContent = meta || "AI News Radar";
  }
  if (readerOriginalLinkEl) readerOriginalLinkEl.href = payload.final_url || payload.url || "#";
  if (readerTranslateButtonEl) {
    readerTranslateButtonEl.hidden = !isReaderTranslationAvailable(payload);
    readerTranslateButtonEl.disabled = false;
    readerTranslateButtonEl.textContent = "翻译";
  }
  if (readerAccessBadgeEl) {
    readerAccessBadgeEl.hidden = !payload.access_status || payload.access_status === "open";
    readerAccessBadgeEl.textContent = payload.access_label || "暂时无法清洗原文";
  }
  readerBodyEl.lang = payload.language || "";
  readerBodyEl.setAttribute("translate", "yes");
  readerBodyEl.innerHTML = payload.content_html || `<p>${escapeHtml(payload.text || "未能提取正文。")}</p>`;
  state.readerOriginalHtml = readerBodyEl.innerHTML;
  state.readerOriginalText = payload.text || readerBodyEl.textContent || "";
  state.readerTranslatedHtml = "";
  state.readerShowingTranslation = false;
}

function cleanedTextForTranslation() {
  const text = (state.readerArticle?.text || readerBodyEl?.textContent || "").trim();
  return text.replace(/\s+/g, " ").slice(0, 4800);
}

async function requestCleanTextTranslation(text, sourceLanguage) {
  const payload = await apiFetch("/api/translate", {
    method: "POST",
    body: JSON.stringify({
      text,
      source_language: sourceLanguage || "auto",
    }),
  });
  return String(payload.translation || "").trim();
}

function renderTranslatedReaderArticle(translatedText) {
  if (!readerBodyEl) return;
  const blocks = String(translatedText || "")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
  readerBodyEl.innerHTML = blocks.length
    ? blocks.map((block) => `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`).join("")
    : "<p>未能生成译文。</p>";
  state.readerTranslatedHtml = readerBodyEl.innerHTML;
  state.readerShowingTranslation = true;
  readerBodyEl.lang = "zh";
  if (readerTranslateButtonEl) {
    readerTranslateButtonEl.textContent = "原文";
    readerTranslateButtonEl.disabled = false;
  }
}

function showOriginalReaderArticle() {
  if (!readerBodyEl || !state.readerOriginalHtml) return;
  readerBodyEl.innerHTML = state.readerOriginalHtml;
  readerBodyEl.lang = state.readerArticle?.language || "";
  state.readerShowingTranslation = false;
  if (readerTranslateButtonEl) {
    readerTranslateButtonEl.textContent = "中文";
    readerTranslateButtonEl.disabled = false;
  }
}

function showTranslatedReaderArticle() {
  if (!readerBodyEl || !state.readerTranslatedHtml) return;
  readerBodyEl.innerHTML = state.readerTranslatedHtml;
  readerBodyEl.lang = "zh";
  state.readerShowingTranslation = true;
  if (readerTranslateButtonEl) {
    readerTranslateButtonEl.textContent = "原文";
    readerTranslateButtonEl.disabled = false;
  }
}

async function translateReaderArticle() {
  if (!readerBodyEl || !readerTranslateButtonEl) return;
  if (state.readerShowingTranslation) {
    showOriginalReaderArticle();
    return;
  }
  if (state.readerTranslatedHtml) {
    showTranslatedReaderArticle();
    return;
  }
  const sourceLanguage = state.readerArticle?.language || readerBodyEl.lang || "en";
  readerBodyEl.setAttribute("translate", "yes");
  readerTranslateButtonEl.disabled = true;
  readerTranslateButtonEl.textContent = "翻译中";
  state.translationProviderMode = translationProviderModeSelectEl?.value || state.translationProviderMode;
  state.translationProviderId = translationProviderSelectEl?.value || state.translationProviderId;
  if (state.translationProviderMode !== "ai") {
    const translatorAvailable = window.Translator?.availability
      ? await window.Translator.availability({ sourceLanguage, targetLanguage: "zh" }).catch(() => "unavailable")
      : "unknown";
    if (window.Translator?.create && translatorAvailable !== "unavailable") {
      try {
        const translator = await window.Translator.create({
          sourceLanguage,
          targetLanguage: "zh",
        });
        const nodes = Array.from(readerBodyEl.querySelectorAll("h2, h3, p, li, blockquote"))
          .filter((node) => node.textContent.trim());
        for (const node of nodes) {
          node.textContent = await translator.translate(node.textContent);
        }
        state.readerTranslatedHtml = readerBodyEl.innerHTML;
        state.readerShowingTranslation = true;
        readerBodyEl.lang = "zh";
        readerTranslateButtonEl.textContent = "原文";
        readerTranslateButtonEl.disabled = false;
        return;
      } catch (_) {
        // Fall through to a visible failure state below.
      }
    }
    readerTranslateButtonEl.textContent = "翻译失败";
    readerTranslateButtonEl.title = "当前浏览器未提供可调用的内置翻译能力";
    readerTranslateButtonEl.disabled = false;
    return;
  }
  try {
    await saveSettings();
    const translatedText = await requestCleanTextTranslation(cleanedTextForTranslation(), sourceLanguage);
    renderTranslatedReaderArticle(translatedText);
  } catch (err) {
    readerTranslateButtonEl.textContent = "翻译失败";
    readerTranslateButtonEl.title = err.message || "翻译失败";
    readerTranslateButtonEl.disabled = false;
  }
}

async function readerAskContext() {
  const article = state.readerArticle || {};
  const item = state.readerItem || article.item || article || {};
  return {
    item_id: await readerItemId(item),
    item_title: article.title || itemTitleText(item),
  };
}

async function openAskAiForReaderArticle(question) {
  openAskAi(await readerAskContext());
  await submitAskPresetQuestion(question);
}

async function summarizeReaderArticle() {
  await openAskAiForReaderArticle(READER_SUMMARY_PROMPT);
}

async function factCheckReaderArticle() {
  await openAskAiForReaderArticle(READER_FACT_CHECK_PROMPT);
}

async function loadCleanArticle(item, cacheKey = "") {
  if (!apiBaseUrl) throw new Error("AI 后端未配置，暂时无法清洗原文。");
  const id = cacheKey || (await readerItemId(item));
  if (state.readerArticleCache.has(id)) {
    const cached = state.readerArticleCache.get(id);
    return { ...cached, cache_status: "hit", item: item || cached.item };
  }
  if (state.readerArticleRequests.has(id)) {
    return state.readerArticleRequests.get(id);
  }
  const request = apiFetch(`/api/read/${encodeURIComponent(id)}`)
    .then((payload) => {
      const article = { ...payload, item: payload.item || item };
      state.readerArticleCache.set(id, article);
      return article;
    })
    .finally(() => {
      state.readerArticleRequests.delete(id);
    });
  state.readerArticleRequests.set(id, request);
  return request;
}

async function openReader(item) {
  if (!readerSheetEl) return;
  if (readerCloseTimer) window.clearTimeout(readerCloseTimer);
  closeReaderFeedbackPopover();
  state.readerItem = item;
  const id = await readerItemId(item);
  state.readerArticleKey = id;
  resetReaderPanelDrag();
  if (state.readerArticleCache.has(id)) {
    const cached = state.readerArticleCache.get(id);
    renderReaderArticle({ ...cached, cache_status: "hit", item });
  } else {
    renderReaderLoading(item);
  }
  readerSheetEl.hidden = false;
  document.body.classList.add("reader-open");
  if (state.readerArticleCache.has(id)) return;
  try {
    const payload = await loadCleanArticle(item, id);
    if (state.readerArticleKey !== id) return;
    renderReaderArticle(payload);
  } catch (err) {
    if (state.readerArticleKey !== id) return;
    if (readerBodyEl) {
      readerBodyEl.innerHTML = `
        <div class="reader-state reader-error">
          <strong>暂时读不到干净正文</strong>
          <p>${escapeHtml(err.message || "文章读取失败。")}</p>
        </div>
      `;
    }
  }
}

function bindReaderLink(linkEl, item) {
  if (!linkEl) return;
  linkEl.href = item.url || "#";
  linkEl.removeAttribute("target");
  linkEl.rel = "noopener noreferrer";
  linkEl.addEventListener("click", (event) => {
    event.preventDefault();
    openReader(item);
  });
}

async function loadVerificationSummary() {
  if (!apiBaseUrl) return { items: [], unavailable: true };
  try {
    return await apiFetch("/api/verification/items");
  } catch (err) {
    return { items: [], unavailable: true, error: err.message };
  }
}

async function loadOptionalBackendData() {
  const [taxonomyResult, verificationResult] = await Promise.allSettled([
    loadTaxonomy(),
    loadVerificationSummary(),
  ]);
  state.taxonomy = taxonomyResult.status === "fulfilled" ? taxonomyResult.value : fallbackTaxonomy;
  state.verificationPayload = verificationResult.status === "fulfilled"
    ? verificationResult.value
    : { items: [], unavailable: true, error: verificationResult.reason?.message || "核验数据加载失败" };
  renderCategoryView(state.taxonomy, state.itemsAi);
  renderVerificationView(state.verificationPayload);
}

async function deepVerifyItem(itemId, item = null) {
  return apiFetch(`/api/verification/${encodeURIComponent(itemId)}/deep-verify`, {
    method: "POST",
    body: JSON.stringify(item ? { item } : {}),
  });
}

function verifiedStatus(item) {
  const score = Number(item.authority_score ?? -1);
  if (score >= 85) return "一手来源";
  if (score >= 70) return "可参考";
  if (score >= 0) return "低可信";
  return "待核验";
}

function renderVerificationMetric(label, value, tone = "") {
  const node = document.createElement("div");
  node.className = `verification-metric ${tone}`.trim();
  const labelEl = document.createElement("span");
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.textContent = value;
  node.append(labelEl, valueEl);
  return node;
}

function renderVerificationView(payload) {
  if (!verificationSummaryEl || !verificationListEl || !verificationMetaEl) return;
  const backendItems = Array.isArray(payload?.items) ? payload.items : [];
  const fallbackItems = backendItems.length ? backendItems : (state.itemsAi || []).slice(0, 12);
  const unavailable = Boolean(payload?.unavailable);
  const lowTrust = backendItems.filter((item) => Number(item.authority_score ?? 100) < 70);
  const deepQueue = fallbackItems.filter((item) => !item.deep_verified).slice(0, 8);
  const firstParty = backendItems.filter((item) => Number(item.authority_score ?? 0) >= 85);
  const thirdParty = backendItems.filter((item) => Number(item.authority_score ?? -1) >= 0 && Number(item.authority_score ?? 0) < 85);

  verificationMetaEl.textContent = unavailable
    ? (payload?.error || "未连接后端")
    : `${fmtNumber(backendItems.length)} 条核验记录`;

  verificationSummaryEl.innerHTML = "";
  verificationSummaryEl.append(
    renderVerificationMetric("待核验", fmtNumber(deepQueue.length), "watch"),
    renderVerificationMetric("低可信", fmtNumber(lowTrust.length), lowTrust.length ? "warn" : "ok"),
    renderVerificationMetric("深度核验队列", fmtNumber(deepQueue.length)),
    renderVerificationMetric("第三方信源评分", fmtNumber(thirdParty.length)),
    renderVerificationMetric("一手来源覆盖", fmtNumber(firstParty.length), firstParty.length ? "ok" : "")
  );

  verificationListEl.innerHTML = "";
  const sections = [
    ["待核验", deepQueue],
    ["低可信", lowTrust],
    ["深度核验队列", deepQueue],
    ["第三方信源评分", thirdParty],
    ["一手来源覆盖", firstParty],
  ];
  sections.forEach(([title, items]) => {
    const section = document.createElement("section");
    section.className = "verification-section";
    const head = document.createElement("div");
    head.className = "verification-section-head";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const count = document.createElement("span");
    count.textContent = `${fmtNumber(items.length)} 条`;
    head.append(heading, count);
    section.appendChild(head);

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "verification-empty";
      empty.textContent = unavailable ? "连接后端后可查看。" : "暂无条目。";
      section.appendChild(empty);
    } else {
      items.slice(0, 5).forEach((item) => {
        const row = document.createElement("div");
        row.className = "verification-row";
        const titleEl = document.createElement("a");
        titleEl.href = item.url || "#";
        titleEl.target = "_blank";
        titleEl.rel = "noopener noreferrer";
        titleEl.textContent = itemTitleText(item);
        const meta = document.createElement("span");
        meta.textContent = `${verifiedStatus(item)} · ${item.authority_score ?? "--"} 分`;
        row.append(titleEl, meta);
        section.appendChild(row);
      });
    }
    verificationListEl.appendChild(section);
  });
}

function getFilteredItems() {
  const q = state.query.trim().toLowerCase();
  return modeItems().filter((item) => {
    const siteId = item.site_id || "";
    const source = item.source || "未分区";
    if (isSiteHidden(siteId)) return false;
    if (isSourceHidden(siteId, source)) return false;
    if (state.siteFilter && item.site_id !== state.siteFilter) return false;
    if (!q) return true;
    const hay = `${item.title || ""} ${item.title_zh || ""} ${item.title_en || ""} ${item.site_name || ""} ${item.source || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function itemTitleText(item) {
  return (item.title_zh || item.title || item.title_en || "未命名更新").trim();
}

function boleFeedbackItemKey(item) {
  if (!item || typeof item !== "object") return "";
  return String(item.item_id || item.id || item.url || itemTitleText(item)).trim();
}

function boleFeedbackActionLabel(action) {
  const labels = {
    more_relevant: "更相关",
    more_like_this: "多看类似",
    less_relevant: "少看类似",
    not_interested: "不感兴趣",
  };
  return labels[action] || "已反馈";
}

function boleFeedbackAdjustment(action) {
  if (action === "more_like_this") return 24;
  if (action === "more_relevant") return 16;
  if (action === "less_relevant") return -18;
  if (action === "not_interested") return -34;
  return 0;
}

const BOLE_FEEDBACK_DEFAULT_ACTION_ORDER = ["more_like_this", "less_relevant", "not_interested"];
const BOLE_FEEDBACK_GENERIC_TARGET = "整条新闻";
const BOLE_FEEDBACK_TOPIC_SORT_KEYS = {
  Agent: "agent",
  OpenAI: "openai",
  Anthropic: "anthropic",
  Google: "google",
  Microsoft: "microsoft",
  Amazon: "amazon",
  Meta: "meta",
  NVIDIA: "nvidia",
  GitHub: "github",
  "Code AI": "code ai",
  "RAG / 知识库": "rag zhishiku",
  本地部署: "bendibushu",
  多模态: "duomotai",
  开源模型: "kaiyuanmoxing",
  "AI 搜索": "ai sousuo",
  产品与工具: "chanpin gongju",
  模型能力: "moxing nengli",
  开发者集成: "kaifazhe jicheng",
  研究学习: "yanjiu xuexi",
  行业影响: "hangye yingxiang",
  商业信号: "shangye xinhao",
  纯融资快讯: "rongzi",
  融资: "rongzi",
  营销稿: "yingxiao",
  重复转载: "chongfu",
  空泛观点: "kongfan",
  过度学术: "xueshu",
  浅层汇总: "huizong",
  整条新闻: "zhengwen",
};

const BOLE_FEEDBACK_EXTRA_TARGET_ALIASES = {
  OpenAI: ["openai", "chatgpt", "gpt", "sam altman"],
  Anthropic: ["anthropic", "claude"],
  Google: ["google", "gemini", "deepmind"],
  Microsoft: ["microsoft", "copilot"],
  Amazon: ["amazon", "aws"],
  Meta: ["meta", "llama"],
  NVIDIA: ["nvidia", "cuda"],
  GitHub: ["github"],
  融资: ["融资", "funding", "capital", "投资", "raises"],
  营销稿: ["营销", "marketing", "sponsored"],
};

function ensureBoleFeedbackFilters() {
  if (!state.boleFeedbackFilters || typeof state.boleFeedbackFilters !== "object") {
    state.boleFeedbackFilters = {};
  }
  const filters = state.boleFeedbackFilters;
  filters.query = String(filters.query || "");
  filters.topic = String(filters.topic || "");
  filters.action = String(filters.action || "");
  filters.sort = ["time", "topic", "action"].includes(filters.sort) ? filters.sort : "time";
  filters.actionOrder = Array.isArray(filters.actionOrder) && filters.actionOrder.length
    ? filters.actionOrder.filter((action) => BOLE_FEEDBACK_DEFAULT_ACTION_ORDER.includes(action))
    : [...BOLE_FEEDBACK_DEFAULT_ACTION_ORDER];
  BOLE_FEEDBACK_DEFAULT_ACTION_ORDER.forEach((action) => {
    if (!filters.actionOrder.includes(action)) filters.actionOrder.push(action);
  });
  return filters;
}

function boleFeedbackRecordId(feedback) {
  if (!feedback || typeof feedback !== "object") return "";
  const id = String(feedback.id || feedback.local_id || "").trim();
  if (id) return id;
  const key = String(feedback.item_key || boleFeedbackItemKey(feedback.item)).trim();
  return key ? `session:${key}` : "";
}

function boleFeedbackIsServerId(id) {
  const value = String(id || "");
  return Boolean(value) && !value.startsWith("session:");
}

function boleFeedbackTombstoneKeys(feedback) {
  const keys = [];
  const id = boleFeedbackRecordId(feedback);
  const itemKey = feedback?.item_key || boleFeedbackItemKey(feedback?.item);
  if (id) keys.push(`id:${id}`);
  if (itemKey) keys.push(`item:${itemKey}`);
  return keys;
}

function isBoleFeedbackTombstoned(feedback) {
  if (!state.boleFeedbackUndoTombstones) state.boleFeedbackUndoTombstones = new Set();
  return boleFeedbackTombstoneKeys(feedback).some((key) => state.boleFeedbackUndoTombstones.has(key));
}

function rememberBoleFeedbackUndo(feedback) {
  if (!state.boleFeedbackUndoTombstones) state.boleFeedbackUndoTombstones = new Set();
  boleFeedbackTombstoneKeys(feedback).forEach((key) => state.boleFeedbackUndoTombstones.add(key));
}

function clearBoleFeedbackUndo(feedback) {
  if (!state.boleFeedbackUndoTombstones) state.boleFeedbackUndoTombstones = new Set();
  boleFeedbackTombstoneKeys(feedback).forEach((key) => state.boleFeedbackUndoTombstones.delete(key));
}

function boleFeedbackSemanticText(item) {
  if (!item || typeof item !== "object") return "";
  const signals = Array.isArray(item.ai_signals) ? item.ai_signals.join(" ") : "";
  const tags = Array.isArray(item.ai_tags) ? item.ai_tags.join(" ") : "";
  return [
    item.title,
    item.title_zh,
    item.title_en,
    item.summary,
    item.description,
    item.ai_label,
    signals,
    tags,
  ].filter(Boolean).join(" ").toLowerCase();
}

function boleFeedbackKnownTargetLabels() {
  return [...Object.keys(BOLE_FEEDBACK_EXTRA_TARGET_ALIASES), ...Object.keys(BOLE_PROFILE_LABEL_ALIASES || {})];
}

function boleFeedbackMatchedTargetLabels(feedback) {
  const labels = [];
  const add = (label) => {
    const value = String(label || "").trim();
    if (!value || isBoleFeedbackGenericTarget(value) || labels.includes(value)) return;
    labels.push(value);
  };
  add(feedback?.target || feedback?.topic || feedback?.item?.feedback_target);
  const item = feedback?.item || {};
  const storedTargets = Array.isArray(item.matched_targets) ? item.matched_targets : [];
  storedTargets.forEach(add);
  const signals = Array.isArray(item.ai_signals) ? item.ai_signals.map((signal) => String(signal || "").trim()).filter(Boolean) : [];
  const knownLabels = boleFeedbackKnownTargetLabels();
  signals.forEach((signal) => {
    if (knownLabels.includes(signal) || BOLE_FEEDBACK_TOPIC_SORT_KEYS[signal]) add(signal);
  });
  const hay = boleFeedbackSemanticText(item);
  for (const label of knownLabels) {
    if (label === "融资" && signals.includes("融资")) {
      add(label);
      continue;
    }
    const aliases = BOLE_PROFILE_LABEL_ALIASES[label] || BOLE_FEEDBACK_EXTRA_TARGET_ALIASES[label] || [];
    const candidates = [label, ...aliases].map((value) => String(value || "").toLowerCase()).filter(Boolean);
    if (candidates.some((candidate) => hay.includes(candidate))) add(label);
  }
  return labels;
}

function boleFeedbackTargetLabel(feedback) {
  const matched = boleFeedbackMatchedTargetLabels(feedback);
  if (matched.length) return matched[0];
  return BOLE_FEEDBACK_GENERIC_TARGET;
}

function formatBoleFeedbackTime(value) {
  const date = new Date(value || Date.now());
  if (Number.isNaN(date.getTime())) return "刚刚";
  const pad = (part) => String(part).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function boleFeedbackSearchText(feedback) {
  return [
    feedback?.item?.title,
    feedback?.item?.title_zh,
    feedback?.item?.title_en,
    feedback?.item?.summary,
    feedback?.item?.description,
    feedback?.item?.site_name,
    feedback?.item?.source,
    boleFeedbackActionLabel(feedback?.action),
    boleFeedbackTargetLabel(feedback),
    ...boleFeedbackMatchedTargetLabels(feedback),
  ].filter(Boolean).join(" ").toLowerCase();
}

function boleFeedbackTopicSortKey(label) {
  const value = String(label || BOLE_FEEDBACK_GENERIC_TARGET).trim();
  return (BOLE_FEEDBACK_TOPIC_SORT_KEYS[value] || value).toLowerCase();
}

function isBoleFeedbackGenericTarget(label) {
  return String(label || "").trim() === BOLE_FEEDBACK_GENERIC_TARGET || String(label || "").trim() === "这条新闻";
}

function boleFeedbackSpecificTargetLabel(feedback) {
  const label = boleFeedbackTargetLabel(feedback);
  return isBoleFeedbackGenericTarget(label) ? "" : label;
}

function boleFeedbackTopicOptions(items = state.boleFeedbackItems) {
  return Array.from(
    new Set(
      (Array.isArray(items) ? items : [])
        .filter((feedback) => feedback && !isBoleFeedbackTombstoned(feedback))
        .map(boleFeedbackTargetLabel)
        .filter((label) => label && !isBoleFeedbackGenericTarget(label)),
    ),
  ).sort((a, b) => boleFeedbackTopicSortKey(a).localeCompare(boleFeedbackTopicSortKey(b), "zh-Hans-CN"));
}

function boleFeedbackVisibleItems() {
  const filters = ensureBoleFeedbackFilters();
  const query = filters.query.trim().toLowerCase();
  const actionOrder = filters.actionOrder.length ? filters.actionOrder : BOLE_FEEDBACK_DEFAULT_ACTION_ORDER;
  const rows = (Array.isArray(state.boleFeedbackItems) ? state.boleFeedbackItems : [])
    .filter((feedback) => feedback && !isBoleFeedbackTombstoned(feedback))
    .filter((feedback) => {
      if (filters.topic && boleFeedbackTargetLabel(feedback) !== filters.topic) return false;
      if (filters.action && feedback.action !== filters.action) return false;
      if (query && !boleFeedbackSearchText(feedback).includes(query)) return false;
      return true;
    });
  return rows.sort((a, b) => {
    if (filters.sort === "topic") {
      const byTopic = boleFeedbackTopicSortKey(boleFeedbackTargetLabel(b)) < boleFeedbackTopicSortKey(boleFeedbackTargetLabel(a)) ? 1
        : boleFeedbackTopicSortKey(boleFeedbackTargetLabel(a)) < boleFeedbackTopicSortKey(boleFeedbackTargetLabel(b)) ? -1
        : 0;
      if (byTopic) return byTopic;
    } else if (filters.sort === "action") {
      const byAction = actionOrder.indexOf(a.action) - actionOrder.indexOf(b.action);
      if (byAction) return byAction;
    }
    return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
  });
}

function currentBoleFeedbackForItem(item) {
  const key = boleFeedbackItemKey(item);
  if (!key || !state.boleFeedbackByKey) return null;
  return state.boleFeedbackByKey.get(key) || null;
}

function recordBoleSessionFeedback(feedback, options = {}) {
  if (!feedback || !feedback.item) return null;
  const key = boleFeedbackItemKey(feedback.item);
  if (!key) return null;
  if (!state.boleFeedbackByKey) state.boleFeedbackByKey = new Map();
  const normalized = {
    id: feedback.id || feedback.local_id || `session:${key}`,
    action: feedback.action || "",
    item: feedback.item,
    item_key: key,
    target: feedback.target || feedback.topic || boleFeedbackTargetLabel(feedback),
    matched_targets: uniqueBolePickStrings([
      ...(Array.isArray(feedback.matched_targets) ? feedback.matched_targets : []),
      ...(Array.isArray(feedback.item?.matched_targets) ? feedback.item.matched_targets : []),
      ...boleFeedbackMatchedTargetLabels(feedback),
    ]).filter((label) => !isBoleFeedbackGenericTarget(label)).slice(0, 8),
    created_at: feedback.created_at || new Date().toISOString(),
  };
  if (!options.preserveUndoTombstone) clearBoleFeedbackUndo(normalized);
  state.boleFeedbackByKey.set(key, normalized);
  return normalized;
}

function removeBoleSessionFeedback(feedback) {
  const item = feedback?.item || feedback;
  const key = feedback?.item_key || boleFeedbackItemKey(item);
  if (key && state.boleFeedbackByKey) state.boleFeedbackByKey.delete(key);
}

const BOLE_PROFILE_LABEL_ALIASES = {
  Agent: ["agent", "智能体", "agentic"],
  "Code AI": ["code ai", "coding", "代码", "编程"],
  "RAG / 知识库": ["rag", "知识库", "retrieval"],
  "本地部署": ["本地", "local", "部署", "量化", "quantization", "on-device"],
  多模态: ["多模态", "multimodal", "图像", "视频", "语音"],
  开源模型: ["开源", "open model", "open-source model"],
  "AI 搜索": ["ai search", "搜索"],
  产品与工具: ["产品", "工具", "product", "tool", "app"],
  模型能力: ["模型", "model", "benchmark", "能力"],
  开发者集成: ["开发者", "developer", "api", "sdk", "integration"],
  研究学习: ["研究", "research", "paper", "arxiv"],
  行业影响: ["行业", "industry", "policy", "企业"],
  商业信号: ["商业", "business", "pricing", "funding", "融资"],
  纯融资快讯: ["融资", "funding"],
  营销稿: ["营销稿", "营销", "marketing", "软文"],
  重复转载: ["转载", "duplicate", "repost"],
  空泛观点: ["空泛", "opinion"],
  过度学术: ["过度学术"],
  浅层汇总: ["浅层", "roundup"],
};

function uniqueBolePickStrings(values) {
  const seen = new Set();
  const result = [];
  (Array.isArray(values) ? values : []).forEach((value) => {
    const text = String(value || "").trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    result.push(text);
  });
  return result;
}

function normalizeBolePickText(value) {
  return String(value || "").toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
}

function compactBolePickText(value) {
  return normalizeBolePickText(value).replace(/[，。、“”‘’：:；;！!？?（）()\[\]【】《》<>·.,/\\|\s_-]/g, "");
}

function boleProfileEntryLabel(entry) {
  if (typeof entry === "string") return entry;
  if (!entry || typeof entry !== "object") return "";
  return entry.label || entry.source || "";
}

function activeBolePersonalizationProfile() {
  const status = state.personalizationStatus || {};
  if (status.state !== "confirmed" || status.enabled === false) return null;
  return status.active_profile && typeof status.active_profile === "object" ? status.active_profile : null;
}

function boleProfileInterestLabels(profile, key) {
  if (!profile || typeof profile !== "object") return [];
  return uniqueBolePickStrings((Array.isArray(profile[key]) ? profile[key] : []).map(boleProfileEntryLabel));
}

function boleProfileSourcePreferences(profile) {
  if (!profile || typeof profile !== "object" || !Array.isArray(profile.source_preferences)) return [];
  return profile.source_preferences
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const source = String(entry.source || "").trim();
      const weight = Number(entry.weight || 0);
      if (!source || !Number.isFinite(weight)) return null;
      return { source, weight };
    })
    .filter(Boolean);
}

function boleProfileLabelTokens(label) {
  const normalized = normalizeBolePickText(label);
  const aliases = BOLE_PROFILE_LABEL_ALIASES[label] || BOLE_PROFILE_LABEL_ALIASES[normalized] || [];
  const parts = normalized.split(/[\s,，、;；/|]+/);
  return uniqueBolePickStrings([normalized, ...aliases, ...parts])
    .map((token) => normalizeBolePickText(token))
    .filter((token) => token && token !== "ai" && compactBolePickText(token).length >= 2);
}

function boleProfileSearchText(item) {
  const signals = Array.isArray(item.ai_signals) ? item.ai_signals.join(" ") : "";
  return normalizeBolePickText([
    item.title_zh,
    item.title,
    item.title_en,
    item.summary,
    item.description,
    item.ai_label,
    item.ai_relevance_reason,
    signals,
    item.site_name,
    item.source,
  ].filter(Boolean).join(" "));
}

function boleSourceSearchText(item) {
  return normalizeBolePickText([
    item.site_name,
    item.site_id,
    item.source,
  ].filter(Boolean).join(" "));
}

function boleSourcePreferenceMatchesItem(source, item) {
  const normalized = normalizeBolePickText(source);
  if (!normalized) return false;
  const text = boleSourceSearchText(item);
  return text.includes(normalized);
}

function boleBehaviorSearchText(item) {
  const signals = Array.isArray(item.ai_signals) ? item.ai_signals.join(" ") : "";
  return normalizeBolePickText([
    item.title_zh,
    item.title,
    item.title_en,
    item.summary,
    item.description,
    item.ai_label,
    item.ai_relevance_reason,
    signals,
    item.site_name,
    item.source,
  ].filter(Boolean).join(" "));
}

function boleBehaviorMatchForItem(item, profile) {
  const behavior = profile?.behavior_preferences || {};
  const labels = uniqueBolePickStrings([
    behavior.summary_depth,
    behavior.verification_strictness,
    ...(Array.isArray(behavior.deep_reading_policy) ? behavior.deep_reading_policy : []),
    ...(Array.isArray(behavior.reading_depth) ? behavior.reading_depth : []),
  ]);
  const preferenceText = normalizeBolePickText(labels.join(" "));
  const itemText = boleBehaviorSearchText(item);
  const positive = [];
  let adjustment = 0;
  if (
    (/工程|细节|deep|developer|engineering/.test(preferenceText))
    && (/工程|开发|集成|部署|sdk|api|developer|tooling|engineering|integration|workflow|trace|hook/.test(itemText))
  ) {
    positive.push("工程细节");
    adjustment += 14;
  }
  if ((/核验|事实|strict|verify|fact/.test(preferenceText)) && (/官方|official|benchmark|policy|incident|安全|合规/.test(itemText))) {
    positive.push("事实核验");
    adjustment += 8;
  }
  return {
    positive: uniqueBolePickStrings(positive).slice(0, 2),
    adjustment: Math.min(16, adjustment),
  };
}

function boleProfileLabelMatchesItem(label, item) {
  const text = boleProfileSearchText(item);
  const compactText = compactBolePickText(text);
  return boleProfileLabelTokens(label).some((token) => {
    const normalized = normalizeBolePickText(token);
    const compact = compactBolePickText(token);
    return text.includes(normalized) || (compact && compactText.includes(compact));
  });
}

function boleProfileMatchForItem(item, profile = activeBolePersonalizationProfile()) {
  if (!profile) return { positive: [], negative: [], sourcePositive: [], sourceNegative: [], behaviorPositive: [], adjustment: 0 };
  const positive = boleProfileInterestLabels(profile, "positive_interests")
    .filter((label) => boleProfileLabelMatchesItem(label, item))
    .slice(0, 3);
  const negative = boleProfileInterestLabels(profile, "negative_interests")
    .filter((label) => boleProfileLabelMatchesItem(label, item))
    .slice(0, 3);
  const positiveBonus = Math.min(18, positive.length * 10);
  const negativePenalty = Math.min(32, negative.length * 18);
  const sourcePreferences = boleProfileSourcePreferences(profile).filter((entry) => boleSourcePreferenceMatchesItem(entry.source, item));
  const sourcePositive = sourcePreferences.filter((entry) => entry.weight > 0).map((entry) => entry.source).slice(0, 2);
  const sourceNegative = sourcePreferences.filter((entry) => entry.weight < 0).map((entry) => entry.source).slice(0, 2);
  const sourceAdjustment = Math.max(
    -18,
    Math.min(18, Math.round(sourcePreferences.reduce((sum, entry) => sum + entry.weight * 18, 0))),
  );
  const behaviorMatch = boleBehaviorMatchForItem(item, profile);
  return {
    positive,
    negative,
    sourcePositive,
    sourceNegative,
    behaviorPositive: behaviorMatch.positive,
    adjustment: positiveBonus - negativePenalty + sourceAdjustment + behaviorMatch.adjustment,
  };
}

function personalizedBoleScore(item, baseScore, profile = activeBolePersonalizationProfile()) {
  const matches = boleProfileMatchForItem(item, profile);
  const score = Math.max(1, Math.min(100, Math.round(baseScore + matches.adjustment)));
  return { score, matches };
}

function sourceGroupKey(siteId, source) {
  return `${siteId || ""}::${source || ""}`;
}

function findSourceGroupNode(sourceKey) {
  const groups = newsListEl?.querySelectorAll(".source-group") || [];
  return Array.from(groups).find((group) => group.dataset.sourceKey === sourceKey) || null;
}

function findSiteGroupNode(siteId) {
  const groups = newsListEl?.querySelectorAll(".site-group") || [];
  return Array.from(groups).find((group) => group.dataset.siteId === siteId) || null;
}

function collapseSourceGroup(sourceKey) {
  state.expandedSourceGroups.delete(sourceKey);
  renderList();
  window.requestAnimationFrame(() => {
    const group = findSourceGroupNode(sourceKey);
    const header = group?.querySelector(".source-group-head");
    if (header) header.scrollIntoView({ behavior: "auto", block: "start" });
  });
}

function collapseSiteGroup(siteId) {
  state.expandedSites.delete(siteId);
  renderList();
  window.requestAnimationFrame(() => {
    const group = findSiteGroupNode(siteId);
    const header = group?.querySelector(".site-group-head");
    if (header) header.scrollIntoView({ behavior: "auto", block: "start" });
  });
}

function sourcePreferenceHiddenCount() {
  const prefs = state.sourcePrefs || emptySourcePrefs();
  return uniqueStrings(prefs.hiddenSites).length
    + Object.values(prefs.hiddenSourcesBySite || {}).reduce((sum, sources) => sum + uniqueStrings(sources).length, 0);
}

function sourcePrefsHiddenSourceSet(siteId) {
  return new Set(uniqueStrings(state.sourcePrefs?.hiddenSourcesBySite?.[siteId]));
}

function isSiteHidden(siteId) {
  return uniqueStrings(state.sourcePrefs?.hiddenSites).includes(siteId);
}

function isSourceHidden(siteId, source) {
  return sourcePrefsHiddenSourceSet(siteId).has(source);
}

function sourceOrderIndex(siteId, source) {
  const order = uniqueStrings(state.sourcePrefs?.sourceOrderBySite?.[siteId]);
  const index = order.indexOf(source);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

function siteOrderIndex(siteId) {
  const order = uniqueStrings(state.sourcePrefs?.siteOrder);
  const index = order.indexOf(siteId);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

function toggleDataDrawer(forceOpen) {
  if (!dataDrawerEl || !dataDrawerButtonEl) return;
  const willOpen = typeof forceOpen === "boolean" ? forceOpen : dataDrawerEl.hidden;
  dataDrawerEl.hidden = !willOpen;
  dataDrawerButtonEl.setAttribute("aria-expanded", String(willOpen));
}

function openDataDrawer() {
  toggleDataDrawer(true);
}

function closeDataDrawer() {
  toggleDataDrawer(false);
}

function renderDataDrawerMeta() {
  if (!dataDrawerMetaEl) return;
  const status = state.sourceStatus;
  const sites = Array.isArray(status?.sites) ? status.sites : [];
  const ok = Number(status?.successful_sites || 0);
  const total = sites.length || Number(state.statsAi?.length || 0);
  dataDrawerMetaEl.textContent = total ? `${fmtNumber(ok || total)}/${fmtNumber(total)} 源可用` : "数据加载中";
}

function updateSourceHiddenButton() {
  if (!sourceHiddenCountEl) return;
  sourceHiddenCountEl.textContent = `已屏蔽 ${fmtNumber(sourcePreferenceHiddenCount())}`;
}

function moveBefore(list, item, beforeItem) {
  const values = uniqueStrings(list);
  const without = values.filter((value) => value !== item);
  const beforeIndex = without.indexOf(beforeItem);
  if (beforeIndex === -1) {
    without.push(item);
  } else {
    without.splice(beforeIndex, 0, item);
  }
  return without;
}

function sourceSelectionKey(type, siteId, source = "") {
  return type === "source" ? `source::${siteId}::${source}` : `site::${siteId}`;
}

function parseSourceSelectionKey(key) {
  const parts = String(key || "").split("::");
  return {
    type: parts[0],
    siteId: parts[1] || "",
    source: parts.slice(2).join("::"),
  };
}

function buildSourceTree(items, includeHidden = true) {
  const siteMap = new Map();
  items.forEach((item) => {
    const siteId = item.site_id || item.site_name || "unknown";
    const source = item.source || "未分区";
    if (!includeHidden && (isSiteHidden(siteId) || isSourceHidden(siteId, source))) return;
    if (!siteMap.has(siteId)) {
      siteMap.set(siteId, {
        siteId,
        siteName: item.site_name || siteId,
        items: [],
        sourceMap: new Map(),
      });
    }
    const site = siteMap.get(siteId);
    site.items.push(item);
    if (!site.sourceMap.has(source)) site.sourceMap.set(source, []);
    site.sourceMap.get(source).push(item);
  });

  return Array.from(siteMap.values())
    .map((site) => ({
      ...site,
      sources: Array.from(site.sourceMap.entries())
        .map(([source, sourceItems]) => ({ source, items: sourceItems }))
        .sort((a, b) => {
          const byOrder = sourceOrderIndex(site.siteId, a.source) - sourceOrderIndex(site.siteId, b.source);
          if (byOrder !== 0) return byOrder;
          return b.items.length - a.items.length || a.source.localeCompare(b.source, "zh-CN");
        }),
    }))
    .sort((a, b) => {
      const byOrder = siteOrderIndex(a.siteId) - siteOrderIndex(b.siteId);
      if (byOrder !== 0) return byOrder;
      return b.items.length - a.items.length || a.siteName.localeCompare(b.siteName, "zh-CN");
    });
}

function currentSourceTree(includeHidden = true) {
  return buildSourceTree(modeItems(), includeHidden);
}

function renderDragGrip() {
  const grip = document.createElement("span");
  grip.className = "drag-grip";
  grip.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 4; i += 1) {
    grip.appendChild(document.createElement("span"));
  }
  return grip;
}

function renderSelectToggle(key) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "source-select-toggle";
  button.setAttribute("aria-label", "选择来源");
  button.setAttribute("aria-pressed", String(state.sourceSortSelection.has(key)));
  button.classList.toggle("selected", state.sourceSortSelection.has(key));
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (state.sourceSortSelection.has(key)) {
      state.sourceSortSelection.delete(key);
    } else {
      state.sourceSortSelection.add(key);
    }
    renderSourceSortDialog();
  });
  return button;
}

function renderSourceSortRowText(title, meta) {
  const text = document.createElement("div");
  text.className = "source-sort-row-text";
  const titleEl = document.createElement("strong");
  titleEl.textContent = title;
  const metaEl = document.createElement("span");
  metaEl.textContent = meta;
  text.append(titleEl, metaEl);
  return text;
}

function renderSourceSortDialog() {
  if (!sourceSortListEl) return;
  const tree = currentSourceTree(false);
  sourceSortListEl.innerHTML = "";
  if (!tree.length) {
    const empty = document.createElement("div");
    empty.className = "source-control-empty";
    empty.textContent = "当前没有可排序的来源。";
    sourceSortListEl.appendChild(empty);
    return;
  }

  tree.forEach((site) => {
    const siteWrap = document.createElement("section");
    siteWrap.className = "source-sort-site";
    const row = document.createElement("div");
    row.className = "source-sort-row";
    row.dataset.sortType = "site";
    row.dataset.siteId = site.siteId;

    const left = document.createElement("div");
    left.className = "source-sort-row-main";
    const grip = renderDragGrip();
    grip.addEventListener("pointerdown", (event) => handleSourceSortPointerStart(event, "site", site.siteId));
    left.append(grip, renderSourceSortRowText(site.siteName, `${fmtNumber(site.items.length)} 条 · ${fmtNumber(site.sources.length)} 个来源`));

    const expand = document.createElement("button");
    expand.type = "button";
    expand.className = "source-expand-toggle";
    const isExpanded = state.sourceSortExpandedSites.has(site.siteId);
    expand.textContent = isExpanded ? "收起" : "展开";
    expand.addEventListener("click", (event) => {
      event.stopPropagation();
      if (isExpanded) {
        state.sourceSortExpandedSites.delete(site.siteId);
      } else {
        state.sourceSortExpandedSites.add(site.siteId);
      }
      renderSourceSortDialog();
    });

    const right = document.createElement("div");
    right.className = "source-sort-row-actions";
    right.append(expand, renderSelectToggle(sourceSelectionKey("site", site.siteId)));

    row.append(left, right);
    siteWrap.appendChild(row);

    if (isExpanded) {
      const subList = document.createElement("div");
      subList.className = "source-sort-sub-list";
      site.sources.forEach((sourceRow) => {
        const sourceNode = document.createElement("div");
        sourceNode.className = "source-sort-sub-row";
        sourceNode.dataset.sortType = "source";
        sourceNode.dataset.siteId = site.siteId;
        sourceNode.dataset.source = sourceRow.source;

        const sourceLeft = document.createElement("div");
        sourceLeft.className = "source-sort-row-main";
        const sourceGrip = renderDragGrip();
        sourceGrip.addEventListener("pointerdown", (event) => handleSourceSortPointerStart(event, "source", site.siteId, sourceRow.source));
        sourceLeft.append(sourceGrip, renderSourceSortRowText(sourceRow.source, `${fmtNumber(sourceRow.items.length)} 条`));
        sourceNode.append(sourceLeft, renderSelectToggle(sourceSelectionKey("source", site.siteId, sourceRow.source)));
        subList.appendChild(sourceNode);
      });
      siteWrap.appendChild(subList);
    }
    sourceSortListEl.appendChild(siteWrap);
  });
}

function handleSourceSortPointerStart(event, type, siteId, source = "") {
  state.sourcePointerDrag = {
    type,
    siteId,
    source,
  };
  event.preventDefault();
}

function handleSourceSortPointerEnd(event) {
  if (!state.sourcePointerDrag) return;
  const target = document.elementFromPoint(event.clientX, event.clientY)?.closest?.("[data-sort-type]");
  const drag = state.sourcePointerDrag;
  state.sourcePointerDrag = null;
  if (!target || target.dataset.sortType !== drag.type) return;

  if (drag.type === "site") {
    const targetSiteId = target.dataset.siteId || "";
    if (!targetSiteId || targetSiteId === drag.siteId) return;
    const currentOrder = currentSourceTree(false).map((site) => site.siteId);
    state.sourcePrefs.siteOrder = moveBefore(currentOrder, drag.siteId, targetSiteId);
  }

  if (drag.type === "source") {
    const targetSiteId = target.dataset.siteId || "";
    const targetSource = target.dataset.source || "";
    if (targetSiteId !== drag.siteId || !targetSource || targetSource === drag.source) return;
    const site = currentSourceTree(false).find((item) => item.siteId === drag.siteId);
    const currentOrder = site ? site.sources.map((item) => item.source) : uniqueStrings(state.sourcePrefs.sourceOrderBySite[drag.siteId]);
    state.sourcePrefs.sourceOrderBySite[drag.siteId] = moveBefore(currentOrder, drag.source, targetSource);
  }

  saveSourcePrefs();
  renderSourceSortDialog();
  renderList();
}

function openSourceSortDialog() {
  if (!sourceSortDialogEl) return;
  state.sourceSortSelection.clear();
  renderSourceSortDialog();
  sourceSortDialogEl.hidden = false;
  document.body.classList.add("source-control-open");
}

function closeSourceSortDialog() {
  if (!sourceSortDialogEl) return;
  sourceSortDialogEl.hidden = true;
  document.body.classList.remove("source-control-open");
}

function blockSelectedSourceGroups() {
  const prefs = sanitizeSourcePrefs(state.sourcePrefs);
  state.sourceSortSelection.forEach((key) => {
    const selection = parseSourceSelectionKey(key);
    if (selection.type === "site" && selection.siteId) {
      prefs.hiddenSites = uniqueStrings([...prefs.hiddenSites, selection.siteId]);
    }
    if (selection.type === "source" && selection.siteId && selection.source) {
      prefs.hiddenSourcesBySite[selection.siteId] = uniqueStrings([
        ...(prefs.hiddenSourcesBySite[selection.siteId] || []),
        selection.source,
      ]);
    }
  });
  state.sourcePrefs = prefs;
  state.sourceSortSelection.clear();
  saveSourcePrefs();
  updateSourceHiddenButton();
  renderSourceSortDialog();
  renderList();
}

function restoreHiddenSourcePreference(type, siteId, source = "") {
  const prefs = sanitizeSourcePrefs(state.sourcePrefs);
  if (type === "site") {
    prefs.hiddenSites = prefs.hiddenSites.filter((item) => item !== siteId);
  }
  if (type === "source" && prefs.hiddenSourcesBySite[siteId]) {
    prefs.hiddenSourcesBySite[siteId] = prefs.hiddenSourcesBySite[siteId].filter((item) => item !== source);
  }
  state.sourcePrefs = prefs;
  saveSourcePrefs();
  updateSourceHiddenButton();
  renderHiddenSourcesDialog();
  renderList();
}

function hiddenSourceLabel(type, siteId, source = "") {
  const site = currentSourceTree(true).find((item) => item.siteId === siteId);
  const siteName = site?.siteName || siteId || "未知来源";
  return type === "site" ? siteName : `${siteName} / ${source}`;
}

function renderHiddenSourcesDialog() {
  if (!sourceHiddenListEl) return;
  sourceHiddenListEl.innerHTML = "";
  const prefs = sanitizeSourcePrefs(state.sourcePrefs);
  const rows = [
    ...prefs.hiddenSites.map((siteId) => ({ type: "site", siteId, source: "" })),
    ...Object.entries(prefs.hiddenSourcesBySite).flatMap(([siteId, sources]) => sources.map((source) => ({ type: "source", siteId, source }))),
  ];
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "source-control-empty";
    empty.textContent = "暂无屏蔽来源。";
    sourceHiddenListEl.appendChild(empty);
    return;
  }
  rows.forEach((row) => {
    const node = document.createElement("div");
    node.className = "source-hidden-row";
    const label = document.createElement("span");
    label.textContent = hiddenSourceLabel(row.type, row.siteId, row.source);
    const restore = document.createElement("button");
    restore.type = "button";
    restore.textContent = "恢复";
    restore.addEventListener("click", () => restoreHiddenSourcePreference(row.type, row.siteId, row.source));
    node.append(label, restore);
    sourceHiddenListEl.appendChild(node);
  });
}

function openSourceHiddenDialog() {
  if (!sourceHiddenDialogEl) return;
  renderHiddenSourcesDialog();
  sourceHiddenDialogEl.hidden = false;
  document.body.classList.add("source-control-open");
}

function closeSourceHiddenDialog() {
  if (!sourceHiddenDialogEl) return;
  sourceHiddenDialogEl.hidden = true;
  document.body.classList.remove("source-control-open");
}

function renderBoleFeedbackList() {
  if (!boleFeedbackListEl) return;
  syncBoleFeedbackFilterControls();
  const items = boleFeedbackVisibleItems();
  boleFeedbackListEl.innerHTML = "";
  if (typeof boleFeedbackCountEl !== "undefined" && boleFeedbackCountEl) {
    const total = (Array.isArray(state.boleFeedbackItems) ? state.boleFeedbackItems : []).filter((feedback) => !isBoleFeedbackTombstoned(feedback)).length;
    boleFeedbackCountEl.textContent = items.length === total ? `${total} 条` : `${items.length} / ${total} 条`;
  }
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "bole-feedback-empty";
    empty.textContent = "没有匹配记录";
    boleFeedbackListEl.appendChild(empty);
    return;
  }
  items.slice(0, 30).forEach((feedback) => {
    const row = document.createElement("div");
    const tone = feedback.action === "more_like_this" || feedback.action === "more_relevant" ? " positive" : " negative";
    row.className = `bole-feedback-row${tone}`;
    row.dataset.feedbackId = boleFeedbackRecordId(feedback);
    const mark = document.createElement("span");
    mark.className = "mark";
    if (typeof mark.setAttribute === "function") mark.setAttribute("aria-hidden", "true");
    else mark.ariaHidden = "true";
    mark.innerHTML = feedback.action === "more_like_this" || feedback.action === "more_relevant"
      ? '<svg class="lucide-icon feedback-thumb-icon" viewBox="-1 -1 26 26"><path d="M7 10v12"></path><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"></path></svg>'
      : '<svg class="lucide-icon" viewBox="0 0 24 24"><path d="M8 12h8"></path><path d="M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z"></path></svg>';
    const text = document.createElement("div");
    text.className = "bole-feedback-row-text";
    const title = document.createElement("strong");
    title.textContent = feedback.item?.title || "未命名更新";
    const meta = document.createElement("span");
    meta.textContent = `${boleFeedbackActionLabel(feedback.action)}：${boleFeedbackTargetLabel(feedback)} · ${formatBoleFeedbackTime(feedback.created_at)}`;
    const source = document.createElement("span");
    source.textContent = [feedback.item?.site_name, feedback.item?.source].filter(Boolean).join(" · ");
    text.append(title, meta, source);
    const undo = document.createElement("button");
    undo.type = "button";
    undo.textContent = "撤销";
    undo.dataset.boleFeedbackUndo = boleFeedbackRecordId(feedback);
    row.append(mark, text, undo);
    boleFeedbackListEl.appendChild(row);
  });
}

function renderBoleFeedbackOptions(select, rows, value) {
  if (!select) return;
  const previous = select.value;
  select.innerHTML = rows.map((row) => `<option value="${escapeHtml(row.value)}">${escapeHtml(row.label)}</option>`).join("");
  select.value = rows.some((row) => row.value === value) ? value : previous;
  if (!rows.some((row) => row.value === select.value)) select.value = "";
}

function syncBoleFeedbackFilterControls() {
  const filters = ensureBoleFeedbackFilters();
  if (typeof boleFeedbackSearchEl !== "undefined" && boleFeedbackSearchEl && boleFeedbackSearchEl.value !== filters.query) boleFeedbackSearchEl.value = filters.query;
  const topics = boleFeedbackTopicOptions();
  if (filters.topic && !topics.includes(filters.topic)) filters.topic = "";
  renderBoleFeedbackOptions(
    typeof boleFeedbackTopicFilterEl !== "undefined" ? boleFeedbackTopicFilterEl : null,
    [{ value: "", label: "全部主题" }, ...topics.map((topic) => ({ value: topic, label: topic }))],
    filters.topic,
  );
  if (typeof boleFeedbackTopicFilterEl !== "undefined" && boleFeedbackTopicFilterEl) boleFeedbackTopicFilterEl.value = topics.includes(filters.topic) ? filters.topic : "";
  renderBoleFeedbackOptions(
    typeof boleFeedbackActionFilterEl !== "undefined" ? boleFeedbackActionFilterEl : null,
    [
      { value: "", label: "全部反馈" },
      { value: "more_like_this", label: "感兴趣" },
      { value: "less_relevant", label: "少看类似" },
      { value: "not_interested", label: "不感兴趣" },
    ],
    filters.action,
  );
  if (typeof boleFeedbackActionFilterEl !== "undefined" && boleFeedbackActionFilterEl) boleFeedbackActionFilterEl.value = filters.action;
  renderBoleFeedbackOptions(
    typeof boleFeedbackSortSelectEl !== "undefined" ? boleFeedbackSortSelectEl : null,
    [
      { value: "time", label: "按时间" },
      { value: "topic", label: "按主题" },
      { value: "action", label: "按反馈类型" },
    ],
    filters.sort,
  );
  if (typeof boleFeedbackSortSelectEl !== "undefined" && boleFeedbackSortSelectEl) boleFeedbackSortSelectEl.value = filters.sort;
  if (typeof boleFeedbackActionOrderEl !== "undefined" && boleFeedbackActionOrderEl) {
    boleFeedbackActionOrderEl.hidden = filters.sort !== "action";
    boleFeedbackActionOrderEl.innerHTML = filters.actionOrder.map((action, index) => `
      <span class="bole-feedback-order-chip">
        ${escapeHtml(boleFeedbackActionLabel(action))}
        <button type="button" data-bole-feedback-action-order="${escapeHtml(action)}" data-direction="-1" aria-label="${escapeHtml(boleFeedbackActionLabel(action))} 上移"${index === 0 ? " disabled" : ""}>↑</button>
        <button type="button" data-bole-feedback-action-order="${escapeHtml(action)}" data-direction="1" aria-label="${escapeHtml(boleFeedbackActionLabel(action))} 下移"${index === filters.actionOrder.length - 1 ? " disabled" : ""}>↓</button>
      </span>
    `).join("");
  }
}

function setBoleFeedbackFilter(name, value) {
  const filters = ensureBoleFeedbackFilters();
  if (name === "query") filters.query = String(value || "");
  if (name === "topic") filters.topic = String(value || "");
  if (name === "action") filters.action = String(value || "");
  if (name === "sort") filters.sort = ["time", "topic", "action"].includes(value) ? value : "time";
  renderBoleFeedbackList();
}

function moveBoleFeedbackActionOrder(action, direction) {
  const filters = ensureBoleFeedbackFilters();
  const index = filters.actionOrder.indexOf(action);
  const target = index + Number(direction);
  if (index < 0 || target < 0 || target >= filters.actionOrder.length) return;
  const [entry] = filters.actionOrder.splice(index, 1);
  filters.actionOrder.splice(target, 0, entry);
  renderBoleFeedbackList();
}

async function loadBoleFeedback(options = {}) {
  if (!apiBaseUrl) return { items: [] };
  try {
    const payload = await apiFetch("/api/personalization/feedback");
    state.boleFeedbackItems = (Array.isArray(payload.items) ? payload.items : []).filter((feedback) => !isBoleFeedbackTombstoned(feedback));
    state.boleFeedbackByKey = new Map();
    state.boleFeedbackItems = state.boleFeedbackItems.map((feedback) => recordBoleSessionFeedback(feedback, { preserveUndoTombstone: true })).filter(Boolean);
    renderBoleFeedbackList();
    renderBolePicks();
    return payload;
  } catch (err) {
    if (!options.quiet && boleFeedbackListEl) {
      boleFeedbackListEl.innerHTML = `<div class="bole-feedback-empty">${escapeHtml(err.message || "反馈暂时不可用")}</div>`;
    }
    return { items: [] };
  }
}

async function openBoleFeedbackDialog() {
  if (!boleFeedbackDialogEl) return;
  renderBoleFeedbackList();
  boleFeedbackDialogEl.hidden = false;
  document.body.classList.add("bole-feedback-dialog-open");
  if (boleFeedbackButtonEl) boleFeedbackButtonEl.setAttribute("aria-expanded", "true");
  window.requestAnimationFrame(() => boleFeedbackDialogEl.classList.add("open"));
  await loadBoleFeedback({ quiet: true });
}

function closeBoleFeedbackDialog() {
  if (!boleFeedbackDialogEl) return;
  boleFeedbackDialogEl.classList.remove("open");
  boleFeedbackDialogEl.hidden = true;
  document.body.classList.remove("bole-feedback-dialog-open");
  if (boleFeedbackButtonEl) boleFeedbackButtonEl.setAttribute("aria-expanded", "false");
}

function syncBoleSortControls() {
  if (!boleSortPopoverEl) return;
  const mode = state.boleSortMode === "time" ? "time" : "score";
  boleSortPopoverEl.querySelectorAll("[data-bole-sort-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.boleSortMode === mode);
  });
}

function openBoleSortPopover() {
  if (!boleSortPopoverEl) return;
  syncBoleSortControls();
  boleSortPopoverEl.hidden = false;
  if (boleSortButtonEl) boleSortButtonEl.setAttribute("aria-expanded", "true");
  window.requestAnimationFrame(() => boleSortPopoverEl.classList.add("open"));
}

function closeBoleSortPopover() {
  if (!boleSortPopoverEl) return;
  boleSortPopoverEl.classList.remove("open");
  boleSortPopoverEl.hidden = true;
  if (boleSortButtonEl) boleSortButtonEl.setAttribute("aria-expanded", "false");
}

function toggleBoleSortPopover() {
  if (!boleSortPopoverEl) return;
  if (boleSortPopoverEl.hidden) openBoleSortPopover();
  else closeBoleSortPopover();
}

function setBoleSortMode(mode) {
  state.boleSortMode = mode === "time" ? "time" : "score";
  syncBoleSortControls();
  renderBolePicks();
}

function openReaderFeedbackPopover() {
  if (!readerFeedbackPopoverEl) return;
  readerFeedbackPopoverEl.hidden = false;
  if (readerFeedbackTriggerEl) readerFeedbackTriggerEl.setAttribute("aria-expanded", "true");
  window.requestAnimationFrame(() => readerFeedbackPopoverEl.classList.add("open"));
}

function closeReaderFeedbackPopover() {
  if (!readerFeedbackPopoverEl) return;
  readerFeedbackPopoverEl.classList.remove("open");
  readerFeedbackPopoverEl.hidden = true;
  if (readerFeedbackTriggerEl) readerFeedbackTriggerEl.setAttribute("aria-expanded", "false");
}

function toggleReaderFeedbackPopover() {
  if (!readerFeedbackPopoverEl) return;
  if (readerFeedbackPopoverEl.hidden) {
    openReaderFeedbackPopover();
  } else {
    closeReaderFeedbackPopover();
  }
}

function closeBoleTunePopover() {
  if (!boleTunePopoverEl) return;
  boleTunePopoverEl.classList.remove("open");
  boleTunePopoverEl.hidden = true;
  state.boleTuneItem = null;
}

function positionBoleTunePopover(anchor) {
  if (!boleTunePopoverEl || !anchor) return;
  const rect = anchor.getBoundingClientRect();
  const width = Math.min(210, window.innerWidth - 24);
  const left = Math.max(12, Math.min(window.innerWidth - width - 12, rect.right - width));
  const top = Math.max(12, Math.min(window.innerHeight - 120, rect.bottom + 8));
  boleTunePopoverEl.style.left = `${left}px`;
  boleTunePopoverEl.style.top = `${top}px`;
  boleTunePopoverEl.style.width = `${width}px`;
}

function openBoleTunePopover(anchor, item) {
  if (!boleTunePopoverEl) return;
  state.boleTuneItem = item;
  positionBoleTunePopover(anchor);
  boleTunePopoverEl.hidden = false;
  window.requestAnimationFrame(() => boleTunePopoverEl.classList.add("open"));
}

function openBoleDraftSuggestionDialog(suggestion) {
  if (!boleDraftSuggestionDialogEl || !suggestion) return;
  state.bolePendingDraftSuggestion = suggestion;
  const current = baseBoleProfileForSuggestion();
  const patch = suggestion.profile_patch || {};
  const conflict = resolveBoleProfilePatchConflict(current, patch, state.boleConflictStrategy);
  if (conflict.conflicts.length) {
    if (state.boleConflictStrategy === "last_decision") {
      applyResolvedBoleProfile(conflict.profile, { persist: true });
      return;
    }
    openBoleProfileConflictDialog(suggestion, current, patch, conflict.conflicts);
    return;
  }
  if (boleDraftSuggestionBodyEl) {
    const positive = (patch.positive_interests || []).map((item) => item.label).filter(Boolean);
    const negative = (patch.negative_interests || []).map((item) => item.label).filter(Boolean);
    const labels = [...positive, ...negative].slice(0, 3);
    boleDraftSuggestionBodyEl.innerHTML = labels.length
      ? labels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")
      : "<span>新的偏好线索</span>";
  }
  boleDraftSuggestionDialogEl.hidden = false;
  document.body.classList.add("bole-draft-suggestion-open");
  window.requestAnimationFrame(() => boleDraftSuggestionDialogEl.classList.add("open"));
}

function closeBoleProfileConflictDialog() {
  if (!boleProfileConflictDialogEl) return;
  boleProfileConflictDialogEl.classList.remove("open");
  boleProfileConflictDialogEl.hidden = true;
  document.body.classList.remove("bole-profile-conflict-open");
}

async function applyResolvedBoleProfile(profile, options = {}) {
  if (!profile || typeof profile !== "object") return;
  const status = state.personalizationStatus || {};
  state.boleDraftPreview = profile;
  state.personalizationStatus = {
    ...status,
    state: "confirmed",
    enabled: true,
    active_profile: profile,
  };
  renderBoleWorkbench();
  renderBolePicks();
  if (!options.persist || !apiBaseUrl) return;
  try {
    await apiFetch("/api/personalization/draft", {
      method: "POST",
      body: JSON.stringify({
        profile,
        evidence: {
          positive_count: (profile.positive_interests || []).length,
          negative_count: (profile.negative_interests || []).length,
        },
      }),
    });
    const payload = await apiFetch("/api/personalization/confirm", { method: "POST" });
    state.personalizationStatus = payload;
    state.personalizationUnavailable = false;
    state.boleDraftPreview = payload.active_profile || profile;
    renderBoleWorkbench();
    renderBolePicks();
  } catch (err) {
    // Keep the optimistic local result if the backend write fails this round.
  }
}

function openBoleProfileConflictDialog(suggestion, baseProfile, profilePatch, conflicts) {
  if (!boleProfileConflictDialogEl) return;
  const conflict = conflicts[0];
  if (!conflict) return;
  state.bolePendingProfileConflict = { suggestion, baseProfile, profilePatch, conflict };
  const label = conflict.label || "这个主题";
  const incomingNegative = conflict.incoming === "negative";
  if (boleProfileConflictLabelEl) boleProfileConflictLabelEl.textContent = `冲突主题：${label}`;
  if (boleProfileConflictPolicyEl) boleProfileConflictPolicyEl.textContent = "策略：每次询问";
  if (boleProfileConflictExistingTitleEl) {
    boleProfileConflictExistingTitleEl.textContent = conflict.existing === "positive" ? "当前画像：多推荐" : "当前画像：少推荐";
  }
  if (boleProfileConflictIncomingTitleEl) {
    boleProfileConflictIncomingTitleEl.textContent = incomingNegative ? "新反馈：少推荐" : "新反馈：多推荐";
  }
  if (boleProfileConflictExistingSourceEl) {
    boleProfileConflictExistingSourceEl.textContent = `来源：${conflict.existing_entry?.source === "feedback" ? "过往反馈" : "已确认画像"}。`;
  }
  if (boleProfileConflictIncomingSourceEl) {
    boleProfileConflictIncomingSourceEl.textContent = `来源：最近一次${incomingNegative ? "少看类似" : "多看类似"}反馈。`;
  }
  boleProfileConflictDialogEl.hidden = false;
  document.body.classList.add("bole-profile-conflict-open");
  window.requestAnimationFrame(() => boleProfileConflictDialogEl.classList.add("open"));
}

function uniqueBoleProfileEntries(entries) {
  const seen = new Set();
  const result = [];
  (Array.isArray(entries) ? entries : []).forEach((entry) => {
    if (!entry || typeof entry !== "object") return;
    const label = String(entry.label || "").trim();
    if (!label || seen.has(label)) return;
    seen.add(label);
    result.push({ ...entry, label });
  });
  return result;
}

function boleProfileEntryConflictKey(entry) {
  return String(entry?.label || "").trim().toLowerCase();
}

function removeBoleProfileEntryByLabel(entries, label) {
  const key = String(label || "").trim().toLowerCase();
  if (!key) return uniqueBoleProfileEntries(entries);
  return uniqueBoleProfileEntries(entries).filter((entry) => boleProfileEntryConflictKey(entry) !== key);
}

function upsertBoleProfileEntry(entries, entry) {
  const normalized = uniqueBoleProfileEntries([entry])[0];
  if (!normalized) return uniqueBoleProfileEntries(entries);
  return uniqueBoleProfileEntries([...removeBoleProfileEntryByLabel(entries, normalized.label), normalized]);
}

function uniqueBoleSourcePreferences(entries) {
  const seen = new Set();
  const result = [];
  (Array.isArray(entries) ? entries : []).forEach((entry) => {
    if (!entry || typeof entry !== "object") return;
    const source = String(entry.source || "").trim();
    if (!source || seen.has(source)) return;
    seen.add(source);
    const weight = Number(entry.weight);
    result.push({ source, weight: Number.isFinite(weight) ? weight : 0 });
  });
  return result;
}

function resolveBoleProfilePatchConflict(baseProfile = {}, profilePatch = {}, conflictStrategy = "ask") {
  const base = baseProfile && typeof baseProfile === "object" ? baseProfile : {};
  const patch = profilePatch && typeof profilePatch === "object" ? profilePatch : {};
  let positive = uniqueBoleProfileEntries(base.positive_interests || []);
  let negative = uniqueBoleProfileEntries(base.negative_interests || []);
  const conflicts = [];
  const strategy = conflictStrategy === "last_decision" ? "last_decision" : "ask";

  const applyEntry = (entry, incoming) => {
    const normalized = uniqueBoleProfileEntries([entry])[0];
    if (!normalized) return;
    const opposite = incoming === "positive" ? negative : positive;
    const existing = opposite.find((item) => boleProfileEntryConflictKey(item) === boleProfileEntryConflictKey(normalized));
    if (existing) {
      conflicts.push({
        label: normalized.label,
        incoming,
        existing: incoming === "positive" ? "negative" : "positive",
        incoming_entry: normalized,
        existing_entry: existing,
      });
      if (strategy !== "last_decision") return;
      if (incoming === "positive") {
        negative = removeBoleProfileEntryByLabel(negative, normalized.label);
        positive = upsertBoleProfileEntry(positive, normalized);
      } else {
        positive = removeBoleProfileEntryByLabel(positive, normalized.label);
        negative = upsertBoleProfileEntry(negative, normalized);
      }
      return;
    }
    if (incoming === "positive") positive = upsertBoleProfileEntry(positive, normalized);
    else negative = upsertBoleProfileEntry(negative, normalized);
  };

  (patch.positive_interests || []).forEach((entry) => applyEntry(entry, "positive"));
  (patch.negative_interests || []).forEach((entry) => applyEntry(entry, "negative"));

  const profile = {
    ...base,
    ...patch,
    positive_interests: positive,
    negative_interests: negative,
    source_preferences: uniqueBoleSourcePreferences([
      ...(base.source_preferences || []),
      ...(patch.source_preferences || []),
    ]),
    behavior_preferences: {
      ...(base.behavior_preferences || {}),
      ...(patch.behavior_preferences || {}),
    },
  };
  return { profile, conflicts };
}

function applyBoleConflictDecision(baseProfile = {}, profilePatch = {}, decision = "ignore") {
  if (decision === "positive") {
    return mergeBoleProfilePatch(baseProfile, {
      ...profilePatch,
      positive_interests: [
        ...(profilePatch.positive_interests || []),
        ...(profilePatch.negative_interests || []),
      ],
      negative_interests: [],
    }, { conflictStrategy: "last_decision" });
  }
  if (decision === "negative") {
    return mergeBoleProfilePatch(baseProfile, {
      ...profilePatch,
      positive_interests: [],
      negative_interests: [
        ...(profilePatch.negative_interests || []),
        ...(profilePatch.positive_interests || []),
      ],
    }, { conflictStrategy: "last_decision" });
  }
  return mergeBoleProfilePatch(baseProfile, {}, { conflictStrategy: "ask" });
}

function mergeBoleProfilePatch(baseProfile = {}, profilePatch = {}, options = {}) {
  const base = baseProfile && typeof baseProfile === "object" ? baseProfile : {};
  const patch = profilePatch && typeof profilePatch === "object" ? profilePatch : {};
  const strategy = options.conflictStrategy === "last_decision" ? "last_decision" : "ask";
  if ((patch.positive_interests || patch.negative_interests) && strategy) {
    return resolveBoleProfilePatchConflict(base, patch, strategy).profile;
  }
  return {
    ...base,
    ...patch,
    positive_interests: uniqueBoleProfileEntries([
      ...(base.positive_interests || []),
      ...(patch.positive_interests || []),
    ]),
    negative_interests: uniqueBoleProfileEntries([
      ...(base.negative_interests || []),
      ...(patch.negative_interests || []),
    ]),
    source_preferences: uniqueBoleSourcePreferences([
      ...(base.source_preferences || []),
      ...(patch.source_preferences || []),
    ]),
    behavior_preferences: {
      ...(base.behavior_preferences || {}),
      ...(patch.behavior_preferences || {}),
    },
  };
}

function baseBoleProfileForSuggestion() {
  const status = state.personalizationStatus || {};
  return state.boleDraftPreview
    || status.draft_profile
    || status.active_profile
    || collectBoleDraftInput();
}

function currentBoleDraftProfile() {
  return state.boleDraftPreview || collectBoleDraftInput();
}

function closeBoleDraftSuggestionDialog() {
  if (!boleDraftSuggestionDialogEl) return;
  boleDraftSuggestionDialogEl.classList.remove("open");
  boleDraftSuggestionDialogEl.hidden = true;
  document.body.classList.remove("bole-draft-suggestion-open");
}

function mergeDraftSuggestionIntoWorkbench() {
  const suggestion = state.bolePendingDraftSuggestion;
  if (!suggestion) return;
  const patch = suggestion.profile_patch || {};
  const current = baseBoleProfileForSuggestion();
  state.boleDraftPreview = mergeBoleProfilePatch(current, patch);
  state.boleStage = "draft";
  closeBoleDraftSuggestionDialog();
  openBoleWorkbench();
}

function handleBoleProfileConflictDecision(decision) {
  const pending = state.bolePendingProfileConflict;
  if (!pending) return;
  if (decision === "ignore") {
    state.bolePendingProfileConflict = null;
    closeBoleProfileConflictDialog();
    return;
  }
  const profile = applyBoleConflictDecision(pending.baseProfile, pending.profilePatch, decision);
  applyResolvedBoleProfile(profile, { persist: true });
  state.bolePendingProfileConflict = null;
  closeBoleProfileConflictDialog();
}

function feedbackPayloadForItem(action, item) {
  const matchedTargets = boleFeedbackMatchedTargetLabels({ item }).slice(0, 8);
  const feedbackTarget = matchedTargets[0] || "";
  return {
    action,
    item: {
      id: item.item_id || item.id || "",
      title: itemTitleText(item),
      summary: item.summary || item.description || "",
      site_name: item.site_name || "",
      source: item.source || "",
      url: item.url || "",
      published_at: item.published_at || item.first_seen_at || "",
      ai_label: item.ai_label || "",
      ai_signals: Array.isArray(item.ai_signals) ? item.ai_signals : [],
      feedback_target: feedbackTarget,
      matched_targets: matchedTargets,
    },
  };
}

async function submitBoleFeedback(action, item, options = {}) {
  if (!item || !action) return null;
  const localFeedback = recordBoleSessionFeedback({
    action,
    item,
    created_at: new Date().toISOString(),
  });
  if (localFeedback) {
    state.boleFeedbackItems = [localFeedback, ...(state.boleFeedbackItems || []).filter((entry) => boleFeedbackItemKey(entry.item) !== localFeedback.item_key)];
    renderBoleFeedbackList();
    renderBolePicks();
  }
  closeReaderFeedbackPopover();
  closeBoleTunePopover();
  if (!apiBaseUrl) return localFeedback;
  try {
    const payload = await apiFetch("/api/personalization/feedback", {
      method: "POST",
      body: JSON.stringify(feedbackPayloadForItem(action, item)),
    });
    if (payload.feedback) {
      recordBoleSessionFeedback(payload.feedback);
      state.boleFeedbackItems = [payload.feedback, ...(state.boleFeedbackItems || []).filter((entry) => entry.id !== payload.feedback.id && boleFeedbackItemKey(entry.item) !== boleFeedbackItemKey(payload.feedback.item))];
      renderBoleFeedbackList();
      renderBolePicks();
    }
    if (payload.draft_suggestion) openBoleDraftSuggestionDialog(payload.draft_suggestion);
    return payload.feedback || localFeedback;
  } catch (err) {
    return localFeedback;
  }
}

async function undoBoleFeedback(feedbackId) {
  const id = String(feedbackId || "");
  if (!id) return;
  const feedback = (state.boleFeedbackItems || []).find((entry) => boleFeedbackRecordId(entry) === id);
  if (!feedback) return;
  rememberBoleFeedbackUndo(feedback);
  removeBoleSessionFeedback(feedback);
  state.boleFeedbackItems = (state.boleFeedbackItems || []).filter((entry) => boleFeedbackRecordId(entry) !== id);
  renderBoleFeedbackList();
  renderBolePicks();
  if (!apiBaseUrl || !boleFeedbackIsServerId(id)) return;
  try {
    await apiFetch(`/api/personalization/feedback/${encodeURIComponent(feedbackId)}`, { method: "DELETE" });
  } catch (_) {
    renderBoleFeedbackList();
    renderBolePicks();
  }
}

function scorePercent(item) {
  const score = Number(item.priority_score ?? item.ai_score ?? item.score ?? 0);
  if (!Number.isFinite(score) || score <= 0) return 0;
  return Math.round(score <= 1 ? score * 100 : score);
}

function scoreTone(score) {
  if (score >= 90) return "hot";
  if (score >= 75) return "strong";
  return "watch";
}

function labelText(item) {
  const labels = {
    ai_general: "AI信号",
    model_release: "模型发布",
    agent_workflow: "Agent工作流",
    ai_product_update: "产品更新",
    developer_tooling: "开发工具",
    infrastructure: "基础设施",
  };
  return labels[item.ai_label] || item.ai_label || "精选信号";
}

function reasonText(item) {
  const signals = Array.isArray(item.ai_signals) ? item.ai_signals.filter(Boolean).slice(0, 3) : [];
  if (signals.length) return `命中：${signals.join(" / ")}`;
  if (item.ai_relevance_reason) return String(item.ai_relevance_reason).replaceAll("_", " ");
  return "来源与标题信号通过筛选";
}

function timelineIso(item) {
  const published = item.published_at || "";
  const seen = item.first_seen_at || "";
  const generated = state.generatedAt || "";
  if (published && generated) {
    const publishedMs = new Date(published).getTime();
    const generatedMs = new Date(generated).getTime();
    if (Number.isFinite(publishedMs) && Number.isFinite(generatedMs) && publishedMs > generatedMs + 10 * 60 * 1000) {
      return seen || published;
    }
  }
  return published || seen;
}

function timelineMs(item) {
  const d = new Date(timelineIso(item));
  return Number.isNaN(d.getTime()) ? 0 : d.getTime();
}

function normalizedEventText(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[\s\u3000]+/g, "")
    .replace(/[，。、“”‘’：:；;！!？?（）()\[\]【】《》<>·.,/\\|_-]/g, "");
}

function eventTitleText(item) {
  if (!item || typeof item !== "object") return "";
  return String(item.title_original || item.title_en || item.title || item.title_zh || itemTitleText(item)).trim();
}

function eventActionToken(normalized) {
  const action = normalized.match(/(pricing|price|benchmark|coding|release|launch|shipping|upgrade|update|outage|policy|funding|acquisition|收购|融资|发布|上线|升级|更新|降价|定价|价格|评测|榜单|基准|故障|政策)/);
  return action ? action[1] : "";
}

function eventKey(item) {
  const raw = eventTitleText(item);
  const bracket = raw.match(/《([^》]{4,40})》/);
  if (bracket) return `book:${normalizedEventText(bracket[1]).slice(0, 36)}`;

  const normalized = normalizedEventText(raw);
  const model = normalized.match(/(bitcpmcann|deepseekv\d+(?:pro)?|grokv\d+(?:medium)?|gemini\d+(?:\.\d+)?(?:flash|pro)?|gpt\d+(?:\.\d+)?|llama\d+)/);
  if (model) {
    const action = eventActionToken(normalized);
    return `entity:${model[1]}:${action || normalized.slice(0, 28)}`;
  }

  return `title:${normalized.slice(0, 34)}`;
}

function bestBoleFeedbackTargetForRows(rows) {
  return uniqueBolePickStrings(
    (Array.isArray(rows) ? rows : [])
      .map((row) => boleFeedbackSpecificTargetLabel({ item: row?.item }))
      .filter(Boolean),
  )[0] || "";
}

function sourceSignal(item) {
  const site = item.site_name || "";
  const source = item.source || "";
  const hay = `${site} ${source}`.toLowerCase();
  if (site === "AI HOT") return "AI HOT精选";
  if (hay.includes("hackernews") || hay.includes("hacker news")) return "HN热议";
  if (source.includes("GitHub · Trending Today") || hay.includes("github")) return "GitHub趋势";
  if (site === "Official AI Updates") return "官方更新";
  if (site === "Follow Builders") return "Builders";
  if (site === "AIbase") return "AIbase";
  if (site === "OPML RSS") return "OPML";
  return site || "来源";
}

function sourcePriority(item) {
  const signal = sourceSignal(item);
  if (signal === "官方更新") return 100;
  if (signal === "AI HOT精选") return 90;
  if (signal === "AIbase") return 82;
  if (signal === "Builders") return 74;
  if (signal === "OPML") return 68;
  if (signal === "HN热议" || signal === "GitHub趋势") return 62;
  return 50;
}

function clusterBoleEvents(rows) {
  const clusters = new Map();
  rows.forEach((row) => {
    const key = eventKey(row.item);
    if (!clusters.has(key)) clusters.set(key, { key, rows: [], signals: new Set(), score: 0, primary: row });
    const cluster = clusters.get(key);
    cluster.rows.push(row);
    cluster.signals.add(sourceSignal(row.item));
    const currentPrimary = cluster.primary;
    const betterPrimary = sourcePriority(row.item) - sourcePriority(currentPrimary.item)
      || row.score - currentPrimary.score
      || timelineMs(row.item) - timelineMs(currentPrimary.item);
    if (betterPrimary > 0) cluster.primary = row;
  });
  return Array.from(clusters.values()).map((cluster) => {
    const signals = Array.from(cluster.signals);
    const maxScore = Math.max(...cluster.rows.map((row) => row.score));
    const feedbackTarget = bestBoleFeedbackTargetForRows(cluster.rows);
    const primaryItem = feedbackTarget
      ? { ...cluster.primary.item, feedback_target: feedbackTarget }
      : cluster.primary.item;
    const profileMatches = {
      positive: uniqueBolePickStrings(cluster.rows.flatMap((row) => row.profileMatches?.positive || [])),
      negative: uniqueBolePickStrings(cluster.rows.flatMap((row) => row.profileMatches?.negative || [])),
      sourcePositive: uniqueBolePickStrings(cluster.rows.flatMap((row) => row.profileMatches?.sourcePositive || [])),
      sourceNegative: uniqueBolePickStrings(cluster.rows.flatMap((row) => row.profileMatches?.sourceNegative || [])),
      behaviorPositive: uniqueBolePickStrings(cluster.rows.flatMap((row) => row.profileMatches?.behaviorPositive || [])),
    };
    const profileAdjustment = Math.max(...cluster.rows.map((row) => row.profileAdjustment || 0));
    const feedbackRow = cluster.rows.find((row) => row.feedbackAdjustment) || null;
    const sourceBonus = Math.min(12, Math.max(0, signals.length - 1) * 6);
    const candidateBonus = signals.some((s) => s === "AI HOT精选") ? 8
      : signals.some((s) => s === "HN热议" || s === "GitHub趋势") ? 6
      : signals.some((s) => s === "官方更新") ? 5
      : 0;
    return {
      item: primaryItem,
      index: cluster.primary.index,
      rows: cluster.rows,
      sourceSignals: signals,
      sourceCount: signals.length,
      mergedCount: cluster.rows.length,
      profileMatches,
      profileAdjustment,
      feedback: feedbackRow?.feedback || null,
      feedbackAdjustment: feedbackRow?.feedbackAdjustment || 0,
      score: Math.min(100, Math.round(maxScore + sourceBonus + candidateBonus)),
    };
  });
}

function pickBoleItems(items, profile = activeBolePersonalizationProfile()) {
  const ranked = [...items]
    .map((item, index) => {
      const baseScore = scorePercent(item);
      const personalized = personalizedBoleScore(item, baseScore, profile);
      const feedback = currentBoleFeedbackForItem(item);
      const feedbackAdjustment = boleFeedbackAdjustment(feedback?.action);
      return {
        item,
        index,
        baseScore,
        score: Math.max(1, Math.min(100, personalized.score + feedbackAdjustment)),
        profileMatches: personalized.matches,
        profileAdjustment: personalized.matches.adjustment,
        feedback,
        feedbackAdjustment,
      };
    })
    .filter((row) => row.score > 0)
    .sort((a, b) => {
      const byScore = b.score - a.score;
      if (byScore !== 0) return byScore;
      return timelineMs(b.item) - timelineMs(a.item) || a.index - b.index;
    });

  const sorted = clusterBoleEvents(ranked).sort((a, b) => {
    const byFeedback = (b.feedbackAdjustment || 0) - (a.feedbackAdjustment || 0);
    const byProfile = (b.profileAdjustment || 0) - (a.profileAdjustment || 0);
    const byMultiSource = b.sourceCount - a.sourceCount;
    const byScore = b.score - a.score;
    return byFeedback || byProfile || byMultiSource || byScore || timelineMs(b.item) - timelineMs(a.item) || a.index - b.index;
  });

  const picked = [];
  const addPick = (cluster) => {
    if (cluster && !picked.includes(cluster) && picked.length < BOLE_PICK_LIMIT) picked.push(cluster);
  };
  if (!profile) {
    ["AI HOT精选", "HN热议", "GitHub趋势"].forEach((signal) => {
      addPick(sorted.find((cluster) => cluster.sourceSignals.includes(signal)));
    });
  }
  sorted.forEach(addPick);
  return picked;
}

function boleProfileReasonText(row) {
  if (row.feedbackAdjustment > 0) return `已按反馈提升：${boleFeedbackActionLabel(row.feedback?.action)}`;
  if (row.feedbackAdjustment < 0) return `已按反馈降权：${boleFeedbackActionLabel(row.feedback?.action)}`;
  const positive = row.profileMatches?.positive || [];
  const negative = row.profileMatches?.negative || [];
  const sourcePositive = row.profileMatches?.sourcePositive || [];
  const sourceNegative = row.profileMatches?.sourceNegative || [];
  const behaviorPositive = row.profileMatches?.behaviorPositive || [];
  if (positive.length) return `符合您的画像：${positive.slice(0, 2).join(" / ")}`;
  if (negative.length) return `已按画像降权：${negative.slice(0, 2).join(" / ")}`;
  if (sourcePositive.length) return `符合您的来源偏好：${sourcePositive.slice(0, 2).join(" / ")}`;
  if (sourceNegative.length) return `已按来源偏好降权：${sourceNegative.slice(0, 2).join(" / ")}`;
  if (behaviorPositive.length) return `符合阅读偏好：${behaviorPositive.slice(0, 2).join(" / ")}`;
  return "";
}

function boleReasonText(row) {
  const signals = row.sourceSignals || [];
  const sourceText = signals.length ? `多源命中：${signals.join(" / ")}` : "来源命中：单源";
  const mergeText = row.mergedCount > 1 ? `合并${row.mergedCount}条同事件` : "单条事件";
  const profileText = boleProfileReasonText(row);
  return `精选理由：${profileText ? `${profileText} · ` : ""}${sourceText} · ${mergeText} · ${reasonText(row.item)}`;
}

function buildBoleLead(row) {
  const { item, score } = row;
  const lead = document.createElement("a");
  lead.className = "bole-lead-card";
  bindReaderLink(lead, item);

  const top = document.createElement("div");
  top.className = "bole-lead-top";
  const kicker = document.createElement("span");
  kicker.className = "bole-kicker";
  kicker.textContent = `${labelText(item)} · ${fmtTime(timelineIso(item))}`;
  const scoreEl = document.createElement("strong");
  scoreEl.className = `bole-score-orb ${scoreTone(score)}`;
  scoreEl.innerHTML = `<span>${score}</span><small>分</small>`;
  top.append(kicker, scoreEl);

  const title = document.createElement("div");
  title.className = "bole-lead-title";
  title.textContent = itemTitleText(item);

  const reason = document.createElement("div");
  reason.className = "bole-lead-reason";
  reason.textContent = reasonText(item);

  const foot = document.createElement("div");
  foot.className = "bole-lead-foot";
  foot.innerHTML = `<span>${item.site_name || "来源"}</span><span>${item.source || "未分区"}</span>`;

  lead.append(top, title, reason, foot);
  return lead;
}

function buildBoleTimelineRow(row, rank) {
  const { item, score } = row;
  const link = document.createElement("a");
  link.className = "bole-row";
  bindReaderLink(link, item);

  const time = document.createElement("time");
  time.className = "bole-row-time";
  time.textContent = fmtTime(timelineIso(item));

  const body = document.createElement("div");
  body.className = "bole-row-body";
  const meta = document.createElement("div");
  meta.className = "bole-row-meta";
  meta.innerHTML = `<span>#${rank}</span><span>${item.site_name || "来源"}</span><strong>${score}分</strong>`;
  (row.sourceSignals || []).slice(0, 4).forEach((signal) => {
    const tag = document.createElement("span");
    tag.className = "source-hit";
    tag.textContent = signal;
    meta.appendChild(tag);
  });
  const title = document.createElement("div");
  title.className = "bole-row-title";
  title.textContent = itemTitleText(item);
  const reason = document.createElement("div");
  reason.className = "bole-row-reason";
  reason.textContent = boleReasonText(row);

  const tune = document.createElement("button");
  tune.type = "button";
  tune.className = "bole-row-tune-button";
  if (tune.setAttribute) tune.setAttribute("aria-label", "调整推荐");
  else tune.ariaLabel = "调整推荐";
  tune.innerHTML = `
    <svg class="lucide-icon" aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="1"></circle>
      <circle cx="12" cy="5" r="1"></circle>
      <circle cx="12" cy="19" r="1"></circle>
    </svg>
  `;
  if (tune.addEventListener) {
    tune.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openBoleTunePopover(tune, item);
    });
  }

  body.append(meta, title, reason, tune);
  link.append(time, body);
  return link;
}

function renderBolePicks() {
  if (!bolePicksListEl || !bolePicksMetaEl) return;
  const activeProfile = activeBolePersonalizationProfile();
  const picks = pickBoleItems(state.itemsAi || [], activeProfile);
  bolePicksListEl.innerHTML = "";
  bolePicksListEl.className = "bole-board";
  if (!picks.length) {
    bolePicksMetaEl.textContent = "暂无评分数据";
    const empty = document.createElement("div");
    empty.className = "bole-empty";
    empty.textContent = "当前数据里没有可展示的评分字段。";
    bolePicksListEl.appendChild(empty);
    return;
  }

  const topScore = Math.max(...picks.map((row) => row.score));
  const displayPicks = state.boleSortMode === "time"
    ? [...picks].sort((a, b) => timelineMs(b.item) - timelineMs(a.item) || b.score - a.score || a.index - b.index)
    : picks;
  const sortLabel = state.boleSortMode === "time" ? "按时间排序" : "按得分排序";
  const profileLabel = activeProfile ? " · 已应用画像" : "";
  bolePicksMetaEl.textContent = `${sortLabel}${profileLabel} · Top ${fmtNumber(picks.length)} · 最高 ${topScore} 分`;

  const list = document.createElement("div");
  list.className = "bole-compact-list";
  displayPicks.forEach((row, index) => {
    list.appendChild(buildBoleTimelineRow(row, index + 1));
  });

  bolePicksListEl.appendChild(list);
}

function itemImageUrl(item) {
  const raw = String(item.image_url || item.thumbnail_url || item.media_url || "").trim();
  if (!/^https?:\/\//i.test(raw)) return "";
  if (/(^|\/)(image|placeholder|blank|spacer|transparent|pixel|loading|lazy|default)([-_.]?\d+)?\.(png|gif|jpe?g|webp|svg)(\?|$)|placehold\.co|1x1|^data:/i.test(raw)) {
    return "";
  }
  return raw;
}

function renderItemNode(item) {
  const node = itemTpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".site").textContent = item.site_name;
  const kind = sourceKind(item.site_id);
  const categoryEl = node.querySelector(".category");
  categoryEl.textContent = kind.label;
  categoryEl.classList.add(`kind-${kind.tone}`);
  node.querySelector(".source").textContent = `分区: ${item.source}`;
  node.querySelector(".time").textContent = fmtTime(item.published_at || item.first_seen_at);

  const titleEl = node.querySelector(".title");
  const zh = (item.title_zh || "").trim();
  const en = (item.title_en || "").trim();
  titleEl.textContent = "";
  if (zh && en && zh !== en) {
    const primary = document.createElement("span");
    primary.textContent = zh;
    const sub = document.createElement("span");
    sub.className = "title-sub";
    sub.textContent = en;
    titleEl.appendChild(primary);
    titleEl.appendChild(sub);
  } else {
    titleEl.textContent = item.title || zh || en;
  }
  bindReaderLink(titleEl, item);
  const thumbEl = node.querySelector(".card-thumb");
  const thumbUrl = itemImageUrl(item);
  node.classList.toggle("has-thumb", Boolean(thumbUrl));
  if (thumbEl && thumbUrl) {
    thumbEl.src = thumbUrl;
    thumbEl.hidden = false;
    thumbEl.addEventListener(
      "error",
      () => {
        thumbEl.hidden = true;
        node.classList.remove("has-thumb");
      },
      { once: true },
    );
  }
  const readerBtn = document.createElement("button");
  readerBtn.type = "button";
  readerBtn.className = "card-action reader-action";
  readerBtn.textContent = "阅读";
  readerBtn.disabled = !apiBaseUrl;
  readerBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openReader(item);
  });
  const verifyBtn = document.createElement("button");
  verifyBtn.type = "button";
  verifyBtn.className = "card-action verify-action";
  verifyBtn.textContent = "深度核验";
  verifyBtn.disabled = !apiBaseUrl;
  verifyBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    verifyBtn.disabled = true;
    verifyBtn.textContent = apiBaseUrl ? "核验中..." : "未配置";
    if (!apiBaseUrl) return;
    try {
      const result = await deepVerifyItem(itemIdentity(item), item);
      const verifiedItem = { ...item, ...result };
      verifyBtn.textContent = "已核验";
      state.verificationPayload = { items: [verifiedItem, ...(state.verificationPayload?.items || [])] };
      renderVerificationView(state.verificationPayload);
    } catch (_) {
      verifyBtn.disabled = false;
      verifyBtn.textContent = "重试核验";
    }
  });
  const actions = document.createElement("div");
  actions.className = "card-actions";
  actions.append(readerBtn, verifyBtn);
  node.appendChild(actions);
  return node;
}

function buildSourceGroupNode(source, items, siteId = "") {
  const sourceKey = sourceGroupKey(siteId, source);
  const expanded = state.expandedSourceGroups.has(sourceKey);
  const previewItems = expanded ? items : items.slice(0, SOURCE_ITEM_PREVIEW_COUNT);
  const section = document.createElement("section");
  section.className = "source-group";
  section.dataset.sourceKey = sourceKey;
  const header = document.createElement("header");
  header.className = "source-group-head";
  const title = document.createElement("h3");
  title.textContent = source;
  const meta = document.createElement("div");
  meta.className = "source-toggle-meta";
  const count = document.createElement("span");
  count.className = "source-count";
  count.textContent = `${fmtNumber(items.length)} 条`;
  if (items.length > SOURCE_ITEM_PREVIEW_COUNT) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "source-toggle-action";
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.setAttribute("aria-label", expanded ? `收起 ${source}` : `展开 ${source} 全部 ${fmtNumber(items.length)} 条`);
    const label = document.createElement("span");
    label.className = "source-toggle-label";
    label.textContent = expanded ? "收起" : "展开";
    const icon = document.createElement("span");
    icon.className = "source-toggle-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = expanded ? "▴" : "▾";
    toggle.append(label, icon);
    toggle.addEventListener("click", () => {
      if (expanded) {
        collapseSourceGroup(sourceKey);
      } else {
        state.expandedSourceGroups.add(sourceKey);
        renderList();
      }
    });
    meta.append(count, toggle);
  } else {
    meta.appendChild(count);
  }
  const listEl = document.createElement("div");
  listEl.className = "source-group-list";
  header.append(title, meta);
  section.append(header, listEl);
  previewItems.forEach((item) => listEl.appendChild(renderItemNode(item)));
  return section;
}

function groupBySource(items) {
  const groupMap = new Map();
  items.forEach((item) => {
    const key = item.source || "未分区";
    if (!groupMap.has(key)) {
      groupMap.set(key, []);
    }
    groupMap.get(key).push(item);
  });

  return Array.from(groupMap.entries()).sort((a, b) => {
    const byOrder = sourceOrderIndex(items[0]?.site_id || "", a[0]) - sourceOrderIndex(items[0]?.site_id || "", b[0]);
    if (byOrder !== 0) return byOrder;
    return b[1].length - a[1].length || a[0].localeCompare(b[0], "zh-CN");
  });
}

function renderGroupedBySource(items) {
  const groups = groupBySource(items);
  const frag = document.createDocumentFragment();

  groups.forEach(([source, groupItems]) => {
    frag.appendChild(buildSourceGroupNode(source, groupItems, state.siteFilter || groupItems[0]?.site_id || ""));
  });

  newsListEl.appendChild(frag);
}

function renderGroupedBySiteAndSource(items) {
  const siteMap = new Map();
  items.forEach((item) => {
    if (!siteMap.has(item.site_id)) {
      siteMap.set(item.site_id, {
        siteName: item.site_name || item.site_id,
        items: [],
      });
    }
    siteMap.get(item.site_id).items.push(item);
  });

  const sites = Array.from(siteMap.entries()).sort((a, b) => {
    const byOrder = siteOrderIndex(a[0]) - siteOrderIndex(b[0]);
    if (byOrder !== 0) return byOrder;
    const byCount = b[1].items.length - a[1].items.length;
    if (byCount !== 0) return byCount;
    return a[1].siteName.localeCompare(b[1].siteName, "zh-CN");
  });

  const frag = document.createDocumentFragment();
  sites.forEach(([siteId, site]) => {
    const siteSection = document.createElement("section");
    siteSection.className = "site-group";
    siteSection.dataset.siteId = siteId;
    const header = document.createElement("header");
    header.className = "site-group-head";
    const title = document.createElement("h3");
    title.textContent = site.siteName;
    const meta = document.createElement("div");
    meta.className = "site-toggle-meta";
    const count = document.createElement("span");
    count.textContent = `${fmtNumber(site.items.length)} 条`;
    const siteListEl = document.createElement("div");
    siteListEl.className = "site-group-list";

    const sourceGroups = groupBySource(site.items);
    const siteExpanded = state.expandedSites.has(siteId);
    if (sourceGroups.length > SOURCE_GROUP_PREVIEW_COUNT) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "site-toggle-action";
      toggle.setAttribute("aria-expanded", String(siteExpanded));
      toggle.setAttribute("aria-label", siteExpanded ? `收起 ${site.siteName}` : `展开 ${site.siteName} 全部 ${fmtNumber(sourceGroups.length)} 个来源`);
      const label = document.createElement("span");
      label.className = "site-toggle-label";
      label.textContent = siteExpanded ? "收起" : "展开";
      const icon = document.createElement("span");
      icon.className = "site-toggle-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = siteExpanded ? "▴" : "▾";
      toggle.append(label, icon);
      toggle.addEventListener("click", () => {
        if (siteExpanded) {
          collapseSiteGroup(siteId);
        } else {
          state.expandedSites.add(siteId);
          renderList();
        }
      });
      meta.append(count, toggle);
    } else {
      meta.appendChild(count);
    }

    header.append(title, meta);
    siteSection.append(header, siteListEl);

    const visibleGroups = siteExpanded ? sourceGroups : sourceGroups.slice(0, SOURCE_GROUP_PREVIEW_COUNT);
    visibleGroups.forEach(([source, groupItems]) => {
      siteListEl.appendChild(buildSourceGroupNode(source, groupItems, siteId));
    });
    frag.appendChild(siteSection);
  });

  newsListEl.appendChild(frag);
}

function renderList() {
  const filtered = getFilteredItems();
  resultCountEl.textContent = `${fmtNumber(filtered.length)} 条`;
  updateSourceHiddenButton();

  newsListEl.innerHTML = "";

  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "当前筛选条件下没有结果。";
    newsListEl.appendChild(empty);
    return;
  }

  if (state.siteFilter) {
    renderGroupedBySource(filtered);
    return;
  }

  renderGroupedBySiteAndSource(filtered);
}

function waytoagiViews(waytoagi) {
  const updates7d = Array.isArray(waytoagi?.updates_7d) ? waytoagi.updates_7d : [];
  const latestDate = waytoagi?.latest_date || (updates7d.length ? updates7d[0].date : null);
  const updatesToday = Array.isArray(waytoagi?.updates_today) && waytoagi.updates_today.length
    ? waytoagi.updates_today
    : (latestDate ? updates7d.filter((u) => u.date === latestDate) : []);
  return { updates7d, updatesToday, latestDate };
}

function renderWaytoagi(waytoagi) {
  const { updates7d, updatesToday, latestDate } = waytoagiViews(waytoagi);
  if (waytoagiTodayBtnEl) waytoagiTodayBtnEl.classList.toggle("active", state.waytoagiMode === "today");
  if (waytoagi7dBtnEl) waytoagi7dBtnEl.classList.toggle("active", state.waytoagiMode === "7d");
  waytoagiUpdatedAtEl.textContent = `更新时间：${fmtTime(waytoagi.generated_at)}`;

  waytoagiMetaEl.innerHTML = "";
  const rootLink = document.createElement("a");
  rootLink.href = waytoagi.root_url || "#";
  rootLink.target = "_blank";
  rootLink.rel = "noopener noreferrer";
  rootLink.textContent = "主页面";
  const historyLink = document.createElement("a");
  historyLink.href = waytoagi.history_url || "#";
  historyLink.target = "_blank";
  historyLink.rel = "noopener noreferrer";
  historyLink.textContent = "历史更新页";
  const todayCount = document.createElement("span");
  todayCount.textContent = `最近更新日(${latestDate || "--"})：${fmtNumber(waytoagi.count_today || updatesToday.length)} 条`;
  const weekCount = document.createElement("span");
  weekCount.textContent = `近 7 日：${fmtNumber(waytoagi.count_7d || updates7d.length)} 条`;
  [rootLink, "·", historyLink, "·", todayCount, "·", weekCount].forEach((part) => {
    if (typeof part === "string") {
      const sep = document.createElement("span");
      sep.textContent = part;
      waytoagiMetaEl.appendChild(sep);
    } else {
      waytoagiMetaEl.appendChild(part);
    }
  });

  waytoagiListEl.innerHTML = "";
  if (waytoagi.has_error) {
    const div = document.createElement("div");
    div.className = "waytoagi-error";
    div.textContent = waytoagi.error || "WaytoAGI 数据加载失败";
    waytoagiListEl.appendChild(div);
    return;
  }

  const updates = state.waytoagiMode === "today" ? updatesToday : updates7d;
  if (!updates.length) {
    const div = document.createElement("div");
    div.className = "waytoagi-empty";
    div.textContent = state.waytoagiMode === "today"
      ? "最近更新日没有更新，可切换到近7日查看。"
      : (waytoagi.warning || "近 7 日没有更新");
    waytoagiListEl.appendChild(div);
    return;
  }

  updates.forEach((u) => {
    const row = document.createElement("a");
    row.className = "waytoagi-item";
    row.href = u.url || "#";
    row.target = "_blank";
    row.rel = "noopener noreferrer";
    const dateEl = document.createElement("span");
    dateEl.className = "d";
    dateEl.textContent = fmtDate(u.date);
    const titleEl = document.createElement("span");
    titleEl.className = "t";
    titleEl.textContent = u.title;
    row.append(dateEl, titleEl);
    waytoagiListEl.appendChild(row);
  });
}

function renderMetric(label, value, tone = "") {
  const node = document.createElement("div");
  node.className = `health-metric ${tone}`.trim();
  const labelEl = document.createElement("span");
  labelEl.className = "health-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("strong");
  valueEl.textContent = value;
  node.append(labelEl, valueEl);
  return node;
}

function renderIssueList(title, items) {
  const wrap = document.createElement("div");
  wrap.className = "health-issue";
  const titleEl = document.createElement("div");
  titleEl.className = "health-issue-title";
  titleEl.textContent = title;
  const list = document.createElement("ul");
  items.slice(0, 6).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = typeof item === "string" ? item : JSON.stringify(item);
    list.appendChild(li);
  });
  if (items.length > 6) {
    const li = document.createElement("li");
    li.textContent = `另有 ${fmtNumber(items.length - 6)} 项`;
    list.appendChild(li);
  }
  wrap.append(titleEl, list);
  return wrap;
}

function renderSourceHealth(errorMessage = "") {
  if (!sourceHealthEl) return;
  sourceHealthEl.innerHTML = "";

  const status = state.sourceStatus;
  if (!status) {
    const empty = document.createElement("div");
    empty.className = "health-empty";
    empty.textContent = errorMessage || "源状态未生成";
    sourceHealthEl.appendChild(empty);
    renderAdvancedSummary();
    renderDataDrawerMeta();
    return;
  }

  const sites = Array.isArray(status.sites) ? status.sites : [];
  const failedSites = Array.isArray(status.failed_sites) ? status.failed_sites : [];
  const zeroSites = Array.isArray(status.zero_item_sites) ? status.zero_item_sites : [];
  const rss = status.rss_opml || {};
  const agentmail = status.agentmail || {};
  const xApi = status.x_api || {};
  const failedFeeds = Array.isArray(rss.failed_feeds) ? rss.failed_feeds : [];
  const skippedFeeds = Array.isArray(rss.skipped_feeds) ? rss.skipped_feeds : [];
  const replacedFeeds = Array.isArray(rss.replaced_feeds) ? rss.replaced_feeds : [];

  const metricGrid = document.createElement("div");
  metricGrid.className = "health-grid";
  metricGrid.append(
    renderMetric("内置源", `${fmtNumber(status.successful_sites || 0)}/${fmtNumber(sites.length)}`, failedSites.length ? "warn" : "ok"),
    renderMetric("RSS", rss.enabled ? `${fmtNumber(rss.ok_feeds || 0)}/${fmtNumber(rss.effective_feed_total || 0)}` : "未启用"),
    renderMetric("X API", xApi.enabled ? (xApi.skipped ? "待窗口" : `${fmtNumber(xApi.item_count || 0)}条`) : "未启用", xApi.error ? "bad" : ""),
    renderMetric("AgentMail", agentmail.enabled ? `${fmtNumber(agentmail.item_count || 0)}封` : "未启用", agentmail.error ? "bad" : ""),
    renderMetric("失败源", fmtNumber(failedSites.length + failedFeeds.length), failedSites.length || failedFeeds.length ? "bad" : "ok"),
    renderMetric("替换/跳过", `${fmtNumber(replacedFeeds.length)}/${fmtNumber(skippedFeeds.length)}`)
  );
  sourceHealthEl.appendChild(metricGrid);

  const issues = document.createElement("div");
  issues.className = "health-issues";
  if (failedSites.length) issues.appendChild(renderIssueList("失败站点", failedSites));
  if (zeroSites.length) issues.appendChild(renderIssueList("零结果站点", zeroSites));
  if (failedFeeds.length) issues.appendChild(renderIssueList("失败 RSS", failedFeeds));
  if (skippedFeeds.length) {
    issues.appendChild(renderIssueList("跳过 RSS", skippedFeeds.map((item) => `${item.feed_url} · ${item.reason || "skipped"}`)));
  }

  if (issues.childElementCount) {
    sourceHealthEl.appendChild(issues);
  } else {
    const ok = document.createElement("div");
    ok.className = "health-ok";
    ok.textContent = "源状态正常";
    sourceHealthEl.appendChild(ok);
  }
  renderAdvancedSummary();
  renderDataDrawerMeta();
}

async function loadNewsData() {
  return fetchFreshJson(`./data/latest-24h.json?t=${Date.now()}`, "加载 latest-24h.json 失败");
}

async function loadAllModeData() {
  if (state.allDataLoaded) return;
  if (!state.allDataPromise) {
    state.allDataPromise = fetchFreshJson(`./${state.allDataUrl}?t=${Date.now()}`, "加载 latest-24h-all.json 失败")
      .then((payload) => {
        state.itemsAllRaw = payload.items_all_raw || payload.items_all || state.itemsAi;
        state.itemsAll = payload.items_all || state.itemsAi;
        state.totalRaw = payload.total_items_raw || state.itemsAllRaw.length;
        state.totalAllMode = payload.total_items_all_mode || state.itemsAll.length;
        state.allDataLoaded = true;
      })
      .catch((err) => {
        state.allDataPromise = null;
        throw err;
      });
  }
  return state.allDataPromise;
}

async function loadWaytoagiData() {
  return fetchFreshJson(`./data/waytoagi-7d.json?t=${Date.now()}`, "加载 waytoagi-7d.json 失败");
}

async function loadSourceStatusData() {
  return fetchFreshJson(`./data/source-status.json?t=${Date.now()}`, "加载 source-status.json 失败");
}

async function init() {
  const [newsResult, waytoagiResult, statusResult] = await Promise.allSettled([
    loadNewsData(),
    loadWaytoagiData(),
    loadSourceStatusData(),
  ]);

  if (newsResult.status === "fulfilled") {
    const payload = newsResult.value;
    state.itemsAi = payload.items_ai || payload.items || [];
    state.itemsAllRaw = payload.items_all_raw || payload.items_all || [];
    state.itemsAll = payload.items_all || [];
    state.statsAi = payload.site_stats || [];
    state.totalAi = payload.total_items || state.itemsAi.length;
    state.totalRaw = payload.total_items_raw || state.itemsAllRaw.length;
    state.totalAllMode = payload.total_items_all_mode || state.itemsAll.length;
    state.allDataUrl = payload.all_mode_data_url || state.allDataUrl;
    state.allDataLoaded = Boolean(payload.items_all || payload.items_all_raw);
    state.generatedAt = payload.generated_at;

    setStats(payload);
    renderDataDrawerMeta();
    renderModeSwitch();
    renderCoverageStrip();
    renderBolePicks();
    renderSiteFilters();
    renderList();
    updatedAtEl.textContent = fmtTime(state.generatedAt);
  } else {
    updatedAtEl.textContent = "新闻数据加载失败";
    newsListEl.innerHTML = `<div class="empty">${newsResult.reason.message}</div>`;
    renderCoverageStrip(newsResult.reason.message);
  }

  if (statusResult.status === "fulfilled") {
    state.sourceStatus = statusResult.value;
    renderSourceHealth();
    renderCoverageStrip();
  } else {
    renderSourceHealth(statusResult.reason.message);
    renderCoverageStrip(statusResult.reason.message);
  }

  if (waytoagiResult.status === "fulfilled") {
    state.waytoagiData = waytoagiResult.value;
    renderWaytoagi(state.waytoagiData);
  } else {
    waytoagiUpdatedAtEl.textContent = "加载失败";
    waytoagiListEl.innerHTML = `<div class="waytoagi-error">${waytoagiResult.reason.message}</div>`;
  }

  renderCategoryView(state.taxonomy, state.itemsAi);
  renderVerificationView(state.verificationPayload);
  loadOptionalBackendData();
  loadSettings();
}

searchInputEl.addEventListener("input", (e) => {
  state.query = e.target.value;
  renderList();
});

siteSelectEl.addEventListener("change", (e) => {
  state.siteFilter = e.target.value;
  renderSiteFilters();
  renderList();
});

modeAiBtnEl.addEventListener("click", () => {
  state.mode = "ai";
  renderModeSwitch();
  renderSiteFilters();
  renderList();
});

modeAllBtnEl.addEventListener("click", async () => {
  state.mode = "all";
  renderModeSwitch();
  newsListEl.innerHTML = "";
  const loading = document.createElement("div");
  loading.className = "empty";
  loading.textContent = "正在加载全量更新...";
  newsListEl.appendChild(loading);
  try {
    await loadAllModeData();
    renderSiteFilters();
    renderList();
  } catch (err) {
    newsListEl.innerHTML = "";
    const failed = document.createElement("div");
    failed.className = "empty";
    failed.textContent = err.message;
    newsListEl.appendChild(failed);
  }
});

if (allDedupeToggleEl) {
  allDedupeToggleEl.addEventListener("change", (e) => {
    state.allDedup = Boolean(e.target.checked);
    renderModeSwitch();
    renderSiteFilters();
    renderList();
  });
}

if (waytoagiTodayBtnEl) {
  waytoagiTodayBtnEl.addEventListener("click", () => {
    state.waytoagiMode = "today";
    if (state.waytoagiData) renderWaytoagi(state.waytoagiData);
  });
}

if (waytoagi7dBtnEl) {
  waytoagi7dBtnEl.addEventListener("click", () => {
    state.waytoagiMode = "7d";
    if (state.waytoagiData) renderWaytoagi(state.waytoagiData);
  });
}

document.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    setMobileView(btn.dataset.view || "today");
  });
});
desktopViewButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    setMobileView(btn.dataset.view || "today");
  });
});

if (dataDrawerButtonEl) dataDrawerButtonEl.addEventListener("click", openDataDrawer);
if (dataDrawerCloseEl) dataDrawerCloseEl.addEventListener("click", closeDataDrawer);
if (dataDrawerEl) {
  dataDrawerEl.addEventListener("click", (event) => {
    if (event.target === dataDrawerEl) closeDataDrawer();
  });
}

if (sourceSortButtonEl) sourceSortButtonEl.addEventListener("click", openSourceSortDialog);
if (sourceHiddenButtonEl) sourceHiddenButtonEl.addEventListener("click", openSourceHiddenDialog);
if (sourceSortCloseEl) sourceSortCloseEl.addEventListener("click", closeSourceSortDialog);
if (sourceHiddenCloseEl) sourceHiddenCloseEl.addEventListener("click", closeSourceHiddenDialog);
if (sourceSortBlockButtonEl) sourceSortBlockButtonEl.addEventListener("click", blockSelectedSourceGroups);
if (sourceSortDialogEl) {
  sourceSortDialogEl.addEventListener("click", (event) => {
    if (event.target === sourceSortDialogEl) closeSourceSortDialog();
  });
}
if (sourceHiddenDialogEl) {
  sourceHiddenDialogEl.addEventListener("click", (event) => {
    if (event.target === sourceHiddenDialogEl) closeSourceHiddenDialog();
  });
}
if (boleSortButtonEl) {
  boleSortButtonEl.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleBoleSortPopover();
  });
}
if (boleSortPopoverEl) {
  boleSortPopoverEl.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-bole-sort-mode]");
    if (!button) return;
    event.stopPropagation();
    setBoleSortMode(button.dataset.boleSortMode);
    closeBoleSortPopover();
  });
}
if (boleFeedbackButtonEl) boleFeedbackButtonEl.addEventListener("click", openBoleFeedbackDialog);
if (boleFeedbackCloseEl) boleFeedbackCloseEl.addEventListener("click", closeBoleFeedbackDialog);
if (boleFeedbackDialogEl) {
  boleFeedbackDialogEl.addEventListener("click", (event) => {
    if (event.target === boleFeedbackDialogEl) closeBoleFeedbackDialog();
  });
}
if (boleFeedbackSearchEl) boleFeedbackSearchEl.addEventListener("input", () => setBoleFeedbackFilter("query", boleFeedbackSearchEl.value));
if (boleFeedbackTopicFilterEl) boleFeedbackTopicFilterEl.addEventListener("change", () => setBoleFeedbackFilter("topic", boleFeedbackTopicFilterEl.value));
if (boleFeedbackActionFilterEl) boleFeedbackActionFilterEl.addEventListener("change", () => setBoleFeedbackFilter("action", boleFeedbackActionFilterEl.value));
if (boleFeedbackSortSelectEl) boleFeedbackSortSelectEl.addEventListener("change", () => setBoleFeedbackFilter("sort", boleFeedbackSortSelectEl.value));
if (boleFeedbackActionOrderEl) {
  boleFeedbackActionOrderEl.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-bole-feedback-action-order]");
    if (!button) return;
    moveBoleFeedbackActionOrder(button.dataset.boleFeedbackActionOrder, button.dataset.direction);
  });
}
if (boleFeedbackListEl) {
  boleFeedbackListEl.addEventListener("click", (event) => {
    const undo = event.target.closest?.("[data-bole-feedback-undo]");
    if (undo) undoBoleFeedback(undo.dataset.boleFeedbackUndo);
  });
}
if (boleTunePopoverEl) {
  boleTunePopoverEl.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-bole-tune-action]");
    if (!button) return;
    submitBoleFeedback(button.dataset.boleTuneAction, state.boleTuneItem);
  });
}
if (boleDraftSuggestionCloseEl) boleDraftSuggestionCloseEl.addEventListener("click", closeBoleDraftSuggestionDialog);
if (boleDraftSuggestionDismissEl) boleDraftSuggestionDismissEl.addEventListener("click", closeBoleDraftSuggestionDialog);
if (boleDraftSuggestionSaveEl) boleDraftSuggestionSaveEl.addEventListener("click", mergeDraftSuggestionIntoWorkbench);
if (boleDraftSuggestionDialogEl) {
  boleDraftSuggestionDialogEl.addEventListener("click", (event) => {
    if (event.target === boleDraftSuggestionDialogEl) closeBoleDraftSuggestionDialog();
  });
}
if (boleProfileConflictCloseEl) boleProfileConflictCloseEl.addEventListener("click", closeBoleProfileConflictDialog);
if (boleProfileConflictDialogEl) {
  boleProfileConflictDialogEl.addEventListener("click", (event) => {
    if (event.target === boleProfileConflictDialogEl) closeBoleProfileConflictDialog();
    const button = event.target.closest?.("[data-bole-conflict-decision]");
    if (button) handleBoleProfileConflictDecision(button.dataset.boleConflictDecision);
  });
}
document.addEventListener("pointerdown", (event) => {
  if (!boleSortPopoverEl?.hidden && !event.target.closest?.(".bole-sort-popover, .bole-sort-button")) closeBoleSortPopover();
});
document.addEventListener("pointerdown", (event) => {
  if (boleTunePopoverEl?.hidden) return;
  if (event.target.closest?.(".bole-tune-popover, .bole-row-tune-button")) return;
  closeBoleTunePopover();
});
document.addEventListener("pointerdown", (event) => {
  if (readerFeedbackPopoverEl?.hidden) return;
  if (event.target.closest?.(".reader-feedback-popover, .reader-feedback-trigger")) return;
  closeReaderFeedbackPopover();
});
document.addEventListener("pointerup", handleSourceSortPointerEnd);
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  closeDataDrawer();
  closeSourceSortDialog();
  closeSourceHiddenDialog();
  closeBoleSortPopover();
  closeBoleFeedbackDialog();
  closeBoleTunePopover();
  closeReaderFeedbackPopover();
  closeBoleDraftSuggestionDialog();
  closeBoleProfileConflictDialog();
  closeAiConfigDialog();
  closeBoleWorkbench();
});

if (boleWorkbenchOpenEl) {
  boleWorkbenchOpenEl.addEventListener("click", async () => {
    if (!state.personalizationStatus && apiBaseUrl) await loadPersonalization({ quiet: true });
    openBolePersonalizationEntry();
  });
}
if (boleSettingsOpenEl) {
  boleSettingsOpenEl.addEventListener("click", async () => {
    if (!state.personalizationStatus && apiBaseUrl) await loadPersonalization({ quiet: true });
    openBolePersonalizationEntry();
  });
}
if (aiConfigDialogEl) {
  aiConfigDialogEl.addEventListener("click", (event) => {
    if (event.target === aiConfigDialogEl) closeAiConfigDialog();
  });
}
if (aiConfigPanelEl) {
  aiConfigPanelEl.addEventListener("click", (event) => event.stopPropagation());
}
if (aiConfigAdvancedToggleEl) {
  aiConfigAdvancedToggleEl.addEventListener("click", () => {
    if (!aiConfigAdvancedPanelEl) return;
    aiConfigAdvancedPanelEl.hidden = !aiConfigAdvancedPanelEl.hidden;
    if (aiConfigAdvancedStateEl) aiConfigAdvancedStateEl.textContent = aiConfigAdvancedPanelEl.hidden ? "展开" : "收起";
    aiConfigPanelEl?.classList.toggle("advanced-open", !aiConfigAdvancedPanelEl.hidden);
  });
}
if (aiConfigSkipButtonEl) aiConfigSkipButtonEl.addEventListener("click", skipAiConfigDialog);
if (aiConfigSaveButtonEl) aiConfigSaveButtonEl.addEventListener("click", saveAiConfigAndContinue);
if (aiConfigTestButtonEl) aiConfigTestButtonEl.addEventListener("click", testAiConfigConnection);
if (boleWorkbenchCloseEl) boleWorkbenchCloseEl.addEventListener("click", closeBoleWorkbench);
if (boleWorkbenchEl) {
  boleWorkbenchEl.addEventListener("click", (event) => {
    if (event.target === boleWorkbenchEl) closeBoleWorkbench();
  });
}
boleStageButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const stage = button.dataset.boleStage || "calibration";
    if (stage === "draft") state.boleDraftPreview = collectBoleDraftInput();
    setBoleStage(stage);
  });
});
function handleBoleQuestionChoiceClick(button) {
  const questionId = button.dataset.boleQuestionChoice;
  const question = boleQuestionById(questionId);
  const choice = button.dataset.boleChoice || button.textContent;
  activateBoleQuestion(questionId);
  const answer = normalizeBoleAnswer(state.boleAnswers[questionId]);
  const choices = question?.multiple === false
    ? (answer.choices.includes(choice) ? [] : [choice])
    : answer.choices.includes(choice)
      ? answer.choices.filter((item) => item !== choice)
      : uniqueBoleLabels([...answer.choices, choice]);
  mergeBoleAnswer(questionId, { choices });
  state.boleDraftPreview = collectBoleDraftInput();
  renderBoleWorkbench();
}

function handleBoleQuestionAreaClick(event) {
  const dot = event.target.closest("[data-bole-question-dot]");
  if (dot) {
    transitionBoleQuestion(dot.dataset.boleQuestionDot);
    return;
  }
  const button = event.target.closest("[data-bole-question-choice]");
  if (button) {
    handleBoleQuestionChoiceClick(button);
    return;
  }
  const turn = event.target.closest("[data-bole-question-id]");
  if (turn && turn.classList.contains("answered")) transitionBoleQuestion(turn.dataset.boleQuestionId);
}

if (boleDialogueTurnsEl) {
  boleDialogueTurnsEl.addEventListener("click", handleBoleQuestionAreaClick);
}
if (boleReadingTurnsEl) {
  boleReadingTurnsEl.addEventListener("click", handleBoleQuestionAreaClick);
}
boleQuestionDotGroups.forEach((group) => group.addEventListener("click", handleBoleQuestionAreaClick));
if (boleChatFormEl) {
  boleChatFormEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = boleChatInputEl?.value || "";
    await advanceBoleQuestion(text);
  });
}
if (boleChatInputEl) {
  boleChatInputEl.addEventListener("input", () => {
    const question = activeBoleQuestion(state.boleStage);
    if (!question) return;
    const answer = normalizeBoleAnswer(state.boleAnswers[question.id]);
    mergeBoleAnswer(question.id, {
      choices: answer.choices,
      text: boleChatInputEl.value,
      ai_labels: [],
      ai_note: "",
      follow_up: "",
    });
    state.boleDraftPreview = collectBoleDraftInput();
    renderBoleRecognizedProfile();
    syncBoleActionButtons();
  });
}
if (boleRecognizedProfileEl) {
  boleRecognizedProfileEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-bole-remove-question]");
    if (!button) return;
    removeBoleProfileLabel(button.dataset.boleRemoveQuestion, button.dataset.boleRemoveLabel || "");
  });
}
if (boleConfirmButtonEl) {
  boleConfirmButtonEl.addEventListener("click", () => {
    if (state.boleStage === "draft") confirmBoleProfile();
    else saveBoleDraft();
  });
}
if (boleSkipButtonEl) boleSkipButtonEl.addEventListener("click", skipBolePersonalization);
if (boleResetButtonEl) boleResetButtonEl.addEventListener("click", resetBolePersonalization);
if (boleDisableButtonEl) boleDisableButtonEl.addEventListener("click", disableBolePersonalization);
if (boleContinueButtonEl) {
  boleContinueButtonEl.addEventListener("click", () => {
    if (state.boleStage === "calibration") setBoleStage("preferences");
    else if (state.boleStage === "preferences") setBoleStage("draft");
  });
}

if (askAiButtonEl) {
  askAiButtonEl.addEventListener("click", () => {
    openAskAi();
  });
}
if (desktopAskAiButtonEl) {
  desktopAskAiButtonEl.addEventListener("click", () => {
    openAskAi();
  });
}

if (readerCloseEl) readerCloseEl.addEventListener("click", closeReader);
if (readerPanelEl) {
  readerPanelEl.addEventListener("pointerdown", handleReaderPanelDragStart);
  readerPanelEl.addEventListener("pointermove", handleReaderPanelDragMove);
  readerPanelEl.addEventListener("pointerup", handleReaderPanelDragEnd);
  readerPanelEl.addEventListener("pointercancel", handleReaderPanelDragEnd);
}
if (readerTranslateButtonEl) readerTranslateButtonEl.addEventListener("click", translateReaderArticle);
if (readerSummaryButtonEl) readerSummaryButtonEl.addEventListener("click", summarizeReaderArticle);
if (readerFactCheckButtonEl) readerFactCheckButtonEl.addEventListener("click", factCheckReaderArticle);
if (readerFeedbackTriggerEl) {
  readerFeedbackTriggerEl.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleReaderFeedbackPopover();
  });
}
if (readerFeedbackPopoverEl) {
  readerFeedbackPopoverEl.addEventListener("click", (event) => {
    const button = event.target.closest?.("[data-bole-feedback-action]");
    if (!button) return;
    event.stopPropagation();
    submitBoleFeedback(button.dataset.boleFeedbackAction, state.readerItem);
  });
}
if (readerAskButtonEl) {
  readerAskButtonEl.addEventListener("click", async () => {
    const item = state.readerItem || {};
    openAskAi({
      item_id: await readerItemId(item),
      item_title: itemTitleText(item),
    });
  });
}
if (askAiCloseEl) askAiCloseEl.addEventListener("click", closeAskAi);
if (askAiPanelEl) {
  askAiPanelEl.addEventListener("pointerdown", handleAskPanelDragStart);
  askAiPanelEl.addEventListener("pointermove", handleAskPanelDragMove);
  askAiPanelEl.addEventListener("pointerup", handleAskPanelDragEnd);
  askAiPanelEl.addEventListener("pointercancel", handleAskPanelDragEnd);
}
if (askAiMessagesButtonEl) askAiMessagesButtonEl.addEventListener("click", () => setAskPanelView("messages"));
if (askAiHistoryButtonEl) askAiHistoryButtonEl.addEventListener("click", toggleAskHistory);
if (askAiSubmitEl) askAiSubmitEl.addEventListener("click", submitAskAi);
if (askAiAnswerEl) {
  askAiAnswerEl.addEventListener("mouseup", handleAskSelection);
  askAiAnswerEl.addEventListener("touchend", () => window.setTimeout(handleAskSelection, 80));
  askAiAnswerEl.addEventListener("pointerdown", handleAskLongPress);
  askAiAnswerEl.addEventListener("pointerup", clearAskLongPress);
  askAiAnswerEl.addEventListener("pointercancel", clearAskLongPress);
  askAiAnswerEl.addEventListener("contextmenu", (event) => {
    if (event.target.closest?.(".ask-ai-message.ai .ask-ai-bubble")) {
      event.preventDefault();
    }
  });
}
if (askAiInputEl) {
  askAiInputEl.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      submitAskAi();
    }
  });
}

if (loginButtonEl) loginButtonEl.addEventListener("click", loginAdmin);
if (saveSettingsButtonEl) saveSettingsButtonEl.addEventListener("click", saveSettings);
if (saveAiProfileButtonEl) saveAiProfileButtonEl.addEventListener("click", saveAiProfile);
if (testAiProfileButtonEl) testAiProfileButtonEl.addEventListener("click", () => testAiProfile());
if (resetAiProfileFormButtonEl) resetAiProfileFormButtonEl.addEventListener("click", resetAiProfileForm);
if (translationProviderModeSelectEl) {
  translationProviderModeSelectEl.addEventListener("change", () => {
    state.translationProviderMode = translationProviderModeSelectEl.value || "browser";
    syncTranslationProviderMode();
    saveSettings();
  });
}
if (translationProviderSelectEl) {
  translationProviderSelectEl.addEventListener("change", () => {
    state.translationProviderId = translationProviderSelectEl.value || "";
    saveSettings();
  });
}
if (readingAssistantProviderSelectEl) {
  readingAssistantProviderSelectEl.addEventListener("change", () => {
    state.readingAssistantProviderId = readingAssistantProviderSelectEl.value || "env";
    saveSettings();
  });
}
if (boleConflictStrategySelectEl) {
  boleConflictStrategySelectEl.addEventListener("change", () => {
    state.boleConflictStrategy = boleConflictStrategySelectEl.value === "last_decision" ? "last_decision" : "ask";
    saveSettings();
  });
}
if (askStreamingToggleEl) {
  askStreamingToggleEl.addEventListener("change", () => {
    state.askStreamingEnabled = Boolean(askStreamingToggleEl.checked);
    saveSettings();
  });
}
if (aiProfilesListEl) {
  aiProfilesListEl.addEventListener("click", (event) => {
    const button = event.target.closest?.("button[data-action]");
    if (!button) return;
    const row = button.closest(".ai-profile-row");
    const profileId = row?.dataset.profileId || "";
    const action = button.dataset.action;
    const profile = state.aiProfiles.find((item) => item.id === profileId);
    if (action === "edit" && profile) {
      fillAiProfileForm(profile);
    }
    if (action === "test") {
      testAiProfile(profileId);
    }
    if (action === "delete" && profileId) {
      if (window.confirm && !window.confirm("删除这个 AI 配置？")) return;
      deleteAiProfile(profileId);
    }
  });
}
if (adminPasswordInputEl) {
  adminPasswordInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") loginAdmin();
  });
}

setMobileView(state.mobileView);
renderBoleWorkbench();
init();
