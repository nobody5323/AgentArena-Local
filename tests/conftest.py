from __future__ import annotations

import os
from pathlib import Path


def pytest_configure(config) -> None:
    if config.option.basetemp is not None:
        return
    root = Path(str(config.rootpath))
    parent = root / ".agentarena_pytest_tmp"
    parent.mkdir(exist_ok=True)
    config.option.basetemp = str(parent / str(os.getpid()))
