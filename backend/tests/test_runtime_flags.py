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


if __name__ == "__main__":
    test_runtime_override_persists()
    print("runtime_flags tests passed")
