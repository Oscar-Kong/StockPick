"""Versioned contracts for quant model outputs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ModelMetadata:
    """Metadata attached to prediction/allocation artifacts."""

    model_name: str
    model_version: str
    trained_at: datetime | None = None
    data_window: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "data_window": self.data_window,
        }

