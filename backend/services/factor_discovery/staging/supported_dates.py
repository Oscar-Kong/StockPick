"""Resolve supported staging date ranges and regime slices from the historical database."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from data.db_engine import get_engine
from data.historical_store import DailyQuote
from engines.quant_models import UniversePit


@dataclass
class RegimeSlice:
    slice_id: str
    label: str
    start_date: str
    end_date: str
    regime_type: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "slice_id": self.slice_id,
            "label": self.label,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "regime_type": self.regime_type,
            "evidence": self.evidence,
        }


@dataclass
class SupportedDateRange:
    earliest_quote_date: str | None
    latest_quote_date: str | None
    earliest_universe_date: str | None
    latest_universe_date: str | None
    supported_start: str | None
    supported_end: str | None
    overlap_sessions: int
    slices: list[RegimeSlice] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "earliest_quote_date": self.earliest_quote_date,
            "latest_quote_date": self.latest_quote_date,
            "earliest_universe_date": self.earliest_universe_date,
            "latest_universe_date": self.latest_universe_date,
            "supported_start": self.supported_start,
            "supported_end": self.supported_end,
            "overlap_sessions": self.overlap_sessions,
            "slices": [s.to_dict() for s in self.slices],
        }


def _overlap_sessions(start: str, end: str) -> int:
    with Session(get_engine()) as session:
        return int(
            session.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT up.as_of_date)
                    FROM universe_pit up
                    INNER JOIN daily_quotes dq
                      ON dq.symbol = up.symbol AND dq.date = up.as_of_date
                    WHERE up.is_active = 1
                      AND up.as_of_date >= :start
                      AND up.as_of_date <= :end
                    """
                ),
                {"start": start, "end": end},
            ).scalar()
            or 0
        )


def _spy_volatility_by_month() -> list[tuple[str, float]]:
    with Session(get_engine()) as session:
        rows = session.execute(
            text(
                """
                SELECT substr(date, 1, 7) AS ym,
                       AVG(close) AS avg_close,
                       COUNT(*) AS n
                FROM daily_quotes
                WHERE symbol = 'SPY' AND adjusted = 1
                GROUP BY ym
                ORDER BY ym
                """
            )
        ).fetchall()
    if len(rows) < 3:
        return []
    out: list[tuple[str, float]] = []
    prev = None
    for ym, avg_close, _n in rows:
        if prev is not None and prev > 0:
            ret = float(avg_close) / prev - 1.0
            out.append((str(ym), abs(ret)))
        prev = float(avg_close)
    return out


