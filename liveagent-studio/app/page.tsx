"use client";
import { useEffect, useMemo, useState } from "react";
type View = "home" | "scout" | "breakdown" | "review" | "director" | "tasks" | "settings";
type Agent = {
    id: View;
    code: string;
    title: string;
    en: string;
    tone: string;
    desc: string;
    meta: string;
    action: string;
    localUrl?: string;
};
type Job = {
    job_id: string;
    name: string;
    agent: string;
    status: string;
    status_text: string;
    progress: number;
    message: string;
    error?: string;
    output?: string;
    output_dir?: string;
};
const GATEWAY = "http://127.0.0.1:8785";
const SCOUT_URL = "http://127.0.0.1:8765/";
const icons: Record<string, string> = { home: "M3 11.5 12 4l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z", scout: "M15.5 15.5 21 21M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14Z", video: "M15 10l4.6-3a1 1 0 0 1 1.4.83v8.34a1 1 0 0 1-1.4.83L15 14M4 6h9a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z", review: "M4 19V9m6 10V5m6 14v-7m5 7H2", director: "M4 19.5V4.5l12 4v7l-12 4Zm12-11 4-2v7l-4 2M8 8.5v7", edit: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z", tasks: "M6 7h12M6 12h12M6 17h8M3 7h.01M3 12h.01M3 17h.01", settings: "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7.4-3.5c0-.5-.05-1-.16-1.45l2-1.55-2-3.46-2.42.98a8.5 8.5 0 0 0-2.5-1.45L14 2.5h-4l-.32 2.57a8.5 8.5 0 0 0-2.5 1.45l-2.42-.98-2 3.46 2.42.98a8.5 8.5 0 0 0 2.5 1.45L10 21.5h4l.32-2.57a8.5 8.5 0 0 0 2.5-1.45l2.42.98 2-3.46-2-1.55c.11-.46.16-.95.16-1.45Z", arrow: "M5 12h14m-5-5 5 5-5 5", upload: "M12 16V4m0 0L7 9m5-5 5 5M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5", bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4", plus: "M12 5v14M5 12h14", close: "M6 6l12 12M18 6 6 18", play: "m9 7 8 5-8 5z", check: "m5 12 4 4L19 6", help: "M9.1 9a3 3 0 1 1 5.83 1c0 2-2.93 2-2.93 4m0 4h.01", folder: "M3 6h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" };
function Icon({ name, size = 20 }: {
    name: string;
    size?: number;
}) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={icons[name]}/></svg>; }
const agents: Agent[] = [
    { id: "scout", code: "01", title: "主播发现", en: "Creator Scout", tone: "amber", desc: "在统一工作台中管理关注领域、更新蝉妈妈榜单、筛选候选主播、生成达人拆解并加入快抖录制。", meta: "蝉妈妈 · 抖音 · 快抖", action: "管理主播" },
    { id: "breakdown", code: "02", title: "直播拆解", en: "Live Breakdown", tone: "rose", desc: "上传直播录屏后，真实调用现有拆解程序，完成音频提取、云端转写、事件识别与 Excel 输出。", meta: "视频 · 阿里云转写 · Excel", action: "上传并拆解" },
    { id: "review", code: "03", title: "直播复盘", en: "Live Review", tone: "emerald", desc: "只上传直播视频和巨量百应流量数据：系统先生成逐字稿，再用 Qwen 分析不同时间段的话术与流量表现并输出复盘。", meta: "直播视频 · 巨量百应 · Qwen", action: "上传并复盘" },
    { id: "director", code: "04", title: "视频编导", en: "Video Director", tone: "amber", desc: "接收用户提供的参考短视频链接，提取音轨并生成逐字稿，再输出原创口播脚本、分镜和拍摄建议。", meta: "参考视频 · 逐字稿 · 原创脚本", action: "开始策划" }
];
const demoJobs: Job[] = [];
export default function Home() {
    const [view, setView] = useState<View>("home"), [modal, setModal] = useState<View | null>(null), [guide, setGuide] = useState<Agent | null>(null), [toast, setToast] = useState(""), [jobs, setJobs] = useState<Job[]>(demoJobs), [filter, setFilter] = useState("all"), [search, setSearch] = useState(""), [taskMenu, setTaskMenu] = useState<string | null>(null), [local, setLocal] = useState<any>(null);
    const current = useMemo(() => agents.find(a => a.id === view), [view]);
    const notify = (s: string) => { setToast(s); window.setTimeout(() => setToast(""), 2600); };
    const openScout = () => { const opened = window.open(SCOUT_URL, "liveagent-scout"); if (!opened)
        window.location.href = SCOUT_URL; };
    const navigate = (next: View) => { if (next === "scout") {
        openScout();
        return;
    } setView(next); };
    useEffect(() => { fetch(`${GATEWAY}/api/health`).then(r => r.json()).then(setLocal).catch(() => setLocal(null)); fetch(`${GATEWAY}/api/jobs`).then(r => r.json()).then(x => setJobs(old => [...(x.jobs || []), ...old.filter(j => j.job_id.startsWith("demo-") && !((x.jobs || []).some((n: Job) => n.job_id === j.job_id)))])).catch(() => { }); }, []);
    const activeBreakdownJobs = jobs.filter(j => j.status === "running" && !j.job_id.startsWith("demo-")).map(j => j.job_id).join(",");
    useEffect(() => { if (!local || !activeBreakdownJobs)
        return; const timer = window.setInterval(async () => { for (const id of activeBreakdownJobs.split(",")) {
        try {
            const r = await fetch(`${GATEWAY}/api/jobs/${id}`);
            if (!r.ok)
                continue;
            const x = await r.json();
            setJobs(old => old.map(j => j.job_id === id ? { ...j, ...x } : j));
        }
        catch { }
    } }, 1600); return () => window.clearInterval(timer); }, [activeBreakdownJobs, local]);
    const openAgent = (agent: Agent) => { if (agent.id === "breakdown" || agent.id === "review")
        setModal(agent.id);
    else if (agent.id === "director") {
        setView("director");
        window.setTimeout(() => document.getElementById("director-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    }
    else
        openScout(); };
    const addJob = (job: Job) => { setJobs(old => [job, ...old.filter(x => x.job_id !== job.job_id)]); setView("tasks"); };
    const openJobTarget = async (job: Job, action: "open-file" | "open-folder") => { if (!job.output) {
        notify(job.error || job.message || "该任务还没有输出文件");
        return;
    } try {
        const r = await fetch(`${GATEWAY}/api/jobs/${job.job_id}/${action}`, { method: "POST" });
        const x = await r.json();
        if (!r.ok)
            throw new Error(x.error || "打开失败");
        notify(action === "open-file" ? "正在打开结果文件" : "正在打开文件所在文件夹");
    }
    catch (e: any) {
        notify(e.message || "无法打开，请确认本机工作台已启动");
    } };
    return <main className="app-shell"><Sidebar view={view} setView={navigate}/><section className="main-panel"><header className="topbar"><div><span className="crumb">直播智能工作台</span>{view !== "home" && <><span className="slash">/</span><b>{current?.title ?? (view === "tasks" ? "任务中心" : "设置与连接")}</b></>}</div><div className="top-actions"><span className={`desktop-state ${local ? "online" : "offline"}`}><i />{local ? "本机 Agent 已连接" : "仅预览模式"}</span><button className="icon-button" aria-label="通知" onClick={() => notify("暂时没有新的通知")}><Icon name="bell"/></button><button className="primary small" onClick={() => setModal("breakdown")}><Icon name="plus" size={17}/>新建任务</button></div></header><div className="content">
    {view === "home" && <Dashboard onOpen={navigate} onStart={setModal}/>}
    {current && <AgentPage agent={current} local={local} onStart={() => openAgent(current)} onGuide={() => setGuide(current)} onNotify={notify} onJob={addJob}/>}
    {view === "tasks" && <TaskCenter jobs={jobs} filter={filter} setFilter={setFilter} search={search} setSearch={setSearch} taskMenu={taskMenu} setTaskMenu={setTaskMenu} onNotify={notify} onOpenFile={job => openJobTarget(job, "open-file")} onOpenFolder={job => openJobTarget(job, "open-folder")} onDelete={async (job) => { if (!window.confirm(`确认删除任务“${job.name}”？`))
            return; setJobs(old => old.filter(x => x.job_id !== job.job_id)); if (!job.job_id.startsWith("demo-"))
            fetch(`${GATEWAY}/api/jobs/${job.job_id}`, { method: "DELETE" }).catch(() => { }); notify("任务已删除"); }}/>}
    {view === "settings" && <Settings local={local} onNotify={notify}/>}
  </div></section>
    {modal && <NewTaskModal agent={agents.find(a => a.id === modal)!} local={local} onClose={() => setModal(null)} onJob={job => { setModal(null); addJob(job); }} onNotify={notify}/>}
    {guide && <GuideModal agent={guide} onClose={() => setGuide(null)} onStart={() => { setGuide(null); openAgent(guide); }}/>}
    {toast && <div className="toast"><span><Icon name="check" size={16}/></span>{toast}</div>}</main>;
}
function Sidebar({ view, setView }: {
    view: View;
    setView: (v: View) => void;
}) { return <aside className="sidebar"><button className="brand" onClick={() => setView("home")}><span className="brand-mark"><i /><i /><i /></span><span><b>LiveAgent</b><small>STUDIO</small></span></button><nav className="main-nav"><Nav active={view === "home"} icon="home" label="工作台" go={() => setView("home")}/><div className="nav-label">竞品研究</div><a className="nav-button" href={SCOUT_URL} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}><Icon name="scout"/><span>主播发现</span></a><Nav active={view === "breakdown"} icon="video" label="直播拆解" go={() => setView("breakdown")}/><div className="nav-label">自营优化</div><Nav active={view === "review"} icon="review" label="直播复盘" go={() => setView("review")}/><Nav active={view === "director"} icon="director" label="视频编导" go={() => setView("director")}/><div className="nav-label">管理</div><Nav active={view === "tasks"} icon="tasks" label="任务中心" go={() => setView("tasks")}/></nav><div className="sidebar-foot"><Nav active={view === "settings"} icon="settings" label="设置与连接" go={() => setView("settings")}/><div className="profile"><span>F</span><div><b>我的工作空间</b><small>本机安全运行</small></div><em>···</em></div></div></aside>; }
function Nav({ active, icon, label, badge, go }: {
    active: boolean;
    icon: string;
    label: string;
    badge?: string;
    go: () => void;
}) { return <button className={`nav-button ${active ? "active" : ""}`} onClick={go}><Icon name={icon}/><span>{label}</span>{badge && <em>{badge}</em>}</button>; }
function Dashboard({ onOpen, onStart }: {
    onOpen: (v: View) => void;
    onStart: (v: View) => void;
}) { return <><section className="hero"><div><p className="eyebrow">LIVE COMMERCE INTELLIGENCE</p><h1>把每一场直播，<br /><span>变成下一场的优势。</span></h1><p className="hero-copy">把主播发现、直播拆解、直播复盘与视频编导能力放进同一个工作台，覆盖竞品研究到内容生产。</p><div className="hero-actions"><button className="primary" onClick={() => onStart("breakdown")}><Icon name="plus" size={18}/>开始新任务</button><button className="secondary" onClick={() => onOpen("tasks")}>查看任务中心 <Icon name="arrow" size={17}/></button></div></div><div className="hero-visual"><div className="signal-card"><div className="signal-head"><span>本周洞察</span><b>LIVE</b></div><div className="signal-number">12</div><p>个高转化话术片段</p><div className="mini-chart">{[34, 48, 38, 62, 51, 76, 59, 84, 68, 91, 79, 96].map((h, i) => <i key={i} style={{ height: `${h}%` }}/>)}</div><small><span>↑ 28%</span>对比上周</small></div></div></section><div className="section-heading"><div><p className="eyebrow">YOUR AGENTS</p><h2>四个独立能力，一个完整闭环</h2></div></div><section className="agent-grid">{agents.map(a => <article className={`agent-card ${a.tone}`} key={a.id} onClick={() => onOpen(a.id)}><div className="agent-top"><span className="agent-code">{a.code}</span><span className="agent-state"><i />可使用</span></div><div className="agent-symbol"><Icon name={a.id === "scout" ? "scout" : a.id === "breakdown" ? "video" : a.id === "review" ? "review" : "director"} size={27}/></div><h3>{a.title}</h3><small>{a.en}</small><p>{a.desc}</p><footer><span>{a.meta}</span><button aria-label={`打开${a.title}`}><Icon name="arrow" size={18}/></button></footer></article>)}</section></>; }
function AgentPage({ agent, local, onStart, onGuide, onNotify, onJob }: {
    agent: Agent;
    local: any;
    onStart: () => void;
    onGuide: () => void;
    onNotify: (s: string) => void;
    onJob: (job: Job) => void;
}) {
    const steps = agent.id === "scout" ? ["设置关注领域", "从蝉妈妈更新榜单", "筛选候选主播", "加入快抖监控"] : agent.id === "breakdown" ? ["选择直播视频", "提取音频并上传OSS", "阿里云逐句转写", "大模型拆解并生成Excel"] : agent.id === "review" ? ["上传视频和百应流量表", "生成带时间戳逐字稿并分析话术与流量", "生成内部复盘Excel"] : ["粘贴一个或多个参考视频链接", "提取音轨并生成带时间戳逐字稿", "核对和筛选真实参考逐字稿", "生成原创脚本、分镜与拍摄建议"];
    return <><section className={`agent-hero ${agent.tone}`}><div className="agent-hero-copy"><div className="agent-kicker"><span>{agent.code}</span>{agent.en}</div><h1>{agent.title} Agent</h1><p>{agent.desc}</p><div className="hero-actions"><button className="primary" onClick={() => agent.id === "director" ? document.getElementById("director-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }) : onStart()}><Icon name={agent.localUrl ? "play" : "plus"} size={18}/>{agent.action}</button><button className="secondary" onClick={onGuide}><Icon name="help" size={17}/>使用说明</button></div></div><div className="agent-emblem"><span>{agent.code}</span><Icon name={agent.id === "scout" ? "scout" : agent.id === "breakdown" ? "video" : agent.id === "review" ? "review" : agent.id === "director" ? "director" : "edit"} size={44}/></div></section>
    {agent.id === "review" && <ReviewRequirements local={local} onStart={onStart} onNotify={onNotify}/>}
    {agent.id === "director" && <DirectorWorkspace local={local} onJob={onJob} onNotify={onNotify}/>}
    <div className="two-columns"><section className="surface"><div className="surface-title"><div><p className="eyebrow">WORKFLOW</p><h2>这个 Agent 会怎样工作</h2></div><span className="ready-dot"><i />{local ? "本机已连接" : "桌面功能未连接"}</span></div><div className="workflow">{steps.map((s, i) => <div className="workflow-row" key={s}><span>{String(i + 1).padStart(2, "0")}</span><div><b>{s}</b><small>{i === 0 ? "准备必要资料即可" : i === steps.length - 1 ? "结果保存到本机输出目录" : "自动完成，进度实时显示"}</small></div>{i < steps.length - 1 && <em />}</div>)}</div></section><section className="surface activity-panel"><div className="surface-title"><div><p className="eyebrow">CONNECTION</p><h2>运行状态</h2></div></div><div className="empty-orb"><Icon name={local ? "check" : "play"} size={28}/></div><h3>{local ? "本机能力已经连通" : "当前打开的是在线展示页"}</h3><p>{local ? "现在可以真正启动 Agent、选择文件并查看进度。" : "需要控制本机文件或软件的功能，请运行桌面文件“01_启动_LiveAgent_Studio.cmd”，再使用自动打开的页面。"}</p><button className="secondary wide" onClick={onStart}>{agent.action}</button></section></div></>;
}
function ReviewRequirements({ local, onStart, onNotify }: {
    local: any;
    onStart: () => void;
    onNotify: (s: string) => void;
}) { const ready = local?.model?.verified && local?.oss?.verified; return <section className="review-kit"><div className="review-kit-head"><div><p className="eyebrow">TWO FILE WORKFLOW</p><h2>只需要上传两个文件</h2></div><span className={`model-pill ${ready ? "connected" : "missing"}`}><i />{ready ? `Qwen 与 OSS 已验证` : "开始前需验证 Qwen 与 OSS"}</span></div><div className="file-requirements two"><div><span>1</span><p><b>完整直播视频<em>必需</em></b><small>MP4、MOV、MKV 或 AVI。系统会自动生成带时间戳的逐字稿，无需提前拆解。</small></p></div><div><span>2</span><p><b>巨量百应流量数据<em>必需</em></b><small>直播详情页导出的分钟级流量综合趋势 Excel，用来比较不同直播时段的进入、离开、在线、停留、互动、关注、商品曝光与点击。</small></p></div></div><div className="model-explain"><Icon name="review"/><p><b>系统如何分析？</b><br />第一步通过阿里云语音转写从视频生成逐字稿；第二步用 Qwen 比较不同时间段的话术与进入、离开、实时在线、停留、互动、关注、商品曝光和点击的同步变化；第三步按统一模板输出 Excel 和 Word。本流程不分析 GMV、成交、订单或销量。</p><button onClick={() => ready ? onNotify("Qwen 与 OSS 均已实际验证") : onNotify("请先到设置与连接填写并验证阿里云配置")}>{ready ? "连接已验证" : "去设置连接"}</button></div><button className="primary review-start" onClick={onStart}>上传视频和流量表 <Icon name="arrow" size={17}/></button></section>; }
function DirectorWorkspace({ local, onJob, onNotify }: {
    local: any;
    onJob: (job: Job) => void;
    onNotify: (s: string) => void;
}) {
    const [links, setLinks] = useState(""), [sources, setSources] = useState<any[]>([]), [failures, setFailures] = useState<any[]>([]);
    const [busy, setBusy] = useState(false), [phase, setPhase] = useState(""), [outputDir, setOutputDir] = useState("");
    const [douyinStatus, setDouyinStatus] = useState<any>(null), [loginBusy, setLoginBusy] = useState(false);
    const api = async (path: string, body: any) => { const r = await fetch(`${GATEWAY}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); const x = await r.json(); if (!r.ok) throw new Error(x.error || "操作失败"); return x; };
    const refreshDouyin = async () => { try { const r = await fetch(`${GATEWAY}/api/director/douyin-login`); const x = await r.json(); if (!r.ok) throw new Error(x.error || "读取失败"); setDouyinStatus(x); return x; } catch (e: any) { setDouyinStatus({ ready: false, message: e.message }); return null; } };
    const openDouyinLogin = async () => { setLoginBusy(true); try { const x = await api("/api/director/douyin-login", {}); setDouyinStatus(x); onNotify("已打开 LiveAgent 抖音登录窗口"); } catch (e: any) { onNotify(e.message); } finally { setLoginBusy(false); } };
    useEffect(() => { if (local) refreshDouyin(); }, [local]);
    const chooseFolder = async () => { try { const r = await fetch(`${GATEWAY}/api/select-folder`, { method: "POST" }); const x = await r.json(); if (!r.ok) throw new Error(x.error || "选择失败"); if (x.path) setOutputDir(x.path); } catch (e: any) { onNotify(e.message); } };
    const parseLinks = async () => { if (!local?.model?.verified || !local?.oss?.verified) { onNotify("请先在设置与连接中实际验证 Qwen 与 OSS"); return; } const items = links.split(/\r?\n/).map(line => line.trim()).filter(Boolean); if (!items.length) { onNotify("请先粘贴至少一个短视频链接"); return; } setBusy(true); setSources([]); setFailures([]); setPhase("正在逐条获取视频音轨并生成带时间戳逐字稿；链接较多时需要几分钟"); try { const x = await api("/api/director/sources", { links: items }); setSources(x.sources || []); setFailures(x.failures || []); onNotify(x.message || "短视频逐字稿处理完成"); } catch (e: any) { onNotify(e.message); } finally { setBusy(false); setPhase(""); } };
    const editTranscript = (index: number, value: string) => setSources(old => old.map((item, i) => i === index ? { ...item, transcript: value } : item));
    const create = async () => { if (!sources.length) { onNotify("请先解析短视频链接并生成逐字稿"); return; } const brief = { product: "参考视频主题", category: "", audience: "", benefits: "", price: "", pain: "", persona: "", duration: "60秒", count: "3", prohibited: "", notes: "" }; setBusy(true); try { const job = await api("/api/director/jobs", { name: "参考视频_短视频编导方案", brief, sources, output_dir: outputDir }); onJob(job); onNotify("视频编导任务已开始，可在任务中心查看进度"); } catch (e: any) { onNotify(e.message); } finally { setBusy(false); } };
    return <section className="director-workspace" id="director-workspace">
    <div className="director-step"><b>01 · 粘贴参考短视频链接</b><p className="director-hint">每行一个链接或一整行抖音分享文案，最多 10 条。Agent 会准确提取其中的视频链接；如果平台要求登录、验证码或禁止读取，会逐条显示真实失败原因。</p><div className={`douyin-login ${douyinStatus?.ready ? "ready" : ""}`}><div><b>{douyinStatus?.ready ? "抖音读取状态可用" : "首次使用请刷新抖音状态"}</b><small>{douyinStatus?.message || "打开专用窗口后访问或登录抖音，LiveAgent 会使用这次会话读取视频。"}</small></div><button className="secondary" disabled={loginBusy} onClick={openDouyinLogin}>{loginBusy ? "正在打开…" : "登录抖音"}</button><button className="secondary" onClick={refreshDouyin}>刷新状态</button></div><textarea className="director-link-input" value={links} onChange={e => setLinks(e.target.value)} placeholder={'例如：\n6.66 复制分享文案 https://v.douyin.com/xxxxxx/ 复制此链接，打开抖音搜索\nhttps://www.douyin.com/video/xxxxxxxx'}/><button className="primary" disabled={busy} onClick={parseLinks}>{busy ? "正在提取音轨并转写…" : "解析链接并生成逐字稿"}<Icon name="arrow" size={17}/></button>{phase && <div className="research-status"><span className="research-spinner"/><p><b>正在处理参考视频</b><small>{phase}</small></p></div>}</div>
    {(sources.length > 0 || failures.length > 0) && <div className="director-step"><b>02 · 核对参考视频逐字稿</b><p className="director-hint">只会使用成功解析的逐字稿生成新脚本。你可以直接修正识别错误，也可以排除不想参考的视频。</p>{failures.length > 0 && <div className="director-failures">{failures.map((item, i) => <p key={`${item.url}-${i}`}><b>解析失败：</b>{item.url}<small>{item.error}</small></p>)}</div>}<div className="director-source-list">{sources.map((item, i) => <article key={`${item.url}-${i}`}><div className="source-title"><span>{i + 1}</span><div><h4>{item.title || `参考视频 ${i + 1}`}</h4><p>{item.author || "作者信息未提供"} · {item.duration ? `${Math.round(Number(item.duration))} 秒` : "时长未知"}</p><a href={item.url} target="_blank" rel="noreferrer">打开原视频</a></div><button onClick={() => setSources(old => old.filter((_, x) => x !== i))}>排除</button></div><textarea value={item.transcript || ""} onChange={e => editTranscript(i, e.target.value)} /></article>)}</div></div>}
    {sources.length > 0 && <div className="director-step"><b>03 · 生成原创脚本、分镜和拍摄建议</b><div className="director-output"><input value={outputDir} onChange={e => setOutputDir(e.target.value)} placeholder="留空则保存到系统默认目录"/><button className="secondary" onClick={chooseFolder}><Icon name="folder" size={17}/>选择保存文件夹</button><button className="primary" disabled={busy} onClick={create}>{busy ? "正在创建…" : "生成视频编导方案"}<Icon name="arrow" size={17}/></button></div><small>输出 Word 和 Excel：参考逐字稿拆解、原创口播脚本、逐镜分镜、拍摄清单、合规提醒和剪辑建议。</small></div>}</section>;
}
function ScoutWorkspace({ local, onNotify }: {
    local: any;
    onNotify: (s: string) => void;
}) { const [themes, setThemes] = useState<any[]>([]), [candidates, setCandidates] = useState<any[]>([]), [selected, setSelected] = useState<number[]>([]), [description, setDescription] = useState(""), [draft, setDraft] = useState<any>(null), [themeId, setThemeId] = useState(""), [period, setPeriod] = useState("day"), [busy, setBusy] = useState(false); const api = async (path: string, init?: RequestInit) => { const r = await fetch(`${GATEWAY}/api/scout${path}`, init); const x = await r.json(); if (!r.ok)
    throw new Error(x.error || "操作失败"); return x; }; const refresh = async () => { if (!local)
    return; try {
    const [t, c] = await Promise.all([api("/api/themes"), api(`/api/candidates${themeId ? `?theme_id=${themeId}` : ""}`)]);
    setThemes(t.themes || []);
    setCandidates(c.candidates || []);
    if (!themeId && t.themes?.[0])
        setThemeId(String(t.themes[0].id));
}
catch (e: any) {
    onNotify(e.message);
} }; useEffect(() => { refresh(); }, [local, themeId]); const understand = async () => { if (description.trim().length < 4) {
    onNotify("请先写一句关注领域描述");
    return;
} setBusy(true); try {
    setDraft((await api("/api/themes/parse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ description }) })).theme);
}
catch (e: any) {
    onNotify(e.message);
}
finally {
    setBusy(false);
} }; const save = async () => { try {
    await api("/api/themes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...draft, description }) });
    setDraft(null);
    setDescription("");
    onNotify("关注领域已创建");
    refresh();
}
catch (e: any) {
    onNotify(e.message);
} }; const updateStatus = async (status: string) => { if (!selected.length)
    return onNotify("请先勾选主播"); await api("/api/candidates/status", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_ids: selected, status }) }); onNotify("主播状态已更新"); refresh(); }; const startRank = async () => { if (!themeId)
    return onNotify("请先创建并选择关注领域"); try {
    await api("/api/chanmama/export/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ theme_id: Number(themeId), period }) });
    onNotify("已开始从蝉妈妈更新榜单");
}
catch (e: any) {
    onNotify(e.message);
} }; const reports = async () => { if (!selected.length)
    return onNotify("请先勾选主播"); await api("/api/reports/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_ids: selected }) }); onNotify("达人拆解已开始生成"); }; const addQuick = async () => { if (!selected.length)
    return onNotify("请先勾选主播"); await api("/api/recorder/add", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidate_ids: selected }) }); onNotify("已加入快抖录制监控"); }; if (!local)
    return <section className="surface scout-workspace"><h2>请先启动本机工作台</h2><p>启动后这里会读取你原有的关注领域、候选主播和蝉妈妈状态。</p></section>; return <section className="scout-workspace"><div className="scout-create"><div><p className="eyebrow">STEP 01 · 关注领域</p><h2>用一句话告诉 Agent 你要找什么主播</h2><textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="例如：寻找中高端女装主播，粉丝30万以下，排除童装和品牌官方号"/><button className="primary" onClick={understand} disabled={busy}>{busy ? "正在理解…" : "让 Agent 理解"}</button></div>{draft && <div className="theme-draft"><b>{draft.name || "新关注领域"}</b><p>类目：{draft.platform_category || "待确认"}</p><p>人群：{draft.target_audience || "待确认"}</p><p>粉丝上限：{draft.max_followers || "不限"}</p><button className="primary" onClick={save}>确认并创建</button></div>}</div><div className="scout-toolbar"><label>关注领域<select value={themeId} onChange={e => setThemeId(e.target.value)}>{themes.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label><label>榜单周期<select value={period} onChange={e => setPeriod(e.target.value)}><option value="day">日榜</option><option value="week">周榜</option><option value="month">月榜</option></select></label><button className="secondary" onClick={startRank}>从蝉妈妈更新榜单</button><button className="secondary" onClick={refresh}>刷新候选池</button></div><div className="candidate-actions"><b>已选择 {selected.length} 位主播</b><span /><button onClick={() => updateStatus("rejected")}>排除</button><button onClick={() => updateStatus("approved")}>通过</button><button onClick={reports}>生成达人拆解</button><button className="primary" onClick={addQuick}>自动加入快抖</button></div><div className="candidate-table"><div className="candidate-head"><span /><span>主播</span><span>领域</span><span>粉丝</span><span>销售表现</span><span>推荐分</span><span>状态</span></div>{candidates.slice(0, 80).map(c => <div className="candidate-row" key={c.id}><input type="checkbox" checked={selected.includes(c.id)} onChange={e => setSelected(old => e.target.checked ? [...old, c.id] : old.filter(x => x !== c.id))}/><b>{c.anchor_name}<small>{c.douyin_id || ""}</small></b><span>{c.theme_name || c.category}</span><span>{c.followers ?? "—"}</span><span>{c.estimated_gmv_text || c.estimated_gmv || "—"}<small>销量 {c.sales_volume_text || c.sales_volume || "—"}</small></span><strong>{Number(c.score || 0).toFixed(1)}</strong><em>{c.status}</em></div>)}</div></section>; }
function TaskCenter({ jobs, filter, setFilter, search, setSearch, taskMenu, setTaskMenu, onNotify, onOpenFile, onOpenFolder, onDelete }: {
    jobs: Job[];
    filter: string;
    setFilter: (s: string) => void;
    search: string;
    setSearch: (s: string) => void;
    taskMenu: string | null;
    setTaskMenu: (s: string | null) => void;
    onNotify: (s: string) => void;
    onOpenFile: (j: Job) => void;
    onOpenFolder: (j: Job) => void;
    onDelete: (j: Job) => void;
}) { const counts = { all: jobs.length, running: jobs.filter(x => x.status === "running").length, confirm: jobs.filter(x => x.status === "confirm").length, completed: jobs.filter(x => x.status === "completed").length }; const rows = jobs.filter(j => (filter === "all" || j.status === filter) && j.name.toLowerCase().includes(search.toLowerCase())); return <><div className="page-title"><div><p className="eyebrow">TASK CENTER</p><h1>任务中心</h1><p>任务失败时会直接显示后台返回的真实原因；任务完成后可以直接打开文件或所在文件夹。</p></div><button className="primary" onClick={() => onNotify("任务状态已刷新")}>刷新状态</button></div><section className="surface"><div className="filter-row"><button className={`chip ${filter === "all" ? "active" : ""}`} onClick={() => setFilter("all")}>全部 {counts.all}</button><button className={`chip ${filter === "running" ? "active" : ""}`} onClick={() => setFilter("running")}>进行中 {counts.running}</button><button className={`chip ${filter === "confirm" ? "active" : ""}`} onClick={() => setFilter("confirm")}>等待确认 {counts.confirm}</button><button className={`chip ${filter === "completed" ? "active" : ""}`} onClick={() => setFilter("completed")}>已完成 {counts.completed}</button><span /><label>搜索任务<input placeholder="输入任务名称" value={search} onChange={e => setSearch(e.target.value)}/></label></div><div className="task-table"><div className="task-head"><span>任务名称</span><span>Agent</span><span>进度</span><span>状态</span><span>说明</span><span /></div>{rows.map((r, i) => <div className={`task-row ${r.status === "failed" ? "failed-row" : ""}`} key={r.job_id}><span><i className={`file-dot d${i % 3}`}/><b>{r.name}</b></span><span>{r.agent}</span><span><em className="progress"><i style={{ width: `${r.progress}%` }}/></em><small>{r.progress}%</small></span><span><b className={`status ${r.status}`}>{r.status_text}</b></span><span>{r.error || r.message}</span><div className="task-actions"><button aria-label="任务菜单" onClick={() => setTaskMenu(taskMenu === r.job_id ? null : r.job_id)}>•••</button>{taskMenu === r.job_id && <div className="task-menu"><button onClick={() => { onNotify(`${r.name}：${r.error || r.message}`); setTaskMenu(null); }}>查看详情</button>{r.output && <><button onClick={() => { onOpenFile(r); setTaskMenu(null); }}>打开文件</button><button onClick={() => { onOpenFolder(r); setTaskMenu(null); }}>打开所在文件夹</button></>}<button className="danger" onClick={() => { onDelete(r); setTaskMenu(null); }}>删除任务</button></div>}</div></div>)}</div></section><section className="recovery"><div className="recovery-icon">!</div><div><b>任务不会静默失败</b><p>网络、云服务、依赖或文件格式出错时，失败原因会保留在任务说明中。</p></div><button onClick={() => onNotify("恢复中心：当前没有需要恢复的任务")}>查看恢复中心</button></section></>; }
function Settings({ local, onNotify }: {
    local: any;
    onNotify: (s: string) => void;
}) {
    const [form, setForm] = useState({ dashscope_api_key: "", oss_access_key_id: "", oss_access_key_secret: "", oss_endpoint: local?.oss?.endpoint || "https://oss-cn-beijing.aliyuncs.com", oss_bucket: local?.oss?.bucket || "", quick_recorder_exe: local?.recorder?.path || "" }), [busy, setBusy] = useState(false);
    const change = (k: string, v: string) => setForm(x => ({ ...x, [k]: v }));
    const save = async () => { setBusy(true); try {
        const r = await fetch(`${GATEWAY}/api/connections/configure`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
        const x = await r.json();
        if (!r.ok)
            throw new Error(x.error || "保存失败");
        onNotify("配置已保存；云配置发生变化时请继续点击实际验证");
        window.setTimeout(() => window.location.reload(), 700);
    }
    catch (e: any) {
        onNotify(e.message);
    }
    finally {
        setBusy(false);
    } };
    const verify = async () => { setBusy(true); try {
        const r = await fetch(`${GATEWAY}/api/connections/verify`, { method: "POST" });
        const x = await r.json();
        if (!r.ok)
            throw new Error((x.errors || []).join("；") || "验证失败");
        onNotify("Qwen 与 OSS 均已通过实际连接验证");
        window.setTimeout(() => window.location.reload(), 900);
    }
    catch (e: any) {
        onNotify(e.message);
    }
    finally {
        setBusy(false);
    } };
    const model = local?.model || {}, oss = local?.oss || {};
    return <>
    <div className="page-title"><div><p className="eyebrow">SETTINGS</p><h1>设置与连接</h1><p>“已配置”只表示本机保存了资料；只有实际请求成功后才会显示“已验证”。</p></div><button className="secondary" onClick={() => window.location.reload()}>刷新状态</button></div>
    <section className="surface setup-overview">
      <div><p className="eyebrow">NEW USER CHECKLIST</p><h2>第一次使用，请准备云服务配置</h2><p>不要沿用来源不明的 Bucket、OSS AccessKey 或百炼 Key。录制助手是可选功能，可在下方单独填写本机路径。</p></div>
      <div className="setup-checklist"><span><b>1</b>新的百炼 API Key</span><span><b>2</b>新的 OSS Bucket</span><span><b>3</b>新 RAM 用户的 AccessKey ID</span><span><b>4</b>与该 ID 配套的 AccessKey Secret</span></div>
      <p className="tutorial-warning">所有密钥只填写在本机页面里，不要截图、不要发到聊天中，也不要转发给其他人。</p>
    </section>
    <section className="surface connection-setup">
      <div className="surface-title"><div><p className="eyebrow">STEP 01</p><h2>连接阿里云百炼 Qwen</h2><p>Qwen 用于理解逐字稿、比较直播时段并生成深度分析。</p></div><span className={model.verified ? "verified" : "unverified"}>{model.verified ? "已实际验证" : model.configured ? "已配置，未验证" : "尚未配置"}</span></div>
      <details className="binding-tutorial" open><summary>从零创建百炼 API Key（点这里展开/收起）</summary><ol><li><span>1</span><p><b>打开百炼密钥页面并登录。</b>使用准备付费和长期使用的阿里云账号，不要切换到旧账号。</p></li><li><span>2</span><p><b>确认地域为“华北2（北京）”。</b>本项目默认调用北京地域的百炼服务；地域不一致时，Key 和接口可能无法配套使用。</p></li><li><span>3</span><p><b>点击“创建 API Key”。</b>归属业务空间选择“默认业务空间”，描述可以写“LiveAgent”。权限首次配置可选择“全部”。请创建百炼按量付费的通用 Key，不要使用 Token Plan 或 Coding Plan 的专属 Key。</p></li><li><span>4</span><p><b>立即复制完整密钥。</b>新密钥通常以 <b>sk-ws</b> 开头，旧格式可能以 <b>sk-</b> 开头；完整明文通常只在创建时显示一次。</p></li><li><span>5</span><p><b>粘贴到本页的 DashScope API Key 输入框。</b>先不要点击验证，继续完成下面的 OSS 配置。</p></li></ol><div className="tutorial-links"><a href="https://bailian.console.aliyun.com/?tab=model#/api-key" target="_blank" rel="noreferrer">打开百炼 API Key 页面 ↗</a><a href="https://help.aliyun.com/zh/model-studio/get-api-key" target="_blank" rel="noreferrer">查看阿里云官方说明 ↗</a></div><p className="tutorial-warning">不要只复制页面显示的脱敏 Key；必须使用创建弹窗中显示的完整密钥。</p></details>
      <label>DashScope API Key<input type="password" value={form.dashscope_api_key} onChange={e => change("dashscope_api_key", e.target.value)} placeholder={model.configured ? "已保存；不修改可留空" : "粘贴完整的 sk-ws… 或 sk-… Key"}/><small className="field-help">这里填写百炼模型 API Key，不是阿里云 AccessKey ID，也不是 Token Plan/Coding Plan Key。</small></label>
    </section>
    <section className="surface connection-setup">
      <div className="surface-title"><div><p className="eyebrow">STEP 02</p><h2>连接阿里云 OSS</h2><p>OSS 临时存放从视频提取的音频，供云端语音转写读取。</p></div><span className={oss.verified ? "verified" : "unverified"}>{oss.verified ? "已实际验证" : oss.configured ? "已配置，未验证" : "尚未配置"}</span></div>
      <details className="binding-tutorial" open><summary>从零创建新的 OSS Bucket 与 RAM 凭证（点这里展开/收起）</summary>
        <div className="tutorial-section"><h3>A. 新建一个全新的 Bucket</h3><ol><li><span>1</span><p>点击“打开 OSS Bucket 页面”，确认右上角登录的是<b>拥有这个新 Bucket 的同一个阿里云主账号</b>，然后点击“创建 Bucket”。</p></li><li><span>2</span><p>Bucket 名称必须全网唯一。建议写 <b>liveagent-audio-你的数字</b>，例如 liveagent-audio-26081801；不要再填写旧名称。</p></li><li><span>3</span><p>地域选择<b>华北2（北京）</b>；存储类型选择<b>标准存储</b>；存储冗余选择<b>本地冗余</b>；读写权限选择<b>私有</b>。</p></li><li><span>4</span><p>“阻止公共访问”保持开启。版本控制、实时日志、定时备份、HDFS 等附加功能都可以保持关闭或默认值，然后完成创建。</p></li><li><span>5</span><p>创建后进入 Bucket 的“概览”，确认公网 Endpoint 为 <b>https://oss-cn-beijing.aliyuncs.com</b>。输入框里只填 Endpoint，不要拼接 Bucket 名称。</p></li></ol></div>
        <div className="tutorial-section"><h3>B. 新建专用 RAM 用户并按最小权限授权</h3><ol><li><span>1</span><p>点击“打开 RAM 用户页面”，选择“创建用户”。登录名称建议填 <b>liveagent-oss</b>，显示名称可填“LiveAgent OSS”。这个用户只供程序调用，不需要启用控制台登录。</p></li><li><span>2</span><p>为刚创建的 Bucket 新建一条<b>自定义权限策略</b>，对象资源只覆盖该 Bucket 下的 <b>live-breakdown/*</b> 与 <b>liveagent-director/*</b> 前缀。</p></li><li><span>3</span><p>对象权限授予 <b>PutObject、GetObject、DeleteObject、ListParts、AbortMultipartUpload</b>，Bucket 本身另授予 <b>GetBucketInfo</b>；不要授予账号级 <b>AliyunOSSFullAccess</b>。</p></li><li><span>4</span><p>把这条自定义策略授权给专用 RAM 用户，然后进入<b>“认证管理”或“凭证管理”</b>创建 AccessKey。不会编写策略时，请先查看阿里云 RAM 官方文档。</p></li><li><span>5</span><p>创建成功后立即保存同一组 <b>AccessKey ID</b> 和 <b>AccessKey Secret</b>。ID 通常以 LTAI 开头，Secret 只完整显示一次；两项不能分别来自不同的 Key。</p></li></ol></div>
        <div className="tutorial-section"><h3>C. 回到本页填写四个字段</h3><ul><li><b>AccessKey ID：</b>新 RAM 用户生成的 LTAI…</li><li><b>AccessKey Secret：</b>与上面 ID 同时生成的完整 Secret</li><li><b>Endpoint：</b>北京地域填写 https://oss-cn-beijing.aliyuncs.com</li><li><b>Bucket：</b>只填写刚创建的 Bucket 名称，例如 liveagent-audio-26081801</li></ul></div>
        <div className="tutorial-links"><a href="https://oss.console.aliyun.com/bucket" target="_blank" rel="noreferrer">打开 OSS Bucket 页面 ↗</a><a href="https://ram.console.aliyun.com/users" target="_blank" rel="noreferrer">打开 RAM 用户页面 ↗</a><a href="https://help.aliyun.com/zh/ram/user-guide/grant-permissions-to-the-ram-user" target="_blank" rel="noreferrer">查看 RAM 官方授权说明 ↗</a></div><p className="tutorial-warning">如果验证提示“bucket does not belong to you”，表示 AccessKey 所属主账号与 Bucket 所属主账号不是同一个；请重新在拥有新 Bucket 的账号下创建 RAM 用户和 AccessKey。</p>
      </details>
      <div className="setup-grid"><label>AccessKey ID<input type="password" value={form.oss_access_key_id} onChange={e => change("oss_access_key_id", e.target.value)} placeholder={oss.configured ? "已保存；不修改可留空" : "粘贴新 RAM 用户的 LTAI… ID"}/><small className="field-help">必须与下面的 Secret 来自同一次创建。</small></label><label>AccessKey Secret<input type="password" value={form.oss_access_key_secret} onChange={e => change("oss_access_key_secret", e.target.value)} placeholder={oss.configured ? "已保存；不修改可留空" : "粘贴与该 ID 配套的完整 Secret"}/><small className="field-help">Secret 不会再次完整显示，丢失时请重新创建 AccessKey。</small></label><label>Endpoint<input value={form.oss_endpoint} onChange={e => change("oss_endpoint", e.target.value)} placeholder="https://oss-cn-beijing.aliyuncs.com"/><small className="field-help">不要填写 Bucket 域名，也不要在末尾添加 Bucket 名称。</small></label><label>Bucket<input value={form.oss_bucket} onChange={e => change("oss_bucket", e.target.value)} placeholder="例如 liveagent-audio-26081801"/><small className="field-help">只填新 Bucket 名称，不要填写网址。</small></label></div>
    </section>
    <section className="surface connection-setup">
      <div className="surface-title"><div><p className="eyebrow">OPTIONAL</p><h2>连接快抖直播录制助手</h2><p>只有使用主播发现中的“加入快抖录制”时才需要配置。LiveAgent Studio 不附带该第三方软件。</p></div><span className={local?.recorder?.found ? "verified" : "unverified"}>{local?.recorder?.found ? "路径有效" : local?.recorder?.configured ? "路径无效" : "可选，未配置"}</span></div>
      <label>录制助手 EXE 完整路径<input value={form.quick_recorder_exe} onChange={e => change("quick_recorder_exe", e.target.value)} placeholder="例如 C:\\Program Files\\录制助手\\录制助手.exe"/><small className="field-help">请在资源管理器中找到 EXE，按住 Shift 右键复制文件路径后粘贴到这里。可以带英文双引号，保存时会自动处理；留空表示不使用录制功能。</small></label>
    </section>
    <section className="surface final-check"><p className="eyebrow">STEP 03</p><h2>保存并实际验证</h2><ol><li>填写云服务配置；如需录制功能，再粘贴录制助手 EXE 路径。</li><li>点击“保存到本机”，系统会同时检查录制助手路径是否真实存在。</li><li>再点击“实际验证 Qwen 与 OSS”；两项都显示“已实际验证”后即可开始直播拆解和复盘。</li></ol><div className="error-guide"><b>常见报错：</b><span><strong>百炼 401</strong>：Key 不完整、已失效或误用了其他类型 Key。</span><span><strong>OSS 403 / AccessDenied</strong>：自定义策略没有覆盖当前 Bucket/前缀，或 AccessKey 与 Bucket 不属于同一主账号。</span><span><strong>录制助手路径无效</strong>：请粘贴以 .exe 结尾的完整文件路径，而不是快捷方式。</span></div></section>
    <div className="connection-actions"><button className="secondary" disabled={busy} onClick={save}>1. 保存到本机</button><button className="primary" disabled={busy} onClick={verify}>{busy ? "正在检查…" : "2. 实际验证 Qwen 与 OSS"}</button></div>
  </>;
}
function NewTaskModal({ agent, local, onClose, onJob, onNotify }: {
    agent: Agent;
    local: any;
    onClose: () => void;
    onJob: (j: Job) => void;
    onNotify: (s: string) => void;
}) { const [file, setFile] = useState<File | null>(null), [traffic, setTraffic] = useState<File | null>(null), [drag, setDrag] = useState(false), [trafficDrag, setTrafficDrag] = useState(false), [busy, setBusy] = useState(false), [name, setName] = useState(`新的${agent.title}任务`), [outputDir, setOutputDir] = useState(""), [error, setError] = useState(""); const chooseFolder = async () => { setError(""); try {
    const r = await fetch(`${GATEWAY}/api/select-folder`, { method: "POST" });
    const x = await r.json();
    if (!r.ok)
        throw new Error(x.error || "文件夹选择失败");
    if (x.path)
        setOutputDir(x.path);
}
catch (e: any) {
    setError(e.message || "无法打开文件夹选择器");
} }; const create = async () => { if (agent.id === "scout") {
    onClose();
    return;
} if (!file) {
    setError("请先选择直播视频");
    return;
} if (agent.id === "review" && !traffic) {
    setError("请再选择巨量百应流量 Excel");
    return;
} if (!local) {
    setError("当前打开的是在线展示页，无法访问你电脑上的处理程序。请运行桌面文件“01_启动_LiveAgent_Studio.cmd”，再在自动打开的页面上传。");
    return;
} if (!local?.model?.verified || !local?.oss?.verified) {
    setError("Qwen 或 OSS 尚未通过实际连接验证，请先到“设置与连接”完成配置和验证。");
    return;
} setBusy(true); setError(""); try {
    const fd = new FormData();
    fd.append("video", file);
    fd.append("name", name);
    if (traffic)
        fd.append("traffic", traffic);
    if (outputDir.trim())
        fd.append("output_dir", outputDir.trim());
    const url = agent.id === "review" ? "/api/review/jobs" : "/api/breakdown/jobs";
    const r = await fetch(`${GATEWAY}${url}`, { method: "POST", body: fd });
    const x = await r.json();
    if (!r.ok)
        throw new Error(x.error || "提交失败");
    onJob(x);
}
catch (e: any) {
    setError(e.message);
}
finally {
    setBusy(false);
} }; const selectTrafficFile = (candidate?: File | null) => {
    if (!candidate)
        return;
    if (!/\.(xlsx?|csv)$/i.test(candidate.name)) {
        setError("请拖入巨量百应导出的 Excel 或 CSV 文件");
        return;
    }
    setTraffic(candidate);
    setError("");
}; const drop = <label className={`drop-zone ${drag ? "drag" : ""}`} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files[0] || null); }}><input type="file" accept="video/*,.mkv,.avi" onChange={e => setFile(e.target.files?.[0] || null)}/><span><Icon name={file ? "check" : "upload"} size={30}/></span><b>{file ? file.name : "把直播视频拖到这里"}</b><p>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB · 已选择` : "或点击选择完整直播录屏"}</p><small>支持 MP4、MOV、MKV、AVI</small></label>; return <div className="modal-backdrop" onMouseDown={onClose}><div className={`modal ${agent.id === "review" ? "review-task-modal" : ""}`} onMouseDown={e => e.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">NEW TASK · {agent.code}</p><h2>开始{agent.title}</h2></div><button onClick={onClose}><Icon name="close"/></button></div>{drop}{agent.id === "review" && <label className={`traffic-picker ${trafficDrag ? "drag" : ""}`} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setTrafficDrag(true); }} onDragLeave={e => { e.preventDefault(); setTrafficDrag(false); }} onDrop={e => { e.preventDefault(); setTrafficDrag(false); selectTrafficFile(e.dataTransfer.files?.[0]); }}><span><Icon name={traffic ? "check" : "upload"}/></span><p><b>{traffic ? traffic.name : "把巨量百应流量 Excel 拖到这里"}</b><small>{traffic ? `${(traffic.size / 1024 / 1024).toFixed(1)} MB · 已选择` : "也可以点击选择直播详情页导出的分钟级流量表"}</small></p><input type="file" accept=".xlsx,.xls,.csv" onChange={e => selectTrafficFile(e.target.files?.[0])}/></label>}<div className="modal-field"><label>任务名称</label><input value={name} onChange={e => setName(e.target.value)}/></div>{(agent.id === "breakdown" || agent.id === "review") && <div className="modal-field output-folder-field"><label>{agent.id === "review" ? "复盘结果保存位置" : "拆解文件保存位置"}</label><div><input value={outputDir} onChange={e => setOutputDir(e.target.value)} placeholder="点击右侧按钮选择文件夹；留空则保存到系统默认目录"/><button type="button" className="secondary" onClick={chooseFolder}><Icon name="folder" size={17}/>选择文件夹</button></div><small>{agent.id === "review" ? "任务完成后，Excel、Word 和处理说明会一起复制到这里。" : "任务完成后，Excel 会复制到这里；任务中心仍可直接打开文件。"}</small></div>}{error && <div className="form-error">{error}</div>}<div className="modal-note"><span>i</span><p><b>{local?.model?.verified && local?.oss?.verified ? "Qwen 与 OSS 已验证" : "开始前需要完成连接验证"}</b><br />{agent.id === "review" ? "系统会先转写视频，再把逐字稿与流量表交给 Qwen 分析。" : "系统会从视频提取音频、上传 OSS、转写并生成拆解 Excel。"}</p></div><footer><button className="secondary" onClick={onClose}>取消</button><button className="primary" disabled={busy} onClick={create}>{busy ? "正在提交…" : "创建并开始"}<Icon name="arrow" size={17}/></button></footer></div></div>; }
function GuideModal({ agent, onClose, onStart }: {
    agent: Agent;
    onClose: () => void;
    onStart: () => void;
}) { const copy = agent.id === "scout" ? ["在当前页面描述关注领域", "确认 Agent 解析出的筛选条件", "从蝉妈妈更新榜单并筛选主播", "生成达人拆解或加入快抖录制"] : agent.id === "breakdown" ? ["在设置中填写并验证百炼与 OSS", "准备完整直播录屏，建议 MP4", "上传视频后在任务中心看实时进度", "完成后打开逐字稿拆解 Excel"] : agent.id === "review" ? ["在设置中验证 Qwen 与 OSS", "上传完整直播视频", "上传同场巨量百应分钟流量 Excel", "系统自动转写、分析并生成复盘 Excel"] : ["粘贴一个或多个由你选择的短视频链接", "Agent 提取音轨并生成带时间戳逐字稿", "核对、修正或排除参考逐字稿", "基于真实逐字稿生成原创脚本、分镜与拍摄建议"]; return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal guide-modal" onMouseDown={e => e.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">HOW TO USE · {agent.code}</p><h2>{agent.title}使用说明</h2></div><button onClick={onClose}><Icon name="close"/></button></div><div className="guide-steps">{copy.map((x, i) => <div key={x}><span>{i + 1}</span><p><b>{x}</b><small>{i === 0 ? "准备与进入" : i === 3 ? "查看最终输出" : "系统会引导你完成"}</small></p></div>)}</div>{agent.id === "director" && <div className="editor-example"><b>参考素材原则：</b><p>Agent 不再自动搜索或判断“高赞”。只有你粘贴的链接会被处理；成功解析的逐字稿是后续原创脚本的唯一参考素材，失败链接会明确说明原因。</p></div>}<footer><button className="secondary" onClick={onClose}>我知道了</button><button className="primary" onClick={onStart}>现在开始 <Icon name="arrow" size={17}/></button></footer></div></div>; }
