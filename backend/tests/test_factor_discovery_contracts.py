"""Tests for Factor Discovery contracts (Phase 1) and disabled launch behavior."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_factor_discovery import (
    AstNode,
    BinaryNode,
    BinaryOperator,
    ConstantNode,
    CrossSectionNode,
    CrossSectionOperator,
    DiscoveryPeriodSplit,
    FactorDefinition,
    FactorDirection,
    FactorHypothesis,
    FactorLifecycleStatus,
    FieldNode,
    HypothesisSource,
    InputDataClass,
    NeutralizationKey,
    NeutralizeNode,
    ResearchPeriodRole,
    RollingNode,
    RollingOperator,
    UnaryNode,
    UnaryOperator,
    ZeroDivisionPolicy,
    can_transition_factor_status,
    collect_field_ids,
    formula_hash,
    validate_factor_status_transition,
)
from models.schemas_research import ExperimentValidateRequest, ResearchExperimentCreate
from services.experiment_job_service import stage_order_for_experiment
from services.experiment_validation_service import validate_experiment
from services.research_experiments_service import create_experiment

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "factor_discovery"
AST_ADAPTER = TypeAdapter(AstNode)


def _load_ast(name: str) -> AstNode:
    raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return AST_ADAPTER.validate_python(raw)


def _round_trip_ast(node: AstNode) -> AstNode:
    payload = json.loads(json.dumps(node.model_dump(mode="json"), sort_keys=True))
    return AST_ADAPTER.validate_python(payload)


@pytest.fixture
def research_db(isolated_backend_env):
    init_quant_db()
    return isolated_backend_env


@pytest.fixture
def client(research_db):
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


# --- Stage order ---


def test_stage_order_default_immutable():
    order = stage_order_for_experiment("walk_forward")
    assert order[0] == "validating"
    assert order[-1] == "complete"
    assert isinstance(order, tuple)


def test_stage_order_scan_evaluation():
    order = stage_order_for_experiment("scan_evaluation")
    assert "replaying_scans" in order
    assert "generating_charts" in order
    assert order[-1] == "complete"


# --- AST validation ---


def test_ast_field_node():
    node = FieldNode(field_id="close")
    assert collect_field_ids(node) == frozenset({"close"})


def test_ast_constant_rejects_non_finite():
    with pytest.raises(ValidationError):
        ConstantNode(value=float("nan"))


def test_ast_unary_requires_child():
    with pytest.raises(ValidationError):
        UnaryNode(op=UnaryOperator.ABS)  # type: ignore[call-arg]


def test_ast_binary_requires_two_children():
    with pytest.raises(ValidationError):
        BinaryNode(op=BinaryOperator.ADD, left=FieldNode(field_id="close"))  # type: ignore[call-arg]


def test_ast_rolling_window_positive():
    with pytest.raises(ValidationError):
        RollingNode(op=RollingOperator.LAG, window=0, child=FieldNode(field_id="close"))


def test_ast_rolling_correlation_requires_right_child():
    with pytest.raises(ValidationError):
        RollingNode(
            op=RollingOperator.ROLLING_CORRELATION,
            window=20,
            child=FieldNode(field_id="close"),
        )


def test_ast_rolling_correlation_rejects_extra_child_on_lag():
    with pytest.raises(ValidationError):
        RollingNode(
            op=RollingOperator.LAG,
            window=1,
            child=FieldNode(field_id="close"),
            right=FieldNode(field_id="volume"),
        )


def test_ast_rolling_correlation_accepts_two_children():
    node = RollingNode(
        op=RollingOperator.ROLLING_CORRELATION,
        window=20,
        child=FieldNode(field_id="return_1d"),
        right=FieldNode(field_id="relative_volume"),
    )
    assert "return_1d" in collect_field_ids(node)
    assert "relative_volume" in collect_field_ids(node)


def test_ast_unknown_kind_rejected():
    with pytest.raises(ValidationError):
        AST_ADAPTER.validate_python({"kind": "EVIL", "field_id": "close"})


def test_ast_extra_fields_rejected():
    with pytest.raises(ValidationError):
        FieldNode(field_id="close", evil=True)  # type: ignore[call-arg]


def test_ast_max_depth_enforced():
    child: AstNode = FieldNode(field_id="close")
    for _ in range(MAX_AST_DEPTH := 33):
        child = UnaryNode(op=UnaryOperator.ABS, child=child)
    with pytest.raises(ValueError, match="maximum depth"):
        formula_hash(child)


def test_golden_fixtures_round_trip():
    for name in (
        "simple_field_rank.json",
        "lagged_momentum.json",
        "safe_division_fcf_mcap.json",
        "sector_neutral_composite.json",
        "nested_rolling.json",
    ):
        original = _load_ast(name)
        again = _round_trip_ast(original)
        assert formula_hash(original) == formula_hash(again)


# --- Formula hash ---


def test_formula_hash_stable_across_key_order():
    a = _load_ast("simple_field_rank.json")
    shuffled = json.loads((FIXTURES / "simple_field_rank.json").read_text())
    b = AST_ADAPTER.validate_python(shuffled)
    assert formula_hash(a) == formula_hash(b)
    assert formula_hash(a).startswith("sha256:")


def test_formula_hash_ignores_metadata():
    expr = _load_ast("simple_field_rank.json")
    h1 = formula_hash(expr)
    def_a = FactorDefinition(
        factor_id="disc_test_a",
        version="1.0.0",
        display_name="Name A",
        expression=expr,
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="penny",
        rebalance_frequency="weekly",
        holding_period_sessions=5,
        lifecycle_status=FactorLifecycleStatus.DRAFT,
        notes="note a",
    )
    def_b = def_a.model_copy(
        update={
            "display_name": "Name B",
            "lifecycle_status": FactorLifecycleStatus.PROMISING,
            "notes": "note b",
        }
    )
    assert def_a.formula_hash() == def_b.formula_hash() == h1


def test_formula_hash_sensitive_to_operator_and_window():
    base = formula_hash(_load_ast("simple_field_rank.json"))
    other = formula_hash(_load_ast("nested_rolling.json"))
    assert base != other

    rank = CrossSectionNode(
        op=CrossSectionOperator.RANK,
        child=FieldNode(field_id="return_126d"),
    )
    pct = CrossSectionNode(
        op=CrossSectionOperator.PERCENTILE_RANK,
        child=FieldNode(field_id="return_126d"),
    )
    assert formula_hash(rank) != formula_hash(pct)

    div_null = BinaryNode(
        op=BinaryOperator.DIVIDE,
        left=FieldNode(field_id="free_cash_flow"),
        right=FieldNode(field_id="market_cap"),
        zero_policy=ZeroDivisionPolicy.NULL,
    )
    div_zero = div_null.model_copy(update={"zero_policy": ZeroDivisionPolicy.ZERO})
    assert formula_hash(div_null) != formula_hash(div_zero)


def test_formula_hash_winsorize_bounds_semantic():
    base = CrossSectionNode(
        op=CrossSectionOperator.WINSORIZE,
        child=FieldNode(field_id="return_126d"),
        winsorize_lower=0.01,
        winsorize_upper=0.99,
    )
    other = base.model_copy(update={"winsorize_lower": 0.05})
    assert formula_hash(base) != formula_hash(other)
    third = base.model_copy(update={"winsorize_upper": 0.95})
    assert formula_hash(base) != formula_hash(third)


def test_formula_hash_winsorize_defaults_match_explicit():
    implicit = CrossSectionNode(
        op=CrossSectionOperator.WINSORIZE,
        child=FieldNode(field_id="return_126d"),
    )
    explicit = CrossSectionNode(
        op=CrossSectionOperator.WINSORIZE,
        child=FieldNode(field_id="return_126d"),
        winsorize_lower=0.01,
        winsorize_upper=0.99,
    )
    assert formula_hash(implicit) == formula_hash(explicit)


def test_formula_hash_rank_ignores_winsorize_defaults():
    rank = CrossSectionNode(
        op=CrossSectionOperator.RANK,
        child=FieldNode(field_id="return_126d"),
    )
    rank_with_defaults = rank.model_copy(update={"winsorize_lower": 0.01, "winsorize_upper": 0.99})
    assert formula_hash(rank) == formula_hash(rank_with_defaults)


def test_golden_fixture_hashes_recorded():
    expected = {
        "simple_field_rank.json": "sha256:befadea3a67003233a1085b9a0292f42423a527cd01039cf6c8734c8ec36787e",
        "lagged_momentum.json": "sha256:ba339c3661060d124635caac5626118ae652afa096d336852ebea12e729e5408",
        "safe_division_fcf_mcap.json": "sha256:6d2091ed34a13e61cb96ee3fc9f9b3a49c8b9ed6f0e48dc079b2b459707e0171",
        "sector_neutral_composite.json": "sha256:1c3a690cddfd7c047a566e9ca96cf2950ad56c63714fd37aaa73e3bee2c68bd8",
        "nested_rolling.json": "sha256:f014123ec837dadbe52a6c2dc3bb5fc278f484c02727d7050e7a616a1c4ac989",
    }
    for name, digest in expected.items():
        assert formula_hash(_load_ast(name)) == digest


# --- Period split ---


def test_period_split_valid():
    split = DiscoveryPeriodSplit(
        discovery_start=date(2022, 1, 1),
        discovery_end=date(2023, 6, 30),
        validation_start=date(2023, 7, 15),
        validation_end=date(2024, 6, 30),
        sealed_test_start=date(2024, 7, 15),
        sealed_test_end=date(2025, 6, 30),
        min_sealed_test_days=63,
    )
    assert split.role_for_date(date(2022, 6, 1)) == ResearchPeriodRole.DISCOVERY
    assert split.role_for_date(date(2024, 1, 1)) == ResearchPeriodRole.VALIDATION
    assert split.role_for_date(date(2025, 1, 1)) == ResearchPeriodRole.SEALED_TEST
    assert split.role_for_date(date(2020, 1, 1)) is None


def test_period_split_overlap_rejected():
    with pytest.raises(ValidationError):
        DiscoveryPeriodSplit(
            discovery_start=date(2022, 1, 1),
            discovery_end=date(2023, 12, 31),
            validation_start=date(2023, 6, 1),
            validation_end=date(2024, 6, 30),
            sealed_test_start=date(2024, 7, 1),
            sealed_test_end=date(2025, 6, 30),
        )


def test_period_split_sealed_minimum():
    with pytest.raises(ValidationError):
        DiscoveryPeriodSplit(
            discovery_start=date(2022, 1, 1),
            discovery_end=date(2023, 6, 30),
            validation_start=date(2023, 7, 15),
            validation_end=date(2024, 6, 30),
            sealed_test_start=date(2024, 7, 15),
            sealed_test_end=date(2024, 8, 1),
            min_sealed_test_days=90,
        )


# --- Lifecycle ---


@pytest.mark.parametrize(
    "current,target,allowed",
    [
        (FactorLifecycleStatus.DRAFT, FactorLifecycleStatus.COMPILED, True),
        (FactorLifecycleStatus.VALIDATED, FactorLifecycleStatus.PAPER, True),
        (FactorLifecycleStatus.PAPER, FactorLifecycleStatus.PRODUCTION, True),
        (FactorLifecycleStatus.DRAFT, FactorLifecycleStatus.PRODUCTION, False),
        (FactorLifecycleStatus.PROMISING, FactorLifecycleStatus.PRODUCTION, False),
        (FactorLifecycleStatus.VALIDATED, FactorLifecycleStatus.PRODUCTION, False),
        (FactorLifecycleStatus.REJECTED, FactorLifecycleStatus.PRODUCTION, False),
    ],
)
def test_lifecycle_transitions(current, target, allowed):
    assert can_transition_factor_status(current, target) is allowed
    if not allowed:
        with pytest.raises(ValueError):
            validate_factor_status_transition(current, target)


# --- Hypothesis & definition ---


def test_factor_hypothesis_dedupes_tags_and_data_classes():
    hyp = FactorHypothesis(
        hypothesis_id="hyp_1",
        name="Volume momentum",
        economic_rationale="High volume predicts continuation.",
        expected_mechanism="Attention-driven buying pressure.",
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="penny",
        holding_period_sessions=5,
        rebalance_frequency="weekly",
        required_data_classes=[InputDataClass.VOLUME, InputDataClass.VOLUME, InputDataClass.PRICE],
        tags=["Momentum", " momentum "],
        creation_source=HypothesisSource.USER,
    )
    assert hyp.required_data_classes == [InputDataClass.VOLUME, InputDataClass.PRICE]
    assert hyp.tags == ["momentum"]


def test_factor_definition_from_fixture():
    raw = json.loads((FIXTURES / "full_factor_definition.json").read_text())
    defn = FactorDefinition.model_validate(raw)
    assert defn.lifecycle_status == FactorLifecycleStatus.DRAFT
    assert "return_126d" in defn.required_fields
    assert defn.formula_hash().startswith("sha256:")


# --- Disabled factor_discovery ---


def test_factor_discovery_validate_not_enabled(research_db, monkeypatch):
    monkeypatch.setattr(
        "services.experiment_validation_service.FACTOR_DISCOVERY_ENABLED",
        False,
    )
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="factor_discovery",
            sleeve="penny",
            universe_definition={"source": "full_bucket"},
            parameters={},
        )
    )
    assert result.can_run is False
    assert any(c.key == "factor_discovery_enabled" for c in result.checks)


def test_factor_discovery_launch_disabled(client, research_db, monkeypatch):
    import config

    monkeypatch.setattr(config, "FACTOR_DISCOVERY_ENABLED", False, raising=False)
    monkeypatch.setattr(
        "services.experiment_launch_service.FACTOR_DISCOVERY_ENABLED",
        False,
    )
    exp = create_experiment(
        ResearchExperimentCreate(
            name="FD disabled",
            experiment_type="factor_discovery",
            sleeve="penny",
            universe_definition={"source": "full_bucket"},
            parameters={},
        )
    )
    from unittest.mock import patch

    with patch("services.experiment_launch_service._EXECUTOR") as mock_exec:
        mock_exec.submit.side_effect = lambda fn, *a, **k: fn(*a, **k)
        r = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "failed"
    assert "not enabled" in body["message"].lower()
    job = client.get(f"/api/v2/research/experiments/jobs/{body['job_id']}").json()
    assert job["status"] == "failed"
    assert job.get("run_id") in (None, "")
