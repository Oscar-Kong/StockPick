# Factor Discovery — Data Inventory

Field names and metadata taken from code in `backend/data/`, `backend/engines/`, `backend/scoring/`, and `backend/quant_core/`.  
**PIT** = point-in-time only where code explicitly supports historical `as_of` lookup or truncation.

---

## Summary by category

| Category | Research-ready | Display / live only | PIT-capable | Notes |
|----------|----------------|----------------------|-------------|-------|
| Prices (OHLCV) | Yes | Yes | Truncate by date | Mixed adjustment across providers |
| Returns | Derived | — | Yes (from truncated prices) | `quant_core/returns.py` |
| Volume | Yes | Yes | Truncate | |
| Volatility | Derived | Yes | Truncate | ATR, rolling std in `scoring/technical.py` |
| Liquidity | Partial | Yes | Truncate | `scoring/penny_liquidity.py` |
| Market cap | Partial | Yes | PIT sparse | `fundamentals_pit.market_cap` |
| Financial statements | Partial | Yes | PIT sparse (FMP) | Most fields live-only |
| Valuation | Partial | Yes | PIT: `pe_ratio` | Percentile factors need history |
| Profitability | Partial | Yes | PIT: `roe`, `profit_margin` | |
| Growth | Live info | Yes | No | `revenueGrowth`, `earningsGrowth` in info dict |
| Balance-sheet quality | Partial | Yes | No | `debtToEquity`, `goodwill` |
| Cash flow | Partial | Yes | No | `freeCashflow` |
| Analyst estimates | Partial | Yes | No | `eps_estimate` in medium_factors |
| Corporate actions | Implicit | — | Partial | Via adjusted flag (unreliable) |
| Sector / industry | Yes | Yes | Snapshot | `info.sector`, `info.industry` |
| Macroeconomic | Regime only | Yes | No | FRED via `fred_client`, OpenBB |
| Portfolio data | Yes | Yes | N/A | Holdings, ledger — not cross-sectional factors |
| Alternative / sentiment | Partial | Yes | No | StockTwits, Finnhub news |

---

## 1. Prices

### `daily_quotes` (`historical_store.py`)

| Field | Type | Source | Storage | Frequency | History |
|-------|------|--------|---------|-----------|---------|
| `open`, `high`, `low`, `close`, `volume` | Float | `PriceService` → `MarketDataClient` | SQLite/Postgres `daily_quotes` | Daily | Per-symbol, grows with scans/ingest |
| `adjusted` | Int flag | Set to `1` on write | Same | — | **Does not store adjustment factor** |

**Providers (priority from config):**

| Provider | File | Adjusted? | Notes |
|----------|------|-----------|-------|
| yfinance | `yfinance_client.py` | Yes (`auto_adjust=True`) | Default fallback |
| AkShare | `akshare_client.py` | **No** (`adjust=""`) | East Money US |
| FMP | `market_data_client.py` | Unadjusted | Daily bars |
| Alpha Vantage | `av_client.py` | Unadjusted | Fallback |

**Update:** On scan, analyze, or explicit history refresh (`PriceService.download_batch()`).

**Missing data:** Empty DataFrame → symbol skipped in Stage A/B; quality flags in `data_quality_flags`.

**PIT:** `scan_evaluation_pit.truncate_history(df, as_of)` — rows with `date > as_of` removed.  
**Not PIT:** No automatic correction for restatements.

**Survivorship:** Delisted symbols may retain history; universe filtered by current `listing_master`.

**Use:** Production Scan, research, display.

---

## 2. Returns

### Derived (not stored)

| Field | Computation | Module |
|-------|-------------|--------|
| `ret1` | `simple_returns(close)` | `quant_core/returns.py` |
| `log_ret` | `log_returns(close)` | same |
| `fwd_return_{h}` | `forward_return_label(prices, h)` | `quant_core/labels.py` |
| `fwd_excess_return_{h}` | vs benchmark | same |
| Forward % | `forward_return_pct()` | `scan_evaluation_pit.py` |

