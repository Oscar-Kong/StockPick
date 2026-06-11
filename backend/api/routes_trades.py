"""Trade journal routes with process-quality review."""
from __future__ import annotations

import os
import uuid
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from data import cache as cache_module
from models.schemas import (
    TradeCreateRequest,
    TradeItem,
    TradeManualResponse,
    TradeReviewSnapshot,
    TradeStatsResponse,
    TradeUpdateRequest,
)
from services.trade_review import parse_iso_datetime, review_trade
from services.image_trade_analyzer import analyze_trade_screenshot
from services.trade_feedback_service import record_outcome_for_trade, record_prediction_for_trade
from services.portfolio_snapshot_service import journal_trade_sync_status

router = APIRouter(prefix="/trades", tags=["trades"])

_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage", "trade_uploads")
)
os.makedirs(_UPLOAD_DIR, exist_ok=True)


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _to_trade_item(row: dict) -> TradeItem:
    status, synced = journal_trade_sync_status(
        trade_id=int(row["id"]),
        quantity=row.get("quantity"),
    )
    return _to_trade_response(
        row,
        portfolio_synced=synced if status != "needs_quantity" else False,
        portfolio_sync_status=status,
    )


def _trade_response_after_sync(row: dict, synced: bool, msg: str | None) -> TradeManualResponse:
    status, _ = journal_trade_sync_status(trade_id=int(row["id"]), quantity=row.get("quantity"))
    return _to_trade_response(
        row,
        portfolio_synced=synced,
        portfolio_message=msg,
        portfolio_sync_status=status,
    )


def _to_trade_response(
    row: dict,
    *,
    portfolio_synced: bool = False,
    portfolio_message: str | None = None,
    portfolio_sync_status: str | None = None,
) -> TradeManualResponse:
    review = row.get("review") or {}
    return TradeManualResponse(
        id=int(row["id"]),
        symbol=row["symbol"],
        side=row.get("side", "long"),
        entry_time=datetime.fromisoformat(row["entry_time"]),
        exit_time=datetime.fromisoformat(row["exit_time"]) if row.get("exit_time") else None,
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]) if row.get("exit_price") is not None else None,
        quantity=float(row["quantity"]) if row.get("quantity") is not None else None,
        stop_loss=float(row["stop_loss"]) if row.get("stop_loss") is not None else None,
        take_profit=float(row["take_profit"]) if row.get("take_profit") is not None else None,
        setup_tags=row.get("setup_tags") or [],
        thesis=row.get("thesis") or "",
        notes=row.get("notes") or "",
        screenshot_path=row.get("screenshot_path"),
        review=TradeReviewSnapshot(**review),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        portfolio_synced=portfolio_synced,
        portfolio_message=portfolio_message,
        portfolio_sync_status=portfolio_sync_status,
    )


def _build_review(
    *,
    side: str,
    entry_price: float,
    exit_price: float | None,
    quantity: float | None,
    stop_loss: float | None,
    take_profit: float | None,
    thesis: str,
    setup_tags: list[str],
) -> dict:
    snap = review_trade(
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        thesis=thesis,
        tags=setup_tags,
    )
    return {
        "pnl_abs": snap.pnl_abs,
        "pnl_pct": snap.pnl_pct,
        "planned_rr": snap.planned_rr,
        "quality_score": snap.quality_score,
        "quality_label": snap.quality_label,
        "process_good": snap.process_good,
        "review_note": snap.review_note,
        "flags": snap.flags,
    }


def _on_trade_opened(row: dict, *, sleeve: str | None = None) -> tuple[bool, str | None]:
    try:
        record_prediction_for_trade(
            int(row["id"]),
            symbol=row["symbol"],
            side=row.get("side", "long"),
            entry_price=float(row["entry_price"]),
            setup_tags=row.get("setup_tags") or [],
            sleeve=sleeve,
        )
    except Exception:
        pass
    return _sync_trade_to_portfolio(row)


