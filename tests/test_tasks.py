from pathlib import Path

import pytest
from pydantic import ValidationError

from agentarena_local.tasks import TaskConfig, TaskType, load_task


def test_load_task_parses_debug_example() -> None:
    task = load_task(Path("examples/python_debug_login/task.yaml"))

    assert task.type is TaskType.debug
    assert task.test_commands[0].command == "pytest examples/python_debug_login/repo/tests"


def test_task_requires_success_criteria() -> None:
    with pytest.raises(ValidationError):
        TaskConfig.model_validate(
            {
                "id": "missing-criteria",
                "title": "Missing criteria",
                "type": "planning",
                "repo": ".",
                "description": "A planning task.",
                "instructions": "Write a plan.",
                "success_criteria": [],
            }
        )


def test_task_supports_all_v0_1_types() -> None:
    for task_type in ("planning", "debug", "generation"):
        task = TaskConfig.model_validate(
            {
                "id": f"{task_type}-task",
                "title": f"{task_type.title()} task",
                "type": task_type,
                "repo": ".",
                "description": "Description.",
                "instructions": "Instructions.",
                "success_criteria": ["Criterion."],
            }
        )
        assert task.type.value == task_type


def test_task_supports_lightweight_swe_command_groups() -> None:
    task = TaskConfig.model_validate(
        {
            "id": "strict-task",
            "title": "Strict task",
            "type": "generation",
            "repo": ".",
            "description": "Description.",
            "instructions": "Instructions.",
            "success_criteria": ["Criterion."],
            "baseline": {
                "commands": [
                    {
                        "name": "bug-repro-before",
                        "command": "pytest tests/test_bug.py",
                    }
                ]
            },
            "fail_to_pass": {
                "commands": [
                    {
                        "name": "bug-repro-after",
                        "command": "pytest tests/test_bug.py",
                    }
                ]
            },
            "pass_to_pass": {
                "commands": [
                    {
                        "name": "regression",
                        "command": "pytest tests/test_existing.py",
                    }
                ]
            },
            "hidden": {
                "commands": [
                    {
                        "name": "hidden",
                        "command": "pytest tests_hidden",
                    }
                ]
            },
        }
    )

    assert task.has_strict_evaluation() is True
    assert task.baseline_commands()[0].name == "bug-repro-before"
    assert task.fail_to_pass_commands()[0].command == "pytest tests/test_bug.py"
    assert task.pass_to_pass_commands()[0].name == "regression"
    assert task.hidden_commands()[0].name == "hidden"
