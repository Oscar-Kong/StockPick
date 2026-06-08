"""WeightStore — load/apply/persist dynamic factor weights."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import (
    DYNAMIC_WEIGHTS_ENABLED,
    FACTOR_MODEL_VERSION,
    WEIGHT_REBALANCE_LAMBDA,
)
from data.db_engine import get_engine
from engines.factor.catalog import signal_name_to_factor_id, static_weights
from engines.quant_models import FactorWeight, MarketRegime
from engines.weighting.regime_classifier import REGIMES, RegimeResult, classify_spy, features_to_json
from engines.weighting.weight_estimator import estimate_all_regime_weights
from screeners.base import WeightedSignal

logger = logging.getLogger(__name__)


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class WeightStore:
    @staticmethod
    def persist_regime(result: RegimeResult) -> None:
        engine = get_engine()
        with Session(engine) as session:
            row = session.get(MarketRegime, result.features.as_of_date)
            payload = dict(
                as_of_date=result.features.as_of_date,
                regime=result.regime,
                features_json=features_to_json(result),
            )
            if row:
                row.regime = payload["regime"]
                row.features_json = payload["features_json"]
            else:
                session.add(MarketRegime(**payload))
            session.commit()

    @staticmethod
    def current_regime(*, refresh: bool = False) -> str:
        today = _utc_today()
        engine = get_engine()
        if not refresh:
            with Session(engine) as session:
                row = session.get(MarketRegime, today)
                if row:
                    return row.regime
        result = classify_spy()
        if result:
            WeightStore.persist_regime(result)
            return result.regime
        return "neutral"

    @staticmethod
    def load(sleeve: str, regime: str | None = None) -> dict[str, float]:
        """factor_id → weight; static catalog when dynamic disabled or no rows."""
        regime = regime or WeightStore.current_regime()
        static = static_weights(sleeve)
        if not DYNAMIC_WEIGHTS_ENABLED:
            return static

        engine = get_engine()
        with Session(engine) as session:
            rows = (
                session.query(FactorWeight)
                .filter(
                    FactorWeight.sleeve == sleeve,
                    FactorWeight.regime == regime,
                    FactorWeight.effective_to.is_(None),
                    FactorWeight.model_version == FACTOR_MODEL_VERSION,
                )
                .all()
            )
            if not rows:
                return static
            return {r.factor_id: float(r.weight) for r in rows}

    @staticmethod
    def apply_to_signals(
        signals: list[WeightedSignal],
        sleeve: str,
        regime: str | None = None,
    ) -> list[WeightedSignal]:
        if not DYNAMIC_WEIGHTS_ENABLED:
            return signals
        weights = WeightStore.load(sleeve, regime)
        if not weights:
            return signals

        out: list[WeightedSignal] = []
        for sig in signals:
            fid = signal_name_to_factor_id(sleeve, sig.name)
            w = weights.get(fid)
            if w is None:
                out.append(sig)
            else:
                out.append(
                    WeightedSignal(sig.name, sig.value, w, sig.description)
                )
        total = sum(s.weight for s in out)
        if total <= 0:
            return signals
        return [
            WeightedSignal(s.name, s.value, s.weight / total, s.description)
            for s in out
        ]

    @staticmethod
    def _load_previous_weights(session: Session, sleeve: str, regime: str) -> dict[str, float]:
        rows = (
            session.query(FactorWeight)
            .filter(
                FactorWeight.sleeve == sleeve,
                FactorWeight.regime == regime,
                FactorWeight.effective_to.is_(None),
                FactorWeight.model_version == FACTOR_MODEL_VERSION,
            )
            .all()
        )
        return {r.factor_id: float(r.weight) for r in rows}

    @staticmethod
    def rebalance_sleeve(
        sleeve: str,
        *,
        smooth: bool = True,
        ic_panel: dict[str, dict] | None = None,
    ) -> dict[str, dict[str, float]]:
        """Estimate, smooth, persist weights for all regimes. Returns new weights."""
        est = estimate_all_regime_weights(sleeve, ic_panel)
        lam = WEIGHT_REBALANCE_LAMBDA if smooth else 0.0
        today = _utc_today()
        engine = get_engine()

        with Session(engine) as session:
            for regime, w_new_est in est.items():
                w_old = WeightStore._load_previous_weights(session, sleeve, regime)
                if not w_old:
                    w_old = static_weights(sleeve)
                w_final = {}
                for fid in w_new_est:
                    old = w_old.get(fid, 0.0)
                    est_w = w_new_est[fid]
                    w_final[fid] = lam * old + (1 - lam) * est_w
                total = sum(w_final.values()) or 1.0
                w_final = {fid: w / total for fid, w in w_final.items()}

                session.query(FactorWeight).filter(
                    FactorWeight.sleeve == sleeve,
                    FactorWeight.regime == regime,
                    FactorWeight.effective_to.is_(None),
                    FactorWeight.model_version == FACTOR_MODEL_VERSION,
                ).update({"effective_to": today})

                ic_at = (ic_panel or {}).get(next(iter(w_final), ""), {}).get("ic")
                for fid, w in w_final.items():
                    session.add(
                        FactorWeight(
                            sleeve=sleeve,
                            regime=regime,
                            factor_id=fid,
                            weight=round(w, 6),
                            ic_at_set=ic_at,
                            effective_from=today,
                            effective_to=None,
                            model_version=FACTOR_MODEL_VERSION,
                        )
                    )
                est[regime] = w_final
            session.commit()
        return est

    @staticmethod
    def rebalance_all_sleeves(*, smooth: bool = True) -> dict:
        out = {}
        for sleeve in ("penny", "medium", "compounder"):
            out[sleeve] = WeightStore.rebalance_sleeve(sleeve, smooth=smooth)
        return out

    @staticmethod
    def list_active_weights(sleeve: str) -> dict[str, dict[str, float]]:
        """regime → factor weights for API."""
        engine = get_engine()
        result: dict[str, dict[str, float]] = {r: {} for r in REGIMES}
        with Session(engine) as session:
            rows = (
                session.query(FactorWeight)
                .filter(
                    FactorWeight.sleeve == sleeve,
                    FactorWeight.effective_to.is_(None),
                    FactorWeight.model_version == FACTOR_MODEL_VERSION,
                )
                .all()
            )
            for row in rows:
                result.setdefault(row.regime, {})[row.factor_id] = float(row.weight)
        for regime in REGIMES:
            if not result[regime]:
                result[regime] = static_weights(sleeve)
        return result
