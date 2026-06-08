"""Versioned strategy definitions — factor weights and rule parameters."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from data.db_engine import get_engine

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    version_id = Column(String, primary_key=True)
    bucket = Column(String, nullable=False)
    config_json = Column(Text, nullable=False)
    changelog = Column(Text, default="")
    created_at = Column(DateTime, nullable=False)
    active = Column(String, default="true")


# Default strategy configs — simple, not over-tuned
DEFAULT_STRATEGIES: dict[str, dict[str, Any]] = {
    "penny_v1": {
        "bucket": "penny",
        "version": "penny_v1",
        "hold_horizon_days": 14,
        "weights": {
            "momentum": 0.25,
            "volume_spike": 0.25,
            "rsi": 0.15,
            "volatility_fit": 0.15,
            "sentiment": 0.20,
        },
        "hard_filters": {
            "min_price": 0.50,
            "max_price": 5.0,
            "min_volume": 500_000,
        },
        "backtest": {"hold_days": 10, "stop_pct": 0.10, "target_pct": 0.15},
    },
    "medium_v1": {
        "bucket": "medium",
        "version": "medium_v1",
        "hold_horizon_days": 20,
        "weights": {
            "trend": 0.20,
            "breakout": 0.20,
            "relative_strength": 0.20,
            "ml_signal": 0.15,
            "sector_strength": 0.10,
            "fundamentals": 0.15,
        },
        "hard_filters": {
            "min_price": 10.0,
            "max_price": 150.0,
            "min_volume": 1_000_000,
        },
        "backtest": {"hold_days": 20, "stop_pct": 0.07, "target_pct": 0.10},
    },
    "compounder_v1": {
        "bucket": "compounder",
        "version": "compounder_v1",
        "hold_horizon_days": 365,
        "weights": {
            "revenue_eps": 0.25,
            "roic_margin": 0.25,
            "moat_proxy": 0.20,
            "valuation": 0.15,
            "macro_regime": 0.15,
        },
        "hard_filters": {
            "min_market_cap": 5_000_000_000,
            "min_revenue_growth": 0.08,
        },
        "backtest": {"hold_days": 252, "stop_pct": 0.20, "target_pct": None},
    },
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_strategy_db() -> None:
    Base.metadata.create_all(bind=engine)
    registry = StrategyRegistry()
    registry.ensure_defaults()


@dataclass
class StrategyConfig:
    version_id: str
    bucket: str
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def weights(self) -> dict[str, float]:
        return self.config.get("weights", {})

    @property
    def backtest_params(self) -> dict[str, Any]:
        return self.config.get("backtest", {})


class StrategyRegistry:
    def __init__(self, session: Session | None = None):
        self._session = session

    def _get_session(self) -> Session:
        return self._session or SessionLocal()

    def ensure_defaults(self) -> None:
        session = self._get_session()
        try:
            for vid, cfg in DEFAULT_STRATEGIES.items():
                existing = session.get(StrategyVersion, vid)
                if not existing:
                    session.add(
                        StrategyVersion(
                            version_id=vid,
                            bucket=cfg["bucket"],
                            config_json=json.dumps(cfg),
                            changelog="Initial version",
                            created_at=_utcnow(),
                            active="true",
                        )
                    )
            session.commit()
        finally:
            if not self._session:
                session.close()

    def get_active(self, bucket: str) -> StrategyConfig:
        session = self._get_session()
        try:
            row = (
                session.query(StrategyVersion)
                .filter(StrategyVersion.bucket == bucket, StrategyVersion.active == "true")
                .order_by(StrategyVersion.created_at.desc())
                .first()
            )
            if row:
                return StrategyConfig(
                    version_id=row.version_id,
                    bucket=row.bucket,
                    config=json.loads(row.config_json),
                )
        finally:
            if not self._session:
                session.close()

        # Fallback to defaults
        default_key = f"{bucket}_v1"
        cfg = DEFAULT_STRATEGIES.get(default_key, {})
        return StrategyConfig(version_id=default_key, bucket=bucket, config=cfg)

    def get_current_version_id(self, bucket: str) -> str:
        return self.get_active(bucket).version_id

    def list_versions(self, bucket: str | None = None) -> list[dict]:
        session = self._get_session()
        try:
            q = session.query(StrategyVersion)
            if bucket:
                q = q.filter(StrategyVersion.bucket == bucket)
            rows = q.order_by(StrategyVersion.created_at.desc()).all()
            return [
                {
                    "version_id": r.version_id,
                    "bucket": r.bucket,
                    "changelog": r.changelog,
                    "created_at": r.created_at.isoformat(),
                    "active": r.active == "true",
                    "config": json.loads(r.config_json),
                }
                for r in rows
            ]
        finally:
            if not self._session:
                session.close()

    def register_version(
        self,
        version_id: str,
        bucket: str,
        config: dict,
        changelog: str = "",
        activate: bool = False,
    ) -> None:
        session = self._get_session()
        try:
            if activate:
                session.query(StrategyVersion).filter(StrategyVersion.bucket == bucket).update(
                    {"active": "false"}
                )
            session.merge(
                StrategyVersion(
                    version_id=version_id,
                    bucket=bucket,
                    config_json=json.dumps(config),
                    changelog=changelog,
                    created_at=_utcnow(),
                    active="true" if activate else "false",
                )
            )
            session.commit()
        finally:
            if not self._session:
                session.close()
