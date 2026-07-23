"""Instrumentation for scan Stage A → Stage B history reuse."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ScanDataFlowMetrics:
    bulk_download_ms: float = 0.0
    bulk_symbols_returned: int = 0
    bulk_symbols_requested: int = 0
    bulk_coverage_ratio: float = 0.0
    bulk_download_partial: bool = False
    bulk_source: str = ""
    stage_a_rank_ms: float = 0.0
    stage_b_build_ms: float = 0.0
    bulk_cache_hits: int = 0
    provider_fallbacks: int = 0
    history_reload_count: int = 0
    candidate_build_calls: int = 0
    fundamental_cache_hits: int = 0
    fundamental_refreshes: int = 0
    per_symbol_sources: list[dict[str, str]] = field(default_factory=list)
    per_symbol_diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def record_candidate_source(self, symbol: str, source: str) -> None:
        self.per_symbol_sources.append({"symbol": symbol.upper(), "history_source": source})

    def record_candidate_diagnostics(self, symbol: str, diagnostics: dict[str, Any]) -> None:
        self.per_symbol_diagnostics.append({"symbol": symbol.upper(), **diagnostics})

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["cache_hit_count"] = self.bulk_cache_hits
        return payload
