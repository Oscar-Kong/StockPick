"""Neutralization operators for Factor Discovery execution."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engines.factor.discovery.execution_errors import NeutralizationError
from engines.factor.discovery.panel_models import FactorExecutionConfig, NeutralizationDiagnostics
from models.schemas_factor_discovery import NeutralizationKey


def _demean_by_group(
    values: pd.Series,
    groups: pd.Series,
    *,
    min_group_size: int,
    diag: NeutralizationDiagnostics,
) -> pd.Series:
    df = values.to_frame("v")
    df["g"] = groups.values
    df["td"] = df.index.get_level_values(0)
    counts = df.groupby(["td", "g"])["v"].transform("count")
    means = df.groupby(["td", "g"])["v"].transform("mean")
    demeaned = df["v"] - means
    demeaned = demeaned.where(df["g"].notna())
    demeaned = demeaned.where(counts >= min_group_size)
    diag.rows_missing_classification += int(df["g"].isna().sum())
    diag.rows_small_group += int(((counts < min_group_size) & df["g"].notna()).sum())
    diag.rows_neutralized += int(demeaned.notna().sum())
    diag.dates_processed = int(df["td"].nunique())
    diag.groups_processed = int(df.dropna(subset=["g"]).groupby(["td", "g"]).ngroups)
    return demeaned


def neutralize_sector(
    values: pd.Series,
    sector: pd.Series,
    config: FactorExecutionConfig,
) -> tuple[pd.Series, NeutralizationDiagnostics]:
    diag = NeutralizationDiagnostics(key=NeutralizationKey.SECTOR.value)
    if sector is None:
        raise NeutralizationError(code="missing_sector", message="sector classification required")
    out = _demean_by_group(values, sector, min_group_size=config.min_neutralization_group_size, diag=diag)
    return out, diag


def neutralize_industry(
    values: pd.Series,
    industry: pd.Series,
    config: FactorExecutionConfig,
) -> tuple[pd.Series, NeutralizationDiagnostics]:
    diag = NeutralizationDiagnostics(key=NeutralizationKey.INDUSTRY.value)
    if industry is None:
        raise NeutralizationError(code="missing_industry", message="industry classification required")
    out = _demean_by_group(values, industry, min_group_size=config.min_neutralization_group_size, diag=diag)
    return out, diag


def neutralize_market_cap(
    values: pd.Series,
    market_cap: pd.Series,
    eligibility: pd.Series,
    config: FactorExecutionConfig,
) -> tuple[pd.Series, NeutralizationDiagnostics]:
    diag = NeutralizationDiagnostics(key=NeutralizationKey.MARKET_CAP.value)
    out = pd.Series(np.nan, index=values.index, dtype=float)

    for date, day_vals in values.groupby(level="date"):
        idx = day_vals.index
        elig = eligibility.loc[idx].astype(bool)
        y = day_vals.where(elig)
        mc = market_cap.loc[idx]
        valid = elig & y.notna() & (mc > 0)
        y = y.loc[valid]
        mc = mc.loc[valid.index]
        if len(y) < config.min_cross_sectional_observations:
            diag.rows_small_group += int(elig.sum())
            diag.dates_processed += 1
            continue
        x = np.log(mc.to_numpy(dtype=float))
        yv = y.to_numpy(dtype=float)
        if np.std(x) == 0.0:
            diag.regression_failures += len(y)
            diag.dates_processed += 1
            continue
        design = np.column_stack([np.ones(len(x)), x])
        beta, _, _, _ = np.linalg.lstsq(design, yv, rcond=None)
        resid = yv - design @ beta
        out.loc[y.index] = resid
        diag.rows_neutralized += len(y)
        diag.dates_processed += 1

    return out, diag
