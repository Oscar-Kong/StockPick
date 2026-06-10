#!/usr/bin/env python3
"""Validate Robinhood example CSV against reconstruction + daily decision."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.robinhood.csv_importer import parse_robinhood_csv
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio, validation_report
from models.schemas import Bucket, PortfolioDecisionRequest, PortfolioHolding
from services.portfolio_decision_service import run_portfolio_daily_decision
from services.portfolio_snapshot_service import validate_robinhood_csv

EXAMPLE_CSV = '''Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2025-05-01,2025-05-01,2025-05-02,,Robinhood instant bank transfer,RTP,,,$900.00
2025-05-02,2025-05-02,2025-05-03,,Stock lending payment,SLIP,,,$0.01
2025-05-03,2025-05-03,2025-05-04,AMC,"AMC Entertainment
CUSIP: 00165C302",Buy,20,1.95,($39.00)
2025-05-04,2025-05-04,2025-05-05,CYCU,Cycurion Inc,Buy,33,0.89,($29.37)
2025-05-05,2025-05-05,2025-05-06,LIDR,Lidar Technologies,Buy,10.123456,1.20,($12.15)
2025-05-05,2025-05-05,2025-05-06,LIDR,Lidar Technologies,Buy,13.443238,1.18,($15.86)
2025-05-06,2025-05-06,2025-05-07,RBBN,Ribbon Communications,Buy,8,2.50,($20.00)
2025-05-07,2025-05-07,2025-05-08,RBBN,Ribbon Communications,Sell,8,2.66,$21.24
2025-05-08,2025-05-08,2025-05-09,BBAI,BigBear.ai,Buy,5,3.00,($15.00)
2025-05-09,2025-05-09,2025-05-10,BBAI,BigBear.ai,Sell,5,2.80,$14.00
'''


def main() -> None:
    rows, warnings = parse_robinhood_csv(EXAMPLE_CSV)
    rebuild = rebuild_portfolio(rows)
    base = validate_robinhood_csv(EXAMPLE_CSV)

    cash = max(0.0, rebuild.cash_delta)
    holdings = [
        PortfolioHolding(
            symbol=h["symbol"],
            shares=h["shares"],
            avg_cost=h["avg_cost"],
            bucket=Bucket(h.get("bucket", "penny")),
        )
        for h in base["open_holdings"]
    ]

    decision = None
    decision_err = None
    try:
        decision = run_portfolio_daily_decision(
            PortfolioDecisionRequest(cash=cash, holdings=holdings, persist=False)
        )
    except Exception as exc:
        decision_err = str(exc)

    report = {
        "parse_warnings": warnings,
        "parsed_transactions": [
            {
                "activity_date": r.activity_date,
                "instrument": r.instrument or "(cash)",
                "trans_code": r.trans_code,
                "row_type": r.row_type,
                "quantity": r.quantity,
                "price": r.price,
                "amount": r.amount,
                "description": (r.description or "")[:80],
            }
            for r in rows
        ],
        "excluded_rows": rebuild.excluded_rows,
        "unknown_trans_codes": rebuild.unknown_trans_codes,
        "cash_movements": [
            {
                "date": r.activity_date,
                "trans_code": r.trans_code,
                "amount": r.amount,
                "description": r.description,
            }
            for r in rows
            if r.row_type in ("cash", "income")
        ],
        "net_cash_delta": rebuild.cash_delta,
        "reconstructed_open_holdings": base["open_holdings"],
        "closed_positions": base["closed_positions"],
        "per_symbol_validation": base["per_symbol_validation"],
        "rebuild_warnings": rebuild.warnings,
        "expected_checks": {
            "open_AMC_20": next((h for h in base["open_holdings"] if h["symbol"] == "AMC"), None),
            "open_CYCU_33": next((h for h in base["open_holdings"] if h["symbol"] == "CYCU"), None),
            "open_LIDR": next((h for h in base["open_holdings"] if h["symbol"] == "LIDR"), None),
            "closed_symbols": sorted(c["symbol"] for c in base["closed_positions"]),
        },
    }

    if decision_err:
        report["decision_error"] = decision_err
    elif decision:
        report["portfolio"] = {
            "cash": decision.cash,
            "total_value": decision.total_value,
            "invested_value": decision.invested_value,
        }
        report["decisions"] = []
        for item in decision.items:
            below_cost = item.price_available and item.price > 0 and item.price < item.avg_cost
            report["decisions"].append(
                {
                    "symbol": item.symbol,
                    "bucket": item.bucket,
                    "shares": item.shares,
                    "avg_cost": item.avg_cost,
                    "latest_price": item.price if item.price_available else None,
                    "price_available": item.price_available,
                    "below_avg_cost": below_cost,
                    "market_value": item.market_value,
                    "pl_pct": item.pl_pct,
                    "current_weight_pct": item.current_weight,
                    "target_weight_pct": item.target_weight,
                    "max_allowed_weight_pct": item.max_allowed_weight,
                    "buy_pct": item.buy_pct,
                    "keep_pct": item.keep_pct,
                    "sell_pct": item.sell_pct,
                    "final_decision": item.decision,
                    "suggested_action": item.suggested_action,
                    "reasons": item.reasons,
                    "risk_flags": item.risk_flags,
                    "raw_scoring": {
                        "alpha_score": item.alpha_score,
                        "momentum_score": item.momentum_score,
                        "liquidity_score": item.liquidity_score,
                        "risk_score": item.risk_score,
                        "data_quality_score": item.data_quality_score,
                        "overweight_penalty": item.overweight_penalty,
                        "missing_data_penalty": item.missing_data_penalty,
                        "stop_loss_trigger": item.stop_loss_trigger,
                        "final_buy_raw": item.final_buy_raw,
                        "final_keep_raw": item.final_keep_raw,
                        "final_sell_raw": item.final_sell_raw,
                    },
                    "score_v2": item.score,
                    "risk_index": item.risk_index,
                }
            )

        buys = [d for d in report["decisions"] if d["final_decision"] == "buy" and d["bucket"] == "penny"]
        report["penny_buy_analysis"] = []
        for b in buys:
            raw = b["raw_scoring"]
            explanation = {
                "symbol": b["symbol"],
                "below_avg_cost": b["below_avg_cost"],
                "likely_drivers": [],
            }
            if raw["momentum_score"] and raw["momentum_score"] >= 50:
                explanation["likely_drivers"].append(f"momentum={raw['momentum_score']}")
            if raw["alpha_score"] and raw["alpha_score"] >= 55:
                explanation["likely_drivers"].append(f"alpha={raw['alpha_score']}")
            if b["current_weight_pct"] < b["target_weight_pct"]:
                explanation["likely_drivers"].append(
                    f"underweight ({b['current_weight_pct']}% vs target {b['target_weight_pct']}%)"
                )
            if b["below_avg_cost"] and not explanation["likely_drivers"]:
                explanation["warning"] = "BUY may be driven only by below-avg-cost — logic bug"
            report["penny_buy_analysis"].append(explanation)

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
