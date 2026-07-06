"""Staging CLI smoke tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_preflight_cli_help():
    proc = subprocess.run(
        [sys.executable, str(BACKEND / "scripts/factor_discovery_staging_preflight.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "preflight" in proc.stdout.lower()


def test_audit_cli_json(isolated_backend_env, tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "FACTOR_RESEARCH_SNAPSHOT_ROOT", str(tmp_path), raising=False)
    proc = subprocess.run(
        [sys.executable, str(BACKEND / "scripts/factor_discovery_audit.py"), "--json", "--allow-test"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(BACKEND),
    )
    assert proc.returncode in (0, 1)
    assert "artifact_hash" in proc.stdout or "status" in proc.stdout
