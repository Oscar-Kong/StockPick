"""Robinhood CSV parsing, reconstruction, and decision engine tests."""
from __future__ import annotations

import pytest

from integrations.robinhood.csv_importer import parse_robinhood_csv, row_hash_from_fields
from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio
from services.portfolio_decision_engine import DecisionInput, compute_holding_decision, max_weight_for_sleeve


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


def _parse_and_rebuild(csv: str = EXAMPLE_CSV):
    rows, warnings = parse_robinhood_csv(csv)
    rebuild = rebuild_portfolio(rows)
    return rows, warnings, rebuild


def test_multiline_quoted_description():
    rows, _ = parse_robinhood_csv(EXAMPLE_CSV)
    amc = [r for r in rows if r.instrument == "AMC"]
    assert len(amc) == 1
    assert "AMC Entertainment" in amc[0].description
    assert amc[0].row_type == "buy"


def test_parentheses_dollar_parsing():
    rows, _ = parse_robinhood_csv(EXAMPLE_CSV)
    amc = next(r for r in rows if r.instrument == "AMC")
    assert amc.amount == pytest.approx(-39.0)
    rbbn_sell = next(r for r in rows if r.instrument == "RBBN" and r.row_type == "sell")
    assert rbbn_sell.amount == pytest.approx(21.24)
    slip = next(r for r in rows if r.trans_code == "SLIP")
    assert slip.amount == pytest.approx(0.01)


def test_amount_overrides_wrong_price_column():
    """Robinhood Price column can disagree with Amount; cash impact is authoritative."""
    csv = """Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2025-06-01,2025-06-01,2025-06-02,LIDR,Lidar Technologies,Buy,10,1.19,($19.10)
"""
    rows, _ = parse_robinhood_csv(csv)
    lidr = next(r for r in rows if r.instrument == "LIDR")
    assert lidr.price == pytest.approx(1.91)


def test_rtp_slip_do_not_create_holdings():
    _, _, rebuild = _parse_and_rebuild()
    symbols = {h.symbol for h in rebuild.open_holdings}
    assert "RTP" not in symbols
    assert "SLIP" not in symbols
    assert "" not in symbols


def test_rtp_affects_cash_only():
    _, _, rebuild = _parse_and_rebuild()
    assert rebuild.cash_delta == pytest.approx(900.0 + 0.01 - 39.0 - 29.37 - 12.15 - 15.86 - 20.0 + 21.24 - 15.0 + 14.0, rel=0.01)


def test_open_holdings_amc_cycu_lidr():
    _, _, rebuild = _parse_and_rebuild()
    by = {h.symbol: h for h in rebuild.open_holdings}
    assert set(by) == {"AMC", "CYCU", "LIDR"}
    assert by["AMC"].shares == pytest.approx(20)
    assert by["CYCU"].shares == pytest.approx(33)
    assert by["LIDR"].shares == pytest.approx(23.566694, rel=1e-4)


def test_closed_positions_bbai_rbbn():
    _, _, rebuild = _parse_and_rebuild()
    closed = {c.symbol for c in rebuild.closed_positions}
    assert closed == {"BBAI", "RBBN"}


def test_buy_increases_sell_decreases():
    csv = """Activity Date,Process Date,Settle Date,Instrument,Description,Trans Code,Quantity,Price,Amount
2025-01-01,2025-01-01,2025-01-02,TEST,Test Co,Buy,10,5.00,($50.00)
2025-01-02,2025-01-02,2025-01-03,TEST,Test Co,Sell,3,6.00,$18.00
"""
    _, _, rebuild = _parse_and_rebuild(csv)
    h = rebuild.open_holdings[0]
    assert h.symbol == "TEST"
    assert h.shares == pytest.approx(7)
    assert h.total_bought == pytest.approx(10)
    assert h.total_sold == pytest.approx(3)


def test_duplicate_row_hash_stable():
    h1 = row_hash_from_fields(
        activity_date="2025-05-03",
        process_date="2025-05-03",
        instrument="AMC",
        trans_code="BUY",
        quantity=20,
        price=1.95,
        amount=-39.0,
        description="AMC Entertainment",
    )
    h2 = row_hash_from_fields(
        activity_date="2025-05-03",
        process_date="2025-05-03",
        instrument="AMC",
        trans_code="BUY",
        quantity=20,
        price=1.95,
        amount=-39.0,
        description="AMC Entertainment",
    )
    assert h1 == h2


