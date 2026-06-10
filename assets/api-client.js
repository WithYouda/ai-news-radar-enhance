(function () {
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

  window.AI_NEWS_RADAR_API = {
    apiFetch,
    fetchFreshJson,
  };
})();
