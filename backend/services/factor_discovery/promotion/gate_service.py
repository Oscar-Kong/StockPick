"""Evaluate versioned promotion gates from staging diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone

from models.schemas_factor_promotion import PromotionGateEvaluation, PromotionGateResult, PromotionGateVerdict
from services.factor_discovery.promotion.gate_policy import load_gate_policy


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _metric_value(diagnostics: dict, key: str) -> float | int | None:
    entry = diagnostics.get(key)
    if isinstance(entry, dict):
        if entry.get("status") == "not_applicable":
            return None
        return entry.get("value")
    return entry


class FactorPromotionGateService:
    def evaluate(
        self,
        *,
        diagnostics: dict,
        staging_report: dict | None = None,
        sleeve: str = "",
        blocking_leakage_controls: list[str] | None = None,
    ) -> PromotionGateEvaluation:
        policy = load_gate_policy()
        gates_cfg = policy["gates"]
        results: list[PromotionGateResult] = []
        blocking: list[str] = []

        obs = _metric_value(diagnostics, "observation_count")
        cfg = gates_cfg["sufficient_observations"]
        min_obs = int(cfg.get("min_valid_validation_dates", 20))
        if obs is None:
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = "observation count unavailable"
        elif int(obs) >= min_obs:
            verdict = PromotionGateVerdict.PASS
            explanation = f"{obs} >= {min_obs}"
        else:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"{obs} < {min_obs}"
        if verdict == PromotionGateVerdict.FAIL and cfg.get("blocking"):
            blocking.append("sufficient_observations")
        results.append(
            PromotionGateResult(
                gate_id="sufficient_observations",
                display_name=str(cfg.get("display_name", "Sufficient observations")),
                verdict=verdict,
                threshold=str(min_obs),
                observed=str(obs),
                explanation=explanation,
                blocking=bool(cfg.get("blocking")),
            )
        )

        date_cov = diagnostics.get("date_coverage")
        cfg = gates_cfg["sufficient_pit_date_coverage"]
        min_dates = int(cfg.get("min_date_count", 20))
        date_val = date_cov.get("value") if isinstance(date_cov, dict) else date_cov
        if isinstance(date_cov, dict) and date_cov.get("status") == "not_applicable":
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = date_cov.get("reason", "date coverage N/A")
        elif date_val is not None and int(date_val) >= min_dates:
            verdict = PromotionGateVerdict.PASS
            explanation = f"{date_val} >= {min_dates}"
        elif date_val is not None:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"{date_val} < {min_dates}"
        else:
            coverage = (staging_report or {}).get("manifest", {}).get("date_range", {})
            valid_dates = diagnostics.get("coverage", {}).get("valid_cross_sectional_dates")
            if valid_dates and int(valid_dates) >= min_dates:
                verdict = PromotionGateVerdict.PASS
                explanation = f"{valid_dates} cross-sectional dates"
                date_val = valid_dates
            else:
                verdict = PromotionGateVerdict.NOT_APPLICABLE
                explanation = "date coverage not reported"
        if verdict == PromotionGateVerdict.FAIL and cfg.get("blocking"):
            blocking.append("sufficient_pit_date_coverage")
        results.append(
            PromotionGateResult(
                gate_id="sufficient_pit_date_coverage",
                display_name=str(cfg.get("display_name", "PIT date coverage")),
                verdict=verdict,
                threshold=str(min_dates),
                observed=str(date_val),
                explanation=explanation,
                blocking=bool(cfg.get("blocking")),
            )
        )

        sym_cov = diagnostics.get("symbol_coverage")
        cfg = gates_cfg["sufficient_symbol_coverage"]
        min_sym = int(cfg.get("min_symbol_count", 3))
        sym_val = sym_cov.get("value") if isinstance(sym_cov, dict) else sym_cov
        if isinstance(sym_cov, dict) and sym_cov.get("status") == "not_applicable":
            coverage = diagnostics.get("coverage") or {}
            sym_val = coverage.get("symbol_count")
            if sym_val is None and staging_report:
                for cell in staging_report.get("cell_results", []):
                    if cell.get("sleeve") == sleeve and cell.get("factor_id") == diagnostics.get("factor_id"):
                        sym_val = (cell.get("coverage") or {}).get("symbol_count")
                        break
        if sym_val is None:
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = "symbol coverage not reported"
        elif int(sym_val) >= min_sym:
            verdict = PromotionGateVerdict.PASS
            explanation = f"{sym_val} >= {min_sym}"
        else:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"{sym_val} < {min_sym}"
        if verdict == PromotionGateVerdict.FAIL and cfg.get("blocking"):
            blocking.append("sufficient_symbol_coverage")
        results.append(
            PromotionGateResult(
                gate_id="sufficient_symbol_coverage",
                display_name=str(cfg.get("display_name", "Symbol coverage")),
                verdict=verdict,
                threshold=str(min_sym),
                observed=str(sym_val),
                explanation=explanation,
                blocking=bool(cfg.get("blocking")),
            )
        )

        mean_ic = _metric_value(diagnostics, "mean_rank_ic")
        cfg = gates_cfg["positive_stable_oos_ic"]
        min_ic = float(cfg.get("min_mean_rank_ic", 0.01))
        if mean_ic is None:
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = "mean rank IC not available"
        elif float(mean_ic) >= min_ic:
            verdict = PromotionGateVerdict.PASS
            explanation = f"{mean_ic} >= {min_ic}"
        else:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"{mean_ic} < {min_ic}"
        results.append(
            PromotionGateResult(
                gate_id="positive_stable_oos_ic",
                display_name=str(cfg.get("display_name", "OOS IC")),
                verdict=verdict,
                threshold=str(min_ic),
                observed=str(mean_ic),
                explanation=explanation,
                blocking=bool(cfg.get("blocking")),
            )
        )

        ic_std = _metric_value(diagnostics, "rank_ic_std")
        cfg = gates_cfg["acceptable_ic_dispersion"]
        max_std = float(cfg.get("max_rank_ic_std", 0.15))
        if ic_std is None:
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = "IC std not reported"
        elif float(ic_std) <= max_std:
            verdict = PromotionGateVerdict.PASS
            explanation = f"{ic_std} <= {max_std}"
        else:
            verdict = PromotionGateVerdict.WARNING
            explanation = f"{ic_std} > {max_std}"
        results.append(
            PromotionGateResult(
                gate_id="acceptable_ic_dispersion",
                display_name=str(cfg.get("display_name", "IC dispersion")),
                verdict=verdict,
                threshold=str(max_std),
                observed=str(ic_std),
                explanation=explanation,
                blocking=bool(cfg.get("blocking")),
            )
        )

        leakage_cfg = gates_cfg["no_leakage_flags"]
        leakage_blockers = blocking_leakage_controls or []
        staging_blockers = (staging_report or {}).get("promotion_readiness", {}).get("blocking_findings", [])
        leakage_hits = [b for b in staging_blockers if "leakage" in b.lower() or "negative_control" in b.lower()]
        if leakage_blockers or leakage_hits:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"leakage flags: {leakage_blockers or leakage_hits}"
            if leakage_cfg.get("blocking"):
                blocking.append("no_leakage_flags")
        else:
            verdict = PromotionGateVerdict.PASS
            explanation = "no blocking leakage flags"
        results.append(
            PromotionGateResult(
                gate_id="no_leakage_flags",
                display_name=str(leakage_cfg.get("display_name", "No leakage")),
                verdict=verdict,
                explanation=explanation,
                blocking=bool(leakage_cfg.get("blocking")),
            )
        )

        repro_cfg = gates_cfg["reproducibility_pass"]
        repro = (staging_report or {}).get("reproducibility_results") or []
        mismatches = [r for r in repro if r.get("comparison_status") == "MISMATCH"]
        if not repro:
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = "no reproducibility runs in staging report"
        elif mismatches:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"{len(mismatches)} reproducibility mismatches"
            if repro_cfg.get("blocking"):
                blocking.append("reproducibility_pass")
        else:
            verdict = PromotionGateVerdict.PASS
            explanation = "reproducibility exact/semantic match"
        results.append(
            PromotionGateResult(
                gate_id="reproducibility_pass",
                display_name=str(repro_cfg.get("display_name", "Reproducibility")),
                verdict=verdict,
                explanation=explanation,
                blocking=bool(repro_cfg.get("blocking")),
            )
        )

        neg_cfg = gates_cfg["negative_controls_ok"]
        controls = (staging_report or {}).get("negative_controls") or []
        blocking_ctrl = [c for c in controls if c.get("blocking") and not c.get("passed")]
        if not controls:
            verdict = PromotionGateVerdict.NOT_APPLICABLE
            explanation = "negative controls not in staging report"
        elif blocking_ctrl:
            verdict = PromotionGateVerdict.FAIL
            explanation = f"blocking controls failed: {[c.get('control_id') for c in blocking_ctrl]}"
            if neg_cfg.get("blocking"):
                blocking.append("negative_controls_ok")
        else:
            verdict = PromotionGateVerdict.PASS
            explanation = "blocking negative controls passed"
        results.append(
            PromotionGateResult(
                gate_id="negative_controls_ok",
                display_name=str(neg_cfg.get("display_name", "Negative controls")),
                verdict=verdict,
                explanation=explanation,
                blocking=bool(neg_cfg.get("blocking")),
            )
        )

        for gate_id, cfg in gates_cfg.items():
            if gate_id in {r.gate_id for r in results}:
                continue
            results.append(
                PromotionGateResult(
                    gate_id=gate_id,
                    display_name=str(cfg.get("display_name", gate_id)),
                    verdict=PromotionGateVerdict.NOT_APPLICABLE,
                    explanation="not evaluated in this staging slice",
                    blocking=bool(cfg.get("blocking")),
                )
            )

        overall = not blocking
        return PromotionGateEvaluation(
            policy_id=policy["policy_id"],
            policy_version=policy["policy_version"],
            evaluated_at=_utcnow(),
            overall_pass=overall,
            blocking_failures=blocking,
            gates=results,
        )
