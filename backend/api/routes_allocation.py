"""Allocation recommendation routes (FinRL scaffold)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from models.schemas import AllocationRecommendationResponse, Bucket
from services.allocation_recommender import get_allocation_recommendation

router = APIRouter(prefix="/allocation", tags=["allocation"])


@router.get("/recommendation/{bucket}", response_model=AllocationRecommendationResponse)
def allocation_recommendation(bucket: Bucket, symbols: str | None = Query(default=None)):
    parsed = []
    if symbols:
        parsed = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    return AllocationRecommendationResponse(**get_allocation_recommendation(bucket, parsed))

