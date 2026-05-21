from __future__ import annotations

import json
from pathlib import Path


ABTEST_COLUMNS = ["Rank", "Variant", "Agent", "Task", "Score", "Tests", "Files", "Diff", "Violations", "Time", "Failures"]


def save_abtest_outputs(output_dir: Path, rows: list[list[str]], results: list[dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = [dict(zip(ABTEST_COLUMNS, row, strict=True)) for row in rows]
    (output_dir / "abtest_leaderboard.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_lines = ["# AGENTS.md A/B Test Leaderboard", "", "|" + "|".join(ABTEST_COLUMNS) + "|", "|" + "|".join(["---"] * len(ABTEST_COLUMNS)) + "|"]
    for row in rows:
        md_lines.append("|" + "|".join(row) + "|")
    (output_dir / "abtest_leaderboard.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    html_rows = "\n".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    (output_dir / "abtest_report.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>AgentArena A/B Test</title>
<style>body{{font-family:Arial,sans-serif;margin:32px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}th{{background:#f3f4f6}}</style>
</head><body><h1>AGENTS.md A/B Test</h1><table><thead><tr>{''.join(f'<th>{col}</th>' for col in ABTEST_COLUMNS)}</tr></thead><tbody>{html_rows}</tbody></table></body></html>""",
        encoding="utf-8",
    )
