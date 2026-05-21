from agentarena_local.gui.app import AGENTS, launch_gui


def test_gui_smoke_imports_without_pyside_import_side_effects() -> None:
    assert callable(launch_gui)
    assert {"claude", "codex", "manual", "cursor", "cline", "windsurf"}.issubset(AGENTS)
