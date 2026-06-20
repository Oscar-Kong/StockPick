# Quant Lab manual test checklist

Use with a **seeded demo DB** for deterministic results:

```bash
cd backend
python scripts/seed_quant_lab_demo.py --sleeve medium
DATABASE_URL=sqlite:///$(pwd)/../storage/dev/quant_lab_demo.db \
  python -m uvicorn main:app --port 18731
```

Frontend: `NEXT_PUBLIC_API_URL=http://127.0.0.1:18731 npm run dev`

---

## Page shell

- [ ] Open `/quant-lab` — no console errors
- [ ] All six tabs visible
- [ ] URL updates with `?tab=`
- [ ] Refresh preserves tab
- [ ] Browser back/forward works
- [ ] Invalid `?tab=foo` falls back to Factor Performance
- [ ] Evidence overview loads (expand section)
- [ ] Pairs evidence card shows a run after seed (not “No saved run”)

## Factor Performance

- [ ] Empty DB: explains how to run IC panel job
- [ ] Seeded DB: table shows factors with IC values
- [ ] Sleeve switch refetches
- [ ] Refresh works
- [ ] Stale badge when IC older than 7 days

## Walk-Forward

- [ ] Latest run hint on load (seeded DB)
- [ ] Invalid date range shows validation error
- [ ] Run button disabled while running
- [ ] Double-click does not submit twice
- [ ] Completed run persists after refresh

## Predictions

- [ ] Resolved and unresolved counts distinct
- [ ] Feedback partial failure still shows predictions
- [ ] No fake 0% for missing outcomes

## Pairs

- [ ] Last run hydrates on tab open (seeded DB)
- [ ] Run with 2+ symbols succeeds
- [ ] Evidence overview updates after new run
- [ ] Validation for &lt;2 symbols and &gt;20 symbols

## Data Quality

- [ ] Single health fetch (Network tab — one `getQuantHealthSummary` chain per refresh)
- [ ] Scheduler failure shows warning, health may still show
- [ ] Failed job count when applicable

## Model Admin

- [ ] Version, weights, audit, factors load independently
- [ ] One panel failure does not blank entire tab

## Research boundary

- [ ] Reliability cards state results do **not** change live scan rankings
- [ ] Research-only badges on walk-forward and pairs
