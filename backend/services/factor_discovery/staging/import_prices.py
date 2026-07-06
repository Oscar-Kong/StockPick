"""Staging-only price import with batch metadata."""
from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import config as app_config
from data.historical_store import HistoricalStore
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.staging.policies import HistoricalAdjustedPricesPolicy
from services.factor_discovery.staging.symbol_identity import normalize_symbol, validate_symbol


@dataclass
class PriceImportReport:
    batch_id: str
    accepted_rows: int
    rejected_rows: int
    source_file_hash: str
    blocking_codes: list[str]
    rejected_details: list[dict]

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "accepted_rows": self.accepted_rows,
            "rejected_rows": self.rejected_rows,
            "source_file_hash": self.source_file_hash,
            "blocking_codes": self.blocking_codes,
            "rejected_details": self.rejected_details[:50],
        }


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return f"sha256:{h.hexdigest()}"


def _validate_input_path(path: Path) -> Path:
    root = Path(getattr(app_config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", "") or "")
    resolved = path.resolve()
    if root:
        root = root.resolve()
        if not str(resolved).startswith(str(root)):
            raise FactorDiscoveryError("STAGING_INPUT_PATH_ESCAPE", "path outside staging input root")
    if path.suffix.lower() not in {".csv"}:
        raise FactorDiscoveryError("STAGING_INPUT_FORMAT", "only CSV supported")
    return resolved


class FactorDiscoveryStagingPriceImporter:
    def __init__(self, policy: HistoricalAdjustedPricesPolicy | None = None) -> None:
        self._policy = policy or HistoricalAdjustedPricesPolicy()
        self._store = HistoricalStore()

    def import_csv(
        self,
        path: Path,
        *,
        provider_id: str,
        provider_data_version: str,
        actor: str,
        reason: str,
        dry_run: bool = False,
        conflict_policy: str = "reject",
    ) -> PriceImportReport:
        resolved = _validate_input_path(path)
        source_hash = _file_hash(resolved)
        batch_id = f"price_batch_{uuid.uuid4().hex[:12]}"
        accepted = 0
        rejected = 0
        rejected_details: list[dict] = []
        blocking: list[str] = []
        rows_by_symbol: dict[str, list[dict]] = {}

        with resolved.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            required = {"symbol", "date", "open", "high", "low", "close", "volume", "adjusted"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise FactorDiscoveryError("STAGING_INPUT_SCHEMA", f"missing columns; need {sorted(required)}")
            for i, row in enumerate(reader, start=2):
                ok, err = validate_symbol(row["symbol"])
                if not ok:
                    rejected += 1
                    rejected_details.append({"line": i, "reason": err})
                    continue
                try:
                    adj = int(row.get("adjusted", "1"))
                    if adj not in (0, 1):
                        raise ValueError("adjusted must be 0 or 1")
                    for k in ("open", "high", "low", "close", "volume"):
                        float(row[k])
                    if float(row["close"]) <= 0:
                        raise ValueError("nonpositive close")
                except Exception as exc:
                    rejected += 1
                    rejected_details.append({"line": i, "reason": str(exc)})
                    continue
                sym = normalize_symbol(row["symbol"])
                rows_by_symbol.setdefault(sym, []).append(
                    {
                        "date": row["date"][:10],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                        "adjusted": adj,
                    }
                )
                accepted += 1

        if conflict_policy != "reject":
            blocking.append("unsupported_conflict_policy")

        if dry_run:
            return PriceImportReport(batch_id, accepted, rejected, source_hash, blocking, rejected_details)

        for sym, rows in rows_by_symbol.items():
            for r in rows:
                if r["adjusted"] != 1:
                    rejected += 1
                    rejected_details.append({"symbol": sym, "reason": "raw_row_rejected"})
                    continue
            adj_rows = [r for r in rows if r["adjusted"] == 1]
            if adj_rows:
                self._store.upsert_quotes(sym, adj_rows)

        from services.factor_discovery.evidence_paths import factor_discovery_paths

        meta_root = factor_discovery_paths().staging_input
        meta_root.mkdir(parents=True, exist_ok=True)
        meta = {
            "batch_id": batch_id,
            "provider_id": provider_id,
            "provider_data_version": provider_data_version,
            "policy_id": self._policy.policy_id,
            "source_file_hash": source_hash,
            "source_path": str(resolved.name),
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "actor": actor,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        (meta_root / "batches" / f"{batch_id}.json").parent.mkdir(parents=True, exist_ok=True)
        (meta_root / "batches" / f"{batch_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return PriceImportReport(batch_id, accepted, rejected, source_hash, blocking, rejected_details)