def test_duplicate_csv_upload_dedupes():
    from data.portfolio_store import SessionLocal, TradeHistory, init_portfolio_db, upsert_ledger_rows, DEFAULT_ACCOUNT_ID

    init_portfolio_db()
    rows, _ = parse_robinhood_csv(EXAMPLE_CSV)
    hashes = [r.row_hash for r in rows]

    session = SessionLocal()
    try:
        session.query(TradeHistory).filter(TradeHistory.row_hash.in_(hashes)).delete()
        session.commit()
    finally:
        session.close()

    imported1, _ = upsert_ledger_rows(DEFAULT_ACCOUNT_ID, rows, source_file_id=9901)
    imported2, skipped2 = upsert_ledger_rows(DEFAULT_ACCOUNT_ID, rows, source_file_id=9902)
    assert imported1 == len(rows)
    assert imported2 == 0
    assert skipped2 == len(rows)

    session = SessionLocal()
    try:
        count = session.query(TradeHistory).filter(TradeHistory.row_hash.in_(hashes)).count()
        assert count == len(rows)
    finally:
        session.close()


def test_decision_pcts_sum_to_100():
    out = compute_holding_decision(
        DecisionInput(
            symbol="AMC",
            sleeve="penny",
            shares=20,
            avg_cost=1.95,
            latest_price=2.10,
            alpha_score=55,
            momentum_score=52,
            liquidity_score=60,
            risk_score=45,
            data_quality_score=70,
            current_weight=0.05,
            target_weight=0.06,
            max_allowed_weight=max_weight_for_sleeve("penny"),
        ),
        total_portfolio_value=10000,
    )
    assert out.buy_pct + out.keep_pct + out.sell_pct == pytest.approx(100, abs=0.05)


def test_missing_price_produces_review():
    out = compute_holding_decision(
        DecisionInput(
            symbol="XYZ",
            sleeve="penny",
            shares=100,
            avg_cost=1.0,
            latest_price=None,
            alpha_score=80,
            momentum_score=80,
            liquidity_score=80,
            risk_score=20,
            data_quality_score=80,
            current_weight=0.1,
            target_weight=0.05,
            max_allowed_weight=0.08,
        ),
        total_portfolio_value=5000,
    )
    assert out.final_decision == "review"
    assert not out.price_available
    assert "missing" in out.suggested_action.lower() or out.missing_data_penalty > 0


def test_overweight_penny_does_not_buy():
    max_w = max_weight_for_sleeve("penny")
    out = compute_holding_decision(
        DecisionInput(
            symbol="HOT",
            sleeve="penny",
            shares=5000,
            avg_cost=1.0,
            latest_price=1.0,
            alpha_score=85,
            momentum_score=75,
            liquidity_score=70,
            risk_score=30,
            data_quality_score=80,
            current_weight=max_w + 0.05,
            target_weight=max_w * 0.5,
            max_allowed_weight=max_w,
        ),
        total_portfolio_value=100000,
    )
    assert out.final_decision != "buy"
    assert out.final_buy_raw == 0.0 or out.final_decision in ("keep", "sell", "review")


def test_below_avg_cost_alone_never_buys():
    max_w = max_weight_for_sleeve("penny")
    out = compute_holding_decision(
        DecisionInput(
            symbol="DIP",
            sleeve="penny",
            shares=100,
            avg_cost=2.0,
            latest_price=1.5,  # below cost
            alpha_score=52,
            momentum_score=48,
            liquidity_score=60,
            risk_score=40,
            data_quality_score=70,
            current_weight=0.02,
            target_weight=0.05,
            max_allowed_weight=max_w,
        ),
        total_portfolio_value=10000,
    )
    assert out.final_decision != "buy"
    assert out.final_buy_raw == 0.0


def test_final_decision_matches_highest_pct_when_clear():
    out = compute_holding_decision(
        DecisionInput(
            symbol="WEAK",
            sleeve="penny",
            shares=100,
            avg_cost=2.0,
            latest_price=1.0,
            alpha_score=25,
            momentum_score=20,
            liquidity_score=30,
            risk_score=85,
            data_quality_score=60,
            current_weight=0.12,
            target_weight=0.04,
            max_allowed_weight=0.08,
        ),
        total_portfolio_value=10000,
    )
    assert out.sell_pct >= out.buy_pct
    assert out.final_decision in ("sell", "keep", "review")
