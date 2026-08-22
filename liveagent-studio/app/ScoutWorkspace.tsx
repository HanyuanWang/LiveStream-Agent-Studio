"use client";

import { useEffect, useState } from "react";

const GATEWAY = "http://127.0.0.1:8785";

type Props = { local: any; onNotify: (message: string) => void };

export default function ScoutWorkspace({ local, onNotify }: Props) {
  const [themes, setThemes] = useState<any[]>([]);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState<any>(null);
  const [themeId, setThemeId] = useState("");
  const [period, setPeriod] = useState("day");
  const [busy, setBusy] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [chanmama, setChanmama] = useState<any>({});
  const [relay, setRelay] = useState<any>({});

  const api = async (path: string, init?: RequestInit) => {
    const response = await fetch(`${GATEWAY}/api/scout${path}`, init);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "操作失败");
    return payload;
  };
  const post = (path: string, body: any = {}) => api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const refresh = async () => {
    if (!local) return;
    try {
      const [themeData, candidateData, chanData, relayData] = await Promise.all([
        api("/api/themes"),
        api(`/api/candidates${themeId ? `?theme_id=${themeId}` : ""}`),
        api("/api/chanmama/status"),
        api("/api/relay/status"),
      ]);
      setThemes(themeData.themes || []);
      setCandidates(candidateData.candidates || []);
      setChanmama(chanData || {});
      setRelay(relayData || {});
      if (!themeId && themeData.themes?.[0]) setThemeId(String(themeData.themes[0].id));
    } catch (error: any) { onNotify(error.message); }
  };
  useEffect(() => { refresh(); }, [local, themeId]);

  const run = async (work: () => Promise<any>, success: string) => {
    setBusy(true);
    try { await work(); onNotify(success); await refresh(); }
    catch (error: any) { onNotify(error.message); }
    finally { setBusy(false); }
  };
  const understand = () => run(async () => {
    if (description.trim().length < 4) throw new Error("请先写一句关注领域描述");
    setDraft((await post("/api/themes/parse", { description })).theme);
  }, "筛选条件已解析，请确认后创建");
  const createTheme = () => run(async () => {
    await post("/api/themes", { ...draft, description });
    setDraft(null); setDescription("");
  }, "关注领域已创建");
  const deleteTheme = () => run(async () => {
    if (!themeId) throw new Error("请先选择关注领域");
    if (!window.confirm("删除这个关注领域及其候选主播？")) throw new Error("已取消删除");
    await api(`/api/themes/${themeId}`, { method: "DELETE" });
    setThemeId(""); setSelected([]);
  }, "关注领域已删除");
  const updateStatus = (status: string) => run(async () => {
    if (!selected.length) throw new Error("请先勾选主播");
    await post("/api/candidates/status", { candidate_ids: selected, status });
  }, "主播状态已更新");
  const importLeaderboard = () => run(async () => {
    if (!themeId || !importFile) throw new Error("请先选择关注领域和榜单文件");
    const bytes = new Uint8Array(await importFile.arrayBuffer());
    let binary = "";
    for (let index = 0; index < bytes.length; index += 32768) binary += String.fromCharCode(...bytes.subarray(index, index + 32768));
    await post("/api/imports", { theme_id: Number(themeId), file_name: importFile.name, source: "其他", content_base64: btoa(binary) });
    setImportFile(null);
  }, "榜单已导入候选池");

  if (!local) return <section className="surface scout-workspace scout-offline">
    <div>
      <p className="eyebrow">桌面功能尚未连接</p>
      <h2>主播发现需要在安装它的电脑上运行</h2>
      <p>它要读取你原来的关注领域、蝉妈妈登录状态，并操作本机的快抖录制助手，因此在线展示页无法单独完成这些操作。</p>
    </div>
    <ol>
      <li><span>1</span><p><b>打开桌面的 codex 文件夹</b><small>进入 liveagent-studio-prototype 文件夹。</small></p></li>
      <li><span>2</span><p><b>运行“01_启动_LiveAgent_Studio.cmd”</b><small>看到“LiveAgent Studio is ready”后，系统会自动打开可操作页面。</small></p></li>
      <li><span>3</span><p><b>在自动打开的页面进入“主播发现”</b><small>这时关注领域、蝉妈妈榜单、候选主播和快抖录制功能都会直接显示。</small></p></li>
    </ol>
    <div className="scout-offline-actions">
      <a className="primary" href="http://127.0.0.1:4173/">打开本机工作台</a>
      <button className="secondary" onClick={() => window.location.reload()}>重新检测连接</button>
    </div>
    <p className="offline-tip">如果“打开本机工作台”显示无法访问，说明桌面服务还没有启动，请先完成上面的第 1、2 步。</p>
  </section>;

  return <section className="scout-workspace">
    <div className="scout-create">
      <div><p className="eyebrow">STEP 01 · 关注领域</p><h2>用一句话告诉 Agent 你要找什么主播</h2><textarea value={description} onChange={event => setDescription(event.target.value)} placeholder="例如：中高端女装，粉丝30万以下，排除童装和品牌官方号"/><button className="primary" onClick={understand} disabled={busy}>让 Agent 理解</button></div>
      {draft && <div className="theme-draft"><b>{draft.name || "新关注领域"}</b><p>类目：{draft.platform_category || "待确认"}</p><p>目标人群：{draft.target_audience || "待确认"}</p><p>粉丝上限：{draft.max_followers || "不限"}</p>{draft.parser_warning && <small>{draft.parser_warning}</small>}<button className="primary" onClick={createTheme}>确认并创建</button></div>}
    </div>

    <div className="scout-operations">
      <div><p className="eyebrow">蝉妈妈</p><b>{chanmama.message || (chanmama.logged_in ? "登录状态已保存" : "尚未确认登录")}</b><span className={chanmama.busy ? "busy" : "idle"}>{chanmama.busy ? "运行中" : "空闲"}</span><footer><button onClick={() => run(() => post("/api/chanmama/login/start"), "蝉妈妈专用浏览器已打开，请完成登录")}>打开登录</button><button onClick={() => run(() => post("/api/chanmama/login/complete"), "登录状态已保存")}>我已登录</button><button onClick={() => run(() => post("/api/chanmama/stop"), "当前蝉妈妈操作已停止")}>停止操作</button></footer></div>
      <div><p className="eyebrow">快抖录制</p><b>把通过的主播加入录制监控</b><span>由原快抖连接执行</span><footer><button onClick={() => run(() => post("/api/recorder/launch"), "快抖录制助手已打开")}>打开快抖</button><button onClick={() => run(() => post("/api/recorder/start-monitor"), "快抖监控已启动")}>启动监控</button><button onClick={() => run(() => post("/api/recorder/stop-monitor"), "快抖监控已停止")}>停止监控</button></footer></div>
      <div><p className="eyebrow">录制转交</p><b>{relay.message || "把录制完成的视频交给直播拆解"}</b><span>{relay.running ? "正在运行" : "等待扫描"}</span><footer><button onClick={() => run(() => post("/api/relay/scan"), "已扫描录制目录")}>立即扫描</button></footer></div>
    </div>

    <div className="scout-toolbar">
      <label>关注领域<select value={themeId} onChange={event => setThemeId(event.target.value)}><option value="">请选择</option>{themes.map(theme => <option key={theme.id} value={theme.id}>{theme.name}</option>)}</select></label>
      <label>榜单周期<select value={period} onChange={event => setPeriod(event.target.value)}><option value="day">日榜</option><option value="week">周榜</option><option value="month">月榜</option></select></label>
      <button className="secondary" onClick={() => run(async () => { if (!themeId) throw new Error("请先选择关注领域"); await post("/api/chanmama/export/start", { theme_id: Number(themeId), period }); }, "已开始从蝉妈妈更新榜单")}>从蝉妈妈更新</button>
      <button className="secondary" onClick={refresh}>刷新</button><button className="danger-text" onClick={deleteTheme}>删除领域</button>
    </div>

    <div className="scout-import"><label><b>也可以导入本地榜单 Excel / CSV</b><input type="file" accept=".xlsx,.xls,.csv" onChange={event => setImportFile(event.target.files?.[0] || null)}/><span>{importFile?.name || "选择文件"}</span></label><button onClick={importLeaderboard} disabled={!importFile}>导入候选池</button></div>

    <div className="candidate-actions"><b>已选择 {selected.length} 位主播</b><span/><button onClick={() => updateStatus("rejected")}>排除</button><button onClick={() => updateStatus("approved")}>通过</button><button onClick={() => run(async () => { if (!selected.length) throw new Error("请先勾选主播"); await post("/api/reports/generate", { candidate_ids: selected }); }, "达人拆解已开始生成")}>生成达人拆解</button><button className="primary" onClick={() => run(async () => { if (!selected.length) throw new Error("请先勾选主播"); await post("/api/recorder/add", { candidate_ids: selected }); }, "已加入快抖并开启自动拆解")}>加入快抖</button></div>
    <div className="candidate-table"><div className="candidate-head"><span/><span>主播</span><span>领域</span><span>粉丝</span><span>销售表现</span><span>推荐分</span><span>状态</span></div>{candidates.slice(0, 100).map(candidate => <div className="candidate-row" key={candidate.id}><input type="checkbox" checked={selected.includes(candidate.id)} onChange={event => setSelected(old => event.target.checked ? [...old, candidate.id] : old.filter(id => id !== candidate.id))}/><b>{candidate.anchor_name}<small>{candidate.douyin_id || ""}</small></b><span>{candidate.theme_name || candidate.category || "—"}</span><span>{candidate.followers ?? "—"}</span><span>{candidate.estimated_gmv_text || candidate.estimated_gmv || "—"}<small>销量 {candidate.sales_volume_text || candidate.sales_volume || "—"}</small></span><strong>{Number(candidate.score || 0).toFixed(1)}</strong><em>{candidate.status}</em></div>)}</div>
  </section>;
}
