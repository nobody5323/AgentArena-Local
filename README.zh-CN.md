# AgentArena Local

[English](README.md) | [简体中文](README.zh-CN.md)

AgentArena Local 是一个本地 AI 编程 Agent 评测平台。它可以在你自己的 Git
仓库里为每个 Agent 创建隔离的 worktree，收集代码 diff，运行测试，检查约束，
计算分数，并生成排行榜、报告和仪表盘。

## 功能特性

- 支持多种 Agent：Claude、Codex、Gemini、Aider、Manual、Cursor、Cline、Windsurf
- 支持 Debug、Planning、Feature Slice Generation 等任务类型
- 每次运行都使用独立 Git worktree，避免污染主工作区
- 使用 Pydantic 校验 `task.yaml`
- 支持 setup/test 命令执行和日志保存
- 统计 diff、约束、失败原因和综合评分
- 支持 AGENTS.md A/B 测试
- CLI 排行榜和历史运行浏览
- 静态 HTML 报告和 Plotly.js 仪表盘
- 中文 Web GUI：React、Vite、Lightswind UI、FastAPI 后端
- 支持从 Web GUI 打开 Cursor GUI worktree
- 支持 Windows EXE 构建脚本

## 安装

```powershell
pip install -e ".[dev]"
```

建议使用 Python 3.11+。如果要使用 Web GUI，还需要 Node.js 18+。

## 快速开始

```powershell
agentarena init
agentarena validate examples/python_debug_login/task.yaml
agentarena run --agents claude,codex,manual --task examples/python_debug_login/task.yaml
agentarena leaderboard
agentarena report --format html
agentarena dashboard
```

运行结果保存在 `.agentarena/runs/`，报告保存在 `.agentarena/reports/`。

## Web GUI 使用

```powershell
agentarena gui
```

然后打开：

```text
http://127.0.0.1:5173
```

这个命令会同时启动：

- FastAPI 后端：`http://127.0.0.1:8765`
- Vite Web GUI：`http://127.0.0.1:5173`

v0.5 的 Web GUI 使用中文界面，可以选择任务、选择 Agent、启动评测、查看实时日志、
刷新排行榜、生成报告和仪表盘，也可以一键打开 Cursor GUI worktree。

## Codex 与 Claude 对比

```powershell
agentarena run --agents claude,codex --task examples/python_debug_login/task.yaml
agentarena leaderboard --type debug
```

## Cursor / Cline / Windsurf 手动模式

这些工具更像 IDE 或插件，不一定适合直接在后台命令行中自动运行。

Cursor 已经在 Web GUI 中提供了 `打开 Cursor` 按钮。点击后，AgentArena 会创建隔离
worktree，写入 `AGENTARENA_TASK.md`，并用 Cursor 打开该目录。

CLI 手动模式示例：

```powershell
agentarena run --agent cursor --task examples/python_feature_todo_filter/task.yaml --keep-worktree
agentarena run --agent cline --task examples/python_feature_todo_filter/task.yaml --keep-worktree
agentarena run --agent windsurf --task examples/python_feature_todo_filter/task.yaml --keep-worktree
```

## Planning 评测

Planning 任务通常不应该修改代码。AgentArena 会把 Agent 输出保存为 `plan.md`，
按关键词覆盖率、测试计划、风险说明等维度评分，并记录是否发生代码修改。

```powershell
agentarena run --agents claude,codex --task examples/planning_student_filter/task.yaml
agentarena leaderboard --type planning
```

## Debug 评测

Debug 任务用于修复已有缺陷，并通过测试和约束验证修复质量。

```powershell
agentarena run --agents claude,codex,manual --task examples/python_debug_login/task.yaml
```

## Feature Slice Generation

Generation 任务用于实现一个小功能切片。你可以在 `task.yaml` 中配置
`expected_files_may_change` 和 `feature_checks`，用于检查功能完成度和文件变更范围。

```powershell
agentarena run --agents claude,codex --task examples/python_feature_todo_filter/task.yaml
agentarena leaderboard --type generation
```

## AGENTS.md A/B 测试

```powershell
agentarena abtest --agents claude,codex --task examples/agents_md_abtest/task.yaml --variants examples/agents_md_abtest/variants
agentarena leaderboard --type abtest
```

每个变体目录都需要包含一个 `AGENTS.md` 文件：

```text
variants/
  no_agents/AGENTS.md
  simple/AGENTS.md
  strict/AGENTS.md
```

## 排行榜

```powershell
agentarena leaderboard
agentarena leaderboard --type debug
agentarena leaderboard --type generation
agentarena leaderboard --type planning
agentarena leaderboard --type abtest
agentarena leaderboard --overall
```

## 报告与仪表盘

```powershell
agentarena report --format html
agentarena dashboard
```

报告和仪表盘会展示总分、任务类型对比、通过率、失败原因分布、AGENTS.md 变体对比、
diff 与得分关系等信息。

## 历史运行

```powershell
agentarena runs
agentarena runs --latest
agentarena show <run_id>
```

## 构建 EXE

```powershell
python scripts/build_exe.py
```

预期产物：

- `dist/AgentArena.exe`

## 发布检查

```powershell
python scripts/release.py
```

发布脚本会运行 pytest，检查 README、examples、pyproject，并尝试构建 wheel。

## 路线图

- 支持更多 Agent
- 增强任务 schema 和评分预设
- 可选 sandbox 后端
- 更丰富的报告对比视图
- 评测任务包导入/导出
