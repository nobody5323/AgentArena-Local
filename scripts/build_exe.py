from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "AgentArena",
        "src/agentarena_local/__main__.py",
    ]
    print("Running:", " ".join(command))
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
