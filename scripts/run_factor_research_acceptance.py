#!/usr/bin/env python3
"""Repo-root wrapper for Phase 11 factor-research acceptance."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_BACKEND_SCRIPT = Path(__file__).resolve().parent.parent / "backend" / "scripts" / "run_factor_research_acceptance.py"
sys.path.insert(0, str(_BACKEND_SCRIPT.parent.parent))
runpy.run_path(str(_BACKEND_SCRIPT), run_name="__main__")
