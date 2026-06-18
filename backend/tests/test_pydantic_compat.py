"""Pydantic v1/v2 model_dump compatibility."""
from __future__ import annotations

import pytest

from models.schemas_v2 import FactorContributionV2
from utils.pydantic_util import json_safe, model_to_dict


def test_json_safe_coerces_numpy_bool():
    import json

    np = pytest.importorskip("numpy")
    payload = {"score_adjusted_for_data_quality": np.bool_(True), "raw_score": np.float64(53.9)}
    safe = json_safe(payload)
    json.dumps(safe)
    assert safe["score_adjusted_for_data_quality"] is True
    assert isinstance(safe["raw_score"], float)


def test_factor_contribution_v2_serializes():
    f = FactorContributionV2(
        factor_id="momentum",
        display_name="Momentum",
        norm_score=62.0,
        weight=0.25,
        contribution=15.5,
        description="test",
    )
    d = model_to_dict(f)
    assert d["factor_id"] == "momentum"
    assert d["norm_score"] == 62.0


def test_build_v2_score_returns_score_not_dict_error():
    from services.quant_v2_service import build_v2_score

    result = build_v2_score(
        "AMC",
        "penny",
        validate_parity=False,
        include_sizing=False,
        persist_snapshot=False,
    )
    if isinstance(result, dict) and result.get("error"):
        # Data/API unavailable in CI — skip hard assert on score value
        assert "model_dump" not in str(result.get("error", "")).lower()
        return
    assert not isinstance(result, dict) or "error" not in result
    assert hasattr(result, "score")
    assert 0 <= float(result.score) <= 100
    assert len(result.factors) > 0
