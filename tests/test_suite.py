from agentarena_local.suite import completed_keys, summarize_suite


def test_suite_summary_computes_pass_at_k_and_unique_wins() -> None:
    rows = [
        {
            "agent": "codex",
            "try_index": 1,
            "task": {"id": "task-a"},
            "score": 75,
            "duration_seconds": 10,
            "agent_exit_code": 0,
            "strict": {"enabled": True, "resolved": True, "hidden_passed": True, "pass_to_pass_passed": True},
            "failures": [],
        },
        {
            "agent": "claude",
            "try_index": 1,
            "task": {"id": "task-a"},
            "score": 30,
            "duration_seconds": 20,
            "agent_exit_code": 124,
            "strict": {"enabled": True, "resolved": False, "hidden_passed": False, "pass_to_pass_passed": True},
            "failures": ["agent_timeout"],
        },
    ]

    stats = {stat.agent: stat for stat in summarize_suite(rows)}

    assert stats["codex"].pass_at_1 == 1.0
    assert stats["codex"].unique_wins == 1
    assert stats["claude"].timeout_rate == 1.0
    assert stats["claude"].failure_distribution == {"agent_timeout": 1}


def test_completed_keys_include_agent_task_try() -> None:
    keys = completed_keys([
        {"agent": "codex", "task": {"id": "task-a"}, "try_index": 2}
    ])

    assert ("codex", "task-a", 2) in keys

