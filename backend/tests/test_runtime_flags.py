"""Tests for runtime API toggle overrides."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.runtime_flags import RuntimeFlagRegistry


def test_runtime_override_persists():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runtime_settings.json"
        reg = RuntimeFlagRegistry(path)
        flag = reg.register("OPENBB_ENABLED", "false")
        assert not flag
        flag.set(True)
        assert flag
        assert path.exists()
        raw = json.loads(path.read_text())
        assert raw["OPENBB_ENABLED"] is True

        reg2 = RuntimeFlagRegistry(path)
        reg2.register("OPENBB_ENABLED", "false")
        assert reg2.effective("OPENBB_ENABLED") is True

        flag.set(False)
        assert "OPENBB_ENABLED" not in json.loads(path.read_text())


def test_env_overlay_does_not_rewrite_shipped_default():
    """Process env must not become registry default — reset restores shipped off."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runtime_settings.json"
        reg = RuntimeFlagRegistry(path)
        flag = reg.register("FACTOR_DISCOVERY_LLM_ENABLED", "false")
        reg.apply_env("FACTOR_DISCOVERY_LLM_ENABLED", True)
        assert flag
        assert reg.default_for("FACTOR_DISCOVERY_LLM_ENABLED") is False
        assert reg.is_overridden("FACTOR_DISCOVERY_LLM_ENABLED") is True
        if path.exists():
            assert "FACTOR_DISCOVERY_LLM_ENABLED" not in json.loads(path.read_text())

        reg.reset()
        assert not flag
        assert reg.default_for("FACTOR_DISCOVERY_LLM_ENABLED") is False


def test_settings_disable_masks_env_overlay():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runtime_settings.json"
        reg = RuntimeFlagRegistry(path)
        flag = reg.register("FACTOR_DISCOVERY_LOOP_ENABLED", "false")
        reg.apply_env("FACTOR_DISCOVERY_LOOP_ENABLED", True)
        assert flag
        flag.set(False)
        assert not flag
        assert json.loads(path.read_text())["FACTOR_DISCOVERY_LOOP_ENABLED"] is False


if __name__ == "__main__":
    test_runtime_override_persists()
    test_env_overlay_does_not_rewrite_shipped_default()
    test_settings_disable_masks_env_overlay()
    print("runtime_flags tests passed")
