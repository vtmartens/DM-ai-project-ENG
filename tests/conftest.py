"""Shared pytest fixtures.

The runtime resolves paths in two ways: ``util.config`` anchors them to the
repository root, while a few modules (``Player``, ``Enemy``, ``main``) open
``data/*.json`` relative to the current working directory. Tests therefore run
from the repository root, and the save/backup/session directories are
redirected into ``tmp_path`` so a test run never touches a developer's saves.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def run_from_repository_root(monkeypatch):
    monkeypatch.chdir(ROOT)


@pytest.fixture(autouse=True)
def disable_ai_narration(monkeypatch):
    """Tests must never make real model calls, even on a developer's machine."""
    for name in (
        "DM_AI_NARRATION",
        "DM_AI_PROVIDER",
        "DM_AI_MODEL",
        "DM_AI_MAX_TOKENS",
        "DM_AI_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def isolated_runtime_dirs(tmp_path, monkeypatch, run_from_repository_root):
    """Point every runtime directory at a throw-away location for this test."""
    import server
    import util.config as config

    dirs = {name: tmp_path / name for name in ("saves", "backup", "sessions")}
    for directory in dirs.values():
        directory.mkdir()

    for module in (config, server):
        monkeypatch.setattr(module, "SAVE_DIR", dirs["saves"])
        monkeypatch.setattr(module, "BACKUPS_DIR", dirs["backup"])
        monkeypatch.setattr(module, "SESSIONS_DIR", dirs["sessions"])

    return dirs


@pytest.fixture(autouse=True)
def clean_server_state(run_from_repository_root):
    """Keep the API's module-level session registries isolated per test."""
    import server

    server.active_sessions.clear()
    server.system_notifications.clear()
    yield
    server.active_sessions.clear()
    server.system_notifications.clear()


@pytest.fixture
def recording_io():
    from tests.helpers import RecordingIO

    return RecordingIO()
