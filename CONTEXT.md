# StockPick

Local-first US equities research and decision-support. Two active strategy sleeves: penny (short-term momentum) and compounder (long-term quality).

## Product surfaces

**Scan**:
The production stock-screening workflow. Runs Stage A (bulk filter + preliminary rank) then Stage B (deep scoring) and persists ranked candidates. A new scan updates live rankings.
_Avoid_: Screen (as a system name), screener run (when meaning the full Scan product flow)

**Quant Lab**:
The research, validation, experiment, and evaluation environment. Loads persisted evidence, runs heavy jobs on demand, produces reviewable findings and change proposals. Does not change today's live scan rankings.
_Avoid_: Research console (generic), backtest page (too narrow)

**Workspace**:
Watchlist plus single-symbol deep analysis. Explains one candidate; does not re-rank the universe.
_Avoid_: Research (route name in older docs — UI nav says Workspace)

**Portfolio**:
The unified home workspace at `/` with Today (daily decisions), Research (optimize / backtest / exposure), and Activity (CSV import, ledger). Decision-support only.
_Avoid_: Home (acceptable in conversation but Portfolio is the product name), trading desk, execution layer

**Library**:
Saved scans, research reports, and analyze snapshots for later review.
_Avoid_: Archive, reports folder

## Screening and scoring

**Sleeve** (or **bucket**):
A strategy profile that controls universe filters and scoring emphasis. Active: `penny`, `compounder`. Legacy `medium` normalizes to `penny`.
_Avoid_: Strategy, theme (unless Trader Intel preset)

**Stage A**:
Fast cross-sectional pass: eligibility filter, momentum/volume/liquidity features, `pre_score` rank; advances top-N to Stage B.
_Avoid_: Pre-screen, filter step

**Stage B**:
Deep scoring for Stage A survivors: technical, fundamental, sentiment, data quality, optional governance.
_Avoid_: Full scan (ambiguous — Scan is the whole pipeline)

**Recommendation**:
A model-generated buy / hold / sell stance with confidence, attribution, and supporting evidence. Research output, not financial advice or an order.
_Avoid_: Signal (too vague), trade (implies execution)

**Evidence**:
Persisted, reviewable quant artifacts: factor IC, walk-forward runs, prediction outcomes, experiment results, scan-evaluation reports. Quant Lab surfaces evidence; Scan consumes scoring outputs.
_Avoid_: Proof (informal), metrics dump

**Change proposal**:
A reviewable draft in Quant Lab describing a scoring or policy change. Never auto-applied to production Scan.
_Avoid_: PR (code sense), config patch

## Portfolio and decisions

**Daily decision**:
Model-generated buy / keep / sell guidance for holdings and opportunities on Portfolio → Today. Informs the user; does not execute trades.
_Avoid_: Auto-trade, rebalance order

**Ledger**:
Editable transaction history and Robinhood CSV import on Portfolio → Activity. Source of truth for holdings reconstruction.
_Avoid_: Journal (legacy route name)

## Research integrity

**Look-ahead bias**:
Using information not knowable at the decision date (future prices, unreleased fundamentals, post-as-of bars) in features or scoring.
_Avoid_: Future leak, peeking

**Survivorship bias**:
Evaluating only symbols that still exist today instead of the point-in-time universe.
_Avoid_: Current-universe backtest (when PIT universe was required)

**Alphabetical baseline**:
A scan-evaluation negative control that ranks by symbol name to detect universe-selection artifacts. Not a production algorithm.
_Avoid_: A–Z sort (informal)

**Point-in-time (PIT)**:
Data and universe constrained to what was knowable on an `as_of` date (`universe_pit`, `feature_provenance`, truncated history).
_Avoid_: Live snapshot (when historical replay is intended)
