"""Instrument identity mapping for staging universe import."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from services.factor_discovery.staging.symbol_identity import normalize_symbol, validate_symbol


@dataclass
class InstrumentMapping:
    instrument_id: str
    source_symbol: str
    canonical_symbol: str
    exchange: str | None = None
    mapping_version: str = "symbol_mapping_v1"


@dataclass
class SymbolMappingReport:
    mappings: list[InstrumentMapping] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    def mapping_hash(self) -> str:
        payload = json.dumps(
            [{"instrument_id": m.instrument_id, "canonical": m.canonical_symbol} for m in self.mappings],
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


class StagingSymbolMappingService:
    """Ticker-only mapping layer until stable instrument IDs exist in schema."""

    def __init__(self, *, mapping_version: str = "symbol_mapping_v1") -> None:
        self._mapping_version = mapping_version
        self._seen: dict[str, str] = {}

    def resolve(self, source_symbol: str, *, exchange: str | None = None) -> InstrumentMapping:
        ok, err = validate_symbol(source_symbol)
        if not ok:
            raise ValueError(err or source_symbol)
        canonical = normalize_symbol(source_symbol)
        if canonical in self._seen and self._seen[canonical] != source_symbol:
            raise ValueError(f"ambiguous_mapping:{canonical}")
        self._seen[canonical] = source_symbol
        instrument_id = f"inst_{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"
        return InstrumentMapping(
            instrument_id=instrument_id,
            source_symbol=source_symbol,
            canonical_symbol=canonical,
            exchange=exchange,
            mapping_version=self._mapping_version,
        )

    def resolve_many(self, rows: list[dict]) -> SymbolMappingReport:
        report = SymbolMappingReport()
        for row in rows:
            try:
                mapping = self.resolve(str(row["symbol"]), exchange=row.get("exchange"))
                report.mappings.append(mapping)
            except ValueError as exc:
                msg = str(exc)
                if msg.startswith("ambiguous_mapping:"):
                    report.ambiguous.append(msg.split(":", 1)[1])
                else:
                    report.rejected.append(str(row.get("symbol")))
        return report
