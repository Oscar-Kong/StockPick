# OpenAlpha-Inspired Integration (US Equities)

Patterns adapted from [OpenAlpha](https://github.com/ziyouqitan/OpenAlpha) (CSI 500 / A-share). **Not a fork** — formulas are reimplemented on US OHLCV via your existing `PriceService`.

---

## What was added

| Piece | Location |
|-------|----------|
| Operator library (`ts_mean`, `ts_ols`, `cs_rank`, …) | `backend/engines/factor/operators.py` |
| US factor scorers (0–100) | `backend/scoring/openalpha_factors.py` |
| Formula registry (JSON) | `backend/engines/factor/openalpha_registry.json` |
| Expression loader | `backend/engines/factor/expr.py` |
| Live catalog merge (opt-in) | `backend/engines/factor/openalpha_catalog.py` |
| Live signal injection | `backend/engines/factor/openalpha_signals.py` |
| Batch IC evaluation | `backend/scripts/alpha_batch_eval.py` |
| Combo optimizer (heuristic) | `backend/scripts/alpha_combo_optimizer.py` |
| Tests | `backend/tests/test_openalpha_factors.py` |

---

## Formula registry

| ID | Sleeve | OpenAlpha ref | US implementation |
|----|--------|---------------|-----------------|
| `oa_penny_vwap_gap` | penny | 5000001 | 5d mean(VWAP − close) |
| `oa_penny_ols_residual` | penny | 5000006 | −OLS residual(price ~ return) |
| `oa_penny_vol_ret_corr` | penny | 5000010 | corr(rank volume, rank return) |
| `oa_medium_spy_corr` | medium | 5000012 | 20d corr with SPY returns |
| `oa_medium_ret_autocorr` | medium | 5000014 | return autocorrelation (OLS α) |
| `oa_medium_vol_asymmetry` | medium | 5000024 | std(low ret) − std(high ret) |

Edit weights or add formulas in `openalpha_registry.json`, then re-run batch eval before enabling live.

---

## Enable in live scans (optional)

Default: **off** (research-only).

```bash
# backend/.env
OPENALPHA_FACTORS_ENABLED=true
```

When on:

- Factors merge into `active_factor_catalog()` with renormalized base weights.
- Screeners append experimental legs via `append_openalpha_signals()`.
- IC panel includes `penny_oa_*` / `medium_oa_*` factor IDs.

Restart backend after changing `.env`.

---

## Research workflow

### 1. List formulas

```bash
cd backend
.venv/bin/python scripts/alpha_batch_eval.py --list
```

### 2. Batch IC on a universe

```bash
.venv/bin/python scripts/alpha_batch_eval.py --universe sp500 --export
# or
.venv/bin/python scripts/alpha_batch_eval.py --symbols AAPL,MSFT,NVDA,AMD,COST --export
```

Output: `backend/data_store/research/openalpha_batch_eval.json`

### 3. Single-factor validation (existing tool)

```bash
.venv/bin/python scripts/factor_validation.py --symbols AAPL,MSFT --factor vwap_close_gap
```

OpenAlpha keys: `vwap_close_gap`, `ols_price_residual`, `vol_ret_corr`, `spy_corr_20d`, `ret_autocorr`, `vol_asymmetry`.

### 4. Combo optimizer

After batch export:

```bash
.venv/bin/python scripts/alpha_combo_optimizer.py --sleeve medium --top 5 --export
```

Output: `backend/data_store/research/openalpha_combo_medium.json`

This is a **heuristic IC-weighted combo** — validate on forward labels (`factor_research_export.py`) before promoting weights.

### 5. Full factor panel (Round 2)

```bash
.venv/bin/python scripts/factor_research_export.py --factor medium_rs_vs_spy
.venv/bin/python scripts/factor_validation.py --panel --rebalance
```

---

## Sector-neutral operator

`cs_industry_neutral(values, groups)` in `operators.py` demeans within sector — use in future panel jobs when batch-evaluating cross-sectional alphas on full universes.

---

## What we did **not** import

- CSI 500 data or weights from OpenAlpha Google Drive bundle
- A-share T+1 / VWAP execution model
- `simres` expression engine (notebooks are reference only)

---

## Promotion checklist

Before setting `OPENALPHA_FACTORS_ENABLED=true` in production:

1. Batch IC `avg_ic` > 0.03 on your universe for that factor.
2. Quintile spread positive in `alpha_batch_eval` output.
3. No collapse in existing sleeve IC (`factor_validation.py --panel`).
4. Document weight change in commit / notes.

---

## See also

- [USER_GUIDE.md](USER_GUIDE.md) — when to use Screen vs Research vs offline research
- [QUANT_STACK.md](QUANT_STACK.md) — runtime planes
- [MANUAL_INTEGRATION.md](MANUAL_INTEGRATION.md) — ops checklist
