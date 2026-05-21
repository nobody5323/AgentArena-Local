import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./vendor/lightswind.css";
import "./styles.css";

const API_BASE = import.meta.env.VITE_AGENTARENA_API || "http://127.0.0.1:8765";

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function App() {
  const [status, setStatus] = useState("连接中");
  const [root, setRoot] = useState("");
  const [tasks, setTasks] = useState([]);
  const [agents, setAgents] = useState([]);
  const [taskFile, setTaskFile] = useState("examples/python_debug_login/task.yaml");
  const [selectedAgents, setSelectedAgents] = useState(["codex"]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [logs, setLogs] = useState(["正在连接 AgentArena API..."]);
  const [jobId, setJobId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState(120);
  const cursorAvailable = agents.some((agent) => agent.name === "cursor" && agent.gui);

  const selectedLabel = useMemo(() => selectedAgents.join(", "), [selectedAgents]);

  async function refresh() {
    try {
      const [health, options, board] = await Promise.all([
        api("/api/health"),
        api("/api/options"),
        api("/api/leaderboard"),
      ]);
      setStatus("已连接");
      setRoot(health.root);
      setTasks(options.tasks || []);
      setAgents(options.agents || []);
      setLeaderboard(board.rows || []);
      if ((options.tasks || []).length && !taskFile) {
        setTaskFile(options.tasks[0].path);
      }
      if (!selectedAgents.length) {
        const firstReady = (options.agents || []).find((agent) => agent.available);
        if (firstReady) setSelectedAgents([firstReady.name]);
      }
    } catch (error) {
      setStatus("未连接");
      setLogs((current) => [...current, `API 连接失败：${error.message}`]);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!jobId) return undefined;
    const timer = window.setInterval(async () => {
      const job = await api(`/api/jobs/${jobId}`);
      setLogs(job.logs.length ? job.logs : ["任务已排队..."]);
      if (job.status === "succeeded" || job.status === "failed") {
        window.clearInterval(timer);
        setBusy(false);
        setJobId(null);
        refresh();
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [jobId]);

  function toggleAgent(agent) {
    if (!agent.available) return;
    setSelectedAgents((current) => {
      if (current.includes(agent.name)) {
        return current.length === 1 ? current : current.filter((item) => item !== agent.name);
      }
      return [...current, agent.name];
    });
  }

  async function runBenchmark() {
    setBusy(true);
    setLogs([`正在启动 ${selectedLabel} 的评测...`]);
    try {
      const job = await api("/api/run", {
        method: "POST",
        body: JSON.stringify({ task_file: taskFile, agents: selectedAgents, timeout: timeoutSeconds }),
      });
      setJobId(job.job_id);
    } catch (error) {
      setBusy(false);
      setLogs((current) => [...current, `评测启动失败：${error.message}`]);
    }
  }

  async function cancelRun() {
    if (!jobId) return;
    try {
      await api(`/api/jobs/${jobId}/cancel`, { method: "POST" });
      setLogs((current) => [...current, "已请求停止"]);
    } catch (error) {
      setLogs((current) => [...current, `停止失败：${error.message}`]);
    } finally {
      setBusy(false);
      setJobId(null);
    }
  }

  async function makeReport(kind) {
    setBusy(true);
    const label = kind === "dashboard" ? "仪表盘" : "报告";
    setLogs([`正在生成${label}...`]);
    try {
      const result = await api("/api/reports", {
        method: "POST",
        body: JSON.stringify({ kind }),
      });
      setLogs([`${label}已保存：${result.path}`]);
      await refresh();
    } catch (error) {
      setLogs([`${label}生成失败：${error.message}`]);
    } finally {
      setBusy(false);
    }
  }

  function openReport(kind) {
    const label = kind === "dashboard" ? "仪表盘" : "报告";
    window.open(`${API_BASE}/api/reports/file/${kind}`, "_blank", "noopener,noreferrer");
    setLogs([`正在打开${label}。如果页面显示 404，请先生成${label}。`]);
  }

  async function openCursor() {
    setLogs(["正在打开 Cursor 任务会话..."]);
    try {
      const result = await api("/api/cursor/session", {
        method: "POST",
        body: JSON.stringify({ task_file: taskFile }),
      });
      setLogs([
        `Cursor 已打开：${result.worktree}`,
        `任务说明：${result.instruction_file}`,
      ]);
    } catch (error) {
      setLogs([`Cursor 启动失败：${error.message}`]);
    }
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#fff8ff] text-slate-900">
      <div className="anime-sky" />
      <section className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 py-6">
        <nav className="flex items-center justify-between rounded-[28px] border border-white/80 bg-white/70 px-5 py-3 shadow-[0_18px_60px_rgba(244,114,182,0.16)] backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-pink-400 via-fuchsia-400 to-sky-300 text-xl font-black text-white shadow-lg">
              A
            </div>
            <div>
              <p className="text-sm font-semibold text-fuchsia-500">AgentArena Local</p>
              <h1 className="text-xl font-black tracking-tight">中文 Web 评测控制台</h1>
            </div>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            <button className="pill" onClick={refresh}>刷新</button>
            <span className={status === "已连接" ? "pill good" : "pill warn"}>{status}</span>
          </div>
        </nav>

        <div className="grid flex-1 gap-6 py-8 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="flex flex-col justify-center">
            <div className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-pink-200 bg-white/80 px-4 py-2 text-sm font-bold text-pink-500 shadow-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_18px_#34d399]" />
              本地运行、隔离 worktree、实时日志
            </div>
            <h2 className="max-w-3xl text-5xl font-black leading-tight tracking-tight md:text-7xl">
              在本机对比不同编程 Agent 的表现。
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
              选择任务和 Agent，启动隔离 Git worktree 评测，查看分数、失败原因、
              diff、计划输出和 AGENTS.md 变体结果。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button className="shine-btn" disabled={busy} onClick={runBenchmark}>开始评测</button>
              {busy && <button className="soft-btn danger" onClick={cancelRun}>停止</button>}
              <button className="soft-btn" disabled={busy || !cursorAvailable} onClick={openCursor}>打开 Cursor</button>
              <button className="soft-btn" disabled={busy} onClick={() => makeReport("dashboard")}>生成仪表盘</button>
              <button className="soft-btn" disabled={busy} onClick={() => openReport("dashboard")}>打开仪表盘</button>
              <button className="soft-btn" disabled={busy} onClick={() => makeReport("report")}>生成报告</button>
              <button className="soft-btn" disabled={busy} onClick={() => openReport("report")}>打开报告</button>
            </div>
          </section>

          <section className="relative">
            <div className="mascot-card">
              <div className="orb orb-one" />
              <div className="orb orb-two" />
              <div className="relative z-10">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-black uppercase tracking-[0.18em] text-pink-500">评测设置</p>
                    <h3 className="mt-2 text-3xl font-black">任务控制台</h3>
                  </div>
                  <div className="rounded-2xl bg-emerald-100 px-3 py-2 text-sm font-black text-emerald-600">
                    就绪
                  </div>
                </div>

                <div className="mt-6 grid gap-4">
                  <label className="field">
                    <span>项目目录</span>
                    <input value={root || "等待 API..."} readOnly />
                  </label>
                  <label className="field">
                    <span>任务 YAML</span>
                    <select value={taskFile} onChange={(event) => setTaskFile(event.target.value)}>
                      {tasks.map((task) => (
                        <option key={task.path} value={task.path}>{task.title} [{task.type}] - {task.path}</option>
                      ))}
                      {!tasks.length && <option value={taskFile}>{taskFile}</option>}
                    </select>
                  </label>
                  <label className="field">
                    <span>Agent 超时秒数</span>
                    <input
                      type="number"
                      min="10"
                      max="1800"
                      value={timeoutSeconds}
                      onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
                    />
                  </label>
                  <div className="agent-grid">
                    {agents.map((agent) => (
                      <button
                        key={agent.name}
                        className={selectedAgents.includes(agent.name) ? "agent active" : "agent"}
                        onClick={() => toggleAgent(agent)}
                        disabled={!agent.available}
                        title={agent.gui ? "使用打开 Cursor 创建 GUI worktree" : agent.interactive ? "手动模式 Agent，请使用 CLI 或专用 GUI 按钮" : agent.available ? "已在 PATH 中找到" : "PATH 中未找到"}
                      >
                        {agent.name}
                        <small>{agent.gui ? "GUI" : agent.interactive ? "仅 CLI" : agent.available ? "可用" : "缺失"}</small>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <section className="grid gap-5 pb-8 lg:grid-cols-[1fr_0.9fr]">
          <div className="panel">
            <div className="panel-title">
              <div>
                <p>排行榜</p>
                <h3>最新 Agent 分数</h3>
              </div>
              <span className="badge">实时 JSON</span>
            </div>
            <div className="table">
              {leaderboard.map((run) => (
                <div className="table-row" key={`${run.Rank}-${run.Agent}-${run.Task}`}>
                  <span className="rank">#{run.Rank}</span>
                  <strong>{run.Agent}</strong>
                  <span>{run.Type}</span>
                  <span>{run.Tests}</span>
                  <span>{run.Diff} 行</span>
                  <b>{run.Score}</b>
                </div>
              ))}
              {!leaderboard.length && <p className="empty">还没有运行记录。开始一次评测后这里会显示结果。</p>}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">
              <div>
                <p>运行日志</p>
                <h3>评测事件流</h3>
              </div>
              <span className="badge blue">Worktree</span>
            </div>
            <div className="terminal">
              {logs.map((line, index) => (
                <p key={`${line}-${index}`}>{line}</p>
              ))}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
