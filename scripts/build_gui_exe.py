from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "AgentArenaGUI",
        "scripts/gui_entry.py",
    ]
    print("Running:", " ".join(command))
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
