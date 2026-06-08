# Analyze Sector — Technical Report

Engineering reference for the **Research / Analyze** slice of Stock Picker: APIs, data flow, scoring, quant v2 hooks, reports, and UI. For investor-facing usage, see [ANALYZE_PANEL.md](ANALYZE_PANEL.md).

---

## 1. Scope

The **analyze sector** is everything that deep-dives a symbol after screening:

| Surface | Role |
|---------|------|
| **Workspace → Research** | Primary UX: watchlist rail + `AnalysisPanel` |
| **Workspace → Compare** | 2–4 symbol side-by-side (lightweight) |
| **`/analyze/*` API** | v1 stable contract for symbol, watchlist matrix, compare, reports |
| **`/api/v2/*` API** | Parallel quant layer (score, risk, sizing, report) — does not replace v1 shape |
| **Library** | Persisted analyze snapshots and research reports |

Out of scope here: scan pipeline (`routes_scan.py`), portfolio optimizer, trade journal (except cross-links).

---

## 2. System diagram

```mermaid
flowchart TB
  subgraph UI
    WR[WatchlistRail]
    AP[AnalysisPanel]
    CP[ComparePanel]
    RR[ResearchReport]
    ASB[AnalysisSidebar]
  end

  subgraph API_v1["/analyze"]
    AW[GET /watchlist]
    AS[GET /{symbol}]
    AC[GET /compare]
    ABF[GET /{symbol}/bucket-fit]
    AR[GET /{symbol}/report]
  end

  subgraph API_v2["/api/v2 optional"]
    V2S[GET /score/{symbol}]
    V2R[GET /risk/{symbol}]
    V2Z[GET /sizing/{symbol}]
    V2P[GET /report/{symbol}]
  end

  subgraph Services
    AN[analyze_service.py]
    WS[watchlist_scanner.py]
    RRv1[research_report.py]
    RRv2[research_report_v2.py]
    Q2[quant_v2_service.py]
  end

  subgraph Data
    PS[PriceService]
    REC[DataReconciler]
    CACHE[(SQLite cache + snapshots)]
    SCR[screeners/*]
  end

  WR --> AW
  AP --> AS
  AP --> AR
  AP --> V2Z
  AP --> V2R
  CP --> AC
  ASB --> AP

  AW --> AN
  AS --> AN
  AC --> AN
  ABF --> AN
  AR --> RRv1
  AR --> RRv2

  AN --> WS
  AN --> PS
  AN --> REC
  AN --> SCR
  AN --> Q2
  RRv2 --> Q2
  AN --> CACHE
```

---

## 3. API reference (analyze sector)

### 3.1 v1 — stable (`routes_analyze.py`)

| Method | Path | Purpose | Timeout config |
|--------|------|---------|----------------|
| GET | `/analyze/watchlist` | Rows for workspace rail (scores, technicals, alerts) | — |
| GET | `/analyze/{symbol}` | Full symbol analysis | `ANALYZE_ROUTE_TIMEOUT_SECONDS` |
| GET | `/analyze/{symbol}?include_bucket_fit=true` | + penny/medium/compounder scores | same |
| GET | `/analyze/{symbol}?refresh=true` | Bypass in-memory cache | same |
| GET | `/analyze/{symbol}/bucket-fit` | Three-sleeve scores only | same |
| GET | `/analyze/compare?symbols=A,B` | Max 4 symbols | `COMPARE_ROUTE_TIMEOUT_SECONDS` |
| GET | `/analyze/{symbol}/report` | Research memo JSON (v1 or v2 per flag) | `REPORT_ROUTE_TIMEOUT_SECONDS` |

All heavy routes run in a thread pool; on timeout, analyze may return last cached payload or `504`.

**Response contract:** `AnalyzeSymbolResponse` in `models/schemas.py` — unchanged for v1 clients. Quant v2 fields are **not** injected into this object unless explicitly added behind flags in the future.

### 3.2 v2 — parallel (`routes_v2.py`)

Used by sidebar blocks and report v2; optional from the UI:

| Method | Path | When used in Analyze UI |
|--------|------|-------------------------|
| GET | `/api/v2/score/{symbol}?sleeve=` | Validation / future factor rail |
| GET | `/api/v2/risk/{symbol}` | Unified risk breakdown |
| GET | `/api/v2/sizing/{symbol}` | `PositionSizingBlock` when `POSITION_SIZING_V2=true` |
| GET | `/api/v2/report/{symbol}` | Same JSON as report route when `AI_REPORT_SCHEMA=v2` |

