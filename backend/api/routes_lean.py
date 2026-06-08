"""LEAN export/import routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import (
    LeanExportRequest,
    LeanExportResponse,
    LeanImportSummaryRequest,
    LeanImportSummaryResponse,
)
from services.lean_handoff import build_lean_export, load_lean_export, save_lean_summary

router = APIRouter(prefix="/lean", tags=["lean"])


@router.post("/export", response_model=LeanExportResponse)
def lean_export(body: LeanExportRequest):
    try:
        export_id, file_path, payload = build_lean_export(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LEAN export failed: {exc}") from exc

    return LeanExportResponse(
        export_id=export_id,
        created_at=payload.get("created_at", ""),
        bucket=body.bucket,
        symbols=payload.get("symbols", []),
        strategy_version=payload.get("strategy_version"),
        file_path=file_path,
        payload=payload,
        message="LEAN export generated successfully.",
    )


@router.get("/export/{export_id}")
def lean_export_get(export_id: str):
    try:
        return load_lean_export(export_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load export: {exc}") from exc


@router.post("/import-summary", response_model=LeanImportSummaryResponse)
def lean_import_summary(body: LeanImportSummaryRequest):
    try:
        summary_path = save_lean_summary(
            body.export_id,
            status=body.status,
            metrics=body.metrics,
            notes=body.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save summary: {exc}") from exc

    return LeanImportSummaryResponse(
        ok=True,
        export_id=body.export_id,
        status=body.status,
        summary_path=summary_path,
        message="LEAN summary saved successfully.",
    )

