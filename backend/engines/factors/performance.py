"""Factor IC performance dashboard — reads factor_ic_history + deciles."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from config import IC_PANEL_HORIZONS
from data.db_engine import get_engine
from engines.quant_models import FactorDecileHistory, FactorIcHistory, MarketRegime


def get_factor_performance(
    *,
    sleeve: str | None = None,
    factor_id: str | None = None,
    horizon_days: int | None = None,
) -> dict[str, Any]:
    engine = get_engine()
    horizons = [horizon_days] if horizon_days else IC_PANEL_HORIZONS

    with Session(engine) as session:
        latest_date = (
            session.query(FactorIcHistory.as_of_date)
            .order_by(FactorIcHistory.as_of_date.desc())
            .limit(1)
            .scalar()
        )
        if not latest_date:
            return {"as_of_date": None, "factors": [], "by_horizon": {}, "by_regime": {}, "by_sector": {}}

        q = session.query(FactorIcHistory).filter(FactorIcHistory.as_of_date == latest_date)
        if sleeve:
            q = q.filter(FactorIcHistory.sleeve == sleeve)
        if factor_id:
            q = q.filter(FactorIcHistory.factor_id == factor_id)
        rows = q.all()

        dec_q = session.query(FactorDecileHistory).filter(FactorDecileHistory.as_of_date == latest_date)
        if sleeve:
            dec_q = dec_q.filter(FactorDecileHistory.sleeve == sleeve)
        if factor_id:
            dec_q = dec_q.filter(FactorDecileHistory.factor_id == factor_id)
        dec_rows = dec_q.all()

    dec_by_factor: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    by_regime: dict[str, list] = defaultdict(list)
    by_sector: dict[str, list] = defaultdict(list)
    for d in dec_rows:
        if d.horizon_days not in horizons:
            continue
        key = f"{d.horizon_days}"
        dec_by_factor[d.factor_id][key].append(
            {
                "decile": d.decile,
                "avg_forward_return_pct": round((d.avg_forward_return or 0) * 100, 3),
                "sample_n": d.sample_n,
            }
        )
        if d.regime:
            by_regime[d.regime].append(
                {
                    "factor_id": d.factor_id,
                    "horizon_days": d.horizon_days,
                    "decile": d.decile,
                    "avg_forward_return_pct": round((d.avg_forward_return or 0) * 100, 3),
                }
            )

    by_factor: dict[str, dict[str, Any]] = defaultdict(lambda: {"horizons": {}, "sleeve": None})
    by_horizon: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for r in rows:
        if r.horizon_days not in horizons:
            continue
        entry = {
            "factor_id": r.factor_id,
            "sleeve": r.sleeve,
            "horizon_days": r.horizon_days,
            "ic": r.ic,
            "ir": r.ir,
            "hit_rate": r.hit_rate,
            "sample_n": r.sample_n,
            "deciles": sorted(
                dec_by_factor[r.factor_id].get(str(r.horizon_days), []),
                key=lambda x: x["decile"],
            ),
        }
        by_factor[r.factor_id]["factor_id"] = r.factor_id
        by_factor[r.factor_id]["sleeve"] = r.sleeve
        by_factor[r.factor_id]["horizons"][str(r.horizon_days)] = entry
        by_horizon[r.horizon_days].append(entry)

    factors = sorted(by_factor.values(), key=lambda x: x["factor_id"])
    for h in by_horizon:
        by_horizon[h] = sorted(by_horizon[h], key=lambda x: abs(x.get("ic") or 0), reverse=True)

    regime_context = _latest_regime()
    sector_panel = _sector_ic_cache(latest_date)
    for factor_id, horizons_map in sector_panel.items():
        for h_key, sectors in horizons_map.items():
            for sec, stats in sectors.items():
                by_sector[sec].append(
                    {
                        "factor_id": factor_id.split(":")[0] if ":" in factor_id else factor_id,
                        "horizon_days": int(h_key) if str(h_key).isdigit() else h_key,
                        "ic": stats.get("ic"),
                        "hit_rate": stats.get("hit_rate"),
                        "sample_n": stats.get("sample_n"),
                    }
                )

    return {
        "as_of_date": latest_date,
        "horizons": horizons,
        "factors": factors,
        "by_horizon": {str(k): v for k, v in by_horizon.items()},
        "by_regime": dict(by_regime),
        "by_sector": dict(by_sector),
        "market_regime": regime_context,
        "summary": _performance_summary(by_horizon),
    }


def _sector_ic_cache(as_of_date: str) -> dict[str, dict]:
    try:
        from data.cache import Cache

        raw = Cache().get(f"ic_by_sector:{as_of_date}") or {}
        grouped: dict[str, dict] = defaultdict(dict)
        for key, sectors in raw.items():
            parts = key.split(":")
            if len(parts) >= 3:
                fid, _sleeve, horizon = parts[0], parts[1], parts[2]
                grouped[fid][horizon] = sectors
        return dict(grouped)
    except Exception:
        return {}


def _latest_regime() -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.query(MarketRegime).order_by(MarketRegime.as_of_date.desc()).first()
        if not row:
            return None
        return {"regime": row.regime, "as_of_date": row.as_of_date}


def _performance_summary(by_horizon: dict[int, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for h, items in by_horizon.items():
        ics = [x["ic"] for x in items if x.get("ic") is not None]
        if not ics:
            continue
        summary[str(h)] = {
            "mean_ic": round(sum(ics) / len(ics), 4),
            "positive_ic_count": sum(1 for i in ics if i > 0),
            "factor_count": len(ics),
        }
    return summary