See [API_REFERENCE.md](API_REFERENCE.md) for full v2 surface.

### 3.3 Persistence (`routes_saved.py`)

| Artifact | Trigger |
|----------|---------|
| Analyze snapshot | Every successful `GET /analyze/{symbol}` |
| Report snapshot | Successful `GET /analyze/{symbol}/report` (auto-save) |
| Manual report save | `POST /reports` from UI |

Home dashboard **Continue** links read `GET /saved/progress` (latest analyze / scan / report).

---

## 4. Core service: `analyze_service.py`

### 4.1 `build_symbol_analysis(symbol, bucket)`

1. **`analyze_symbol`** (`watchlist_scanner.py`) — runs sleeve screener: enrich → hard filter → score → risk label.
2. **`DataReconciler.reconcile`** — canonical fundamentals + quality score + flags.
3. **`_quick_technicals`** — trend, breakout, RS vs SPY, % from 52w high (1y OHLC).
4. **`compute_alerts`** — earnings, stale, score drop, valuation, governance, reconcile.
5. **OHLC tail** — last 120 daily bars for chart tab.
6. **Cache** — key `analyze:{SYMBOL}:{bucket}`, TTL `ANALYZE_RESULT_TTL`.
7. **Quant hook** — `maybe_persist_from_analysis()` when `PERSIST_SCORE_ATTRIBUTION=true` writes `score_attribution` / `risk_scores`.

Optional `include_bucket_fit=True` calls `score_all_buckets()` (3× screener — slower).

### 4.2 `build_watchlist_matrix()`

Lightweight pass over watchlist rows:

- Technicals from DB-only quotes when possible (`db_only=True`).
- Alerts from watchlist metadata (no full re-score).
- Sort: alert count desc, then score desc.

Powers **WatchlistRail** without N full analyzes.

### 4.3 `build_compare(symbols)`

- Prefers watchlist cache per symbol.
- Reconcile + technicals for each.
- Off-watchlist symbols: single `analyze_symbol(..., "auto")` if no score.
- Highlights: highest score, best RS vs SPY, best data quality.

### 4.4 `score_all_buckets(symbol)`

Runs penny, medium, compounder screeners independently; returns scores, hard-filter pass, top signals, `best_bucket`.

---

## 5. Scoring stack (legacy path)

```
screeners/{penny,medium,compounder}.py
  → hard_filter(ScanOptions)
  → score(ctx) → signals[], risk, metrics
scoring/data_quality.py → adjust_score_for_data_quality
services/market_context.py → enrich_metrics (regime, OpenBB when enabled)
```

**Assigned bucket** comes from watchlist tag or screener default (medium).

When quant v2 flags are on, parallel path in `quant_v2_service.build_v2_score`:

- `ScoringEngine` + `RiskEngine` + optional dynamic weights (`DYNAMIC_WEIGHTS_ENABLED`)
- Factor catalog v1 or v3 (`SLEEVE_FACTORS_V3_ENABLED`)
- Parity check vs legacy `analyze_symbol` score (`parity_delta`)

v1 analyze response remains the **source of truth for the UI headline score** today.

---

## 6. Research reports

### 6.1 v1 (`research_report.py`)

Eight-section dict; LLM optional per section. Used when `AI_REPORT_SCHEMA=v1` (default).

### 6.2 v2 (`research_report_v2.py`)

Ten-section JSON validated against [schemas/ai_research_report_v2.schema.json](schemas/ai_research_report_v2.schema.json).

Built from:

- `build_v2_score` — factors, attribution, regime
- `build_unified_risk` — macro / company / events
- `build_position_sizing` — when enabled
- Fundamentals, technicals, valuation warnings, structure analysis

**Routing:** `GET /analyze/{symbol}/report` branches on `AI_REPORT_SCHEMA`. v2 reports auto-save to Library and `ai_reports_v2` table when persisted.

### 6.3 UI

| Component | Tab / area |
|-----------|------------|
| `ResearchReport.tsx` | AnalysisPanel → Report tab |
| Save to Library | `saveReportSnapshot` in `AnalysisPanel` |

---

## 7. Frontend composition

| File | Responsibility |
|------|----------------|
| `WorkspacePage.tsx` | Shell: rail + tabs (Research / Compare / Journal) |
| `WatchlistRail.tsx` | Symbol list, filter, import, refresh |
| `AnalysisPanel.tsx` | Tabs: overview, quant, data, chart, backtest, report |
| `AnalysisSidebar.tsx` | Technicals, alerts, optional v2 risk/sizing fetch |
| `ScoreBreakdown.tsx` | Factor bars (legacy signals) |
| `ComparePanel.tsx` | Metric table, best-column highlight |
| `PositionSizingBlock.tsx` | v2 sizing when flag on |

