# Lightswind Anime Web GUI Usage

Lightswind UI is a React + Tailwind copy-paste component library, not a native
Codex skill. In this project we use it as the Web GUI style/component source for
an anime-inspired AgentArena interface.

## Installed Package

```powershell
npm install lightswind
```

Current package:

```text
lightswind@^3.1.28
```

Useful commands:

```powershell
npx lightswind list
npx lightswind init
npx lightswind add form
npx lightswind add input
npx lightswind add textarea
npx lightswind add button
npx lightswind add card
npx lightswind add tabs
npx lightswind add table
npx lightswind add dialog
npx lightswind add toast
npx lightswind add aurora-background
npx lightswind add typewriter-input
npx lightswind add magic-card
npx lightswind add sparkle-particles
```

## Recommended Web GUI Stack

Use this stack when replacing the desktop GUI:

```text
Vite + React + TypeScript + Tailwind CSS + Lightswind UI
```

For charts, keep using static Plotly output from AgentArena reports or add a
frontend chart library later.

## AgentArena Web GUI Pages

Build these pages first:

- Runs: list historical `.agentarena/runs`
- Run Detail: show result JSON, logs, diff links, plan links
- Benchmark: choose task YAML, agents, timeout, keep worktree
- A/B Test: choose variants directory and agents
- Leaderboard: score table and filters by task type
- Reports: open latest report and dashboard

## Anime Style Rules

Keep the style "anime dashboard", not toy-like:

- Use a clean dark base with controlled accent colors.
- Use animated accents for focus states, active tabs, and hero panels.
- Use character/mascot imagery only as optional side art, never as the main UI.
- Keep tables dense and readable.
- Use cards for repeated result items only, not nested layout decoration.
- Avoid visual overload: no more than one animated background per page.

Suggested Lightswind components:

- Layout: `card`, `tabs`, `sidebar`, `dialog`, `sheet`
- Forms: `form`, `input`, `textarea`, `select`, `checkbox`, `switch`, `button`
- Feedback: `toast`, `alert`, `progress`, `skeleton`
- Anime/futuristic accents: `aurora-background`, `magic-card`, `sparkle-particles`,
  `typewriter-input`, `border-beam`, `shine-button`
- Data: `table`, `badge`, `tooltip`

## Workflow For Codex

When asked to build the Web GUI:

1. Create a frontend app under `web/`.
2. Install React/Vite/Tailwind if missing.
3. Run `npx lightswind init` inside `web/`.
4. Add only the components needed for the current screen.
5. Implement the UI against the existing AgentArena CLI/result files first.
6. Keep Python evaluation logic in `src/agentarena_local`; do not duplicate runner logic in React.
7. Verify with tests and a browser screenshot.

## Important Notes

Lightswind's README says it is a copy-paste library like shadcn/ui. Prefer:

```powershell
npx lightswind add <component>
```

over importing every component directly from the package. This keeps the Web GUI
customizable and avoids coupling the app to a black-box component bundle.
