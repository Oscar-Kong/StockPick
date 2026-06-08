"""PCA on standardized return series (portfolio diagnostics)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MIN_OBS_PCA = 30
DEFAULT_PC1_CONCENTRATION_THRESHOLD = 0.45


def _standardize_returns(returns: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    clean = returns.dropna(how="any")
    symbols = [str(c).upper() for c in clean.columns]
    if clean.empty:
        return pd.DataFrame(), symbols

    mu = clean.mean()
    sd = clean.std(ddof=1).replace(0, np.nan)
    z = (clean - mu) / sd
    z = z.dropna(how="any")
    return z, symbols


def pca_standardized_returns(
    returns: pd.DataFrame,
    *,
    n_components: int | None = None,
    pc1_concentration_threshold: float = DEFAULT_PC1_CONCENTRATION_THRESHOLD,
) -> dict[str, Any]:
    """
    PCA on z-scored daily returns.

    Returns explained variance ratios, component loadings, symbol loading table,
    and a concentration warning when PC1 dominates.
    """
    z, symbols = _standardize_returns(returns)
    n_obs, n_sym = z.shape if not z.empty else (0, 0)

    if n_sym < 2 or n_obs < MIN_OBS_PCA:
        return {
            "sufficient": False,
            "observations": n_obs,
            "symbols": symbols,
            "n_components": 0,
            "explained_variance_ratio": [],
            "top_components": [],
            "symbol_loadings": [],
            "concentration_warning": False,
            "pc1_variance_ratio": None,
            "reason": "insufficient_observations",
        }

    k = n_components if n_components is not None else min(5, n_sym)
    k = max(1, min(k, n_sym))

    x = z.to_numpy(dtype=float)
    cov = np.cov(x, rowvar=False, ddof=1)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]

    total_var = float(eigvals.sum())
    if total_var <= 0:
        return {
            "sufficient": False,
            "observations": n_obs,
            "symbols": symbols,
            "n_components": 0,
            "explained_variance_ratio": [],
            "top_components": [],
            "symbol_loadings": [],
            "concentration_warning": False,
            "pc1_variance_ratio": None,
            "reason": "zero_variance",
        }

    ratios = (eigvals / total_var).tolist()
    explained = [round(float(r), 6) for r in ratios[:k]]

    top_components: list[dict[str, Any]] = []
    for i in range(k):
        loadings = eigvecs[:, i]
        comp = {
            "component": i + 1,
            "explained_variance_ratio": explained[i],
            "loadings": {
                symbols[j]: round(float(loadings[j]), 4) for j in range(len(symbols))
            },
        }
        top_components.append(comp)

    symbol_loadings: list[dict[str, Any]] = []
    for j, sym in enumerate(symbols):
        row: dict[str, Any] = {"symbol": sym}
        for i in range(k):
            row[f"pc{i + 1}"] = round(float(eigvecs[j, i]), 4)
        symbol_loadings.append(row)

    pc1_ratio = explained[0] if explained else 0.0
    concentration = pc1_ratio >= pc1_concentration_threshold

    return {
        "sufficient": True,
        "observations": n_obs,
        "symbols": symbols,
        "n_components": k,
        "explained_variance_ratio": explained,
        "cumulative_explained_variance": [
            round(float(sum(explained[: i + 1])), 6) for i in range(len(explained))
        ],
        "top_components": top_components,
        "symbol_loadings": symbol_loadings,
        "concentration_warning": concentration,
        "pc1_variance_ratio": pc1_ratio,
        "pc1_concentration_threshold": pc1_concentration_threshold,
    }