**Deep link:** `/workspace?symbol=NVDA` (and `?tab=compare|journal`).

Legacy redirects: `/analyze`, `/watchlist` → `/workspace`.

---

## 8. Configuration flags (analyze-relevant)

| Flag | Effect |
|------|--------|
| `ANALYZE_RESULT_TTL` | In-memory analyze cache seconds |
| `ANALYZE_ROUTE_TIMEOUT_SECONDS` | Symbol / bucket-fit timeout |
| `COMPARE_ROUTE_TIMEOUT_SECONDS` | Compare timeout |
| `REPORT_ROUTE_TIMEOUT_SECONDS` | Report generation timeout |
| `OPENBB_ON_SCAN` | Usually off; analyze may still use OpenBB via metrics |
| `OPENBB_ENABLED` | Governance / macro in alerts and metrics |
| `SCORE_ENGINE_V2_ENABLED` | v2 score API + report inputs |
| `PERSIST_SCORE_ATTRIBUTION` | DB rows on each analyze |
| `RISK_ENGINE_V2` | Unified risk deduction in v2 |
| `POSITION_SIZING_V2` | Sizing block + report §9 |
| `AI_REPORT_SCHEMA` | `v1` vs `v2` report shape |
| `DYNAMIC_WEIGHTS_ENABLED` | v2 factor weights from IC panel |
| `SLEEVE_FACTORS_V3_ENABLED` | Expanded factor catalog |
| `TRADE_FEEDBACK_ENABLED` | Journal → prediction snapshot uses v2 score |

---

## 9. Caching & performance

| Layer | Key / store | Notes |
|-------|-------------|-------|
| In-memory | `Cache` `analyze:{sym}:{bucket}` | Fast repeat loads in same process |
| SQLite snapshots | `save_analyze_snapshot` | Survives restart; Library / progress |
| Price DB | `PriceService` DB-first | Watchlist matrix uses DB-only path |
| Report cache | v2: `Cache` 48h TTL | Stale report returned on timeout |

**Refresh** in UI sets `refresh=true` on analyze API. Watchlist **↻** calls watchlist refresh endpoints (separate from analyze cache).

---

## 10. Alerts model

`services/alerts.py` — shared by watchlist matrix, full analyze, and compare.

Typical alert types: `earnings_soon`, `stale`, `score_drop`, `low_data_quality`, `reconcile`, `valuation`, `governance` (OpenBB).

Alert count drives watchlist sort and rail badges.

---

## 11. Extension guide

| Change | Touch |
|--------|--------|
| New analyze tab | `AnalysisPanel.tsx` TABS + panel body; optional new API |
| New alert rule | `services/alerts.py` + doc in ANALYZE_PANEL.md |
| New factor (v2) | `engines/factor/`, `ScoringEngine`, catalog; wire `build_v2_score` |
| New report section (v2) | `research_report_v2.py` + JSON schema bump |
| Break v1 response | **Avoid** — add v2 fields or new endpoint instead |

Regression checks:

- `backend/tests/test_quant_v2_phase*.py` for quant path
- Manual: `GET /analyze/{symbol}` before/after flag changes
- Parity: `GET /api/v2/score/{symbol}?validate_parity=true`

---

## 12. Related documents

| Doc | Audience |
|-----|----------|
| [ANALYZE_PANEL.md](ANALYZE_PANEL.md) | Investors / operators |
| [INSTITUTIONAL_QUANT_ARCHITECTURE.md](INSTITUTIONAL_QUANT_ARCHITECTURE.md) | Quant v2 phases 1–7 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Whole-app map |
| [API_REFERENCE.md](API_REFERENCE.md) | HTTP catalog |
| [OPENBB.md](OPENBB.md) | Governance hooks in analyze |

---

## 13. Summary

The analyze sector is a **dual-track** design: **v1 analyze** delivers a stable, screener-based composite score and rich UI tabs; **quant v2** adds institutional attribution, risk, sizing, and structured reports behind flags without breaking existing clients. Workspace Research is the integration point—watchlist rail for breadth, AnalysisPanel for depth, Compare for quick ranking, Library for audit trail.

*Last aligned with quant v2 Phase 7 and Research UI refresh.*