### `forward_return_labels` table (`quant_models.py`)

| Field | Notes |
|-------|-------|
| `fwd_return`, `excess_vs_spy`, `excess_vs_sector`, `max_drawdown`, `sector` | Unique on `(symbol, as_of_date, horizon_days)` |

**PIT:** Labels use future bars **only for evaluation**, never for factor input (`SCAN_EVALUATION.md`).

**Use:** Research, IC panel, walk-forward.

---

## 3. Volume

| Field | Source | Module |
|-------|--------|--------|
| `volume` | `daily_quotes` | — |
| `relative_volume` | `relative_volume_ratio_from_df()` | `scoring/penny_liquidity.py` |
| `avg_volume` | `avg_volume_from_history()` | `price_service.py` |
| `dollar_volume` | `close * volume` | `price_service.py`, Stage A |

**Factor IDs (v3):** `penny_rel_volume`, `penny_volume_surge` (`catalog_v3.py`).

---

## 4. Volatility

| Field | Source | Module |
|-------|--------|--------|
| ATR | TA on OHLC | `scoring/technical.py` |
| Rolling std of returns | `rolling_std()` | `quant_core/features.py` |
| `penny_intraday_vol` | High/low range proxy | `scoring/penny_factors.py` |
| Regime vol | SPY ATR proxy | `scoring/regime.py`, `engines/weighting/regime_classifier.py` |

**Use:** Production scoring, research. Full GARCH not implemented (`docs/QUANT_LAB.md`).

---

## 5. Liquidity

| Field | Source | Module |
|-------|--------|--------|
| `relative_volume` | Volume vs 20d avg | `penny_liquidity.py` |
| Spread proxy | High-low / close | `penny_liquidity.py` |
| `avg_dollar_volume` | 20d | `price_service.py` |
| ADV cap | Institutional backtest | `engines/backtest/institutional.py` |
| Penny friction | Spread + slippage haircut | `scan_evaluation_pit.apply_penny_friction()` |

**Stage A weights:** `rel_volume` in `PENNY_FEATURE_WEIGHTS` (`stage_a_ranking.py`).

---

## 6. Market capitalization

| Field | Sources | PIT? |
|-------|---------|------|
| `marketCap` / `market_cap` | yfinance info, AkShare, FMP, AV, OpenBB | `fundamentals_pit` metric `market_cap` (sparse) |
| `float_size` (penny v3) | `sharesOutstanding`, `floatShares`, `marketCap` | No |

**Reconciler canonical:** `market_cap` (`reconciler.py::FIELD_MAP`).

---

## 7. Financial statements

### Live / snapshot (`fundamental_snapshots.data_json`)

Nested `info` + `fundamentals` provider dicts. Key mapped fields via `fundamental_snapshot_service.py`:

- `revenueGrowth`, `earningsGrowth`, `profitMargins`, `grossMargins`, `operatingMargins`
- `freeCashflow`, `returnOnEquity`, `debtToEquity`
- `sector`, `industry`

**Frequency:** One row per symbol per calendar day (upsert).  
**PIT:** **No** — use `fundamentals_pit` instead.

### PIT (`fundamentals_pit`)

| Metric | Source | Ingest |
|--------|--------|--------|
| `pe_ratio`, `revenue_ttm`, `market_cap`, `roe`, `profit_margin` | Reconciler snapshot | `pit_fundamentals.persist_reconcile_as_pit` |
| `revenue_ttm`, `net_income`, `eps`, `operating_income` | FMP income statement | `pit_fmp_ingest.py` |

**Lookup:** `get_pit_metric(symbol, metric, as_of_date)` — latest where `as_of_date <= query`.

**Coverage:** ~40 SP500 symbols default for FMP ingest.  
**Publication delay:** `filing_date`, `available_to_model_at` columns exist; **not universally populated**.

---

## 8. Valuation

