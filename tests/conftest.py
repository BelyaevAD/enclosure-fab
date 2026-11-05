from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ZONE = Path(__file__).resolve().parents[1]
if str(ZONE) not in sys.path:
    sys.path.insert(0, str(ZONE))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    session.config.stash[_EXIT] = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: pytest.Config) -> None:
    # VTK/OCP teardown can crash CPython on Windows after a clean run; keep pytest's own exit code.
    if sys.platform == "win32" and _EXIT in config.stash:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(config.stash[_EXIT])


_EXIT = pytest.StashKey[int]()
