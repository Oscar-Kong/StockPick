# Quant Lab manual test checklist

Use with a **seeded demo DB** for deterministic results:

```bash
cd backend
python scripts/seed_quant_lab_demo.py --sleeve penny
DATABASE_URL=sqlite:///$(pwd)/../storage/dev/quant_lab_demo.db \
  .venv/bin/python -m uvicorn main:app --port 18731
```

Frontend: `NEXT_PUBLIC_API_URL=http://127.0.0.1:18731 npm run dev`

---

## Full workflow (18 steps)

- [ ] **1.** Open `/quant-lab` — lands on Overview (`?section=overview`)
- [ ] **2.** Review confidence score, freshness, versions, prediction counts
- [ ] **3.** Read a data-backed finding in the research brief
- [ ] **4.** Click **Generate ideas** or open Ideas → manual create
- [ ] **5.** Edit idea title/hypothesis/notes and save
- [ ] **6.** **Configure experiment** from an idea → Experiment Studio opens
- [ ] **7.** Choose template, select preset (Quick / Standard / Robust)
- [ ] **8.** Review validation panel — data sufficiency + hypothesis checks
- [ ] **9.** Launch experiment — job starts
- [ ] **10.** Observe job stages on Status step (poll stops on complete/fail)
- [ ] **11.** Open persisted result from Result step or Results section
- [ ] **12.** Read verdict, limitations, evidence impact on detail view
- [ ] **13.** Duplicate experiment with changed parameters
- [ ] **14.** Select 2–4 runs → Compare compatible results
- [ ] **15.** Create follow-up idea from a result
- [ ] **16.** Create change proposal (from evidence review or proposal API)
- [ ] **17.** Review finding in Model Monitor → Evidence review
- [ ] **18.** Hard refresh browser — section URL, ideas, runs, notes persist

---

## Primary sections

- [ ] Overview — single `GET /overview` fetch (Network tab)
- [ ] Ideas — filter, search, archive, duplicate
- [ ] Experiments — all six templates visible on Choose step
- [ ] Results — pagination (20/page), filters (type, verdict, impact, status)
- [ ] Model Monitor — factor, prediction, data, jobs, config, audit, evidence review
- [ ] Legacy tools — factor, walk-forward, predictions, pairs tabs

## States to spot-check

| State | Where |
|-------|-------|
| Loading | Any section first paint |
| Empty | Ideas with no rows, Results with empty index |
| Ready | Overview with seeded brief |
| Queued / running | Experiment job status step |
| Success | Completed run in Results |
| Partial success | Predictions tab with feedback failure |
| Insufficient data | Validation panel before launch |
| Invalid input | WF date range, pairs &lt;2 symbols |
| Feature disabled | Legacy tab when flag off |
| Failed job | Model Monitor jobs + retry (duplicate blocked) |
| Stale evidence | Trust badge on legacy factor tab |
| Integrity blocker | Model Monitor data health list |

## Research boundary

- [ ] Research-only badge visible on Overview and Experiment Studio
- [ ] Reliability cards state results do **not** change live scan rankings
- [ ] No auto-apply of weights from completed experiments

## Console

- [ ] No `pageerror` on Overview, Ideas, Experiments, Results, Model Monitor
- [ ] Partial API failure (503 on overview) shows ErrorState + retry — not blank panel
