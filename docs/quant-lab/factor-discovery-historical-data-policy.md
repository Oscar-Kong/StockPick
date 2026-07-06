# Factor Discovery — historical adjusted price policy

Policy ID: `historical_adjusted_prices_v1`

## Semantics

- Provider: `historical_store_v1`
- Adjustment: provider-declared split/dividend adjusted close (`daily_quotes.adjusted = 1`)
- Duplicate policy: reject conflicting `(symbol, date)` rows
- Missing sessions: reported, not imputed
- Delisting: missing horizon-end prices remain missing (Phase 4 behavior)

## Staging blockers

- Mixed raw/adjusted rows within a symbol
- Non-finite or nonpositive prices
- Unverified adjustment semantics
- Duplicate conflicting rows

Import batches must record provider ID, provider data version, source file hash, actor, and reason.
