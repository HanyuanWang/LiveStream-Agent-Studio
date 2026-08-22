const state = { themes: [], candidates: [], selected: new Set(), draft: null, status: null, chanmama: null, reports: null, relay: null };

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `请求失败：${response.status}`);
  return data;
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show${error ? " error" : ""}`;
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => element.className = "toast", 3600);
}

const pageMeta = {
  dashboard: ["主播发现总览", "从榜单发现低粉高效主播，送入快抖录制流程"],
  themes: ["关注领域", "用自然语言定义不同直播赛道的筛选条件"],
  chanmama: ["蝉妈妈数据源", "使用独立浏览器登录蝉妈妈并把带货达人榜送入候选池"],
  import: ["导入榜单", "读取蝉妈妈或其他平台导出的榜单"],
  candidates: ["候选主播", "在相同领域内比较成交、效率、粉丝与稳定性"],
  recorder: ["录制管理", "管理加入快抖录制的主播，并启动或停止监控"],
};

function showView(name) {
  $$(".view").forEach(view => view.classList.toggle("active", view.id === `view-${name}`));
  $$(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === name));
  $("#pageTitle").textContent = pageMeta[name][0];
  $("#pageSubtitle").textContent = pageMeta[name][1];
  if (name === "candidates") loadCandidates();
  if (name === "chanmama") loadChanmamaStatus();
  if (name === "recorder") loadRelayStatus();
}

function list(value) {
  return String(value || "").split(/[，,、]/).map(item => item.trim()).filter(Boolean);
}

function numberOrNull(value) {
  return value === "" || value === null || Number.isNaN(Number(value)) ? null : Number(value);
}

function formatNumber(value) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  if (number >= 100000000) return `${(number / 100000000).toFixed(1)}亿`;
  if (number >= 10000) return `${(number / 10000).toFixed(number >= 100000 ? 0 : 1)}万`;
  return Math.round(number).toLocaleString("zh-CN");
}

function setStatusLabel(selector, ok, yes = "已连接", no = "未配置") {
  const element = $(selector);
  element.textContent = ok ? yes : no;
  element.classList.toggle("ok", ok);
}

async function loadStatus() {
  state.status = await api("/api/status");
  const d = state.status.dashboard;
  $("#metricThemes").textContent = d.themes || 0;
  $("#metricCandidates").textContent = d.candidates || 0;
  $("#metricApproved").textContent = d.approved || 0;
  $("#metricMonitoring").textContent = d.monitoring || 0;
  setStatusLabel("#statusAi", state.status.ai_configured, "Qwen可用", "本地规则");
  setStatusLabel("#statusQuick", state.status.quick_recorder_found, "已找到", "未找到");
  $("#healthText").textContent = state.status.quick_recorder_found ? "核心组件正常" : "部分组件待配置";
  $("#recorderPath").textContent = state.status.quick_recorder_path;
  $("#recorderBadge").textContent = state.status.quick_recorder_found ? "已找到" : "未找到";
  $("#recorderBadge").classList.toggle("ok", state.status.quick_recorder_found);
}

const relayStatusNames = {
  queued: "等待处理",
  starting: "正在启动",
  checking: "检查录像",
  extracting_audio: "提取音频",
  uploading: "上传音频",
  transcribing: "云端转写",
  analyzing: "事件分析",
  exporting: "导出 Excel",
  completed: "已完成",
  failed: "失败",
  skipped_short: "短片跳过",
};

function formatDuration(seconds) {
  const value = Number(seconds || 0);
  if (!value) return "—";
  if (value < 3600) return `${Math.round(value / 60)}分钟`;
  return `${Math.floor(value / 3600)}小时${Math.round((value % 3600) / 60)}分`;
}

async function loadRelayStatus() {
  const data = await api("/api/recorder/status");
  state.relay = data;
  renderRelayCandidateDetails(data.enabled_candidate_details || []);
  return data;
}

function renderRelayCandidateDetails(candidates) {
  $("#relayPoolCount").textContent = `${candidates.length} 位`;
  const box = $("#relayCandidateDetails");
  if (!candidates.length) {
    box.innerHTML = '<div class="empty-state">尚未把主播加入录制名单</div>';
    return;
  }
  box.innerHTML = candidates.map(candidate => {
    const identity = candidate.douyin_id || candidate.theme_name || "抖音号待补充";
    const profile = candidate.profile_url
      ? `<a href="${escapeHtml(candidate.profile_url)}" target="_blank" rel="noreferrer">打开抖音主页</a>`
      : '<span class="missing-profile">主页链接待补充</span>';
    return `<article class="relay-candidate-item">
      <div><strong>${escapeHtml(candidate.anchor_name || "未命名主播")}</strong><small>${escapeHtml(identity)}</small></div>
      <div><span class="status-pill ${escapeHtml(candidate.status || "monitoring")}">${escapeHtml(statusName(candidate.status || "monitoring"))}</span>${profile}</div>
    </article>`;
  }).join("");
}

function relayScanMessage(result) {
  const detected = Number(result.detected || 0);
  const matched = Number(result.matched ?? result.scanned ?? 0);
  const queued = Number(result.queued || 0);
  const skipped = Number(result.skipped || 0);
  const waiting = Number(result.waiting_stable || 0);
  const unmatched = Number(result.unmatched || 0);
  const processed = Number(result.already_processed || 0);
  const parts = [`发现 ${detected} 条录像`, `匹配主播 ${matched} 条`, `排队 ${queued} 条`];
  if (waiting) parts.push(`等待文件稳定 ${waiting} 条`);
  if (skipped) parts.push(`时长不足 ${skipped} 条`);
  if (processed) parts.push(`已处理 ${processed} 条`);
  if (unmatched) {
    const names = (result.unmatched_files || []).join("、");
    parts.push(`未匹配已启用主播 ${unmatched} 条${names ? `（${names}）` : ""}`);
  }
  return parts.join("；");
}

function renderRelayScanSummary(result) {
  const box = $("#relayScanSummary");
  const hasResult = result && Object.keys(result).length > 0;
  box.classList.toggle("hidden", !hasResult);
  if (hasResult) box.textContent = relayScanMessage(result);
}

const chanmamaPhaseNames = {
  not_configured: "未配置",
  starting_login: "正在启动",
  waiting_for_login: "等待登录",
  finishing_login: "正在保存",
  ready: "可以使用",
  starting_export: "正在启动",
  waiting_for_export: "等待榜单导出",
  exporting: "正在导出",
  waiting_download: "等待文件下载",
  needs_action: "等待人工处理",
  calibration_ready: "页面校准完成",
  downloaded: "下载完成",
  imported: "导入完成",
  stopping: "正在停止",
  error: "需要处理",
};

async function loadChanmamaStatus() {
  const data = await api("/api/chanmama/status");
  const previousPhase = state.chanmama?.phase;
  state.chanmama = data;
  const ready = Boolean(data.logged_in);
  const busy = Boolean(data.busy);
  $("#chanmamaPhase").textContent = chanmamaPhaseNames[data.phase] || data.phase || "—";
  $("#chanmamaLoginState").textContent = ready ? "登录状态已保存" : "尚未登录";
  $("#chanmamaLoginState").classList.toggle("ok", ready);
  $("#chanmamaPageTitle").textContent = data.page_title || "—";
  $("#chanmamaUpdatedAt").textContent = data.updated_at ? new Date(data.updated_at).toLocaleString("zh-CN") : "—";
  $("#chanmamaMessage").textContent = data.message || "—";
  $("#chanmamaDownloadPath").textContent = data.download_path || "尚无下载文件";
  $("#chanmamaBadge").textContent = busy ? "运行中" : ready ? "已连接" : "未登录";
  $("#chanmamaBadge").classList.toggle("ok", ready && !busy);
  $("#statusChanmama").textContent = ready ? "已连接" : "未登录";
  $("#statusChanmama").classList.toggle("ok", ready);
  $("#startChanmamaLogin").classList.toggle("hidden", busy);
  $("#completeChanmamaLogin").classList.toggle("hidden", data.phase !== "waiting_for_login");
  $("#stopChanmama").classList.toggle("hidden", !busy);
  $("#startChanmamaExport").disabled = !ready || busy || !state.themes.length;
  if (previousPhase && previousPhase !== data.phase && data.phase === "imported") {
    toast(data.message || "蝉妈妈榜单已导入候选池");
    await Promise.all([loadStatus(), loadThemes()]);
  }
  return data;
}

async function loadThemes() {
  const data = await api("/api/themes");
  state.themes = data.themes;
  const dashboard = $("#dashboardThemes");
  const listElement = $("#themeList");
  if (!state.themes.length) {
    dashboard.className = "empty-state";
    dashboard.textContent = "还没有创建关注领域";
    listElement.innerHTML = "";
  } else {
    dashboard.className = "";
    dashboard.innerHTML = state.themes.slice(0, 5).map(theme => `
      <div class="theme-mini"><b>${escapeHtml(theme.name)}</b><span>${escapeHtml(theme.platform_category)} · 每日${theme.daily_limit}位</span><em>${theme.candidate_count || 0}候选</em></div>
    `).join("");
    listElement.innerHTML = state.themes.map(theme => `
      <article class="theme-card">
        <div class="top">
          <div><span class="eyebrow dark">${escapeHtml(theme.platform_category)}</span><h3>${escapeHtml(theme.name)}</h3></div>
          <div class="theme-actions">
            <span class="badge ${theme.active ? "ok" : ""}">${theme.active ? "启用" : "暂停"}</span>
            <button class="theme-delete" type="button" data-delete-theme="${theme.id}" data-theme-name="${escapeHtml(theme.name)}" data-candidate-count="${theme.candidate_count || 0}">删除</button>
          </div>
        </div>
        <p>${escapeHtml(theme.description)}</p>
        <div class="tags">${[...(theme.include_keywords || []), ...(theme.preferred_traits || [])].slice(0, 6).map(item => `<span class="tag">${escapeHtml(item)}</span>`).join("")}</div>
        <div class="theme-stats"><span>候选 ${theme.candidate_count || 0}</span><span>通过 ${theme.approved_count || 0}</span><span>监控 ${theme.monitoring_count || 0}</span></div>
      </article>
    `).join("");
  }
  const themeOptions = state.themes.map(theme => `<option value="${theme.id}">${escapeHtml(theme.name)}</option>`).join("");
  $("#importTheme").innerHTML = themeOptions || '<option value="">请先创建关注领域</option>';
  $("#chanmamaTheme").innerHTML = themeOptions || '<option value="">请先创建关注领域</option>';
  $("#candidateTheme").innerHTML = '<option value="">全部领域</option>' + themeOptions;
  $("#manualCandidateTheme").innerHTML = themeOptions || '<option value="">请先创建关注领域</option>';
  $$("[data-delete-theme]").forEach(button => {
    button.addEventListener("click", () => deleteTheme(
      Number(button.dataset.deleteTheme),
      button.dataset.themeName,
      Number(button.dataset.candidateCount || 0),
    ));
  });
}

async function deleteTheme(themeId, themeName, candidateCount) {
  const detail = candidateCount
    ? `，并同时删除该领域下的 ${candidateCount} 位候选主播和相关导入记录`
    : "";
  if (!window.confirm(`确认删除关注领域“${themeName}”${detail}？已生成的达人拆解报告会保留。此操作不可撤销。`)) return;
  try {
    const result = await api(`/api/themes/${themeId}`, { method: "DELETE" });
    state.selected.clear();
    toast(`已删除“${themeName}”，清理 ${result.deleted_candidates || 0} 位候选主播`);
    await Promise.all([loadStatus(), loadThemes()]);
    if ($("#view-candidates").classList.contains("active")) await loadCandidates();
  } catch (error) {
    toast(error.message, true);
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function fillDraft(theme) {
  state.draft = theme;
  $("#draftName").value = theme.name || "";
  $("#draftCategory").value = theme.platform_category || "";
  $("#draftSubcategories").value = (theme.subcategories || []).join("，");
  $("#draftAudience").value = theme.target_audience || "";
  $("#draftMinPrice").value = theme.min_price ?? "";
  $("#draftMaxPrice").value = theme.max_price ?? "";
  $("#draftMaxFollowers").value = theme.max_followers ?? "";
  $("#draftDailyLimit").value = theme.daily_limit || 5;
  $("#draftIncludes").value = (theme.include_keywords || []).join("，");
  $("#draftExcludes").value = (theme.exclude_keywords || []).join("，");
  $("#draftAccountTypes").value = (theme.account_types || []).join("，");
  $("#draftTraits").value = (theme.preferred_traits || []).join("，");
  $("#draftTrials").value = theme.trial_recordings || 2;
  $("#draftAutoAdd").checked = Boolean(theme.auto_add);
  $("#parserBadge").textContent = theme.parser === "qwen" ? "Qwen解析" : "本地规则";
  $("#themeDraftPanel").classList.remove("hidden");
}

function collectDraft() {
  return {
    ...state.draft,
    name: $("#draftName").value.trim(),
    description: $("#themeDescription").value.trim(),
    platform_category: $("#draftCategory").value.trim(),
    subcategories: list($("#draftSubcategories").value),
    include_keywords: list($("#draftIncludes").value),
    exclude_keywords: list($("#draftExcludes").value),
    min_price: numberOrNull($("#draftMinPrice").value),
    max_price: numberOrNull($("#draftMaxPrice").value),
    max_followers: numberOrNull($("#draftMaxFollowers").value),
    account_types: list($("#draftAccountTypes").value),
    preferred_traits: list($("#draftTraits").value),
    target_audience: $("#draftAudience").value.trim(),
    daily_limit: Number($("#draftDailyLimit").value || 5),
    trial_recordings: Number($("#draftTrials").value || 2),
    auto_add: $("#draftAutoAdd").checked,
  };
}

async function loadCandidates() {
  const params = new URLSearchParams();
  if ($("#candidateTheme").value) params.set("theme_id", $("#candidateTheme").value);
  if ($("#candidateStatus").value) params.set("status", $("#candidateStatus").value);
  const data = await api(`/api/candidates?${params}`);
  state.candidates = data.candidates;
  state.selected.clear();
  renderCandidates();
}

function renderCandidates() {
  const body = $("#candidateRows");
  if (!state.candidates.length) {
    body.innerHTML = '<tr><td colspan="9" class="table-empty">当前筛选下没有候选主播</td></tr>';
  } else {
    body.innerHTML = state.candidates.map(candidate => `
      <tr>
        <td><input class="candidate-check" type="checkbox" value="${candidate.id}" ${state.selected.has(candidate.id) ? "checked" : ""}></td>
        <td><strong>${escapeHtml(candidate.anchor_name)}</strong><small>${escapeHtml(candidate.douyin_id || candidate.account_type || candidate.source)}</small></td>
        <td><span>${escapeHtml(candidate.theme_name)}</span><small>${escapeHtml(candidate.category || "类目待确认")}</small></td>
        <td>${formatNumber(candidate.followers)}</td>
        <td><strong>${escapeHtml(candidate.estimated_gmv_text || formatNumber(candidate.estimated_gmv))}</strong><small>销量 ${escapeHtml(candidate.sales_volume_text || formatNumber(candidate.sales_volume))}</small></td>
        <td><span>GPM ${formatNumber(candidate.gpm)}</span><small>UV ${candidate.uv_value ?? "—"}</small></td>
        <td><span class="score">${Number(candidate.score).toFixed(1)}</span></td>
        <td><div class="reason">${(candidate.reasons || []).map(escapeHtml).join(" · ")}</div></td>
        <td><span class="status-pill ${candidate.status}">${statusName(candidate.status)}</span></td>
      </tr>
    `).join("");
  }
  $("#selectedCount").textContent = state.selected.size;
  $$(".candidate-check").forEach(check => check.addEventListener("change", event => {
    const id = Number(event.target.value);
    event.target.checked ? state.selected.add(id) : state.selected.delete(id);
    $("#selectedCount").textContent = state.selected.size;
  }));
}

function statusName(value) {
  return ({ candidate: "候选", approved: "已通过", monitoring: "监控中", rejected: "已排除", recorded: "已录制", analyzed: "已拆解" })[value] || value;
}

async function updateSelectedStatus(status) {
  if (!state.selected.size) return toast("请先选择主播", true);
  await api("/api/candidates/status", { method: "POST", body: JSON.stringify({ candidate_ids: [...state.selected], status }) });
  toast(`已更新 ${state.selected.size} 位主播`);
  await Promise.all([loadCandidates(), loadStatus(), loadThemes()]);
}

async function exportSelected() {
  if (!state.selected.size) return toast("请先选择主播", true);
  const result = await api("/api/recorder/export", { method: "POST", body: JSON.stringify({ candidate_ids: [...state.selected] }) });
  if (result.link_count) window.location.href = result.download_url;
  const missing = result.missing_profiles?.length ? `；${result.missing_profiles.length}位缺少主页链接` : "";
  toast(`已生成${result.link_count}条快抖链接${missing}`);
}

async function addSelectedToQuick() {
  if (!state.selected.size) return toast("请先选择主播", true);
  if (!window.confirm(`确认把选中的 ${state.selected.size} 位主播加入快抖监控名单？`)) return;
  try {
    const result = await api("/api/recorder/add", { method: "POST", body: JSON.stringify({ candidate_ids: [...state.selected] }) });
    const missing = result.missing_profiles?.length ? `；${result.missing_profiles.length}位缺少主页链接` : "";
    toast(`已向快抖发送 ${result.added} 位主播，并加入录制名单${missing}`);
    await Promise.all([loadCandidates(), loadStatus(), loadThemes()]);
  } catch (error) { toast(error.message, true); }
}

async function loadReportStatus() {
  const data = await api("/api/reports/status");
  const previousPhase = state.reports?.phase;
  state.reports = data;
  const box = $("#reportStatus");
  const reports = data.reports || [];
  if (data.phase === "idle" && !reports.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  const links = reports.map(report => {
    const evidence = report.evidence_download_url
      ? ` · <a href="${escapeHtml(report.evidence_download_url)}">${escapeHtml(report.anchor_name)}网页原始数据</a>`
      : "";
    return `<span><a href="${escapeHtml(report.download_url)}">${escapeHtml(report.anchor_name)}拆解报告</a>${evidence}</span>`;
  }).join("");
  box.innerHTML = `<div><b>${escapeHtml(data.message || "达人拆解任务")}</b><span>${data.completed || 0}/${data.total || reports.length || 0}</span></div><div class="report-links">${links}</div>`;
  $("#generateReports").disabled = Boolean(data.busy);
  if (previousPhase && previousPhase !== data.phase && data.phase === "completed") {
    toast(data.message || "达人拆解报告已生成");
    await loadCandidates();
  }
}

async function generateSelectedReports() {
  if (!state.selected.size) return toast("请先选择需要拆解的达人", true);
  if (!window.confirm(`确认生成选中 ${state.selected.size} 位达人的深度拆解报告？`)) return;
  try {
    await api("/api/reports/generate", {
      method: "POST",
      body: JSON.stringify({ candidate_ids: [...state.selected] }),
    });
    toast("已开始读取达人数据并生成报告");
    await loadReportStatus();
  } catch (error) { toast(error.message, true); }
}

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  return btoa(binary);
}

async function init() {
  $$(".nav-item").forEach(item => item.addEventListener("click", () => showView(item.dataset.view)));
  $$('[data-go]').forEach(button => button.addEventListener("click", () => showView(button.dataset.go)));
  $("#quickNewTheme").addEventListener("click", () => showView("themes"));

  $("#parseTheme").addEventListener("click", async () => {
    const description = $("#themeDescription").value.trim();
    if (description.length < 4) return toast("请先写一句对关注领域的描述", true);
    const button = $("#parseTheme");
    button.disabled = true; button.textContent = "Agent正在理解…";
    try {
      const data = await api("/api/themes/parse", { method: "POST", body: JSON.stringify({ description }) });
      fillDraft(data.theme);
      if (data.theme.parser_warning) toast(data.theme.parser_warning, true);
      else toast("已理解，请确认筛选条件");
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = "让 Agent 理解"; }
  });

  $("#cancelDraft").addEventListener("click", () => $("#themeDraftPanel").classList.add("hidden"));
  $("#saveTheme").addEventListener("click", async () => {
    try {
      const theme = collectDraft();
      if (!theme.name || !theme.platform_category) throw new Error("领域名称和平台类目不能为空");
      await api("/api/themes", { method: "POST", body: JSON.stringify(theme) });
      $("#themeDraftPanel").classList.add("hidden");
      $("#themeDescription").value = "";
      toast(`已创建领域：${theme.name}`);
      await Promise.all([loadThemes(), loadStatus()]);
    } catch (error) { toast(error.message, true); }
  });

  $("#importFile").addEventListener("change", event => {
    $("#fileLabel").textContent = event.target.files[0]?.name || "选择榜单文件";
  });
  $("#uploadLeaderboard").addEventListener("click", async () => {
    const file = $("#importFile").files[0];
    const themeId = $("#importTheme").value;
    if (!themeId) return toast("请先创建并选择关注领域", true);
    if (!file) return toast("请选择榜单文件", true);
    const button = $("#uploadLeaderboard");
    button.disabled = true; button.textContent = "正在读取和评分…";
    try {
      const result = await api("/api/imports", { method: "POST", body: JSON.stringify({ theme_id: themeId, source: $("#importSource").value, file_name: file.name, content_base64: await fileToBase64(file) }) });
      const box = $("#importResult");
      box.classList.remove("hidden");
      box.textContent = `成功导入 ${result.imported_count} 位主播。${(result.warnings || []).join("；")}`;
      toast("榜单导入完成，候选主播已评分");
      await Promise.all([loadStatus(), loadThemes()]);
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = "导入并评分"; }
  });

  $("#startChanmamaLogin").addEventListener("click", async () => {
    try {
      const result = await api("/api/chanmama/login/start", { method: "POST", body: "{}" });
      toast("已直接打开蝉妈妈专用 Chrome，请在该窗口完成登录");
      await loadChanmamaStatus();
    } catch (error) { toast(error.message, true); }
  });
  $("#completeChanmamaLogin").addEventListener("click", async () => {
    try {
      await api("/api/chanmama/login/complete", { method: "POST", body: "{}" });
      toast("正在保存蝉妈妈登录状态");
      await loadChanmamaStatus();
    } catch (error) { toast(error.message, true); }
  });
  $("#startChanmamaExport").addEventListener("click", async () => {
    const themeId = $("#chanmamaTheme").value;
    if (!themeId) return toast("请先创建并选择关注领域", true);
    try {
      await api("/api/chanmama/export/start", { method: "POST", body: JSON.stringify({
        theme_id: themeId,
        ranking: $("#chanmamaRanking").value,
        period: $("#chanmamaPeriod").value,
      }) });
      toast("蝉妈妈专用浏览器已启动，等待带货达人榜导出");
      await loadChanmamaStatus();
    } catch (error) { toast(error.message, true); }
  });
  $("#stopChanmama").addEventListener("click", async () => {
    try {
      await api("/api/chanmama/stop", { method: "POST", body: "{}" });
      toast("正在取消蝉妈妈操作");
      await loadChanmamaStatus();
    } catch (error) { toast(error.message, true); }
  });

  $("#candidateTheme").addEventListener("change", loadCandidates);
  $("#candidateStatus").addEventListener("change", loadCandidates);
  $("#importManualCandidate").addEventListener("click", async () => {
    const button = $("#importManualCandidate");
    const themeId = $("#manualCandidateTheme").value;
    const anchorName = $("#manualCandidateName").value.trim();
    const profileUrl = $("#manualCandidateUrl").value.trim();
    if (!themeId) return toast("请先选择关注领域", true);
    if (!anchorName) return toast("请填写主播名称", true);
    if (!profileUrl) return toast("请粘贴抖音主页链接", true);
    button.disabled = true; button.textContent = "正在导入…";
    try {
      const result = await api("/api/candidates/manual", {
        method: "POST",
        body: JSON.stringify({ theme_id: Number(themeId), anchor_name: anchorName, profile_url: profileUrl }),
      });
      const box = $("#manualCandidateResult");
      box.classList.remove("hidden");
      box.textContent = `已导入主播：${result.candidate?.anchor_name || anchorName}。请在下方选中后，点击“自动加入快抖”。`;
      $("#manualCandidateName").value = "";
      $("#manualCandidateUrl").value = "";
      toast("主播已进入候选主播池");
      await Promise.all([loadCandidates(), loadStatus(), loadThemes()]);
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = "导入候选主播"; }
  });
  $("#selectAll").addEventListener("change", event => {
    state.selected.clear();
    if (event.target.checked) state.candidates.forEach(candidate => state.selected.add(candidate.id));
    renderCandidates();
  });
  $$('[data-status]').forEach(button => button.addEventListener("click", () => updateSelectedStatus(button.dataset.status)));
  $("#exportSelected").addEventListener("click", exportSelected);
  $("#generateReports").addEventListener("click", generateSelectedReports);
  $("#addSelectedToQuick").addEventListener("click", addSelectedToQuick);
  $("#launchRecorder").addEventListener("click", async () => {
    try { await api("/api/recorder/launch", { method: "POST", body: "{}" }); toast("已打开快抖直播录制助手"); }
    catch (error) { toast(error.message, true); }
  });
  $("#startQuickMonitor").addEventListener("click", async () => {
    if (!window.confirm("确认启动快抖对全部已启用直播间的监控？")) return;
    try { await api("/api/recorder/start-monitor", { method: "POST", body: "{}" }); toast("已向快抖发送启动监控命令"); }
    catch (error) { toast(error.message, true); }
  });
  $("#stopQuickMonitor").addEventListener("click", async () => {
    if (!window.confirm("确认停止快抖直播间监控？正在录制的任务请先在快抖中确认状态。")) return;
    try { await api("/api/recorder/stop-monitor", { method: "POST", body: "{}" }); toast("已向快抖发送停止监控命令"); }
    catch (error) { toast(error.message, true); }
  });
  try {
    await Promise.all([loadStatus(), loadThemes()]);
    await Promise.all([loadChanmamaStatus(), loadReportStatus(), loadRelayStatus()]);
    window.setInterval(() => loadChanmamaStatus().catch(() => {}), 2500);
    window.setInterval(() => loadReportStatus().catch(() => {}), 3000);
    window.setInterval(() => loadRelayStatus().catch(() => {}), 15000);
  }
  catch (error) { toast(`Agent启动检查失败：${error.message}`, true); }
}

init();
