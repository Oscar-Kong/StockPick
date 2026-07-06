"""Staging-only universe import with versioned config and batch artifacts."""
from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from data.db_engine import get_engine
from engines.quant_models import UniversePit
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.staging.calendar_policy import calendar_session_hash
from services.factor_discovery.staging.import_config import UniverseImportConfig, require_staging_mutations_enabled
from services.factor_discovery.staging.instrument_identity import StagingSymbolMappingService
from services.factor_discovery.staging.policies import UniversePitMembershipPolicy
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService
from sqlalchemy.orm import Session


@dataclass
class UniverseImportReport:
    batch_id: str
    rows_read: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    daily_rows_generated: int = 0
    source_file_hash: str = ""
    config_hash: str = ""
    calendar_hash: str | None = None
    symbol_mapping_hash: str | None = None
    blocking_codes: list[str] = field(default_factory=list)
    rejected_details: list[dict] = field(default_factory=list)
    status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "rows_read": self.rows_read,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "daily_rows_generated": self.daily_rows_generated,
            "source_file_hash": self.source_file_hash,
            "config_hash": self.config_hash,
            "calendar_hash": self.calendar_hash,
            "symbol_mapping_hash": self.symbol_mapping_hash,
            "blocking_codes": self.blocking_codes,
            "rejected_details": self.rejected_details[:50],
            "status": self.status,
        }


def _batch_dir() -> Path:
    from services.factor_discovery.evidence_paths import factor_discovery_paths

    batches = factor_discovery_paths().staging_input / "batches"
    batches.mkdir(parents=True, exist_ok=True)
    return batches


class FactorDiscoveryStagingUniverseImporter:
    def __init__(self, policy: UniversePitMembershipPolicy | None = None) -> None:
        self._policy = policy or UniversePitMembershipPolicy()

    def import_from_config(self, cfg: UniverseImportConfig, *, dry_run: bool = False) -> UniverseImportReport:
        if not dry_run:
            require_staging_mutations_enabled()
        if cfg.environment not in {"staging", "test", "development"}:
            raise FactorDiscoveryError("STAGING_CONFIG_ENVIRONMENT", cfg.environment)

        source_hash = f"sha256:{hashlib.sha256(cfg.input_path.read_bytes()).hexdigest()}"
        batch_id = f"universe_batch_{uuid.uuid4().hex[:12]}"
        report = UniverseImportReport(
            batch_id=batch_id,
            source_file_hash=source_hash,
            config_hash=cfg.config_hash,
        )

        sessions = FactorDiscoveryUniverseAuditService.load_trading_sessions(
            start=cfg.research_start,
            end=cfg.research_end,
        )
        if not sessions:
            report.blocking_codes.append("no_trading_sessions_in_range")
            report.status = "failed"
            return report
        report.calendar_hash = calendar_session_hash(sessions)

        intervals: list[dict] = []
        mapper = StagingSymbolMappingService(mapping_version=cfg.symbol_mapping_version)
        with cfg.input_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            required = {"symbol", "effective_start"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise FactorDiscoveryError("STAGING_INPUT_SCHEMA", f"missing columns {required}")
            for i, row in enumerate(reader, start=2):
                report.rows_read += 1
                try:
                    mapping = mapper.resolve(str(row["symbol"]), exchange=row.get("exchange"))
                except ValueError as exc:
                    report.rows_rejected += 1
                    report.rejected_details.append({"line": i, "reason": str(exc)})
                    continue
                intervals.append(
                    {
                        "symbol": mapping.canonical_symbol,
                        "instrument_id": mapping.instrument_id,
                        "effective_start": row["effective_start"][:10],
                        "effective_end": (row.get("effective_end") or sessions[-1])[:10],
                        "bucket_hint": f"staging:{cfg.universe_id}",
                        "source_id": cfg.source_id,
                        "source_version": cfg.source_version,
                        "eligibility_reason": row.get("eligibility_reason", "interval_membership"),
                    }
                )
                report.rows_accepted += 1

        mapping_report = mapper.resolve_many([{"symbol": iv["symbol"]} for iv in intervals])
        report.symbol_mapping_hash = mapping_report.mapping_hash()
        if mapping_report.ambiguous:
            report.blocking_codes.append("ambiguous_symbol_mappings")
            report.status = "failed"
            return report

        end_inclusive = cfg.effective_date_policy.endswith("inclusive_end")
        daily = FactorDiscoveryUniverseAuditService.expand_interval_membership(
            intervals,
            sessions=sessions,
            effective_end_inclusive=end_inclusive,
        )
        report.daily_rows_generated = len(daily)
        if report.daily_rows_generated == 0:
            report.blocking_codes.append("no_daily_membership_generated")
            report.status = "failed"
            return report

        if dry_run:
            report.status = "dry_run_ok"
            self._persist_batch_meta(cfg, report, intervals_count=len(intervals), dry_run=True)
            return report

        try:
            with Session(get_engine()) as session:
                if cfg.conflict_policy == "replace_staging_bucket":
                    session.query(UniversePit).filter(UniversePit.bucket_hint.like("staging:%")).delete(
                        synchronize_session=False
                    )
                elif cfg.conflict_policy == "reject":
                    for row in daily[:500]:
                        existing = session.get(UniversePit, (row["as_of_date"], row["symbol"]))
                        if existing and not str(existing.bucket_hint or "").startswith("staging:"):
                            report.blocking_codes.append("conflict_with_existing_membership")
                            report.status = "failed"
                            session.rollback()
                            return report

                for row in daily:
                    existing = session.get(UniversePit, (row["as_of_date"], row["symbol"]))
                    if existing:
                        existing.is_active = row["is_active"]
                        existing.bucket_hint = row["bucket_hint"]
                    else:
                        session.add(
                            UniversePit(
                                as_of_date=row["as_of_date"],
                                symbol=row["symbol"],
                                bucket_hint=row["bucket_hint"],
                                is_active=row["is_active"],
                            )
                        )
                session.commit()
        except Exception:
            report.blocking_codes.append("import_transaction_failed")
            report.status = "failed"
            raise

        report.status = "committed"
        self._persist_batch_meta(cfg, report, intervals_count=len(intervals), dry_run=False)
        return report

    def _persist_batch_meta(
        self,
        cfg: UniverseImportConfig,
        report: UniverseImportReport,
        *,
        intervals_count: int,
        dry_run: bool,
    ) -> None:
        meta = {
            "batch_id": report.batch_id,
            "universe_id": cfg.universe_id,
            "source_id": cfg.source_id,
            "source_version": cfg.source_version,
            "policy_id": self._policy.policy_id,
            "source_file_hash": report.source_file_hash,
            "config_hash": report.config_hash,
            "calendar_hash": report.calendar_hash,
            "symbol_mapping_hash": report.symbol_mapping_hash,
            "intervals_read": intervals_count,
            "daily_rows_generated": report.daily_rows_generated,
            "rows_accepted": report.rows_accepted,
            "rows_rejected": report.rows_rejected,
            "actor": cfg.actor,
            "reason": cfg.reason,
            "dry_run": dry_run,
            "status": report.status,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        (_batch_dir() / f"{report.batch_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
