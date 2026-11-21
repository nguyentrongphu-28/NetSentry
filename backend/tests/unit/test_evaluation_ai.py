"""Unit tests for AI evaluation tools (injection cases and validation pipeline)."""

from pathlib import Path
import json
import pytest

from evaluation.ai_eval import evaluate_offline_injection_resistance


def test_injection_cases_integrity():
    cases_file = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "ai" / "injection_cases.json"
    assert cases_file.is_file()

    with open(cases_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "cases" in data
    cases = data["cases"]
    assert len(cases) >= 20

    seen_ids = set()
    for c in cases:
        assert "id" in c
        assert "category" in c
        assert "payload" in c
        assert c["id"] not in seen_ids
        seen_ids.add(c["id"])


def test_question_set_integrity():
    q_file = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "ai" / "question_set.json"
    assert q_file.is_file()

    with open(q_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "questions" in data
    questions = data["questions"]
    assert len(questions) == 8

    rules = {q["rule_id"] for q in questions}
    expected_rules = {f"NET-00{i}" for i in range(1, 9)}
    assert rules == expected_rules


def test_rubric_template_integrity():
    rubric_file = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "ai" / "rubric_template.csv"
    assert rubric_file.is_file()
    lines = rubric_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 9  # Header + 8 rules


def test_ai_eval_offline_pipeline():
    cases_file = Path(__file__).resolve().parent.parent.parent.parent / "evaluation" / "ai" / "injection_cases.json"
    res = evaluate_offline_injection_resistance(cases_file)
    assert res["total_cases"] >= 20
    assert res["passed_cases"] == res["total_cases"]
    assert res["violations"] == 0
    assert res["pass_rate"] == "100.0%"
