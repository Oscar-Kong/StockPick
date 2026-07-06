"""Prompt-template registry tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.llm.prompt_registry import TEMPLATES, get_template


def test_all_initial_templates_registered():
    expected = {
        "factor_research_request_normalizer_v1",
        "factor_hypothesis_generator_v1",
        "factor_hypothesis_critic_v1",
        "factor_dsl_translator_v1",
        "factor_formula_reviewer_v1",
        "factor_run_interpreter_v1",
    }
    assert expected.issubset(set(TEMPLATES.keys()))


def test_prompts_prohibit_code_execution():
    for tid in TEMPLATES:
        tpl = get_template(tid)
        lower = tpl.system_prompt.lower()
        assert "do not execute python" in lower
        assert "sql" in lower
        assert "sealed" in lower


def test_prompts_prohibit_lifecycle_approval():
    tpl = get_template("factor_hypothesis_generator_v1")
    assert "production" in tpl.system_prompt.lower()
