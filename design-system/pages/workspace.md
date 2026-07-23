# Analyze — Research Workspace

> **Canonical page file:** This route uses the same scope as [`analyze.md`](./analyze.md).  
> **Audit filename:** `workspace.md` (§5.1, §15 Phase 0)  
> **Route:** `/workspace?symbol=` (legacy `/analyze` redirects here)

Read **`design-system/MASTER.md`** first, then **`analyze.md`** for full page-specific requirements.

## Quick reference

| Item | Value |
|------|-------|
| Route | `/workspace` |
| Legacy redirect | `/analyze` → `/workspace` |
| Primary components | `WorkspacePage`, `WatchlistRail`, `AnalysisPanel`, `AnalysisTabNav`, `DecisionOverview` |
| Sections | Overview · Drivers · Risk · Evidence · Research |
| Loading | Rail independent of symbol; snapshot → core |
| URL params | `symbol`, analysis tab state |
| Audit sections | `docs/UI_AUDIT_REVISED.md` §12.3 |

All makeover rules, preserved functionality, and Phase checklists are documented in **`analyze.md`**.
