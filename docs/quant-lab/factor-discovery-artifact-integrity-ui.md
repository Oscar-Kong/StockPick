# Factor Discovery — artifact integrity UI (Phase 9A)

Validation detail: `GET /artifacts/{artifact_id}/validation-result`

## Integrity fields

```text
integrity_status: VERIFIED | NOT_VERIFIED | FAILED | UNAVAILABLE
integrity_checked_at
integrity_error_code
integrity_error_summary
```

## UI behavior

- `IntegrityBadge` on validation overview and consequential panels.
- When `integrity_status !== VERIFIED` or `trust_metrics` is false, metrics render dimmed with an alert; promising status is not shown as trusted.
- `FAILED` disables trust-sensitive actions client-side; server remains authoritative.
- No client override of integrity state; no display of corrupted payloads.

Session integrity: `GET /mining/sessions/{id}/integrity` (mining loop enabled).
