"""ML signal routes (Qlib scaffold)."""
from __future__ import annotations

from fastapi import APIRouter

from models.schemas import (
    AlphaIngestRequest,
    AlphaIngestResponse,
    AlphaLatestResponse,
    Bucket,
)
from services.qlib_integration import get_latest_alpha, ingest_alpha_predictions

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/alpha/latest", response_model=AlphaLatestResponse)
def alpha_latest(bucket: Bucket = Bucket.medium):
    return AlphaLatestResponse(**get_latest_alpha(bucket))


@router.post("/alpha/ingest", response_model=AlphaIngestResponse)
def alpha_ingest(body: AlphaIngestRequest):
    payload = ingest_alpha_predictions(
        body.bucket,
        as_of=body.as_of or "",
        model_version=body.model_version,
        items=[item.model_dump() for item in body.items],
    )
    return AlphaIngestResponse(
        ok=True,
        bucket=body.bucket,
        model_version=payload.get("model_version", body.model_version),
        ingested=len(payload.get("items", [])),
        message="Alpha predictions ingested.",
    )

