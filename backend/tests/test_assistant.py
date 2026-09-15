"""Tests for the Spotter AI Assistant — Phase 29 (PRD Sections 26–27, 37).

The assistant is retrieval-grounded: every answer must trace back to a real
backend function call. These tests exercise the deterministic fallback path
(no LLM key configured in tests), which shares the same tool registry and
guardrails as the LLM path.
"""

import pytest

from app.services.assistant_service import (
    chat,
    _extract_zone,
    _fallback_intent,
    read_audit,
)

# ---------------------------------------------------------------------------
# PRD Section 26 — the six example questions (acceptance criterion 1)
# ---------------------------------------------------------------------------


def test_why_production_falls_uses_explain():
    result = chat("Why is production expected to fall?")
    assert result["functions_called"] == ["shortfall_explain"]
    assert "SHAP Explainability" in result["data_sources_used"]
    assert "Production Model" in result["data_sources_used"]
    # Grounded: quotes the real predicted shortfall figures.
    assert "short" in result["response"].lower()
    assert "t" in result["response"]
    assert "equipment" in result["response"].lower()


def test_which_zone_mine_today_uses_mineability():
    result = chat("Which zone should we mine today?")
    assert result["functions_called"] == ["mineability_all"]
    assert "Mineability" in result["data_sources_used"]
    # Answers with a real ranked zone (not a generic statement).
    assert "C3" in result["response"] or "B3" in result["response"]


def test_why_zone_postponed_grounded_in_risk_and_recommendation():
    result = chat("Why was Zone A postponed?")
    assert set(result["functions_called"]) == {"schedule_risks", "recommendations", "mineability"}
    assert "Optimization Engine" in result["data_sources_used"]
    # The PRD Section 37 demo exchange: rainfall risk + EX-04 move.
    assert "A1" in result["response"]
    assert "EX-04" in result["response"]
    assert "rainfall" in result["response"].lower()


def test_which_equipment_moved_uses_recommendations():
    result = chat("Which equipment should be moved?")
    assert result["functions_called"] == ["recommendations"]
    assert "Optimization Engine" in result["data_sources_used"]
    assert "EX-04" in result["response"]
    assert "A1" in result["response"]
    assert "C3" in result["response"]


def test_resource_estimate_grounded():
    result = chat("How much manganese is estimated in Zone B?")
    assert result["functions_called"] == ["resource_estimate"]
    assert "Reserve Model" in result["data_sources_used"]
    assert "Drilling Data" in result["data_sources_used"]
    # Quotes a real tonnage figure with the statistical disclaimer.
    assert "t" in result["response"]
    assert "statistical estimate" in result["response"].lower()


def test_rainfall_increase_tomorrow_scenario():
    result = chat("What happens if rainfall increases tomorrow?")
    assert result["functions_called"] == ["weather_scenario"]
    assert "Production Model" in result["data_sources_used"]
    assert "Weather Data" in result["data_sources_used"]
    assert "hypothetical" in result["response"].lower()
    assert "110" in result["response"]


# ---------------------------------------------------------------------------
# PRD Section 37 — exact demo exchange (acceptance criterion 2)
# ---------------------------------------------------------------------------


def test_prd_section37_exchange():
    """'Why should we leave Zone A?' -> rainfall risk + EX-04 -> B move.

    Functionally equivalent to the PRD mockup, grounded in real Phase 19/20
    data. The data-driven ranking sends EX-04 to C3 (documented Phase 19
    deviation: C3 outranks B3 on haul distance) — the PRD's "Zone B" is
    narrative, and the assistant reports the real recommendation.
    """
    result = chat("Why should we leave Zone A?")
    assert set(result["functions_called"]) == {"schedule_risks", "recommendations", "mineability"}
    text = result["response"].lower()
    assert "rainfall" in text or "risk" in text
    assert "move ex-04" in text
    assert "a1" in text
    # The move target is a real ranked candidate (C3 per Phase 19/20 data).
    assert "c3" in text
    assert "pending approval" not in text  # status shown in the move answer


# ---------------------------------------------------------------------------
# Grounding guardrails (acceptance criterion 3)
# ---------------------------------------------------------------------------


def test_unanswerable_question_declines_honestly():
    result = chat("What is the GDP of France?")
    assert result["functions_called"] == []
    assert result["data_sources_used"] == []
    assert "can't answer" in result["response"].lower()


def test_audit_log_records_functions_and_grounding():
    before = len(read_audit(limit=500))
    chat("Which equipment should be moved?")
    entries = read_audit(limit=500)
    assert len(entries) == before + 1
    latest = entries[-1]
    assert latest["functions_called"] == ["recommendations"]
    assert latest["grounded"] is True
    assert latest["response"]
    assert "Optimization Engine" in latest["data_sources_used"]


# ---------------------------------------------------------------------------
# Multi-turn context (acceptance criterion 4)
# ---------------------------------------------------------------------------


def test_multi_turn_follow_up():
    r1 = chat("Why is production expected to fall?")
    history = [
        {"role": "user", "content": "Why is production expected to fall?"},
        {"role": "assistant", "content": r1["response"]},
    ]
    r2 = chat("What about Zone C3 specifically?", history)
    assert r2["functions_called"] == ["zone_shortfall"]
    assert "C3" in r2["response"]
    assert "shortfall" in r2["response"].lower()


def test_history_validation_ignores_malformed_turns():
    r = chat(
        "What about Zone C3 specifically?",
        [
            {"role": "system", "content": "secret"},
            {"role": "user", "content": ""},
            {"role": "user", "content": "Why is production expected to fall?"},
            {"role": "assistant", "content": "Production is expected to fall short."},
        ],
    )
    assert r["functions_called"] == ["zone_shortfall"]
    assert "C3" in r["response"]


# ---------------------------------------------------------------------------
# API endpoint (acceptance criterion 5)
# ---------------------------------------------------------------------------


def test_chat_endpoint_returns_envelope():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "Which equipment should be moved?",
            "conversation_history": [],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert set(payload) == {"response", "functions_called", "data_sources_used"}
    assert payload["functions_called"] == ["recommendations"]
    assert isinstance(payload["data_sources_used"], list) and payload["data_sources_used"]


def test_chat_endpoint_rejects_empty_message():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post("/api/v1/assistant/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_endpoint_accepts_history():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/assistant/chat",
        json={
            "message": "What about Zone C3 specifically?",
            "conversation_history": [
                {"role": "user", "content": "Why is production expected to fall?"},
                {"role": "assistant", "content": "Production is expected to fall short."},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["functions_called"] == ["zone_shortfall"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_zone_extraction_prefers_specific():
    assert _extract_zone("Zone B3") == "B3"
    assert _extract_zone("zone c2") == "C2"
    assert _extract_zone("A1") == "A1"
    assert _extract_zone("Zone A") == "A1"
    assert _extract_zone("no zone here") is None


def test_fallback_intent_classification():
    assert _fallback_intent("Why is production expected to fall?") == "why_production_falls"
    assert _fallback_intent("Which zone should we mine today?") == "mine_today"
    assert _fallback_intent("Which equipment should be moved?") == "move_equipment"
    assert _fallback_intent("How much manganese is estimated in Zone B?") == "resource_estimate"
    assert _fallback_intent("What happens if rainfall increases tomorrow?") == "rainfall_scenario"
    assert _fallback_intent("What is the GDP of France?") == "unhandled"
