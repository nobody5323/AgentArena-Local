from __future__ import annotations

import subprocess
import sys
import zipfile
from importlib.util import find_spec
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_README_SECTIONS = [
    "Features",
    "Installation",
    "Quick Start",
    "Claude vs Codex",
    "GUI Usage",
    "Build EXE",
    "Roadmap",
]
EXAMPLES = [
    "python_debug_login",
    "python_feature_todo_filter",
    "planning_student_filter",
    "agents_md_abtest",
]


def run(command: list[str]) -> bool:
    print("$", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode == 0


def check_readme() -> bool:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [section for section in REQUIRED_README_SECTIONS if section not in readme]
    if missing:
        print("README missing sections:", ", ".join(missing))
        return False
    return True


def check_examples() -> bool:
    ok = True
    for example in EXAMPLES:
        root = ROOT / "examples" / example
        for name in ("README.md", "task.yaml", "repo"):
            if not (root / name).exists():
                print(f"Missing examples/{example}/{name}")
                ok = False
    return ok


def check_pyproject() -> bool:
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    required = ["agentarena-local", "typer", "PySide6", "agentarena ="]
    missing = [item for item in required if item not in text]
    if missing:
        print("pyproject missing:", ", ".join(missing))
        return False
    return True


def build_wheel() -> bool:
    if find_spec("build") is None or find_spec("hatchling") is None:
        print("build/hatchling is not installed; creating offline pure-Python wheel fallback")
        return build_offline_wheel()
    if run([sys.executable, "-m", "build", "--wheel"]):
        return True
    print("python -m build failed; trying pip wheel fallback")
    if run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", "dist"]):
        return True
    print("pip wheel failed; creating offline pure-Python wheel fallback")
    return build_offline_wheel()


def build_offline_wheel() -> bool:
    name = "agentarena_local"
    version = "0.4.0"
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    wheel_path = dist_dir / f"{name}-{version}-py3-none-any.whl"
    dist_info = f"{name}-{version}.dist-info"
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for package_root in (ROOT / "src" / "agentarena_local", ROOT / "src" / "agentarena"):
            for path in package_root.rglob("*"):
                if path.is_file():
                    wheel.write(path, path.relative_to(ROOT / "src").as_posix())
        wheel.writestr(
            f"{dist_info}/METADATA",
            "\n".join(
                [
                    "Metadata-Version: 2.1",
                    "Name: agentarena-local",
                    f"Version: {version}",
                    "Summary: Local benchmark platform for AI coding agents.",
                    "Requires-Python: >=3.11",
                    "",
                ]
            ),
        )
        wheel.writestr(
            f"{dist_info}/WHEEL",
            "\n".join(
                [
                    "Wheel-Version: 1.0",
                    "Generator: AgentArena Local release.py",
                    "Root-Is-Purelib: true",
                    "Tag: py3-none-any",
                    "",
                ]
            ),
        )
        wheel.writestr(
            f"{dist_info}/entry_points.txt",
            "[console_scripts]\nagentarena=agentarena_local.cli:app\n",
        )
        wheel.writestr(f"{dist_info}/RECORD", "")
    print(f"Created {wheel_path}")
    return wheel_path.exists()


def main() -> int:
    checks = [
        ("pytest", run([sys.executable, "-m", "pytest", "--basetemp=.release_pytest_tmp"])),
        ("README", check_readme()),
        ("examples", check_examples()),
        ("pyproject.toml", check_pyproject()),
        ("wheel", build_wheel()),
    ]
    print("\nRelease checklist")
    for name, ok in checks:
        print(f"- [{'x' if ok else ' '}] {name}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
