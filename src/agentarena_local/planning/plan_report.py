from __future__ import annotations

import json
from pathlib import Path

from agentarena_local.planning.plan_scorer import PlanningScore


def save_planning_result(
    output_dir: Path,
    *,
    plan_file: str,
    score: PlanningScore,
    failures: list[str],
) -> Path:
    result_path = output_dir / "planning_result.json"
    result_path.write_text(
        json.dumps(
            {
                "plan_file": plan_file,
                "score": score.to_dict(),
                "failures": failures,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return result_path
