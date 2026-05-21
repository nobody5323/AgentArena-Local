# AgentArena 中文 Web GUI

AgentArena Local 的中文 Web GUI，提供任务选择、Agent 选择、Cursor GUI 启动、排行榜、报告和运行日志。

## Run

```powershell
npm install
agentarena gui
```

Open:

```text
http://127.0.0.1:5173
```

The FastAPI backend runs at:

```text
http://127.0.0.1:8765
```

For frontend-only development, run `npm run dev` from the repository root or
`npm run dev` inside `web/`, then start the API separately with:

```powershell
python -m uvicorn agentarena_local.web_api:app --host 127.0.0.1 --port 8765
```

## Build

```powershell
cd web
npm run build
```

## Lightswind

This UI imports `lightswind/styles.css` and follows the Lightswind copy-paste
component workflow documented in `../docs/lightswind-anime-web-gui.md`.
