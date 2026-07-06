# Scan selection evaluation harness

Offline research tool that replays **Stage A → Stage B → final ranking** on historical dates and measures whether ranked candidates had useful forward returns.

**This does not change production scan behavior.** Results are evidence for later decisions only.

---

## What it measures

| Layer | Metrics |
|-------|---------|
| **Stage A recall** | Recall@10 / @20 / @50, cap sweep at different `stage_b_cap`, high-return names excluded by Stage A |
| **Ranking quality** | Rank IC, hit rate, score deciles (avg/median return, downside), MAE/MFE, sector concentration, turnover |
| **Forward labels** | 1 / 5 / 20 / 60 **trading sessions** (configurable) |

### Algorithm versions (labels)

| Version | Behavior |
|---------|----------|
| `alphabetical_baseline` | Sort by symbol — negative control |
| `stage_a_v1` | Final score = Stage A `pre_score` only (no Stage B) |
| `stage_a_v2` | Stage A → Stage B (legacy screener) → decomposed scores → final diversification |
| `scoring_engine_v1` | Same pipeline with `ScoringEngine` as Stage B scorer |

Each run stores `scoring_version` (`FACTOR_MODEL_VERSION`) and `strategy_version` (`STRATEGY_VERSION`) in the experiment JSON.

---

## Look-ahead controls

- OHLC features use `truncate_history(..., as_of)` — no bars after the scan date.
- Candidate build uses `reconcile=False` (no live provider fetch); fundamentals caveats are listed in output.
- Forward returns read **future** bars from the full panel **only for labels**, never for scoring.
- Universe: `universe_pit` when seeded; otherwise current universe with an explicit **survivorship bias** caveat.

---

## Quick start on a MacBook

Prerequisites: backend venv, DB with some cached OHLC (run at least one scan or ingest quotes for your test symbols).

```bash
cd backend
source .venv/bin/activate   # or your env
python -m data.cache init_db  # if needed

# Small smoke test — 8 symbols, 2 rebalance dates, alphabetical baseline
python scripts/run_scan_evaluation.py \
  --bucket penny \
  --start-date 2024-03-01 \
  --end-date 2024-05-01 \
  --algorithm-version alphabetical_baseline \
  --max-universe 8 \
  --stage-b-cap 8 \
  --max-results 5 \
  --forward-horizons 5,20 \
  --output-dir data/scan_eval
```

Expected runtime: seconds to ~1 minute on a laptop when OHLC is already in `HistoricalStore`.

### Slightly larger local run

```bash
python scripts/run_scan_evaluation.py \
  --bucket penny \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --algorithm-version stage_a_v2 \
  --max-universe 30 \
  --stage-b-cap 30 \
  --max-results 15 \
  --output-dir data/scan_eval
```

### Compare algorithm versions

```bash
python scripts/run_scan_evaluation.py \
  --bucket penny \
  --start-date 2024-01-01 \
  --end-date 2024-06-30 \
  --compare-versions alphabetical_baseline,stage_a_v1,stage_a_v2 \
  --max-universe 25 \
  --output-dir data/scan_eval
```

---

## Quant Lab integration

Run the same harness from **Quant Lab → Experiments → Scan Selection Evaluation** (`experiment_type: scan_evaluation`).

| Component | Path |
|-----------|------|
| Runner adapter | `services/scan_evaluation_experiment_runner.py` → `ScanEvaluationExperimentRunner.run()` |
| Chart adapter | `services/scan_evaluation_charts.py` → `charts_from_artifact()` |
| Launch | `services/experiment_launch_service.py` → `_run_scan_evaluation()` |
| Index | `services/research_run_service.py` → `adapter_scan_evaluation()` |
| Job stages | `services/experiment_job_service.py` → `stage_order_for_experiment("scan_evaluation")` |
| Results UI | `frontend/src/components/quant-lab/ScanEvaluationResultPanel.tsx` |

### Artifact layout (Quant Lab run)

```
data/scan_eval/{run_id}/
  summary.json              # full comparison payload
  charts.json               # chart JSON (see schema below)
  {version}/                # per-algorithm subdirs when comparing
    {experiment_id}_summary.json
    {experiment_id}_candidates.csv
    {experiment_id}_report.md
```