def _sync_trade_to_portfolio(row: dict) -> tuple[bool, str | None]:
    qty = row.get("quantity")
    if qty is None or float(qty) <= 0:
        return False, "Add a share quantity to update the Home portfolio"
    try:
        from services.portfolio_snapshot_service import (
            apply_manual_trade_to_portfolio,
            evaluate_portfolio_sync_result,
        )

        entry_time = row.get("entry_time")
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
        exit_time = row.get("exit_time")
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
        result = apply_manual_trade_to_portfolio(
            trade_id=int(row["id"]),
            symbol=row["symbol"],
            side=row.get("side", "long"),
            entry_time=entry_time,
            entry_price=float(row["entry_price"]),
            quantity=float(qty),
            exit_time=exit_time,
            exit_price=float(row["exit_price"]) if row.get("exit_price") is not None else None,
            notes=row.get("notes") or "",
        )
        return evaluate_portfolio_sync_result(result)
    except Exception as exc:
        return False, str(exc)[:200]


def _on_trade_closed(row: dict) -> None:
    exit_price = row.get("exit_price")
    if exit_price is None:
        return
    try:
        record_outcome_for_trade(
            int(row["id"]),
            side=row.get("side", "long"),
            entry_price=float(row["entry_price"]),
            exit_price=float(exit_price),
        )
    except Exception:
        pass


@router.get("", response_model=list[TradeItem])
def list_trades(symbol: str | None = None, limit: int = Query(default=100, ge=1, le=500)):
    rows = cache_module.list_trades(symbol=symbol, limit=limit)
    return [_to_trade_item(r) for r in rows]


@router.post("/manual", response_model=TradeManualResponse)
def create_trade_manual(body: TradeCreateRequest):
    if body.quantity is None or float(body.quantity) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity is required — journal trades need share count to update the Home portfolio",
        )
    review = _build_review(
        side=body.side,
        entry_price=body.entry_price,
        exit_price=body.exit_price,
        quantity=body.quantity,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
        thesis=body.thesis,
        setup_tags=body.setup_tags,
    )
    row = cache_module.create_trade(
        symbol=body.symbol,
        side=body.side,
        entry_time=body.entry_time,
        exit_time=body.exit_time,
        entry_price=body.entry_price,
        exit_price=body.exit_price,
        quantity=body.quantity,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
        setup_tags=body.setup_tags,
        thesis=body.thesis,
        notes=body.notes,
        review=review,
    )
    synced, msg = _on_trade_opened(row, sleeve=body.sleeve)
    if body.exit_price is not None:
        _on_trade_closed(row)
    return _trade_response_after_sync(row, synced, msg)


@router.post("/upload", response_model=TradeManualResponse)
async def create_trade_upload(
    symbol: str = Form(...),
    side: str = Form("long"),
    entry_time: str = Form(...),
    exit_time: str | None = Form(None),
    entry_price: float = Form(...),
    exit_price: float | None = Form(None),
    quantity: float | None = Form(None),
    stop_loss: float | None = Form(None),
    take_profit: float | None = Form(None),
    setup_tags: str = Form(""),
    thesis: str = Form(""),
    notes: str = Form(""),
    screenshot: UploadFile | None = File(None),
):
    if quantity is None or float(quantity) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity is required — journal trades need share count to update the Home portfolio",
        )
    parsed_entry = parse_iso_datetime(entry_time)
    if not parsed_entry:
        raise HTTPException(status_code=400, detail="Invalid entry_time format")
    parsed_exit = parse_iso_datetime(exit_time)

    screenshot_path: str | None = None
    screenshot_content: bytes = b""
    screenshot_mime = None
    screenshot_name = None
    if screenshot is not None:
        ext = os.path.splitext(screenshot.filename or "")[1].lower() or ".png"
        file_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(_UPLOAD_DIR, file_name)
        screenshot_content = await screenshot.read()
        with open(file_path, "wb") as f:
            f.write(screenshot_content)
        screenshot_path = file_path
        screenshot_mime = screenshot.content_type
        screenshot_name = screenshot.filename

    tags = _parse_tags(setup_tags)
    review = _build_review(
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        thesis=thesis,
        setup_tags=tags,
    )
    if screenshot_content:
        image_meta = analyze_trade_screenshot(
            screenshot_content,
            mime_type=screenshot_mime,
            filename=screenshot_name,
        )
        review["image_insight"] = image_meta.get("image_insight", "")
        review["image_tags"] = image_meta.get("image_tags", [])
        review["image_analysis_status"] = image_meta.get("analysis_status", "not_run")

    row = cache_module.create_trade(
        symbol=symbol,
        side=side,
        entry_time=parsed_entry,
        exit_time=parsed_exit,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        setup_tags=tags,
        thesis=thesis,
        notes=notes,
        screenshot_path=screenshot_path,
        review=review,
    )
    synced, msg = _on_trade_opened(row)
    if exit_price is not None:
        _on_trade_closed(row)
    return _trade_response_after_sync(row, synced, msg)


