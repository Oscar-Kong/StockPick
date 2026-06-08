#!/usr/bin/env python3
"""Export factor panel + forward labels; optional Alphalens tear sheet."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESEARCH_DIR = Path(__file__).resolve().parents[1] / "data_store" / "research"


def export_factor_panel() -> Path:
    from data.db_engine import get_engine
    from data.historical_store import FactorSnapshot
    from sqlalchemy.orm import Session

    import json

    import pandas as pd

    out = RESEARCH_DIR / "factor_panel.parquet"
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    with Session(engine) as session:
        rows = session.query(FactorSnapshot).limit(50000).all()
    records = []
    for r in rows:
        try:
            factors = json.loads(r.factors_json or "{}")
        except Exception:
            factors = {}
        rec = {"symbol": r.symbol, "date": r.snapshot_date, "bucket": r.bucket, "score": r.score}
        if isinstance(factors, dict):
            rec.update(factors)
        records.append(rec)
    pd.DataFrame(records).to_parquet(out, index=False)
    print(f"factor_panel: {len(records)} rows -> {out}")
    return out


def export_forward_labels() -> Path:
    from data.db_engine import get_engine
    from engines.quant_models import ForwardReturnLabel
    from sqlalchemy.orm import Session

    import pandas as pd

    out = RESEARCH_DIR / "forward_labels.parquet"
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    with Session(engine) as session:
        rows = session.query(ForwardReturnLabel).limit(200000).all()
    records = [
        {
            "symbol": r.symbol,
            "date": r.as_of_date,
            "horizon_days": r.horizon_days,
            "fwd_return": r.fwd_return,
            "excess_vs_spy": r.excess_vs_spy,
            "excess_vs_sector": r.excess_vs_sector,
            "sector": r.sector,
        }
        for r in rows
    ]
    pd.DataFrame(records).to_parquet(out, index=False)
    print(f"forward_labels: {len(records)} rows -> {out}")
    return out


def build_alphalens_report(factor_col: str = "medium_rs_vs_spy") -> Path:
    """Generate HTML tear sheet if alphalens-reloaded is installed."""
    import pandas as pd

    panel_path = RESEARCH_DIR / "factor_panel.parquet"
    labels_path = RESEARCH_DIR / "forward_labels.parquet"
    if not panel_path.exists():
        export_factor_panel()
    if not labels_path.exists():
        export_forward_labels()

    panel = pd.read_parquet(panel_path)
    labels = pd.read_parquet(labels_path)
    if factor_col not in panel.columns:
        raise SystemExit(f"Factor column {factor_col} not in panel. Columns: {list(panel.columns)[:20]}")

    html_out = RESEARCH_DIR / f"alphalens_{factor_col}.html"
    try:
        import alphalens as al

        panel["date"] = pd.to_datetime(panel["date"])
        labels_h = labels[labels["horizon_days"] == 20].copy()
        labels_h["date"] = pd.to_datetime(labels_h["date"])
        prices = labels_h.pivot_table(index="date", columns="symbol", values="fwd_return", aggfunc="first")
        factor = panel.set_index(["date", "symbol"])[factor_col]
        factor_data = al.utils.get_clean_factor_and_forward_returns(
            factor,
            prices,
            periods=(20,),
            max_loss=0.65,
        )
        from matplotlib import pyplot as plt

        al.tears.create_summary_tear_sheet(factor_data)
        plt.savefig(html_out.with_suffix(".png"), dpi=120, bbox_inches="tight")
        plt.close()
        html_out.write_text(
            f"<html><body><h1>Alphalens summary — {factor_col}</h1>"
            f'<img src="{html_out.with_suffix(".png").name}" width="900"/></body></html>',
            encoding="utf-8",
        )
        print(f"alphalens PNG/HTML -> {html_out}")
        return html_out
    except ImportError:
        summary = (
            panel.groupby("bucket")[factor_col].agg(["count", "mean", "std"]).reset_index()
            if factor_col in panel.columns
            else panel.describe()
        )
        html_out.write_text(
            f"<html><body><h1>Factor summary (Alphalens not installed)</h1>"
            f"<pre>{summary.to_string()}</pre>"
            f"<p>Install: pip install alphalens-reloaded matplotlib</p></body></html>",
            encoding="utf-8",
        )
        print(f"fallback HTML -> {html_out}")
        return html_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Round 2 factor research export")
    parser.add_argument("--factor", default="medium_rs_vs_spy", help="Factor column for tear sheet")
    parser.add_argument("--skip-alphalens", action="store_true")
    args = parser.parse_args()
    export_factor_panel()
    export_forward_labels()
    if not args.skip_alphalens:
        build_alphalens_report(args.factor)


if __name__ == "__main__":
    main()
