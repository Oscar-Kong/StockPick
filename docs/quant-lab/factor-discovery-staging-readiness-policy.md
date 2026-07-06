# Factor Discovery — staging readiness policy

Policy ID: `factor_discovery_staging_readiness_v1`

## Status values

- `READY_FOR_EXTENDED_STAGING` — audits pass, reproducibility verified
- `READY_WITH_LIMITATIONS` — known documented limitations (e.g. delisting gap rate)
- `NOT_READY` — blocking data or reproducibility failures

Never returns `READY_FOR_PRODUCTION_SCAN`.

## Categories

Repository health · Data · Snapshots · Execution · Operations

Feature flags remain disabled by default after passing staging.
