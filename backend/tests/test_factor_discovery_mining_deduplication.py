"""Deduplication tests for mining sessions."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.factor.discovery.parser import parse_factor_expression
from services.factor_discovery.mining.deduplication import MiningDeduplicationService, structural_fingerprint


def test_structural_fingerprint_stable():
    ast = parse_factor_expression("rank(return_126d)")
    fp1 = structural_fingerprint(ast)
    fp2 = structural_fingerprint(ast)
    assert fp1 == fp2


def test_duplicate_check_not_found():
    result = MiningDeduplicationService().check_formula_hash(
        session_id="missing",
        lineage_id="missing",
        formula_hash_value="sha256:abc",
    )
    assert result.is_duplicate is False
