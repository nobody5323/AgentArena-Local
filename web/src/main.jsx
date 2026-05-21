import React from "react";
import { createRoot } from "react-dom/client";
import "./vendor/lightswind.css";
import "./styles.css";

const agents = ["Claude", "Codex", "Gemini", "Aider", "Manual", "Cursor", "Cline", "Windsurf"];

const runs = [
  { rank: 1, agent: "Codex", task: "python-debug-login", type: "Debug", score: 92, tests: "pass", diff: 38 },
  { rank: 2, agent: "Claude", task: "todo-filter", type: "Generation", score: 88, tests: "pass", diff: 52 },
  { rank: 3, agent: "Cursor", task: "student-filter-plan", type: "Planning", score: 81, tests: "n/a", diff: 0 },
];

function App() {
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
              <h1 className="text-xl font-black tracking-tight">Anime Web Benchmark Console</h1>
            </div>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            <span className="pill">Runs</span>
            <span className="pill">Leaderboard</span>
            <span className="pill">Reports</span>
          </div>
        </nav>

        <div className="grid flex-1 gap-6 py-8 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="flex flex-col justify-center">
            <div className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-pink-200 bg-white/80 px-4 py-2 text-sm font-bold text-pink-500 shadow-sm">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_18px_#34d399]" />
              Light mode, fast reads, soft anime energy
            </div>
            <h2 className="max-w-3xl text-5xl font-black leading-tight tracking-tight md:text-7xl">
              Compare coding agents in a bright little command room.
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
              Pick a task, choose agents, run isolated Git worktrees, then browse scores,
              failures, diffs, planning output, and AGENTS.md variants.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button className="shine-btn">Run Benchmark</button>
              <button className="soft-btn">Open Dashboard</button>
              <button className="soft-btn">A/B Test</button>
            </div>
          </section>

          <section className="relative">
            <div className="mascot-card">
              <div className="orb orb-one" />
              <div className="orb orb-two" />
              <div className="relative z-10">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-black uppercase tracking-[0.18em] text-pink-500">Benchmark Setup</p>
                    <h3 className="mt-2 text-3xl font-black">Mission Control</h3>
                  </div>
                  <div className="rounded-2xl bg-emerald-100 px-3 py-2 text-sm font-black text-emerald-600">
                    Ready
                  </div>
                </div>

                <div className="mt-6 grid gap-4">
                  <label className="field">
                    <span>Project Directory</span>
                    <input value="C:/Users/.../AgentArena Local" readOnly />
                  </label>
                  <label className="field">
                    <span>Task YAML</span>
                    <input value="examples/python_debug_login/task.yaml" readOnly />
                  </label>
                  <div className="agent-grid">
                    {agents.map((agent) => (
                      <button key={agent} className={agent === "Codex" || agent === "Claude" ? "agent active" : "agent"}>
                        {agent}
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
                <p>Leaderboard</p>
                <h3>Latest Agent Scores</h3>
              </div>
              <span className="badge">Live JSON</span>
            </div>
            <div className="table">
              {runs.map((run) => (
                <div className="table-row" key={run.rank}>
                  <span className="rank">#{run.rank}</span>
                  <strong>{run.agent}</strong>
                  <span>{run.type}</span>
                  <span>{run.tests}</span>
                  <span>{run.diff} lines</span>
                  <b>{run.score}</b>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">
              <div>
                <p>Run Log</p>
                <h3>Evaluation Stream</h3>
              </div>
              <span className="badge blue">Worktree</span>
            </div>
            <div className="terminal">
              <p>$ agentarena run --agents claude,codex --task examples/python_debug_login/task.yaml</p>
              <p>created worktree .agentarena/worktrees/run_codex</p>
              <p>tests: passed | constraints: passed | score: 92</p>
              <p>report saved .agentarena/reports/latest-report.html</p>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
