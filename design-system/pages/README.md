# Page design overrides

Read **`design-system/MASTER.md`** first. Page files here override Master where specified.

Aligned with **`docs/UI_AUDIT_REVISED.md`** (June 2026 revised audit, Phase 0 baseline) and ui-ux-pro-max guidance.

## File map

| File | Route | Audit section |
|------|-------|---------------|
| `home.md` | `/` Today tab | §12.1 Portfolio/Home |
| `portfolio.md` | `/?tab=research\|activity` | §12.1 + §15 Phase 4 #2 |
| `scan.md` | `/scan` | §12.2 |
| `analyze.md` / `workspace.md` | `/workspace` | §12.3 (same scope; `workspace.md` is audit alias) |
| `quant-lab.md` | `/quant-lab` | §12.4 |
| `library.md` | `/library` | §12.5 |
| `settings.md` | `/settings` | §12.6 |

## Implementation order (from audit §15)

```text
Phase 0 — Baseline & verification (screenshots, inventory)
Phase 1 — Accessibility & navigation (focus, mobile nav, chart/heatmap a11y, Library errors)
Phase 2 — Semantic tokens (no global color codemod)
Phase 3 — Shared component consolidation (async shell, MetricTile wraps, chart wrapper)
Phase 4 — Page redesign (shell → Portfolio → Scan → Analyze → Quant Lab → Library → Settings polish)
Phase 5 — Light theme (Settings toggle)
Phase 6 — Cleanup
```

Do not start Phase 4 page work until Phase 0 browser validation confirms crowding/whitespace findings.
