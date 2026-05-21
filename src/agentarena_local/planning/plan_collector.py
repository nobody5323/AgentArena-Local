from __future__ import annotations

from pathlib import Path


def save_plan(output_dir: Path, output_file: str, content: str) -> Path:
    plan_path = output_dir / output_file
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(content, encoding="utf-8")
    return plan_path