Runs are indexed in `backtest_runs` with `run_type=scan_evaluation`. Metrics live in `metrics_json` including `quant_lab.comparison_table`, `caveats`, and `artifact_paths`.

### `charts.json` schema (comparison mode)

```json
{
  "recall_by_version": [
    {"version": "alphabetical_baseline", "recall_at_10": 0.1, "recall_at_20": 0.2, "recall_at_50": 0.3}
  ],
  "hit_rate_by_horizon": [
    {"version": "stage_a_v2", "horizon": "5", "hit_rate": 0.55}
  ],
  "mean_rank_ic_by_horizon": [
    {"version": "stage_a_v2", "horizon": "20", "mean_rank_ic": 0.04}
  ],
  "decile_forward_returns": [
    {"version": "stage_a_v2", "decile": 1, "avg_forward_return_pct": -2.1}
  ]
}
```

Single-run mode uses the shape from `build_chart_series()` in `scan_evaluation_service.py` (decile curves, turnover, sector concentration when data exists). The UI renders only charts present in the artifact.

### Adding a scan algorithm version

1. Implement replay branch in `services/scan_evaluation_replay.py` and register the label in `SUPPORTED_ALGORITHM_VERSIONS`.
2. No Quant Lab changes required — pass the new version in `algorithm_versions`.
3. Re-run evaluation; comparison table and charts pick up the new row automatically.

### Smoke preset (`scan_eval_smoke`)

Available in Experiment Studio presets: ~2-month window, `max_universe=8`, horizons `[5]`, algorithms `alphabetical_baseline` vs `stage_a_v2`. **Smoke test only** — not for production decisions.

### Limitations (unchanged)

- Survivorship bias when `universe_pit` is empty
- Historical OHLC / fundamental availability gaps
- Penny friction models are approximate
- **Evaluation does not change production scan configuration automatically**

---

## Outputs (CLI)

Written under `--output-dir` (default `data/scan_eval/`):

| File | Contents |
|------|----------|
| `{experiment_id}_summary.json` | Full config, per-date snapshots, aggregated summary |
| `{experiment_id}_candidates.csv` | One row per symbol × rebalance date with scores and forward returns |
| `{experiment_id}_report.md` | Concise human-readable summary |
| `{experiment_id}_charts.json` | ChartSeries-style JSON for Quant Lab / `ResultChart` |

---

## Penny realism caveats

When `--bucket penny` (default friction **on**):

- Spread + slippage haircuts (`--spread-bps`, `--slippage-bps`)
- Extra liquidity penalty when ADV &lt; $500k
- Incomplete forward windows flagged (delist / missing sessions)
- Report repeats survivorship and split-adjustment limitations

Disable friction for gross-return analysis: `--no-penny-friction`.

---

## Module map

| Module | Role |
|--------|------|
| `services/scan_evaluation_pit.py` | PIT truncate, forward returns, MAE/MFE, penny friction |
| `services/scan_evaluation_metrics.py` | Deciles, Stage A recall, ranking quality aggregates |
| `services/scan_evaluation_replay.py` | Single-date historical replay |
| `services/scan_evaluation_service.py` | Multi-date experiment orchestration + report writers |
| `scripts/run_scan_evaluation.py` | CLI entry point |
| `tests/test_scan_evaluation.py` | Leakage, windows, deciles, recall, determinism |

---

## Seeding PIT universe (optional)

To reduce survivorship bias, seed `universe_pit` for historical dates before evaluating:

```python
from engines.backtest.universe_pit import seed_universe_pit
seed_universe_pit(["AAPL", "MSFT", ...], as_of_date="2024-03-01", bucket_hint="penny")
```

Without this, the harness uses the current universe list and documents the limitation.

---

## Related docs

- [RUNBOOK.md](RUNBOOK.md) — scan scoring modes and final ranking env vars
- [INSTITUTIONAL_QUANT_ARCHITECTURE.md](INSTITUTIONAL_QUANT_ARCHITECTURE.md) — portfolio backtests (separate from scan eval)
- Walk-forward engine research: `scripts/run_walk_forward_research.py` (ScoringEngine-only, no Stage A)

---

## What this is not

- Not a fill simulator or trade P&amp;L backtester
- Not an auto-tuner for production weights
- Not a substitute for paper trading or staging parity runs (`run_staging_scan_parity.py`)

Use staging parity for **score regression**; use this harness for **selection quality over time**.
