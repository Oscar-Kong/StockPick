# Factor Discovery data provider (Phase 6A)

## Configuration

```bash
FACTOR_RESEARCH_DATA_PROVIDER=disabled   # default
# FACTOR_RESEARCH_DATA_PROVIDER=historical_store
# FACTOR_RESEARCH_DATA_PROVIDER=fixture    # test/development only
```

No fallback chain. Unknown values fail at provider resolution.

## Providers

| Provider | ID | Production |
|----------|-----|------------|
| `disabled` | `disabled_provider_v1` | Yes (default) |
| `historical_store` | `historical_store_v1` | When data passes capability checks |
| `fixture` | `fixture_provider_v1` | **No** — requires explicit `fixture_builder` |

## Historical store capabilities

`HistoricalStoreFactorResearchDataProvider` supports **price-only** research when:

- `daily_quotes` rows exist with `adjusted=1`
- `universe_pit` is non-empty for the requested range

**Not available (Phase 6A):**

- PIT fundamentals
- PIT sector/industry history
- Historical market cap

Use `assess_historical_store_capabilities()` or `factor_discovery_operational_status()` for blocking reasons.

## Snapshot format

Immutable snapshots use `factor_snapshot_csv_bundle_v1`:

- File: `{snapshot_id}.snapshot.json`
- Panel body: CSV with `float_format='%.15g'` (hash-stable roundtrip)
- Hashes recomputed on load; tampering raises `ARTIFACT_INTEGRITY_FAILURE`

## PIT universe

Empty or unverified `universe_pit` rejects materialization with `EMPTY_PIT_UNIVERSE`. Current listings are not substituted historically.

## Phase 6A non-goals

No live API fallback, no mixed adjusted/raw prices, no LLM workflow, no production Scan integration.