| Field | Source | Factor use |
|-------|--------|------------|
| `trailingPE` / `pe_ratio` | Reconciler | `compounder_pe_pct_5y` (needs 5y history — partial) |
| `priceToBook` / `pb_ratio` | Info dict | `compounder_pb_pct_5y` |
| `priceToSalesTrailing12Months` | Info dict | `compounder_ps_pct_5y` |
| DCF / reverse DCF | `engines/valuation/` | Analyze display, not factor panel |

**Warnings:** `valuation_warnings` in scoring — display strings.

---

## 9. Profitability

| Field | Reconciler / info | v3 factor |
|-------|-------------------|-----------|
| `returnOnEquity` / `roe` | Yes | `compounder_roic` (proxy) |
| `profitMargins` | Yes | `compounder_gross_operating_margin` |
| `grossMargins`, `operatingMargins` | Info | same |
| ROIC | Derived from margins + D/E | `scoring/compounder_v3.py` |

**PIT:** `roe`, `profit_margin` in `fundamentals_pit`.

---

## 10. Growth

| Field | Source | PIT? |
|-------|--------|------|
| `revenueGrowth` / `revenue_growth` | Info | No |
| `earningsGrowth` / `eps_growth` | Info | No |
| `revenue_growth_consistency` | Derived in compounder scorer | No |
| `dividendYield`, `payoutRatio` | Info | `compounder_dividend_growth` |

---

## 11. Balance-sheet quality

| Field | Source |
|-------|--------|
| `debtToEquity` / `debt_to_equity` | Info, reconciler |
| `goodwill`, `totalAssets` | Fundamentals dict |
| `share_dilution` | Derived in compounder mapper |

**Factors:** `compounder_debt_ratio`, `compounder_goodwill_ratio`.

---

## 12. Cash flow

| Field | Source |
|-------|--------|
| `freeCashflow` / `free_cash_flow` | Info |
| FCF yield | `freeCashflow / marketCap` | `compounder_fcf_yield` |

---

## 13. Analyst estimates / revisions

| Field | Source | Module |
|-------|--------|--------|
| `eps_estimate`, `eps_growth_estimate` | Info / fundamentals | `scoring/medium_factors.py` |
| Earnings calendar | Finnhub | `finnhub_client.get_earnings()` |
| Revisions engine | `engines/earnings/revisions.py` | Partial — not full estimate panel |

**PIT:** Not implemented for estimate revisions.

---

## 14. Corporate actions

| Mechanism | Status |
|-----------|--------|
| Split/dividend adjustment | Provider-dependent; `adjusted=1` flag only |
| Delist detection | `build_forward_outcomes()` `delisted` flag in scan eval |
| Listing status | `listing_master.py` current snapshot |

**Risk:** Mixed adjusted/unadjusted OHLC in same `daily_quotes` table.

---

## 15. Sector and industry

| Field | Source | Use |
|-------|--------|-----|
| `sector`, `industry` | `get_info()`, reconciler | Sector RS (`scoring/sector_strength.py`), ETF map |
| Sector ETF returns | Computed vs SPY | `medium_sector_rs` |
| Sector IC | `ic_panel._pooled_ic` `by_sector` | Research |

**PIT:** Sector as-of historical membership **not** stored — current `info.sector` at scoring time.

---

## 16. Macroeconomic data

| Series | Source | Module |
|--------|--------|--------|
| `FEDFUNDS`, `UNRATE`, `DGS10` | FRED / OpenBB | `fred_client.py`, `openbb_client.macro_regime_score()` |
| `macro_regime_score` | 0–100 scalar | Regime overlay |
| Quandl `WIKI/SPY` | Reference | `quandl_client.py` |

**Frequency:** Latest observation (90d window).  
**PIT:** **No** — uses latest value at scoring time.  
**Use:** Regime classification, display — not cross-sectional factor research v1.

---

## 17. Portfolio data

| Dataset | Storage | Module |
|---------|---------|--------|
| Holdings | Portfolio tables | `portfolio_summary_service.py` |
| Ledger / trades | SQLite | `integrations/robinhood/` |
| Policy backtest symbols | Experiment param | `portfolio_policy` template |

