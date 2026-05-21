from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskType(StrEnum):
    planning = "planning"
    debug = "debug"
    generation = "generation"


class TestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=300, ge=1)


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    description: str | None = None


class TaskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    type: TaskType
    repo: str = Field(
        ...,
        min_length=1,
        description="Local path or Git URL for the repository under evaluation.",
    )
    description: str = Field(..., min_length=1)
    instructions: str = Field(..., min_length=1)
    success_criteria: list[str] = Field(default_factory=list)
    test_commands: list[TestCommand] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("success_criteria")
    @classmethod
    def require_success_criteria(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("success_criteria must contain at least one item")
        return value


def load_task(path: Path) -> TaskConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"{path} is empty")
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return TaskConfig.model_validate(raw)
