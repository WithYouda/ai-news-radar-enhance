const appConfig = window.AI_NEWS_RADAR_CONFIG || {};
const apiBaseUrl = String(appConfig.apiBaseUrl || "").replace(/\/$/, "");

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
  taxonomy: [],
  verificationPayload: null,
  askContext: {},
  askQuote: "",
  askStreamingEnabled: false,
  activeConversationId: null,
  askHistoryLoaded: false,
  askHistoryVisible: false,
  readerItem: null,
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

const waytoagiUpdatedAtEl = document.getElementById("waytoagiUpdatedAt");
const waytoagiMetaEl = document.getElementById("waytoagiMeta");
const waytoagiListEl = document.getElementById("waytoagiList");
const waytoagiTodayBtnEl = document.getElementById("waytoagiTodayBtn");
const waytoagi7dBtnEl = document.getElementById("waytoagi7dBtn");
const coverageStripEl = document.getElementById("coverageStrip");
const bolePicksListEl = document.getElementById("bolePicksList");
const bolePicksMetaEl = document.getElementById("bolePicksMeta");
const askAiButtonEl = document.getElementById("askAiButton");
const categoryMetaEl = document.getElementById("categoryMeta");
const categoryGridEl = document.getElementById("categoryGrid");
const categoryDetailEl = document.getElementById("categoryDetail");
const verificationMetaEl = document.getElementById("verificationMeta");
const verificationSummaryEl = document.getElementById("verificationSummary");
const verificationListEl = document.getElementById("verificationList");
const askAiSheetEl = document.getElementById("askAiSheet");
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
const readerSheetEl = document.getElementById("readerSheet");
const readerCloseEl = document.getElementById("readerClose");
const readerTitleEl = document.getElementById("readerTitle");
const readerSourceEl = document.getElementById("readerSource");
const readerBodyEl = document.getElementById("readerBody");
const readerOriginalLinkEl = document.getElementById("readerOriginalLink");
const readerAskButtonEl = document.getElementById("readerAskButton");

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
  document.querySelectorAll("[data-mobile-view]").forEach((el) => {
    el.hidden = el.dataset.mobileView !== view;
  });
  document.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
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
  askAiSheetEl.hidden = false;
  document.body.classList.add("ask-ai-open");
  if (askAiInputEl) askAiInputEl.focus();
}

