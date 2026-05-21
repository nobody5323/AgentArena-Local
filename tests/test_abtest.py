from pathlib import Path

from agentarena_local.abtest.experiment import save_abtest_outputs
from agentarena_local.abtest.variant import load_variants


def test_abtest_reads_variants(tmp_path: Path) -> None:
    for name in ("no_agents", "simple", "strict"):
        variant = tmp_path / name
        variant.mkdir()
        (variant / "AGENTS.md").write_text(f"# {name}\n", encoding="utf-8")

    variants = load_variants(tmp_path)

    assert [variant.name for variant in variants] == ["no_agents", "simple", "strict"]


def test_abtest_generates_leaderboard(tmp_path: Path) -> None:
    rows = [["1", "simple", "codex", "task", "90", "True", "1", "5", "0", "1.0s", ""]]

    save_abtest_outputs(tmp_path, rows, [])

    assert (tmp_path / "abtest_leaderboard.json").exists()
    assert (tmp_path / "abtest_leaderboard.md").exists()
    assert (tmp_path / "abtest_report.html").exists()