**Use:** Universe source for experiments (`portfolio_holdings` in `experiment_presets_service.py`), not factor inputs.

---

## 18. Alternative / sentiment data

| Source | Fields | Storage |
|--------|--------|---------|
| StockTwits | Sentiment score | Fetched live in `scoring/sentiment.py` |
| Finnhub news | `headline`, `sentiment_score` | Live fetch, 14d window |
| OpenBB SEC | Filings, insider trades | `openbb_client.py` |
| OpenBB governance | `governance_score`, flags | `OpenBBRiskSnapshot` |

**Factor:** `penny_social_sentiment`, `medium` sentiment leg, `{sleeve}_governance`.

**PIT:** **No** — live fetches at scoring time.

---

## 19. Factor snapshots (research panel)

### `factor_snapshots` (`historical_store.py`)

| Column | Content |
|--------|---------|
| `symbol`, `bucket`, `strategy_version`, `snapshot_date` | Keys |
| `factors_json` | `{signal_name: score}` e.g. `"5-day momentum": 72.3` |
| `score` | Composite |

**Source:** Written on each Stage B scan (`scan_manager.py`).  
**Export:** `scripts/factor_research_export.py` → `data_store/research/factor_panel.parquet`.

**PIT:** `snapshot_date` = run date; pair with truncated prices for research.

---

## 20. Feature provenance

### `feature_provenance` table

| Column | Purpose |
|--------|---------|
| `symbol`, `feature_name`, `as_of_date`, `data_value`, `source`, `filing_date` | Audit trail |

**Written by:** `feature_provenance.persist_feature_provenance()` from reconciler.  
**Use:** Compliance / debugging — not yet wired into factor DSL v1.

---

## 21. Universe coverage

| Universe | Builder | Survivorship |
|----------|---------|--------------|
| Penny seeds | `universe.py::PENNY_DISCOVERY_SEEDS` | Intersect `listing_master` |
| Compounder seeds | `COMPOUNDER_CANDIDATES` | Same |
| S&P500 overlay | Cache `universe:sp500` | Current membership |
| PIT universe | `universe_pit` + `active_symbols_on_date()` | **Only if seeded** |
| Walk-forward | `universe_for_date()` | Uses PIT when available |

**Delisted:** `STALE_OR_DELISTED` manual set in `universe.py`; no automatic historical delist DB.

---

## 22. DSL field whitelist (proposed v1)

Based on research-ready fields above:

**Tier A — always available (OHLCV panel):**
`open`, `high`, `low`, `close`, `volume`, `ret1`, `dollar_volume`

**Tier B — derived from Tier A:**
`ts_mean(close,n)`, `ts_std(ret1,n)`, `ts_corr(close,spy_close,n)`, `cs_rank(volume)`, etc.

**Tier C — PIT fundamentals (sparse):**
`pe_ratio`, `roe`, `profit_margin`, `revenue_ttm`, `market_cap`  
→ require `get_pit_metric()`; fail compile if missing coverage below threshold.

**Tier D — live-only (display / hypothesis context, not v1 DSL):**
sentiment, news, macro, analyst estimates.

---

## 23. Data gaps for rigorous factor discovery

| Gap | Severity | Mitigation in architecture |
|-----|----------|---------------------------|
| Mixed price adjustment | High | Compiler uses single provider per run; document in run metadata |
| Sparse `fundamentals_pit` | High | Tier C fields gated; min coverage check before compile |
| No historical sector membership | Medium | Exclude sector-neutral factors in v1 or use current sector with warning |
| No estimate revision PIT | Medium | Exclude from DSL v1 |
| `factor_values` table not wired | Low | Use `FactorDiscoveryRun` payload instead |
| Sentiment not historical | Low | Tier D — hypothesis only |

---

## Related

- [factor-discovery-audit.md](./factor-discovery-audit.md)
- [factor-discovery-architecture.md](./factor-discovery-architecture.md)
- [../SCAN_EVALUATION.md](../SCAN_EVALUATION.md)
- [../OPENBB.md](../OPENBB.md)
