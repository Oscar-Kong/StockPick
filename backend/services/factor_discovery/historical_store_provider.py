"""Historical-store Factor Discovery data provider (price-only, PIT universe)."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.factor.discovery.panel_models import FactorInputPanel
from engines.factor.discovery.provenance import PanelFieldProvenance, PanelFieldSourceType, PitProvenanceState
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.sessions import extract_canonical_sessions
from engines.quant_models import UniversePit
from services.factor_discovery.capabilities import FactorResearchDataCapabilities
from services.factor_discovery.data_provider import FactorResearchSnapshotRef
from services.factor_discovery.errors import FactorDiscoveryError

HISTORICAL_STORE_PROVIDER_ID = "historical_store_v1"
RESEARCH_POLICY_ID = "research_adjusted_daily_v1"


def _provider_data_version() -> str:
    engine = get_engine()
    with Session(engine) as session:
        latest = session.query(UniversePit.as_of_date).order_by(UniversePit.as_of_date.desc()).limit(1).scalar()
        quote_count = session.execute(
            __import__("sqlalchemy", fromlist=["text"]).text("SELECT COUNT(*) FROM daily_quotes")
        ).scalar()
    return f"sha256:{hashlib.sha256(f'{latest}|{quote_count}'.encode()).hexdigest()[:16]}"


def assess_historical_store_capabilities() -> FactorResearchDataCapabilities:
    from services.factor_discovery.staging.price_audit import FactorDiscoveryPriceAuditService
    from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService

    price = FactorDiscoveryPriceAuditService().audit()
    universe = FactorDiscoveryUniverseAuditService().audit()
    blocking = list(dict.fromkeys(price.blocking_codes + universe.blocking_codes))
    price_ok = price.total_rows > 0 and "no_daily_quotes" not in price.blocking_codes
    adjusted_ok = price.adjusted_rows > 0 and "no_adjusted_rows" not in price.blocking_codes
    date_range = None
    if price.earliest_date and price.latest_date:
        date_range = (price.earliest_date, price.latest_date)
    elif universe.earliest_date and universe.latest_date:
        date_range = (universe.earliest_date, universe.latest_date)
    supported = ("adjusted_close", "volume") if price_ok and adjusted_ok else tuple()
    return FactorResearchDataCapabilities(
        provider_id=HISTORICAL_STORE_PROVIDER_ID,
        price_research_available=price_ok,
        adjusted_prices_available=adjusted_ok,
        pit_universe_available=universe.total_membership_rows > 0,
        pit_fundamentals_available=False,
        pit_sector_history_available=False,
        historical_market_cap_available=False,
        supported_date_range=date_range,
        supported_fields=supported,
        blocking_reasons=tuple(blocking),
        provider_data_version=_provider_data_version(),
    )


def _load_pit_membership(start: str | None, end: str | None) -> dict[tuple[str, str], bool]:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(UniversePit)
        if start:
            q = q.filter(UniversePit.as_of_date >= start)
        if end:
            q = q.filter(UniversePit.as_of_date <= end)
        rows = q.all()
    if not rows:
        raise FactorDiscoveryError("EMPTY_PIT_UNIVERSE", "universe_pit has no rows for requested range")
    return {(r.as_of_date, r.symbol.upper()): bool(r.is_active) for r in rows}


def _load_quotes_adjusted(
    symbols: set[str],
    *,
    start: str | None = None,
    end: str | None = None,
    warmup_calendar_days: int = 200,
) -> dict[str, pd.DataFrame]:
    engine = get_engine()
    from data.historical_store import DailyQuote

    load_start = start
    if start:
        load_start = (date.fromisoformat(start[:10]) - timedelta(days=warmup_calendar_days)).isoformat()

    out: dict[str, pd.DataFrame] = {}
    with Session(engine) as session:
        for sym in sorted(symbols):
            q = session.query(DailyQuote).filter(DailyQuote.symbol == sym, DailyQuote.adjusted == 1)
            if load_start:
                q = q.filter(DailyQuote.date >= load_start)
            if end:
                q = q.filter(DailyQuote.date <= end)
            rows = q.order_by(DailyQuote.date.asc()).all()
            if not rows:
                continue
            if any(r.adjusted != 1 for r in rows):
                raise FactorDiscoveryError("MIXED_ADJUSTED_RAW", f"unadjusted rows for {sym}")
            df = pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp(r.date),
                        "adjusted_close": float(r.close),
                        "volume": float(r.volume),
                    }
                    for r in rows
                ]
            )
            out[sym] = df
    return out


class HistoricalStoreFactorResearchDataProvider:
    provider_id = HISTORICAL_STORE_PROVIDER_ID

    def capabilities(self) -> FactorResearchDataCapabilities:
        return assess_historical_store_capabilities()

    def materialize_panel(
        self,
        *,
        start_session: str | None = None,
        end_session: str | None = None,
        required_fields: set[str] | None = None,
    ) -> FactorInputPanel:
        caps = self.capabilities()
        ok, reasons = caps.ready_for_fields(required_fields or {"adjusted_close", "volume"})
        if not ok:
            raise FactorDiscoveryError("PROVIDER_CAPABILITY_FAILURE", ";".join(reasons))
        membership = _load_pit_membership(start_session, end_session)
        symbols = {sym for (_, sym) in membership.keys()}
        quotes = _load_quotes_adjusted(symbols, start=start_session, end=end_session)
        if not quotes:
            raise FactorDiscoveryError("MISSING_PRICES", "no adjusted quotes in historical store")
        rows: list[dict] = []
        for (d_str, sym), active in membership.items():
            df = quotes.get(sym)
            if df is None:
                continue
            dt = pd.Timestamp(d_str)
            match = df[df["date"] == dt]
            if match.empty:
                continue
            row = match.iloc[0]
            rows.append(
                {
                    "date": dt,
                    "symbol": sym,
                    "adjusted_close": row["adjusted_close"],
                    "volume": row["volume"],
                    "eligible": active,
                }
            )
        if not rows:
            raise FactorDiscoveryError("EMPTY_PANEL", "no overlapping pit and price rows")
        frame = pd.DataFrame(rows).set_index(["date", "symbol"]).sort_index()
        eligibility = frame.pop("eligible").astype(bool)
        if not eligibility.any():
            raise FactorDiscoveryError("EMPTY_PIT_UNIVERSE", "no eligible universe rows")
        prov = {
            "adjusted_close": PanelFieldProvenance(
                field_id="adjusted_close",
                source_type=PanelFieldSourceType.SUPPLIED_PRIMITIVE,
                pit_state=PitProvenanceState.VERIFIED_PIT,
                provider_id=self.provider_id,
                source_policy_id=RESEARCH_POLICY_ID,
                is_adjusted=True,
            ),
            "volume": PanelFieldProvenance(
                field_id="volume",
                source_type=PanelFieldSourceType.SUPPLIED_PRIMITIVE,
                pit_state=PitProvenanceState.VERIFIED_PIT,
                provider_id=self.provider_id,
                source_policy_id=RESEARCH_POLICY_ID,
            ),
        }
        return FactorInputPanel(
            frame=frame,
            eligibility=eligibility,
            data_source_policy_id=RESEARCH_POLICY_ID,
            provider_id=self.provider_id,
            prices_adjusted=True,
            field_provenance=prov,
            has_universe_membership=True,
        )

    def load_snapshot(self, **kwargs) -> tuple[FactorInputPanel, FactorResearchSnapshotRef]:
        panel = self.materialize_panel(
            start_session=kwargs.get("start_session"),
            end_session=kwargs.get("end_session"),
            required_fields=set(kwargs.get("required_fields") or []),
        )
        calendar = extract_canonical_sessions(panel.frame)
        session_hash = canonical_session_hash(calendar)
        caps = self.capabilities()
        snapshot_id = kwargs.get("snapshot_id") or f"fdsnap_hs_{session_hash[-12:]}"
        ref = FactorResearchSnapshotRef(
            snapshot_id=snapshot_id,
            provider_id=self.provider_id,
            data_source_policy_id=RESEARCH_POLICY_ID,
            panel_hash=panel.content_hash,
            canonical_session_hash=session_hash,
            universe_source="universe_pit",
            universe_version=caps.provider_data_version,
            universe_pit_evidence={"source": "universe_pit", "verified": True, "row_count": panel.row_count},
            field_list=sorted(panel.frame.columns.tolist()),
            field_provenance_summary={
                k: v.model_dump(mode="json") for k, v in sorted(panel.field_provenance.items())
            },
            adjustment_status="adjusted",
            start_session=str(panel.start_date),
            end_session=str(panel.end_date),
            row_count=panel.row_count,
            symbol_count=panel.symbol_count,
            date_count=panel.date_count,
            storage_reference=None,
            storage_format="pending_materialization",
            artifact_present=False,
        )
        return panel, ref
