"""Point-in-time history truncation shared by eval, walk-forward, and scan replay."""
from __future__ import annotations

from datetime import date

import pandas as pd


def truncate_history(hist: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Keep rows with session date <= as_of (no look-ahead)."""
    if hist is None or hist.empty:
        return pd.DataFrame()
    df = hist.copy()
    if "date" not in df.columns:
        return pd.DataFrame()
    dates = pd.to_datetime(df["date"]).dt.date
    mask = dates <= as_of
    return df.loc[mask].reset_index(drop=True)
