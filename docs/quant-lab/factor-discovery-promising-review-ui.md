# Factor Discovery — promising review UI (Phase 9A)

## Panel

`PromisingReviewPanel` replaces the Phase 8B banner-only state.

Shows:

- Overall promising-policy result and policy version
- Rule-by-rule table (`RuleTable`: rule, actual, threshold, status, reason)
- Linked artifact, factor version, mining session IDs

Required disclaimers:

> This is promising research evidence, not investment approval.

> The sealed test remains unopened.

> No lifecycle promotion has occurred.

## Allowed actions (Phase 9A)

- View full closed artifact / validation result
- Compare factor versions (where supported)
- Pause or complete session (when server allows)

## Not available

- Open sealed test
- Mark validated / paper / production
- Add to Scan

Data source: `validation-result` → `promising_policy` payload (server-derived rules).
