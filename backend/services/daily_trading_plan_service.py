"""Build deterministic daily trading plan from portfolio, scan, and policy gates."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from config import DATA_CONFIDENCE_STRONG_REC_MIN
from data.finnhub_client import FinnhubClient
from data.price_service import PriceService
from models.schemas import (
  Bucket,
  DailyTradingPlanResponse,
  DailyTradingPlanCandidate,
  DailyTradingPlanFocusItem,
  DailyTradingPlanHolidayRisk,
  DailyTradingPlanRuleCheck,
  PortfolioDecisionItem,
  PortfolioDecisionResponse,
)
from services.daily_trading_distress import evaluate_distress
from services.daily_trading_holiday import assess_holiday_risk
from services.daily_trading_news import classify_news_context
from services.daily_trading_policy import DEFAULT_DAILY_TRADING_POLICY, DailyTradingPolicy
from services.daily_trading_volume import classify_volume_behavior
from services.data_freshness_service import get_market_session_band
from services.scan_manager import scan_manager

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")
PlanDecision = Literal["buy", "manage", "reduce", "exit", "watch", "stay_in_cash"]
CandidateAction = Literal["buy", "watch", "manage", "reduce", "exit"]
RuleStatus = Literal["pass", "fail", "unavailable"]

DISCLAIMER = "Research and decision support only. No order has been placed."


@dataclass
class _ShortTermState:
  positions: list[dict[str, Any]] = field(default_factory=list)
  exposure_pct: float = 0.0
  eligible_capital: float = 0.0


def _now_et(now: datetime | None = None) -> datetime:
  base = now or datetime.now(timezone.utc)
  if base.tzinfo is None:
    base = base.replace(tzinfo=timezone.utc)
  return base.astimezone(NY_TZ)


def _entry_window_open(now_et: datetime, policy: DailyTradingPolicy) -> bool:
  return now_et.time() >= policy.entry_not_before_et


def _short_term_state(
  holdings: list[dict],
  decision: PortfolioDecisionResponse | None,
  total_value: float,
  cash: float,
  policy: DailyTradingPolicy,
) -> _ShortTermState:
  by_sym: dict[str, PortfolioDecisionItem] = {}
  if decision:
    by_sym = {i.symbol: i for i in decision.items}

  positions: list[dict[str, Any]] = []
  invested_st = 0.0
  for h in holdings:
    if (h.get("bucket") or policy.short_term_bucket) != policy.short_term_bucket:
      continue
    shares = float(h.get("shares") or 0)
    if shares <= 0:
      continue
    item = by_sym.get(h["symbol"])
    mv = float(item.market_value) if item and item.market_value else shares * float(h.get("avg_cost") or 0)
    pl_pct = float(item.pl_pct) if item and item.pl_pct is not None else None
    positions.append(
      {
        "symbol": h["symbol"],
        "shares": shares,
        "avg_cost": float(h.get("avg_cost") or 0),
        "market_value": mv,
        "pl_pct": pl_pct,
        "item": item,
      }
    )
    invested_st += mv

  eligible = max(total_value, cash + invested_st, 1.0)
  exposure = round(invested_st / eligible * 100, 2) if eligible > 0 else 0.0
  return _ShortTermState(positions=positions, exposure_pct=exposure, eligible_capital=eligible)


def _plan_id(trading_date: str, payload: dict) -> str:
  digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:12]
  return f"dtp_{trading_date}_{digest}"


def _risk_reward(entry: float, stop_pct: float, target_pct: float) -> float:
  risk = entry * stop_pct
  reward = entry * target_pct
  if risk <= 0:
    return 0.0
  return round(reward / risk, 2)


def _build_rule_checklist(
  *,
  policy: DailyTradingPolicy,
  exposure_pct: float,
  active_positions: int,
  entry_open: bool,
  leverage_used: bool,
  holiday: DailyTradingPlanHolidayRisk,
  candidate_qualified: bool,
  distress_clear: bool,
  trend_confirmed: bool,
  data_confidence_ok: bool,
  liquidity_ok: bool,
  sector_ok: bool,
  risk_reward_ok: bool,
  insufficient_mandatory: list[str],
) -> list[DailyTradingPlanRuleCheck]:
  max_exp = round(policy.max_short_term_exposure * 100, 1)

  def _status(passed: bool | None) -> RuleStatus:
    if passed is None:
      return "unavailable"
    return "pass" if passed else "fail"

  checks = [
    DailyTradingPlanRuleCheck(
      rule_id="MAX_EXPOSURE",
      label=f"Short-term exposure remains at or below {max_exp:.0f}%",
      status=_status(exposure_pct <= max_exp + 1e-6 if exposure_pct is not None else None),
      evidence=f"Current short-term exposure {exposure_pct:.1f}% vs ceiling {max_exp:.0f}%",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="MAX_POSITIONS",
      label=f"At most {policy.max_active_short_term_positions} active short-term position(s)",
      status=_status(active_positions <= policy.max_active_short_term_positions),
      evidence=f"{active_positions} active short-term position(s)",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="ENTRY_TIME",
      label=f"Entry after {policy.entry_not_before_et.strftime('%H:%M')} America/New_York",
      status=_status(entry_open),
      evidence="Entry window open" if entry_open else "Before entry window — watch only",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="NO_LEVERAGE",
      label="No leverage or margin-based sizing",
      status=_status(not leverage_used and not policy.leverage_allowed),
      evidence="Cash-funded sizing only" if not leverage_used else "Leverage detected — blocked",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="TREND_CONFIRMED",
      label="Confirmed positive price trend for new entries",
      status=_status(trend_confirmed if candidate_qualified else None),
      evidence="Uptrend confirmed" if trend_confirmed else "Trend not confirmed",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="LIQUIDITY",
      label="Adequate liquidity and acceptable spread proxy",
      status=_status(liquidity_ok if candidate_qualified else None),
      evidence="Liquidity acceptable" if liquidity_ok else "Liquidity insufficient",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="NO_DISTRESS",
      label="No distressed-security exclusion",
      status=_status(distress_clear if candidate_qualified else None),
      evidence="No distress flags" if distress_clear else "Distress exclusion triggered",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="DATA_CONFIDENCE",
      label=f"Data confidence ≥ {policy.data_confidence_min:.0f}",
      status=_status(data_confidence_ok if candidate_qualified else None),
      evidence="Confidence threshold met" if data_confidence_ok else "Below confidence threshold",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="SECTOR_STRENGTH",
      label="Candidate in comparatively strong sector",
      status=_status(sector_ok if candidate_qualified else None),
      evidence="Sector leadership acceptable" if sector_ok else "Sector leadership weak",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="RISK_REWARD",
      label="Risk/reward acceptable after stop",
      status=_status(risk_reward_ok if candidate_qualified else None),
      evidence="R/R acceptable" if risk_reward_ok else "R/R below minimum",
    ),
    DailyTradingPlanRuleCheck(
      rule_id="HOLIDAY_EXPOSURE",
      label="Reduce exposure before holidays/long weekends when applicable",
      status="pass" if not holiday.recommend_reduce_exposure else "fail",
      evidence=holiday.reason or "No pre-holiday reduction required",
    ),
  ]
  if insufficient_mandatory:
    checks.append(
      DailyTradingPlanRuleCheck(
        rule_id="MANDATORY_DATA",
        label="Mandatory safety checks completable",
        status="unavailable",
        evidence="; ".join(insufficient_mandatory),
      )
    )
  return checks


def _scan_candidates(limit: int = 12) -> list[dict[str, Any]]:
  data = scan_manager.get_latest_scan(Bucket.penny)
  if not data:
    return []
  return list(data.get("results") or [])[:limit]


def _sector_leadership(metrics: dict) -> dict[str, Any]:
  sector = metrics.get("sector") or metrics.get("industry") or "unknown"
  rs = metrics.get("relative_strength_vs_spy") or metrics.get("rs_vs_spy")
  sector_rank = metrics.get("sector_rank") or metrics.get("sector_strength_rank")
  strong = False
  if rs is not None:
    strong = float(rs) >= 0
  elif sector_rank is not None:
    strong = float(sector_rank) <= 3
  else:
    strong = float(metrics.get("alpha_score") or metrics.get("score") or 0) >= 60
  return {
    "sector": sector,
    "relative_strength_vs_spy": rs,
    "sector_rank": sector_rank,
    "is_strong_sector": strong,
  }


def _evaluate_candidate(
  scan_row: dict[str, Any],
  *,
  policy: DailyTradingPolicy,
  price_service: PriceService,
  finnhub: FinnhubClient,
  entry_open: bool,
  exposure_ok: bool,
  slots_available: bool,
) -> dict[str, Any]:
  symbol = str(scan_row.get("symbol") or "").upper()
  price = float(scan_row.get("price") or 0)
  metrics = dict(scan_row.get("metrics") or {})
  score = float(scan_row.get("score") or metrics.get("score") or 0)
  confidence = float(
    scan_row.get("confidence_score")
    or metrics.get("data_confidence")
    or metrics.get("data_quality_score")
    or 0
  )
  momentum = float(metrics.get("momentum_score") or metrics.get("momentum_5d") or 50)
  liquidity = float(metrics.get("liquidity_score") or metrics.get("volume_signal_score") or 50)
  trend = float(metrics.get("trend_score") or momentum)

  reasons: list[str] = []
  rejections: list[str] = []

  history = None
  info = None
  try:
    history = price_service.get_history(symbol, days=120)
    info = price_service.get_info(symbol)
  except Exception as exc:
    logger.debug("history/info fetch failed for %s: %s", symbol, exc)

  hist_len = len(history) if history is not None and not history.empty else 0
  scan_hist = int(metrics.get("history_bars") or metrics.get("hist_len") or 0)
  effective_hist = max(hist_len, scan_hist)
  scan_validated = scan_hist >= 80 and confidence >= 60
  distress = evaluate_distress(
    symbol=symbol,
    price=price,
    history=history,
    info=info,
    metrics=metrics,
    quality_score=confidence,
    hist_len=effective_hist,
    scan_validated=scan_validated,
  )
  if distress.rejected:
    rejections.extend(distress.reasons)

  vol = classify_volume_behavior(history)
  news_raw = {}
  try:
    news_raw = finnhub.news_summary(symbol)
  except Exception:
    pass
  prev_close = float(metrics.get("previous_close") or 0) or None
  news = classify_news_context(
    news_summary=news_raw,
    price=price,
    prev_close=prev_close,
    momentum_score=momentum,
    gap_pct=metrics.get("gap_percent"),
  )

  sector = _sector_leadership(metrics)
  trend_confirmed = trend >= policy.trend_confirmed_min_score and price > 0
  liquidity_ok = liquidity >= policy.liquidity_min_score
  spread_ok = float(metrics.get("spread_score") or liquidity) >= 40
  liquidity_ok = liquidity_ok and spread_ok
  data_confidence_ok = confidence >= policy.data_confidence_min
  sector_ok = bool(sector.get("is_strong_sector"))
  rr = _risk_reward(price, policy.stop_loss_pct, policy.partial_profit_pct)
  risk_reward_ok = rr >= policy.min_risk_reward_ratio

  # News cannot alone create buy
  news_blocks_buy = news.classification in ("positive_news_priced_in", "headline_unconfirmed")
  if news_blocks_buy:
    reasons.append(f"News context: {news.classification}")

  insufficient = distress.insufficient_data
  mandatory_ok = not insufficient

  qualified = (
    not rejections
    and trend_confirmed
    and liquidity_ok
    and data_confidence_ok
    and sector_ok
    and risk_reward_ok
    and exposure_ok
    and slots_available
    and mandatory_ok
    and not news_blocks_buy
    and vol.classification != "possible_distribution"
  )

  if not exposure_ok:
    rejections.append("Short-term exposure at or above policy ceiling")
  if not slots_available:
    rejections.append("Active short-term position already open")
  if not entry_open:
    reasons.append("Entry window not open before 10:00 ET")
  if not trend_confirmed:
    rejections.append("Positive trend not confirmed")
  if not liquidity_ok:
    rejections.append("Liquidity or spread proxy insufficient")
  if not data_confidence_ok:
    rejections.append(f"Data confidence {confidence:.0f} below {policy.data_confidence_min:.0f}")
  if not sector_ok:
    rejections.append("Sector leadership insufficient")
  if not risk_reward_ok:
    rejections.append(f"Risk/reward {rr:.2f} below minimum {policy.min_risk_reward_ratio}")
  if vol.classification == "possible_distribution":
    rejections.append("Volume pattern: possible_distribution")
  if insufficient:
    rejections.append("Mandatory safety data unavailable")

  status = "qualified" if qualified and entry_open else (
    "watch" if (qualified and not entry_open) or (not rejections and not entry_open and trend_confirmed) else "rejected"
  )

  return {
    "symbol": symbol,
    "score": score,
    "status": status,
    "reasons": reasons,
    "rejection_reasons": rejections,
    "qualified": qualified and entry_open,
    "watch_only": qualified and not entry_open,
    "price": price,
    "trend": trend,
    "confidence": confidence,
    "momentum": momentum,
    "liquidity": liquidity,
    "sector": sector,
    "volume": vol,
    "news": news,
    "risk_reward": rr,
    "distress": distress,
    "metrics": metrics,
  }


def build_daily_trading_plan(
  *,
  portfolio_value: float,
  cash: float,
  holdings: list[dict],
  decision: PortfolioDecisionResponse | None = None,
  policy: DailyTradingPolicy | None = None,
  now: datetime | None = None,
  scan_rows: list[dict] | None = None,
  price_service: PriceService | None = None,
  finnhub: FinnhubClient | None = None,
) -> DailyTradingPlanResponse:
  """Orchestrate deterministic daily trading plan — policy engine owns eligibility."""
  pol = policy or DEFAULT_DAILY_TRADING_POLICY
  now_et = _now_et(now)
  as_of = now_et.isoformat()
  trading_date = now_et.date().isoformat()
  session = get_market_session_band(now)
  entry_open = _entry_window_open(now_et, pol)

  st = _short_term_state(holdings, decision, portfolio_value, cash, pol)
  max_exp_pct = round(pol.max_short_term_exposure * 100, 1)
  available_capacity = max(0.0, max_exp_pct - st.exposure_pct)

  holiday_raw = assess_holiday_risk(now)
  holiday = DailyTradingPlanHolidayRisk(
    is_pre_holiday_session=holiday_raw.is_pre_holiday_session,
    recommend_reduce_exposure=holiday_raw.recommend_reduce_exposure,
    reason=holiday_raw.reason,
  )

  ps = price_service or PriceService()
  fh = finnhub or FinnhubClient()

  # Manage existing short-term position first
  if st.positions:
    pos = st.positions[0]
    sym = pos["symbol"]
    pl = pos.get("pl_pct")
    item: PortfolioDecisionItem | None = pos.get("item")
    entry_price = float(item.price if item and item.price else pos["avg_cost"])
    stop_price = round(entry_price * (1 - pol.stop_loss_pct), 4)
    target_price = round(entry_price * (1 + pol.partial_profit_pct), 4)

    action: CandidateAction = "manage"
    plan_decision: PlanDecision = "manage"
    entry_condition = "Manage existing short-term position"
    remaining_plan = "Trail stop; reassess at next session"

    if pl is not None and pl <= -pol.stop_loss_pct * 100:
      action = "exit"
      plan_decision = "exit"
      entry_condition = f"Unrealized loss {pl:.1f}% at/beyond {pol.stop_loss_pct*100:.0f}% stop"
      remaining_plan = "Exit full position per stop discipline"
    elif pl is not None and pl >= pol.partial_profit_pct * 100:
      action = "reduce"
      plan_decision = "reduce"
      entry_condition = f"Unrealized gain {pl:.1f}% reached {pol.partial_profit_pct*100:.0f}% target"
      remaining_plan = f"Sell {pol.partial_profit_fraction*100:.0f}% of position; manage remainder"

    if holiday.recommend_reduce_exposure and plan_decision == "manage":
      plan_decision = "reduce"
      action = "reduce"
      entry_condition = (holiday.reason or "Pre-holiday exposure reduction") + f"; {entry_condition}"

    primary = DailyTradingPlanCandidate(
      symbol=sym,
      action=action,
      entry_not_before=f"{pol.entry_not_before_et.strftime('%H:%M')} America/New_York",
      entry_condition=entry_condition,
      reference_entry_price=entry_price,
      maximum_position_value=round(float(pos["market_value"]), 2),
      maximum_portfolio_weight_pct=round(float(pos["market_value"]) / st.eligible_capital * 100, 2),
      stop_price=stop_price,
      stop_loss_pct=round(pol.stop_loss_pct * 100, 1),
      first_target_price=target_price,
      first_target_gain_pct=round(pol.partial_profit_pct * 100, 1),
      first_target_sell_fraction_pct=round(pol.partial_profit_fraction * 100, 1),
      remaining_position_plan=remaining_plan,
      trend_state="existing_position",
      sector_leadership={},
      volume_classification="n/a",
      news_classification="n/a",
      risk_reward_ratio=_risk_reward(entry_price, pol.stop_loss_pct, pol.partial_profit_pct),
      data_confidence=float(item.data_quality_score or 0) if item else 0.0,
      supporting_evidence=[f"Active short-term holding in {sym}"],
      risk_flags=list(item.risk_flags) if item else [],
    )

    focus = [
      DailyTradingPlanFocusItem(
        symbol=sym,
        rank=1,
        status="qualified",
        reasons=[entry_condition],
        rejection_reasons=[],
      )
    ]

    rules = _build_rule_checklist(
      policy=pol,
      exposure_pct=st.exposure_pct,
      active_positions=len(st.positions),
      entry_open=entry_open,
      leverage_used=False,
      holiday=holiday,
      candidate_qualified=False,
      distress_clear=True,
      trend_confirmed=True,
      data_confidence_ok=True,
      liquidity_ok=True,
      sector_ok=True,
      risk_reward_ok=True,
      insufficient_mandatory=[],
    )

    payload = {
      "decision": plan_decision,
      "exposure": st.exposure_pct,
      "primary": sym,
      "date": trading_date,
    }
    return DailyTradingPlanResponse(
      plan_id=_plan_id(trading_date, payload),
      as_of=as_of,
      market_session=session,
      decision=plan_decision,
      confidence=70.0,
      summary=f"Prioritize {plan_decision} on existing short-term position {sym}.",
      current_short_term_exposure_pct=st.exposure_pct,
      maximum_short_term_exposure_pct=max_exp_pct,
      available_risk_capacity_pct=round(available_capacity, 2),
      active_short_term_positions=len(st.positions),
      focus_list=focus,
      primary_candidate=primary,
      cash_reason=None,
      rule_checklist=rules,
      rejected_candidates=[],
      holiday_risk=holiday,
      review_prompts=[
        "Did you follow the stop/target discipline?",
        "Record any rule overrides before market close.",
      ],
      data_freshness={"scan": "latest_cached", "as_of": as_of},
      disclaimer=DISCLAIMER,
    )

  # No active short-term position — evaluate new entries
  exposure_ok = st.exposure_pct < max_exp_pct - 1e-6
  slots_available = len(st.positions) < pol.max_active_short_term_positions
  rows = scan_rows if scan_rows is not None else _scan_candidates(pol.maximum_focus_symbols * 3)

  evaluated = [
    _evaluate_candidate(
      row,
      policy=pol,
      price_service=ps,
      finnhub=fh,
      entry_open=entry_open,
      exposure_ok=exposure_ok,
      slots_available=slots_available,
    )
    for row in rows
    if row.get("symbol")
  ]
  evaluated.sort(key=lambda x: (-x["score"], x["symbol"]))

  qualified = [e for e in evaluated if e["qualified"]]
  watch = [e for e in evaluated if e["watch_only"]]
  rejected = [e for e in evaluated if e["status"] == "rejected"]

  focus_pool = qualified + watch + [e for e in evaluated if e["status"] == "rejected"][:2]
  focus_items: list[DailyTradingPlanFocusItem] = []
  for rank, ev in enumerate(focus_pool[: pol.maximum_focus_symbols], start=1):
    status = ev["status"]
    focus_items.append(
      DailyTradingPlanFocusItem(
        symbol=ev["symbol"],
        rank=rank,
        status=status,
        reasons=ev["reasons"][:3] or ([f"Score {ev['score']:.0f}"] if status != "rejected" else []),
        rejection_reasons=ev["rejection_reasons"][:5],
      )
    )
  used_symbols = {f.symbol for f in focus_items}
  for ev in evaluated:
    if len(focus_items) >= pol.maximum_focus_symbols:
      break
    if ev["symbol"] in used_symbols:
      continue
    focus_items.append(
      DailyTradingPlanFocusItem(
        symbol=ev["symbol"],
        rank=len(focus_items) + 1,
        status=ev["status"],
        reasons=ev["reasons"][:3] or [f"Score {ev['score']:.0f}"],
        rejection_reasons=ev["rejection_reasons"][:5],
      )
    )
    used_symbols.add(ev["symbol"])

  best = qualified[0] if qualified else (watch[0] if watch else None)

  primary: DailyTradingPlanCandidate | None = None
  plan_decision: PlanDecision = "stay_in_cash"
  cash_reason: str | None = None
  summary = "No candidate passed every required gate — stay in cash."
  confidence = 40.0

  if not exposure_ok:
    cash_reason = f"Short-term exposure {st.exposure_pct:.1f}% meets or exceeds {max_exp_pct:.0f}% ceiling — no new buys."
    summary = cash_reason
  elif holiday.recommend_reduce_exposure and not qualified:
    cash_reason = holiday.reason
    summary = "Pre-holiday session — remain in cash or reduce exposure; no new entry qualified."
  elif best:
    price = float(best["price"])
    max_value = round(st.eligible_capital * pol.max_short_term_exposure, 2)
    max_weight = round(pol.max_short_term_exposure * 100, 2)
    stop_price = round(price * (1 - pol.stop_loss_pct), 4)
    target_price = round(price * (1 + pol.partial_profit_pct), 4)
    vol = best["volume"]
    news = best["news"]
    action: CandidateAction = "buy" if best["qualified"] else "watch"
    plan_decision = "buy" if best["qualified"] else "watch"
    if not entry_open and best["watch_only"]:
      plan_decision = "watch"
      action = "watch"
    confidence = float(best["confidence"])
    entry_condition = (
      f"Confirmed trend (score {best['trend']:.0f}); "
      f"volume={vol.classification}; wait for price hold above support"
    )
    if not entry_open:
      entry_condition = "Watch — entry window not open before 10:00 a.m. ET; " + entry_condition

    primary = DailyTradingPlanCandidate(
      symbol=best["symbol"],
      action=action,
      entry_not_before=f"{pol.entry_not_before_et.strftime('%H:%M')} America/New_York",
      entry_condition=entry_condition,
      reference_entry_price=price,
      maximum_position_value=max_value,
      maximum_portfolio_weight_pct=max_weight,
      stop_price=stop_price,
      stop_loss_pct=round(pol.stop_loss_pct * 100, 1),
      first_target_price=target_price,
      first_target_gain_pct=round(pol.partial_profit_pct * 100, 1),
      first_target_sell_fraction_pct=round(pol.partial_profit_fraction * 100, 1),
      remaining_position_plan="Manage remainder with trailing stop after partial take-profit",
      trend_state=f"confirmed" if best["trend"] >= pol.trend_confirmed_min_score else "unconfirmed",
      sector_leadership=best["sector"],
      volume_classification=vol.classification,
      news_classification=news.classification,
      risk_reward_ratio=best["risk_reward"],
      data_confidence=best["confidence"],
      supporting_evidence=[
        vol.rationale,
        news.rationale,
        f"Scan score {best['score']:.0f}",
      ],
      risk_flags=best["rejection_reasons"][:3],
    )
    summary = (
      f"Primary {'buy' if plan_decision == 'buy' else 'watch'} candidate {best['symbol']} "
      f"from latest cached penny scan."
    )
  elif not evaluated:
    cash_reason = "No scan candidates available — stay in cash until a valid scan exists."
    summary = cash_reason
  else:
    cash_reason = "No symbol passed all mandatory quality, trend, liquidity, and risk gates."
    summary = cash_reason

  # Hard-rule failures block buy
  cand_qualified = bool(best and best.get("qualified"))
  trend_ok = bool(best and best["trend"] >= pol.trend_confirmed_min_score)
  liq_ok = bool(best and best["liquidity"] >= pol.liquidity_min_score)
  distress_ok = bool(best and not best["distress"].rejected)
  dc_ok = bool(best and best["confidence"] >= pol.data_confidence_min)
  sector_ok = bool(best and best["sector"].get("is_strong_sector"))
  rr_ok = bool(best and best["risk_reward"] >= pol.min_risk_reward_ratio)
  insufficient = list(best["distress"].insufficient_data) if best else []

  rules = _build_rule_checklist(
    policy=pol,
    exposure_pct=st.exposure_pct,
    active_positions=len(st.positions),
    entry_open=entry_open,
    leverage_used=False,
    holiday=holiday,
    candidate_qualified=cand_qualified,
    distress_clear=distress_ok,
    trend_confirmed=trend_ok,
    data_confidence_ok=dc_ok,
    liquidity_ok=liq_ok,
    sector_ok=sector_ok,
    risk_reward_ok=rr_ok,
    insufficient_mandatory=insufficient,
  )
  hard_fail = any(r.status == "fail" for r in rules if r.rule_id in {
    "MAX_EXPOSURE", "MAX_POSITIONS", "ENTRY_TIME", "NO_LEVERAGE",
    "TREND_CONFIRMED", "LIQUIDITY", "NO_DISTRESS", "DATA_CONFIDENCE",
  })
  if plan_decision == "buy" and (hard_fail or not cand_qualified):
    plan_decision = "watch" if best else "stay_in_cash"
    if primary:
      primary = primary.model_copy(update={"action": "watch"})
    if not best:
      cash_reason = cash_reason or "Hard rule failure — stay in cash."

  rejected_candidates = [
    {
      "symbol": e["symbol"],
      "reasons": e["rejection_reasons"][:5],
      "score": e["score"],
    }
    for e in rejected[:10]
  ]

  payload = {
    "decision": plan_decision,
    "exposure": st.exposure_pct,
    "primary": primary.symbol if primary else None,
    "date": trading_date,
    "rows": [e["symbol"] for e in evaluated[:5]],
  }
  return DailyTradingPlanResponse(
    plan_id=_plan_id(trading_date, payload),
    as_of=as_of,
    market_session=session,
    decision=plan_decision,
    confidence=confidence,
    summary=summary,
    current_short_term_exposure_pct=st.exposure_pct,
    maximum_short_term_exposure_pct=max_exp_pct,
    available_risk_capacity_pct=round(available_capacity, 2),
    active_short_term_positions=len(st.positions),
    focus_list=focus_items,
    primary_candidate=primary,
    cash_reason=cash_reason,
    rule_checklist=rules,
    rejected_candidates=rejected_candidates,
    holiday_risk=holiday,
    review_prompts=[
      "Did you follow the plan (entry time, size, stop)?",
      "Record overrides and actual actions for end-of-day review.",
    ],
    data_freshness={
      "as_of": as_of,
      "scan_source": "latest_cached",
      "data_confidence_threshold": DATA_CONFIDENCE_STRONG_REC_MIN,
    },
    disclaimer=DISCLAIMER,
  )
