"""Symbol identity tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.symbol_identity import normalize_symbol, symbol_mapping_hash, validate_symbol


def test_normalize_share_class():
    assert normalize_symbol("brk.b") == "BRK-B"


def test_validate_invalid_symbol():
    ok, err = validate_symbol("")
    assert ok is False


def test_mapping_hash_deterministic():
    h1 = symbol_mapping_hash(["AAA", "BBB"])
    h2 = symbol_mapping_hash(["BBB", "AAA"])
    assert h1 == h2
