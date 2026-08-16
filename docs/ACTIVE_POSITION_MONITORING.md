# Active Position Monitoring

Status: quote-only monitoring loop, persistence, scheduler, HTTP API and Portfolio
Today UI implemented. Minute-bar/trade-stream ingestion and external push delivery
remain follow-up work.

## Objective

Provide timely decision support for active T+1 to T+3 momentum positions without
turning every market-data update into a full portfolio rescore or automated trade.

The core rule is:

> Market data may update every minute; recommendations change only when evidence
> crosses a defined state boundary.

## Update tiers

| Cadence | Work | External-data policy |
| --- | --- | --- |
| Every minute | Latest price, day high/low, unrealized P/L, distance to stop/invalidation/target, quote freshness; bid/ask/spread and volume when available | Quote-only or one shared WebSocket subscription; no fundamental or long-history refresh |
| Every 5 minutes | VWAP relationship, intraday structure, volume confirmation, extension, spread deterioration, position-state evaluation | Compute from locally accumulated intraday bars whenever possible |
| Every 15-30 minutes or on a material event | Broader technical reassessment | Reuse cached history; refresh only expired inputs |
| Premarket / after close | Alpha, Stability, fundamentals, longer-history risk context | Full research refresh, normally once or twice per day |

Do not schedule the existing full stored-portfolio decision path every minute: it
forces a quote/history refresh and can multiply provider calls by the number of
positions. Introduce a lightweight quote-refresh seam and a deterministic local
intraday evaluator instead.

## Position states

- `HOLD`: thesis and invalidation structure remain intact.
- `ADD_SETUP`: an add is possible but confirmation is missing.
- `ADD_CONFIRMED`: price structure, volume and spread meet the configured trigger.
- `TRIM`: extension, target proximity or deteriorating risk favors reducing size.
- `EXIT_WARNING`: position is approaching an explicit invalidation condition.
- `EXIT`: a configured invalidation condition has been confirmed.
- `DATA_STALE`: required data is stale or incomplete; suppress actionable advice.

State transitions must be explainable and evidence-bearing. Apply hysteresis (for
example, two quote samples at least four minutes apart or a minimum breach magnitude) and notification
cooldowns so borderline prices do not alternate recommendations every minute.

## Trigger examples

- Stop or thesis-invalidation level crossed and confirmed.
- VWAP or opening-range structure lost/reclaimed.
- Higher-low structure broken.
- Abnormal downside volume or rapidly widening quoted spread.
- Target/extension threshold reached.
- Material news or earnings event detected.

## Provider and safety controls

- Prefer one multi-symbol WebSocket subscription when the paid plan permits it;
  otherwise use batch quotes, then rate-limited per-symbol REST as the fallback.
- Enforce per-provider minute/day budgets, token-bucket throttling, 429 exponential
  backoff, circuit breaking, jitter, request deduplication and cache TTLs.
- Persist quote timestamps and expose stale-data status in the UI.
- Track provider-call counts and cache-hit ratios by job.
- Never place trades. This surface remains decision support.

For regular US market hours, one REST quote per position per minute costs about
`390 x active_position_count` calls per day. A full quote-plus-forced-history cycle
has a lower bound near twice that amount and can be materially higher.

## Data prerequisite

The current latest-quote path does not reliably provide intraday volume or quoted
bid/ask. Price/P&L and level monitoring can be implemented first, but VWAP, volume
acceleration, relative-volume and spread-confirmation decisions require a reliable
minute-OHLCV or trade/quote stream. Missing inputs must produce `DATA_STALE` or a
reduced-confidence non-actionable state, never fabricated confirmation.

## Implementation seams

- `refresh_active_quotes()`: implemented quote-only ingestion for active symbols.
- `refresh_and_store_active_quotes()`: timestamps and caches one shared quote
  snapshot. The opt-in scheduler runs this path every minute during trading sessions.
- `evaluate_intraday_position(snapshot)`: implemented pure, deterministic state
  evaluation using local data. Current confirmation is represented by completed-bar
  count; an actionable add additionally requires explicit volume and quoted-spread
  confirmation. The quote-only loop therefore cannot fabricate `ADD_CONFIRMED`.
- `run_active_position_monitor()`: evaluates cached quotes every five minutes,
  persists the current state, and appends change-only transitions.
- The transition ledger records timestamp, old/new state, evidence and actionability.
- The API notification feed emits actionable state changes only. A 15-minute
  cooldown suppresses churn, while a more severe state bypasses the cooldown.
- Portfolio Today polls the stored result every minute. This GET does not contact a
  market-data provider; manual **Refresh quotes now** performs one bounded quote pass.
- Quote ingestion is restricted to penny holdings, at most 10 symbols per pass and
  1,000 requests per backend process/day by default. Deferred symbols age into
  `DATA_STALE`; tune both caps to the provider plan before enabling the scheduler.

Enable the in-process jobs with `ACTIVE_POSITION_MONITOR_ENABLED=true`. The backend
must remain running for APScheduler to fire. This feature never places orders.

The existing full portfolio decision path remains unchanged and must not be used
as the minute scheduler target.
