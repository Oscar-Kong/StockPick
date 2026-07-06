"""Outcome-driven factor weight nudges from resolved predictions."""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from config import OUTCOME_WEIGHT_FEEDBACK_ENABLED, OUTCOME_WEIGHT_ETA, WEIGHT_MAX, WEIGHT_MIN
from data.db_engine import get_engine
from engines.quant_models import PredictionOutcome, PredictionSnapshot
from engines.weighting.weight_store import WeightStore

logger = logging.getLogger(__name__)


def run_outcome_weight_feedback(*, sleeve: str | None = None) -> dict:
    if not OUTCOME_WEIGHT_FEEDBACK_ENABLED:
        return {"skipped": True, "reason": "OUTCOME_WEIGHT_FEEDBACK_ENABLED=false"}

    engine = get_engine()
    factor_hits: dict[str, list[float]] = defaultdict(list)
    rec_hits: list[float] = []

    with Session(engine) as session:
        rows = (
            session.query(PredictionSnapshot, PredictionOutcome)
            .join(PredictionOutcome, PredictionOutcome.prediction_id == PredictionSnapshot.id)
            .filter(PredictionOutcome.return_60d.isnot(None))
            .all()
        )
        for snap, oc in rows:
            if sleeve and snap.sleeve != sleeve:
                continue
            excess = oc.excess_vs_spy_60d
            if excess is None:
                continue
            hit = 1.0 if excess > 0 else -1.0
            rec_hits.append(hit)
            try:
                feats = json.loads(snap.features_json or "{}")
                for f in feats.get("factors") or []:
                    fid = str(f.get("factor_id") or "")
                    if fid:
                        factor_hits[fid].append(hit * float(f.get("contribution") or 1))
            except Exception:
                pass

    if not factor_hits:
        return {"updated": 0, "reason": "no resolved outcomes"}

    regime = WeightStore.current_regime()
    updates: list[dict] = []
    for sl in ("penny", "compounder"):
        if sleeve and sl != sleeve:
            continue
        weights = WeightStore.load(sl, regime)
        changed = False
        for fid, hits in factor_hits.items():
            if fid not in weights:
                continue
            avg = sum(hits) / len(hits)
            delta = OUTCOME_WEIGHT_ETA * avg * 0.01
            new_w = max(WEIGHT_MIN, min(WEIGHT_MAX, weights[fid] + delta))
            if abs(new_w - weights[fid]) > 1e-6:
                weights[fid] = round(new_w, 4)
                changed = True
                updates.append({"sleeve": sl, "factor_id": fid, "delta": round(delta, 4)})
        if changed:
            total = sum(weights.values()) or 1.0
            weights = {k: round(v / total, 4) for k, v in weights.items()}
            WeightStore.save_weights(sl, regime, weights, ic_snapshot=None)

    return {
        "updated_factors": len(updates),
        "mean_recommendation_hit": round(sum(rec_hits) / len(rec_hits), 3) if rec_hits else None,
        "updates": updates[:20],
        "regime": regime,
    }
