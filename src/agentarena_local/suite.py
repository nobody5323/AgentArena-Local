from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SuiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    tasks: list[str] = Field(..., min_length=1)
    tries: int = Field(default=1, ge=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


@dataclass(frozen=True)
class SuiteStats:
    agent: str
    tasks: int
    attempts: int
    pass_at_1: float
    pass_at_k: float
    avg_score: float
    median_score: float
    hidden_pass_rate: float | None
    regression_pass_rate: float | None
    timeout_rate: float
    avg_duration: float
    unique_wins: int
    failure_distribution: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_suite(path: Path) -> SuiteConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"{path} is empty")
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return SuiteConfig.model_validate(raw)


def append_jsonl(path: Path, item: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def completed_keys(rows: list[dict[str, object]]) -> set[tuple[str, str, int]]:
    keys: set[tuple[str, str, int]] = set()
    for row in rows:
        task = row.get("task", {})
        task_id = task.get("id", "") if isinstance(task, dict) else ""
        keys.add((str(row.get("agent", "")), str(task_id), int(row.get("try_index", 1))))
    return keys


def _resolved(result: dict[str, object]) -> bool:
    strict = result.get("strict")
    if isinstance(strict, dict) and strict.get("enabled"):
        return strict.get("resolved") is True
    return result.get("tests_passed") is True


def _strict_bool(result: dict[str, object], key: str) -> bool | None:
    strict = result.get("strict")
    if not isinstance(strict, dict) or not strict.get("enabled"):
        return None
    value = strict.get(key)
    return value if isinstance(value, bool) else None


def _rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def summarize_suite(rows: list[dict[str, object]]) -> list[SuiteStats]:
    by_agent: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_agent.setdefault(str(row.get("agent", "")), []).append(row)

    task_agent_resolved: dict[str, set[str]] = {}
    for row in rows:
        task = row.get("task", {})
        task_id = str(task.get("id", "")) if isinstance(task, dict) else ""
        if _resolved(row):
            task_agent_resolved.setdefault(task_id, set()).add(str(row.get("agent", "")))

    stats: list[SuiteStats] = []
    for agent, agent_rows in by_agent.items():
        by_task: dict[str, list[dict[str, object]]] = {}
        for row in agent_rows:
            task = row.get("task", {})
            task_id = str(task.get("id", "")) if isinstance(task, dict) else ""
            by_task.setdefault(task_id, []).append(row)

        first_resolved = 0
        any_resolved = 0
        unique_wins = 0
        for task_id, task_rows in by_task.items():
            ordered = sorted(task_rows, key=lambda item: int(item.get("try_index", 1)))
            if ordered and _resolved(ordered[0]):
                first_resolved += 1
            if any(_resolved(row) for row in ordered):
                any_resolved += 1
            if agent in task_agent_resolved.get(task_id, set()) and len(task_agent_resolved.get(task_id, set())) == 1:
                unique_wins += 1

        scores = [float(row.get("score", 0)) for row in agent_rows]
        durations = [float(row.get("duration_seconds", 0.0)) for row in agent_rows]
        hidden_values = [
            value
            for value in (_strict_bool(row, "hidden_passed") for row in agent_rows)
            if value is not None
        ]
        regression_values = [
            value
            for value in (_strict_bool(row, "pass_to_pass_passed") for row in agent_rows)
            if value is not None
        ]
        timeout_count = sum(1 for row in agent_rows if int(row.get("agent_exit_code", 0)) == 124)
        failures: dict[str, int] = {}
        for row in agent_rows:
            for failure in row.get("failures", []):
                failures[str(failure)] = failures.get(str(failure), 0) + 1

        task_count = len(by_task)
        stats.append(
            SuiteStats(
                agent=agent,
                tasks=task_count,
                attempts=len(agent_rows),
                pass_at_1=first_resolved / task_count if task_count else 0.0,
                pass_at_k=any_resolved / task_count if task_count else 0.0,
                avg_score=sum(scores) / len(scores) if scores else 0.0,
                median_score=_median(scores),
                hidden_pass_rate=_rate(hidden_values),
                regression_pass_rate=_rate(regression_values),
                timeout_rate=timeout_count / len(agent_rows) if agent_rows else 0.0,
                avg_duration=sum(durations) / len(durations) if durations else 0.0,
                unique_wins=unique_wins,
                failure_distribution=dict(sorted(failures.items())),
            )
        )

    return sorted(stats, key=lambda item: (item.pass_at_k, item.avg_score), reverse=True)