function closeAskAi() {
  if (!askAiSheetEl) return;
  askAiSheetEl.hidden = true;
  document.body.classList.remove("ask-ai-open");
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

async function submitAskAiStream(question, pendingRow) {
  let streamedText = "";
  let donePayload = null;
  try {
    await apiStream("/api/ask/stream", askRequestBody(question), (event) => {
      if (event.type === "delta") {
        streamedText += String(event.payload?.text || "");
        updateStreamingBubble(pendingRow, streamedText);
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

function setSettingsStatus(text) {
  if (settingsStatusEl) settingsStatusEl.textContent = text;
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
  readerSheetEl.hidden = true;
  document.body.classList.remove("reader-open");
}

function renderReaderLoading(item) {
  if (readerTitleEl) readerTitleEl.textContent = itemTitleText(item);
  if (readerSourceEl) readerSourceEl.textContent = item.site_name || item.source || "AI News Radar";
  if (readerOriginalLinkEl) {
    readerOriginalLinkEl.href = item.url || "#";
    readerOriginalLinkEl.hidden = !item.url;
  }
  if (readerBodyEl) {
    readerBodyEl.innerHTML = '<div class="reader-state">正在清洗原文...</div>';
  }
}

function renderReaderArticle(payload) {
  if (!readerBodyEl) return;
  if (readerTitleEl) readerTitleEl.textContent = payload.title || itemTitleText(payload.item || {});
  if (readerSourceEl) {
    const meta = [payload.site_name, payload.published_at ? fmtTime(payload.published_at) : "", payload.cache_status === "hit" ? "已缓存" : "新抓取"]
      .filter(Boolean)
      .join(" · ");
    readerSourceEl.textContent = meta || "AI News Radar";
  }
  if (readerOriginalLinkEl) readerOriginalLinkEl.href = payload.final_url || payload.url || "#";
  readerBodyEl.innerHTML = payload.content_html || `<p>${escapeHtml(payload.text || "未能提取正文。")}</p>`;
}

async function loadCleanArticle(item) {
  if (!apiBaseUrl) throw new Error("AI 后端未配置，暂时无法清洗原文。");
  const id = await readerItemId(item);
  return apiFetch(`/api/read/${encodeURIComponent(id)}`);
}

async function openReader(item) {
  if (!readerSheetEl) return;
  state.readerItem = item;
  renderReaderLoading(item);
  readerSheetEl.hidden = false;
  document.body.classList.add("reader-open");
  try {
    const payload = await loadCleanArticle(item);
    renderReaderArticle(payload);
  } catch (err) {
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
    if (state.siteFilter && item.site_id !== state.siteFilter) return false;
    if (!q) return true;
    const hay = `${item.title || ""} ${item.title_zh || ""} ${item.title_en || ""} ${item.site_name || ""} ${item.source || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function itemTitleText(item) {
  return (item.title_zh || item.title || item.title_en || "未命名更新").trim();
}

function scorePercent(item) {
  const score = Number(item.ai_score ?? item.score ?? 0);
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

function eventKey(item) {
  const raw = itemTitleText(item);
  const bracket = raw.match(/《([^》]{4,40})》/);
  if (bracket) return `book:${normalizedEventText(bracket[1]).slice(0, 36)}`;

  const normalized = normalizedEventText(raw);
  const model = normalized.match(/(bitcpmcann|deepseekv\d+(?:pro)?|grokv\d+(?:medium)?|gemini\d+(?:\.\d+)?(?:flash|pro)?|gpt\d+(?:\.\d+)?|llama\d+)/);
  if (model) return `entity:${model[1]}`;

  return `title:${normalized.slice(0, 34)}`;
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
    const sourceBonus = Math.min(12, Math.max(0, signals.length - 1) * 6);
    const candidateBonus = signals.some((s) => s === "AI HOT精选") ? 8
      : signals.some((s) => s === "HN热议" || s === "GitHub趋势") ? 6
      : signals.some((s) => s === "官方更新") ? 5
      : 0;
    return {
      item: cluster.primary.item,
      index: cluster.primary.index,
      rows: cluster.rows,
      sourceSignals: signals,
      sourceCount: signals.length,
      mergedCount: cluster.rows.length,
      score: Math.min(100, Math.round(maxScore + sourceBonus + candidateBonus)),
    };
  });
}

function pickBoleItems(items) {
  const ranked = [...items]
    .map((item, index) => ({ item, index, score: scorePercent(item) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => {
      const byScore = b.score - a.score;
      if (byScore !== 0) return byScore;
      return timelineMs(b.item) - timelineMs(a.item) || a.index - b.index;
    });

  const sorted = clusterBoleEvents(ranked).sort((a, b) => {
    const byMultiSource = b.sourceCount - a.sourceCount;
    const byScore = b.score - a.score;
    return byMultiSource || byScore || timelineMs(b.item) - timelineMs(a.item) || a.index - b.index;
  });

  const picked = [];
  const addPick = (cluster) => {
    if (cluster && !picked.includes(cluster) && picked.length < 8) picked.push(cluster);
  };
  ["AI HOT精选", "HN热议", "GitHub趋势"].forEach((signal) => {
    addPick(sorted.find((cluster) => cluster.sourceSignals.includes(signal)));
  });
  sorted.forEach(addPick);
  return picked;
}

function boleReasonText(row) {
  const signals = row.sourceSignals || [];
  const sourceText = signals.length ? `多源命中：${signals.join(" / ")}` : "来源命中：单源";
  const mergeText = row.mergedCount > 1 ? `合并${row.mergedCount}条同事件` : "单条事件";
  return `精选理由：${sourceText} · ${mergeText} · ${reasonText(row.item)}`;
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
  body.append(meta, title, reason);

  link.append(time, body);
  return link;
}

function renderBolePicks() {
  if (!bolePicksListEl || !bolePicksMetaEl) return;
  const picks = pickBoleItems(state.itemsAi || []);
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
  const timelinePicks = [...picks].sort((a, b) => {
    const byTime = timelineMs(b.item) - timelineMs(a.item);
    if (byTime !== 0) return byTime;
    return b.score - a.score || a.index - b.index;
  });
  bolePicksMetaEl.textContent = `按时间倒序 · Top ${fmtNumber(picks.length)} · 最高 ${topScore} 分`;

  const explainer = document.createElement("div");
  explainer.className = "bole-explainer";
  explainer.textContent = "伯乐精选依据：多源命中优先，其次看官方源、AI 分、HN/GitHub/AI HOT 热度和发布时间；同一事件会合并，只保留最值得点开的来源。";

  const list = document.createElement("div");
  list.className = "bole-compact-list";
  timelinePicks.forEach((row, index) => {
    list.appendChild(buildBoleTimelineRow(row, index + 1));
  });

  bolePicksListEl.appendChild(explainer);
  bolePicksListEl.appendChild(list);
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

function buildSourceGroupNode(source, items) {
  const section = document.createElement("section");
  section.className = "source-group";
  const header = document.createElement("header");
  header.className = "source-group-head";
  const title = document.createElement("h3");
  title.textContent = source;
  const count = document.createElement("span");
  count.textContent = `${fmtNumber(items.length)} 条`;
  const listEl = document.createElement("div");
  listEl.className = "source-group-list";
  header.append(title, count);
  section.append(header, listEl);
  items.forEach((item) => listEl.appendChild(renderItemNode(item)));
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

  return Array.from(groupMap.entries()).sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0], "zh-CN"));
}

function renderGroupedBySource(items) {
  const groups = groupBySource(items);
  const frag = document.createDocumentFragment();

  groups.forEach(([source, groupItems]) => {
    frag.appendChild(buildSourceGroupNode(source, groupItems));
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
    const byCount = b[1].items.length - a[1].items.length;
    if (byCount !== 0) return byCount;
    return a[1].siteName.localeCompare(b[1].siteName, "zh-CN");
  });

  const frag = document.createDocumentFragment();
  sites.forEach(([, site]) => {
    const siteSection = document.createElement("section");
    siteSection.className = "site-group";
    const header = document.createElement("header");
    header.className = "site-group-head";
    const title = document.createElement("h3");
    title.textContent = site.siteName;
    const count = document.createElement("span");
    count.textContent = `${fmtNumber(site.items.length)} 条`;
    const siteListEl = document.createElement("div");
    siteListEl.className = "site-group-list";
    header.append(title, count);
    siteSection.append(header, siteListEl);

    const sourceGroups = groupBySource(site.items);
    sourceGroups.forEach(([source, groupItems]) => {
      siteListEl.appendChild(buildSourceGroupNode(source, groupItems));
    });
    frag.appendChild(siteSection);
  });

  newsListEl.appendChild(frag);
}

function renderList() {
  const filtered = getFilteredItems();
  resultCountEl.textContent = `${fmtNumber(filtered.length)} 条`;

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
  const [newsResult, waytoagiResult, statusResult, taxonomyResult, verificationResult] = await Promise.allSettled([
    loadNewsData(),
    loadWaytoagiData(),
    loadSourceStatusData(),
    loadTaxonomy(),
    loadVerificationSummary(),
  ]);

  state.taxonomy = taxonomyResult.status === "fulfilled" ? taxonomyResult.value : fallbackTaxonomy;
  state.verificationPayload = verificationResult.status === "fulfilled"
    ? verificationResult.value
    : { items: [], unavailable: true, error: verificationResult.reason?.message || "核验数据加载失败" };

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
    renderModeSwitch();
    renderCoverageStrip();
    renderBolePicks();
    renderSiteFilters();
    renderList();
    updatedAtEl.textContent = `更新时间：${fmtTime(state.generatedAt)}`;
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

if (askAiButtonEl) {
  askAiButtonEl.addEventListener("click", () => {
    openAskAi();
  });
}

if (readerCloseEl) readerCloseEl.addEventListener("click", closeReader);
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
if (adminPasswordInputEl) {
  adminPasswordInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") loginAdmin();
  });
}

setMobileView(state.mobileView);
init();
