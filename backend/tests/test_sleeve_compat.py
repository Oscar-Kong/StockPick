"""Sleeve compatibility — legacy medium maps to penny."""
from __future__ import annotations

from core.sleeve import normalize_bucket, normalize_sleeve
from models.schemas import Bucket


def test_normalize_sleeve_medium_to_penny():
    assert normalize_sleeve("medium") == "penny"
    assert normalize_sleeve("MEDIUM") == "penny"


def test_normalize_sleeve_active_unchanged():
    assert normalize_sleeve("penny") == "penny"
    assert normalize_sleeve("compounder") == "compounder"


def test_normalize_sleeve_unknown_defaults_penny():
    assert normalize_sleeve("unknown") == "penny"
    assert normalize_sleeve(None) == "penny"


def test_normalize_bucket_medium():
    assert normalize_bucket(Bucket.medium) == Bucket.penny
    assert normalize_bucket("medium") == Bucket.penny