def _build_regime_slices(supported_start: str, supported_end: str) -> list[RegimeSlice]:
    with Session(get_engine()) as session:
        dates = [
            r[0]
            for r in session.execute(
                text(
                    """
                    SELECT DISTINCT up.as_of_date
                    FROM universe_pit up
                    INNER JOIN daily_quotes dq
                      ON dq.symbol = up.symbol AND dq.date = up.as_of_date
                    WHERE up.is_active = 1
                      AND up.as_of_date >= :start
                      AND up.as_of_date <= :end
                    ORDER BY up.as_of_date
                    """
                ),
                {"start": supported_start, "end": supported_end},
            ).fetchall()
        ]
    if len(dates) < 60:
        return [
            RegimeSlice(
                slice_id="full_window",
                label="Full supported window",
                start_date=supported_start,
                end_date=supported_end,
                regime_type="full_coverage",
                evidence={"session_count": len(dates)},
            )
        ]

    # Drop slices whose overlap with available sessions is too thin.
    date_set = set(dates)
    n = len(dates)
    third = max(n // 3, 20)
    early_end = dates[third - 1]
    mid_start = dates[third]
    mid_end = dates[2 * third - 1]
    recent_start = dates[2 * third]

    def _clip_slice(slice_id: str, label: str, start: str, end: str, regime_type: str, evidence: dict) -> RegimeSlice | None:
        overlap = [d for d in dates if start <= d <= end]
        if len(overlap) < 20:
            return None
        return RegimeSlice(
            slice_id=slice_id,
            label=label,
            start_date=overlap[0],
            end_date=overlap[-1],
            regime_type=regime_type,
            evidence={**evidence, "session_count": len(overlap)},
        )

    slices: list[RegimeSlice] = []
    for candidate in [
        _clip_slice("early_historical", "Early historical period", dates[0], early_end, "walk_forward_early", {}),
        _clip_slice("middle_period", "Middle period", mid_start, mid_end, "walk_forward_middle", {}),
        _clip_slice("recent_period", "Recent period", recent_start, dates[-1], "walk_forward_recent", {}),
    ]:
        if candidate:
            slices.append(candidate)
    if not slices:
        slices.append(
            RegimeSlice(
                slice_id="full_window",
                label="Full supported window",
                start_date=dates[0],
                end_date=dates[-1],
                regime_type="full_coverage",
                evidence={"session_count": len(dates)},
            )
        )

    vol = _spy_volatility_by_month()
    drawdown_rows: list = []
    with Session(get_engine()) as session:
        if vol:
            drawdown_rows = session.execute(
                text(
                    """
                    SELECT date, close FROM daily_quotes
                    WHERE symbol = 'SPY' AND adjusted = 1
                      AND date >= :start AND date <= :end
                    ORDER BY date
                    """
                ),
                {"start": supported_start, "end": supported_end},
            ).fetchall()

    if vol:
        median = sorted(v for _, v in vol)[len(vol) // 2]
        high_months = [ym for ym, v in vol if v >= median]
        low_months = [ym for ym, v in vol if v < median]
        high_dates = [d for d in dates if d[:7] in high_months]
        low_dates = [d for d in dates if d[:7] in low_months]
        if len(high_dates) >= 20:
            clipped = [d for d in high_dates if d in date_set]
            if len(clipped) >= 20:
                slices.append(
                    RegimeSlice(
                        slice_id="high_volatility_spy",
                        label="Higher-volatility regime (SPY monthly proxy)",
                        start_date=clipped[0],
                        end_date=clipped[-1],
                        regime_type="high_volatility",
                        evidence={"proxy": "SPY", "months": len(high_months), "session_count": len(clipped)},
                    )
                )
        if len(low_dates) >= 20:
            clipped = [d for d in low_dates if d in date_set]
            if len(clipped) >= 20:
                slices.append(
                    RegimeSlice(
                        slice_id="low_volatility_spy",
                        label="Lower-volatility regime (SPY monthly proxy)",
                        start_date=clipped[0],
                        end_date=clipped[-1],
                        regime_type="low_volatility",
                        evidence={"proxy": "SPY", "months": len(low_months), "session_count": len(clipped)},
                    )
                )
        if len(drawdown_rows) >= 40:
            peak = float(drawdown_rows[0][1])
            max_dd = 0.0
            dd_start = drawdown_rows[0][0]
            dd_end = drawdown_rows[-1][0]
            for d, c in drawdown_rows:
                price = float(c)
                peak = max(peak, price)
                dd = (price / peak) - 1.0 if peak > 0 else 0.0
                if dd < max_dd:
                    max_dd = dd
                    dd_start = d
                    dd_end = d
            if max_dd <= -0.08:
                clipped = [str(d) for d, _c in drawdown_rows if str(d) in date_set]
                if len(clipped) >= 20:
                    slices.append(
                        RegimeSlice(
                            slice_id="spy_stress_drawdown",
                            label="Broad-market stress (SPY drawdown proxy)",
                            start_date=clipped[0],
                            end_date=clipped[-1],
                            regime_type="stress_drawdown",
                            evidence={"proxy": "SPY", "max_drawdown": round(max_dd, 4), "session_count": len(clipped)},
                        )
                    )

    return slices


def resolve_supported_date_range(
    *,
    requested_start: str | None = None,
    requested_end: str | None = None,
    min_overlap_sessions: int = 60,
) -> SupportedDateRange:
    with Session(get_engine()) as session:
        earliest_quote = session.query(func.min(DailyQuote.date)).scalar()
        latest_quote = session.query(func.max(DailyQuote.date)).scalar()
        earliest_universe = (
            session.query(func.min(UniversePit.as_of_date))
            .filter(UniversePit.is_active.is_(True), UniversePit.bucket_hint.like("staging:%"))
            .scalar()
        ) or session.query(func.min(UniversePit.as_of_date)).filter(UniversePit.is_active.is_(True)).scalar()
        latest_universe = (
            session.query(func.max(UniversePit.as_of_date))
            .filter(UniversePit.is_active.is_(True), UniversePit.bucket_hint.like("staging:%"))
            .scalar()
        ) or session.query(func.max(UniversePit.as_of_date)).filter(UniversePit.is_active.is_(True)).scalar()

    supported_start = max(filter(None, [earliest_quote, earliest_universe, requested_start]))
    supported_end = min(filter(None, [latest_quote, latest_universe, requested_end]))
    overlap = 0
    slices: list[RegimeSlice] = []
    if supported_start and supported_end and supported_start <= supported_end:
        overlap = _overlap_sessions(supported_start, supported_end)
        if overlap >= min_overlap_sessions:
            slices = _build_regime_slices(supported_start, supported_end)

    return SupportedDateRange(
        earliest_quote_date=earliest_quote,
        latest_quote_date=latest_quote,
        earliest_universe_date=earliest_universe,
        latest_universe_date=latest_universe,
        supported_start=supported_start if overlap >= min_overlap_sessions else None,
        supported_end=supported_end if overlap >= min_overlap_sessions else None,
        overlap_sessions=overlap,
        slices=slices,
    )