@router.post("/{trade_id}/sync-portfolio", response_model=TradeManualResponse)
def sync_trade_portfolio(trade_id: int):
    row = cache_module.get_trade(trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    synced, msg = _sync_trade_to_portfolio(row)
    if not synced and msg and "quantity" in msg.lower():
        raise HTTPException(status_code=400, detail=msg)
    return _trade_response_after_sync(row, synced, msg)


@router.patch("/{trade_id}", response_model=TradeManualResponse)
def update_trade(trade_id: int, body: TradeUpdateRequest):
    existing = cache_module.get_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")

    side = existing.get("side", "long")
    entry_price = float(existing.get("entry_price"))
    exit_price = body.exit_price if body.exit_price is not None else existing.get("exit_price")
    quantity = body.quantity if body.quantity is not None else existing.get("quantity")
    stop_loss = body.stop_loss if body.stop_loss is not None else existing.get("stop_loss")
    take_profit = (
        body.take_profit if body.take_profit is not None else existing.get("take_profit")
    )
    thesis = body.thesis if body.thesis is not None else (existing.get("thesis") or "")
    setup_tags = body.setup_tags if body.setup_tags is not None else (existing.get("setup_tags") or [])
    review = _build_review(
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        thesis=thesis,
        setup_tags=setup_tags,
    )

    row = cache_module.update_trade(
        trade_id,
        exit_time=body.exit_time,
        exit_price=body.exit_price,
        quantity=body.quantity,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
        setup_tags=body.setup_tags,
        thesis=body.thesis,
        notes=body.notes,
        review=review,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    synced, msg = _sync_trade_to_portfolio(row)
    if row.get("exit_price") is not None:
        _on_trade_closed(row)
    return _trade_response_after_sync(row, synced, msg)


@router.delete("/{trade_id}")
def delete_trade(trade_id: int):
    existing = cache_module.get_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")
    if existing.get("screenshot_path"):
        try:
            os.remove(existing["screenshot_path"])
        except Exception:
            pass
    ok = cache_module.delete_trade(trade_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"ok": True}


@router.get("/{trade_id}/screenshot")
def get_trade_screenshot(trade_id: int):
    row = cache_module.get_trade(trade_id)
    if not row or not row.get("screenshot_path"):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    path = row["screenshot_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return FileResponse(path)


@router.get("/stats/summary", response_model=TradeStatsResponse)
def trade_stats():
    rows = cache_module.list_trades(limit=500)
    total = len(rows)
    closed = 0
    win = 0
    pnl_values: list[float] = []
    quality_values: list[float] = []
    strong_process = 0
    profitable_but_weak = 0
    disciplined_loss = 0
    flag_counter: Counter[str] = Counter()

    for row in rows:
        review = row.get("review") or {}
        pnl_pct = review.get("pnl_pct")
        quality = float(review.get("quality_score") or 0)
        process_good = bool(review.get("process_good"))
        quality_values.append(quality)
        if process_good:
            strong_process += 1
        for flag in review.get("flags") or []:
            flag_counter[str(flag)] += 1
        if pnl_pct is not None:
            closed += 1
            pnl_values.append(float(pnl_pct))
            if float(pnl_pct) >= 0:
                win += 1
                if not process_good:
                    profitable_but_weak += 1
            elif process_good:
                disciplined_loss += 1

    top_flags = [{"flag": k, "count": v} for k, v in flag_counter.most_common(5)]
    return TradeStatsResponse(
        total_trades=total,
        closed_trades=closed,
        win_rate_pct=round((win / closed * 100.0), 2) if closed else 0,
        avg_pnl_pct=round(sum(pnl_values) / len(pnl_values), 4) if pnl_values else 0,
        avg_quality_score=round(sum(quality_values) / len(quality_values), 2)
        if quality_values
        else 0,
        strong_process_rate_pct=round((strong_process / total * 100.0), 2) if total else 0,
        profitable_but_weak_count=profitable_but_weak,
        disciplined_loss_count=disciplined_loss,
        top_flags=top_flags,
    )
