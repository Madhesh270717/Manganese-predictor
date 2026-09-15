"""Spotter AI Assistant orchestration — Phase 29 (PRD Sections 26–27, 37).

Module 5: the natural-language interface over the REAL modules built in
Phases 12–21. This is a RETRIEVAL-GROUNDED assistant, not a freeform LLM:

    USER -> Spotter AI -> Backend -> {Reserve Model, Production Model,
                                      Optimization Engine}
                          -> Results -> Spotter AI -> natural-language answer

The LLM (Anthropic tool-use) does exactly two things:
  (a) classify which backend function(s) the user's question maps to, and
  (c) format the RAW function results into plain language.
It NEVER invents figures: every number in an answer must have come from a
real backend function call in this turn (grounding guardrails below).

Architecture
------------
* A small set of INTENT-TO-FUNCTION mappings (PRD Section 26's example
  questions). Each tool has a schema (name, description, parameters) so
  the LLM can pick the right one and fill its arguments.
* Tools execute REAL service calls (shortfall, explainability,
  recommendations, prospectivity, resource estimates, mineability,
  scenario prediction) — the same services the Phase 16–21 APIs expose.
* The "rainfall increases tomorrow" hypothetical is translated into an
  actual scenario input by re-running the current schedule through the
  production prediction model with the chosen zone's rainfall raised.
* A deterministic fallback formatter produces grounded answers when no
  LLM key is configured (demo machines) or when the LLM call fails —
  the same tool results, the same guardrails.

Grounding guardrails (PRD Section 27)
-------------------------------------
1. The system prompt instructs the LLM to report ONLY figures/facts that
   came from tool results in this turn.
2. If no tool maps to the question, the assistant says so honestly
   instead of guessing.
3. Every response is logged alongside the functions actually called
   (audit trail: response vs grounding evidence, for demo credibility).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grounding / audit
# ---------------------------------------------------------------------------

# Audit log: one JSON line per assistant turn, so responses can be checked
# against the functions that were actually called. Kept on disk (no DB
# dependency), same pattern as the Phase 21 recalculation audit log.
AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml"
    / "data"
    / "processed"
    / "assistant_audit.jsonl"
)

# Zone-name synonyms the extractor accepts (A1, zone a1, zone-a, ...).
ZONE_ALIASES: dict[str, str] = {
    "zone a1": "A1",
    "zone-a1": "A1",
    "zone a": "A1",
    "zone-a": "A1",
    "a1": "A1",
    "zone b2": "B2",
    "zone-b2": "B2",
    "zone b": "B2",
    "zone-b": "B2",
    "b2": "B2",
    "zone b3": "B3",
    "zone-b3": "B3",
    "b3": "B3",
    "zone c2": "C2",
    "zone-c2": "C2",
    "zone c": "C2",
    "zone-c": "C2",
    "c2": "C2",
    "zone c3": "C3",
    "zone-c3": "C3",
    "c3": "C3",
}

# ---------------------------------------------------------------------------
# Tool registry — the intent-to-function mapping (PRD Section 26 examples)
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    name: str
    description: str
    parameters: list[dict]
    function: Callable[..., dict]
    data_sources: list[str]
    # If True, results are included in the context passed to the formatter
    # (all tools are). If False the tool is unusable when data is missing.
    required: bool = True


def _fmt_number(value: Any, digits: int = 1) -> str:
    """Compact thousands formatting for tonne figures in fallback text."""
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,.{digits}f}"


def _tool_shortfall(**kwargs: Any) -> dict:
    """Current production shortfall + PRD Section 15 risk level."""
    from app.services.shortfall_service import get_current_shortfall

    zone_id = kwargs.get("zone_id")
    return get_current_shortfall(zone_id=zone_id)


def _tool_explain(**kwargs: Any) -> dict:
    """SHAP contributor breakdown for the current schedule's shortfall."""
    from app.services.explainability_service import get_shortfall_contributors

    return get_shortfall_contributors(schedule=None)


def _tool_recommendations(**kwargs: Any) -> dict:
    """Mine-wide prioritized reallocation recommendations (Phase 20)."""
    from app.services.recommendation_service import generate_all_recommendations

    return generate_all_recommendations()


def _tool_recommendation_for(**kwargs: Any) -> dict:
    """Single-equipment reallocation recommendation (Phase 20)."""
    from app.services.recommendation_service import generate_recommendation

    result = generate_recommendation(kwargs["equipment_id"])
    if result is None:
        return {"equipment_id": kwargs["equipment_id"], "error": "no recommendation"}
    return result


def _tool_risks(**kwargs: Any) -> dict:
    """Risk triggers for the current schedule (weather + shortfall)."""
    from app.services.production_prediction_service import _current_schedule
    from ml.pipelines.optimization.risk_trigger import detect_schedule_risks

    triggers = detect_schedule_risks(_current_schedule())
    return {"count": len(triggers), "triggers": triggers}


def _tool_alternatives(**kwargs: Any) -> dict:
    """Ranked candidate alternative zones for one at-risk equipment."""
    from app.services.production_prediction_service import _current_schedule
    from ml.pipelines.optimization.candidate_zones import select_candidate_zones
    from ml.pipelines.optimization.zone_comparator import rank_candidates

    equipment_id = kwargs["equipment_id"]
    schedule = _current_schedule()
    current_zone = next(
        (e["zone_id"] for e in schedule if e["equipment_id"] == equipment_id), None
    )
    if current_zone is None:
        return {"equipment_id": equipment_id, "error": "equipment not scheduled"}
    candidates = select_candidate_zones(equipment_id, current_zone)
    ranked = rank_candidates(equipment_id, candidates, schedule)
    return {
        "equipment_id": equipment_id,
        "current_zone_id": current_zone,
        "candidate_count": len(ranked),
        "ranked_candidates": ranked,
    }


def _tool_prospectivity(**kwargs: Any) -> dict:
    """Statistical prospectivity score + classification for one zone."""
    from app.services.reserve_model_service import get_prospectivity

    result = get_prospectivity(kwargs["zone_id"])
    if result is None:
        return {"zone_id": kwargs["zone_id"], "error": "zone not found"}
    return result


def _tool_resource_estimate(**kwargs: Any) -> dict:
    """Statistical resource estimate (volume/tonnage/grade/contained Mn)."""
    from app.services.resource_estimation_service import get_resource_estimate

    result = get_resource_estimate(kwargs["zone_id"])
    if result is None:
        return {"zone_id": kwargs["zone_id"], "error": "zone not found"}
    return result


def _tool_mineability(**kwargs: Any) -> dict:
    """Live mineability score breakdown for one zone."""
    from app.services.mineability_service import get_mineability

    result = get_mineability(kwargs["zone_id"])
    if result is None:
        return {"zone_id": kwargs["zone_id"], "error": "zone not found"}
    return result


def _tool_mineability_all(**kwargs: Any) -> dict:
    """All-zone mineability ranking, sorted desc (for 'mine today')."""
    from app.services.mineability_service import get_all_mineability

    return get_all_mineability()


def _tool_production(**kwargs: Any) -> dict:
    """Production prediction for the current 30-day schedule."""
    from app.services.production_prediction_service import predict_current

    return predict_current()


def _tool_zone_risk(**kwargs: Any) -> dict:
    """Shortfall + risk for ONE zone in the current schedule."""
    return _tool_shortfall(zone_id=kwargs["zone_id"])


def _tool_weather_scenario(**kwargs: Any) -> dict:
    """What-if: predict production if a zone's rainfall rises tomorrow.

    Translation of the PRD question "What happens if rainfall increases
    tomorrow?" into an actual scenario input:
      * take the CURRENT schedule (Phase 10, the 82,000 t target);
      * raise the target zone's rainfall_1d/7d/30d to the configured
        spike values for "tomorrow" (the Phase 8 demo storm numbers);
      * re-run the Phase 15 prediction on the modified feature rows.
    The scenario flag makes it auditable that this is a hypothetical.
    """
    from app.services.production_prediction_service import (
        _build_feature_rows,
        _current_schedule,
        _predict_frame,
        predict_production,
    )
    from app.services.synthetic.production_generator import (
        planned_for_day,
    )
    from app.services.synthetic.schedule_generator import CURRENT_ASSIGNMENTS

    zone_id = kwargs["zone_id"]
    spike_1d = kwargs.get("spike_1d", 110.0)
    schedule = _current_schedule()
    if not schedule:
        return {"error": "empty schedule"}

    today = date.today()
    tomorrow = today + timedelta(days=1)

    # The current schedule runs through today only — extend it by one day so
    # "tomorrow" has scheduled work to run the hypothetical against. Uses the
    # same planned-for-day + CURRENT_ASSIGNMENTS rules as Phase 10.
    assignments_by_zone: dict[str, list[tuple]] = {}
    for assignment in CURRENT_ASSIGNMENTS:
        assignments_by_zone.setdefault(assignment[1], []).append(assignment)
    per_shift = {
        zone: planned_for_day(zone, tomorrow, today - timedelta(days=29)) / (len(units) * 2)
        for zone, units in assignments_by_zone.items()
    }
    for assignment in CURRENT_ASSIGNMENTS:
        equipment_id, z, _operation, _expected = assignment
        schedule.append(
            {
                "zone_id": z,
                "date": tomorrow,
                "shift": "A",
                "equipment_id": equipment_id,
                "expected_output": round(per_shift[z], 1),
            }
        )
        schedule.append(
            {
                "zone_id": z,
                "date": tomorrow,
                "shift": "B",
                "equipment_id": equipment_id,
                "expected_output": round(per_shift[z], 1),
            }
        )

    dates = sorted({e["date"] for e in schedule})

    base_frame = _build_feature_rows(schedule, dates)
    scenario = base_frame.copy()
    tomorrow_mask = scenario["date"] == tomorrow
    zone_mask = scenario["zone_id"] == zone_id
    target_rows = scenario[tomorrow_mask & zone_mask]

    if target_rows.empty:
        return {
            "error": f"zone {zone_id} has no scheduled work tomorrow",
            "zone_id": zone_id,
        }

    scenario.loc[target_rows.index, "rainfall_1d"] = spike_1d
    scenario.loc[target_rows.index, "rainfall_7d"] = spike_1d * 3.0
    scenario.loc[target_rows.index, "rainfall_30d"] = spike_1d * 10.0

    predicted = _predict_frame(scenario)
    baseline = predict_production(schedule)

    scenario_total = round(float(predicted["predicted"].sum()), 1)
    baseline_total = baseline["predicted_tonnes"]

    return {
        "zone_id": zone_id,
        "scenario": f"rainfall spike to {spike_1d:g}mm on {tomorrow.isoformat()}",
        "scenario_flag": True,
        "predicted_tonnes": scenario_total,
        "baseline_predicted_tonnes": baseline_total,
        "target_tonnes": baseline["target_tonnes"],
        "impact_tonnes": round(scenario_total - baseline_total, 1),
        "model_version": baseline.get("model_version"),
        "data_type": "statistical_prediction",
        "note": "hypothetical scenario - model output, not an observed forecast",
    }


# The registry the LLM tool-use loop and the fallback formatter share.
TOOLS: dict[str, Tool] = {
    "production_shortfall": Tool(
        name="production_shortfall",
        description=(
            "Get the current 30-day production shortfall (target vs predicted "
            "tonnes, tonnes and percentage) and the PRD Section 15 risk level. "
            "Use for questions about whether production is behind target, how "
            "much production is expected, or the overall risk level."
        ),
        parameters=[
            {"name": "zone_id", "type": "string", "description": "Optional zone filter (e.g. A1, B3).", "required": False}
        ],
        function=_tool_shortfall,
        data_sources=["Production Model", "Shortfall Detection"],
    ),
    "shortfall_explain": Tool(
        name="shortfall_explain",
        description=(
            "Explain WHY production is expected to fall short: ranked SHAP "
            "contributor categories (equipment downtime, rainfall, blasting "
            "delays, ore grade) with percentages. Use for 'why is production "
            "expected to fall / below target' questions."
        ),
        parameters=[],
        function=_tool_explain,
        data_sources=["Production Model", "SHAP Explainability"],
    ),
    "recommendations": Tool(
        name="recommendations",
        description=(
            "Get the mine-wide prioritized reallocation recommendations: which "
            "equipment should be moved, from which zone to which zone, the "
            "reason, and the expected production/shortfall impact. Use for "
            "'which equipment should be moved' questions."
        ),
        parameters=[],
        function=_tool_recommendations,
        data_sources=["Optimization Engine", "Production Model"],
    ),
    "recommendation_for": Tool(
        name="recommendation_for",
        description=(
            "Get the reallocation recommendation for ONE equipment unit "
            "(e.g. EX-04): from/to zone, reason, before/after impact."
        ),
        parameters=[
            {"name": "equipment_id", "type": "string", "description": "Equipment id, e.g. EX-04.", "required": True}
        ],
        function=_tool_recommendation_for,
        data_sources=["Optimization Engine", "Production Model"],
    ),
    "schedule_risks": Tool(
        name="schedule_risks",
        description=(
            "Get the risk triggers on the current schedule: which equipment in "
            "which zone is at risk and why (weather rainfall threshold or "
            "shortfall). Use for 'which zone is risky' / 'why should we leave "
            "zone X' questions."
        ),
        parameters=[],
        function=_tool_risks,
        data_sources=["Optimization Engine", "Weather Data"],
    ),
    "alternatives_for": Tool(
        name="alternatives_for",
        description=(
            "Get ranked candidate alternative zones for one at-risk equipment, "
            "with multi-criteria scores (production risk, distance, equipment, "
            "prospectivity, shortfall delta). Use for 'which zone should we "
            "mine instead' questions."
        ),
        parameters=[
            {"name": "equipment_id", "type": "string", "description": "Equipment id, e.g. EX-04.", "required": True}
        ],
        function=_tool_alternatives,
        data_sources=["Optimization Engine", "Reserve Model", "Mineability"],
    ),
    "prospectivity": Tool(
        name="prospectivity",
        description=(
            "Get the statistical prospectivity score and HIGH/MEDIUM/LOW "
            "classification for one zone. Use for questions about how "
            "prospective or promising a zone is."
        ),
        parameters=[
            {"name": "zone_id", "type": "string", "description": "Zone id, e.g. B3.", "required": True}
        ],
        function=_tool_prospectivity,
        data_sources=["Reserve Model"],
    ),
    "resource_estimate": Tool(
        name="resource_estimate",
        description=(
            "Get the statistical resource estimate for one zone: estimated "
            "volume, tonnage, average Mn grade, contained Mn, and confidence "
            "level. Use for 'how much manganese is estimated in zone X' "
            "questions."
        ),
        parameters=[
            {"name": "zone_id", "type": "string", "description": "Zone id, e.g. B3.", "required": True}
        ],
        function=_tool_resource_estimate,
        data_sources=["Reserve Model", "Drilling Data"],
    ),
    "mineability_all": Tool(
        name="mineability_all",
        description=(
            "Get the mine-wide mineability ranking (all zones sorted by live "
            "score, Recommended/Conditional/Avoid-Postpone). Use for 'which "
            "zone should we mine today / first' questions."
        ),
        parameters=[],
        function=_tool_mineability_all,
        data_sources=["Mineability", "Weather Data", "Equipment Data"],
    ),
    "mineability": Tool(
        name="mineability",
        description=(
            "Get the live mineability score and Recommended/Conditional/"
            "Avoid-Postpone classification for ONE zone, with component "
            "breakdown. Use for questions about a specific zone's feasibility."
        ),
        parameters=[
            {"name": "zone_id", "type": "string", "description": "Zone id, e.g. B3.", "required": True}
        ],
        function=_tool_mineability,
        data_sources=["Mineability", "Weather Data", "Equipment Data"],
    ),
    "production_prediction": Tool(
        name="production_prediction",
        description=(
            "Get the current production prediction: predicted vs target tonnes "
            "for the 30-day schedule. Use for questions about expected "
            "production volume."
        ),
        parameters=[],
        function=_tool_production,
        data_sources=["Production Model"],
    ),
    "zone_shortfall": Tool(
        name="zone_shortfall",
        description=(
            "Get the shortfall and risk level for ONE zone in the current "
            "schedule. Use for follow-ups like 'what about zone C3'."
        ),
        parameters=[
            {"name": "zone_id", "type": "string", "description": "Zone id, e.g. C3.", "required": True}
        ],
        function=_tool_zone_risk,
        data_sources=["Production Model", "Shortfall Detection"],
    ),
    "weather_scenario": Tool(
        name="weather_scenario",
        description=(
            "What-if scenario: predict production if rainfall increases "
            "tomorrow in one zone. Takes the zone and the spike rainfall in mm. "
            "Use for 'what happens if rainfall increases tomorrow' questions."
        ),
        parameters=[
            {"name": "zone_id", "type": "string", "description": "Zone id, e.g. A1.", "required": True},
            {"name": "spike_1d", "type": "number", "description": "Rainfall spike in mm for tomorrow (default 110).", "required": False}
        ],
        function=_tool_weather_scenario,
        data_sources=["Production Model", "Weather Data"],
    ),
}

# ---------------------------------------------------------------------------
# System prompt — grounding guardrails (PRD Section 27)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Spotter AI, the natural-language assistant for a manganese mine planning platform. You answer questions about reserves, production, and mine scheduling at the MOIL Balaghat illustrative mine.

GROUNDING RULES (non-negotiable):
1. You may ONLY report figures, percentages, tonnages, zone classifications, and facts that were returned by the tool results in THIS turn. Never invent, estimate, or recall a number from training data.
2. If a question cannot be answered with the available tools, say so honestly: explain that the question is outside what the platform's models can answer, and suggest what you CAN answer. Never guess.
3. Never state a prospectivity percentage, tonnage, production figure, or risk classification that was not just retrieved from a real tool call.
4. If a tool result contains an error or a zone is not found, report that instead of substituting values.
5. Prefer the exact numbers from tool results when you quote figures.
6. Always distinguish a hypothetical scenario result (weather_scenario) from an observed forecast.

You have access to these tools:
- production_shortfall: current production shortfall + risk level (optionally per zone)
- shortfall_explain: why production is expected to fall short (SHAP contributor categories)
- recommendations: which equipment should be moved (mine-wide, prioritized)
- recommendation_for: reallocation recommendation for one equipment unit
- schedule_risks: risk triggers on the current schedule (weather + shortfall)
- alternatives_for: ranked candidate alternative zones for one equipment unit
- prospectivity: statistical prospectivity score for one zone
- resource_estimate: statistical resource estimate (tonnage/grade/contained Mn) for one zone
- mineability: live mineability score for one zone
- production_prediction: current production prediction (predicted vs target)
- zone_shortfall: shortfall + risk for one zone
- weather_scenario: what-if production impact of a rainfall increase tomorrow in one zone

Answer in clear, concise plain language for a mine planning engineer. Use the conversation history for context (for example a follow-up 'what about zone C3' refers to the zone mentioned earlier). Keep answers focused; if you used tools, you may briefly mention what data the answer is based on."""


def _tool_schema(tool: Tool) -> dict:
    """Anthropic tool-use schema for one tool."""
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": {
            "type": "object",
            "properties": {
                p["name"]: {"type": p["type"], "description": p["description"]}
                for p in tool.parameters
            },
            "required": [p["name"] for p in tool.parameters if p["required"]],
        },
    }


# ---------------------------------------------------------------------------
# LLM client (Anthropic) — lazy so the module imports without the SDK/key
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic() -> Any:
    """Lazy Anthropic client; None when no API key is configured."""
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client
    if not settings.llm_api_key:
        return None
    import anthropic

    _anthropic_client = anthropic.Anthropic(api_key=settings.llm_api_key)
    return _anthropic_client


# ---------------------------------------------------------------------------
# Multi-turn context
# ---------------------------------------------------------------------------


def _normalize_history(history: list[dict] | None) -> list[dict]:
    """Accept [{role, content}] turns; drop malformed or non-chat entries.

    Only user/assistant turns are forwarded to the LLM. The conversation
    history is trimmed to the most recent HISTORY_LIMIT messages.
    """
    HISTORY_LIMIT = 12
    valid: list[dict] = []
    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            valid.append({"role": role, "content": content.strip()})
    return valid[-HISTORY_LIMIT:]


def _llm_messages(history: list[dict], question: str) -> list[dict]:
    """Rolling conversation history + the current question."""
    messages = [dict(turn) for turn in history]
    messages.append({"role": "user", "content": question})
    return messages


# ---------------------------------------------------------------------------
# Zone / equipment extraction — used by the fallback formatter (and as a
# safety net when the LLM omits arguments)
# ---------------------------------------------------------------------------

_ZONE_RE = re.compile(r"\b(?:zone[-\s]?)?([A-C][1-3])\b", re.IGNORECASE)
_EQUIPMENT_RE = re.compile(r"\b(EX-\d{2}|T-\d{2}|DR-\d{2}|LD-\d{2})\b", re.IGNORECASE)


def _extract_zone(text: str) -> str | None:
    """Zone id from text, preferring the most specific match.

    "Zone B3" must extract B3, not B2: alias keys are checked longest-first
    so "zone b3" wins over "zone b", and the exact grid pattern
    ([A-C][1-3]) is the tie-breaker.
    """
    lowered = text.lower().strip()
    if lowered in ZONE_ALIASES:
        return ZONE_ALIASES[lowered]
    for alias in sorted(ZONE_ALIASES, key=len, reverse=True):
        if alias in lowered:
            return ZONE_ALIASES[alias]
    match = _ZONE_RE.search(text)
    return match.group(1).upper() if match else None


def _extract_equipment(text: str) -> str | None:
    match = _EQUIPMENT_RE.search(text.upper())
    return match.group(1).upper() if match else None


# ---------------------------------------------------------------------------
# Fallback formatter — deterministic, grounded (no LLM key / LLM failure)
# ---------------------------------------------------------------------------


def _sentence(pieces: list[str]) -> str:
    return " ".join(p for p in pieces if p)


def _fallback_answer(intent: str, results: dict[str, dict]) -> tuple[str, list[str]]:
    """Deterministic natural-language answer from real tool results.

    Returns (answer_text, data_sources_used). Mirrors the PRD Section 37
    example exchange: rainfall risk in the current zone + recommended move.
    """
    if intent == "why_production_falls":
        data = results["shortfall_explain"]
        contributors = data.get("contributors", [])
        if not contributors:
            return (
                "I could not compute the shortfall explanation right now.",
                ["Production Model", "SHAP Explainability"],
            )
        top = contributors[0]
        text = _sentence([
            f"Production is expected to fall short of the {_fmt_number(data.get('target_tonnes'))} t target "
            f"by about {_fmt_number(data.get('shortfall_tonnes'))} t.",
            f"The main driver is {top['label'].lower()} "
            f"({top.get('contribution_percentage', 0)}% of the shortfall attribution).",
            "The full breakdown is " + ", ".join(
                f"{c['label']} {c.get('contribution_percentage', 0)}%"
                for c in contributors
            ) + ".",
        ])
        return text, ["Production Model", "SHAP Explainability"]

    if intent == "mine_today":
        zones = results.get("mineability_all", {}).get("zones", [])
        if not zones:
            return (
                "I could not compute mineability rankings right now.",
                ["Mineability", "Weather Data", "Equipment Data"],
            )
        top = zones[0]
        text = _sentence([
            f"Based on live mineability, the best zone to mine today is {top['zone_id']} "
            f"({top.get('mineability_score', 0)} score, {top.get('classification', '')}).",
            f"Components: " + ", ".join(
                f"{key} {value}" for key, value in (top.get("components") or {}).items()
            ) + ".",
        ])
        return text, ["Mineability", "Weather Data", "Equipment Data"]

    if intent == "why_zone_postponed":
        zone = results.get("zone_id")
        risks = results.get("schedule_risks", {}).get("triggers", [])
        mineability = results.get("mineability", {})
        recs = results.get("recommendations", {}).get("recommendations", [])

        zone_triggers = [t for t in risks if t["current_zone_id"] == zone]
        reasons = []
        if zone_triggers:
            reasons.append(
                f"{zone} currently has a {zone_triggers[0]['severity']} risk trigger: "
                f"{zone_triggers[0]['risk_reason']}"
            )
        if mineability and mineability.get("classification") == "Avoid-Postpone":
            reasons.append(
                f"mineability is {mineability.get('mineability_score')} "
                f"({mineability.get('classification')})"
            )
        if not reasons:
            reasons.append(f"no active risk trigger or mineability issue is detected for {zone}")

        text = _sentence([
            f"Regarding why {zone} was postponed: " + "; ".join(reasons) + ".",
        ])

        # Surface the actionable recommendation if one exists (PRD §37 demo).
        move = next(
            (r for r in recs if r.get("from_zone") == zone),
            next((r for r in recs if r.get("to_zone") == zone), None),
        )
        if move:
            text += _sentence([
                f" The recommended action is to move {move['equipment_id']} "
                f"from {move['from_zone']} to {move['to_zone']} "
                f"({move.get('reason', '')}).",
            ])
        return text, ["Optimization Engine", "Weather Data", "Production Model"]

    if intent == "move_equipment":
        recs = results.get("recommendations", {}).get("recommendations", [])
        if not recs:
            return (
                "No equipment reallocation is currently recommended — the schedule "
                "has no active risk trigger.",
                ["Optimization Engine", "Production Model"],
            )
        top = recs[0]
        impact = top.get("expected_impact", {})
        text = _sentence([
            f"The top reallocation is to move {top['equipment_id']} from "
            f"{top['from_zone']} to {top['to_zone']} ({top.get('reason', '')}).",
            "Expected impact: production "
            f"{_fmt_number(impact.get('production_before'))} t -> "
            f"{_fmt_number(impact.get('production_after'))} t and shortfall "
            f"{_fmt_number(impact.get('shortfall_before'))} t -> "
            f"{_fmt_number(impact.get('shortfall_after'))} t.",
            f"Status: {top.get('status', '')} (requires approval).",
        ])
        return text, ["Optimization Engine", "Production Model"]

    if intent == "resource_estimate":
        estimate = results.get("resource_estimate", {})
        zone = results.get("zone_id")
        if estimate.get("error"):
            return (
                f"I could not find a resource estimate for zone {zone}.",
                ["Reserve Model", "Drilling Data"],
            )
        if estimate.get("insufficient_data"):
            return (
                f"Zone {zone} has insufficient drilling data, so no statistical "
                "resource estimate is available yet.",
                ["Reserve Model", "Drilling Data"],
            )
        text = _sentence([
            f"Zone {zone} is estimated to hold about {_fmt_number(estimate.get('estimated_tonnage'))} t "
            f"of manganese ore ({_fmt_number(estimate.get('estimated_volume_m3'))} m3), "
            f"with an average Mn grade of {estimate.get('avg_mn_grade')}% and "
            f"~{_fmt_number(estimate.get('estimated_contained_mn'))} t contained Mn.",
            f"Confidence: {estimate.get('confidence_level', '')}.",
            "This is a statistical estimate, not a certified reserve (PRD Section 8).",
        ])
        return text, ["Reserve Model", "Drilling Data"]

    if intent == "rainfall_scenario":
        scenario = results.get("weather_scenario", {})
        zone = scenario.get("zone_id") or results.get("zone_id")
        if scenario.get("error"):
            return (
                f"I could not run the rainfall scenario for zone {zone}: {scenario.get('error')}",
                ["Production Model", "Weather Data"],
            )
        text = _sentence([
            f"If rainfall in {zone} increases tomorrow ({scenario.get('scenario', '')}), "
            f"predicted production would drop from {_fmt_number(scenario.get('baseline_predicted_tonnes'))} t "
            f"to {_fmt_number(scenario.get('predicted_tonnes'))} t — an impact of "
            f"{abs(scenario.get('impact_tonnes', 0)):,.1f} t below the "
            f"{_fmt_number(scenario.get('target_tonnes'))} t target.",
            "This is a hypothetical model scenario, not an observed forecast.",
        ])
        return text, ["Production Model", "Weather Data"]

    if intent == "zone_shortfall":
        data = results.get("zone_shortfall", {})
        zone = results.get("zone_id")
        if data.get("error"):
            return (
                f"I could not find shortfall data for zone {zone}: {data.get('error')}",
                ["Production Model", "Shortfall Detection"],
            )
        text = _sentence([
            f"Zone {zone} is predicted to produce {_fmt_number(data.get('predicted'))} t "
            f"vs a planned {_fmt_number(data.get('target'))} t "
            f"({_fmt_number(data.get('shortfall_tonnes'))} t shortfall, "
            f"{data.get('shortfall_percentage')}%), a {data.get('risk_level')} risk level.",
        ])
        return text, ["Production Model", "Shortfall Detection"]

    if intent == "current_state":
        shortfall = results.get("shortfall", {})
        text = _sentence([
            f"Production is predicted at {_fmt_number(shortfall.get('predicted'))} t "
            f"against a target of {_fmt_number(shortfall.get('target'))} t "
            f"({_fmt_number(shortfall.get('shortfall_tonnes'))} t shortfall, "
            f"{shortfall.get('shortfall_percentage')}%), risk level {shortfall.get('risk_level')}.",
        ])
        return text, ["Production Model", "Shortfall Detection"]

    return (
        "I can't answer that from the mine data I have access to. I can help with "
        "production shortfalls and their causes, which zones to mine or move "
        "equipment to, resource estimates, and rainfall scenarios.",
        [],
    )


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

_FALLBACK_INTENTS: list[tuple[str, list[list[str]]]] = [
    # Each intent: list of token groups; ANY group must be fully present.
    # Ordered most-specific first so a zone "leave" question doesn't fall
    # into the generic "why production" bucket.
    ("rainfall_scenario", [["rainfall", "tomorrow"], ["rain", "tomorrow"], ["rainfall", "increas"], ["rain", "increas"], ["weather", "scenario"]]),
    ("resource_estimate", [["manganese", "estimated"], ["manganese", "estimate"], ["how much", "manganese"], ["reserve", "tonnage"], ["resource", "estimate"]]),
    ("move_equipment", [["equipment", "move"], ["equipment", "moved"], ["equipment", "relocat"], ["equipment", "reallocat"], ["move", "machine"], ["which", "excavator"]]),
    ("why_zone_postponed", [["leave", "zone"], ["postpon", "zone"], ["abandon", "zone"], ["defer", "zone"], ["why", "not", "mine", "zone"]]),
    ("mine_today", [["mine", "today"], ["which", "zone", "mine"], ["best", "zone"], ["where", "mine"], ["which", "zone", "should"]]),
    ("why_production_falls", [["why", "production"], ["production", "fall"], ["production", "short"], ["production", "below"], ["production", "drop"], ["below", "target"], ["why", "shortfall"]]),
    ("zone_shortfall", [["zone", "shortfall"], ["zone", "risk"], ["what", "about", "zone"]]),
    ("current_state", [["production", "status"], ["production", "predict"], ["how", "are", "we"], ["current", "target"]]),
]


def _fallback_intent(question: str) -> str:
    """Keyword intent classification used when the LLM is unavailable.

    Each intent has token groups; ANY group fully present in the question
    matches. Deliberately ordered so the most specific intents (rainfall,
    resource, move, zone-leave) win over the generic catch-alls. Returns
    "unhandled" when nothing matches — the assistant then declines
    honestly instead of inventing an answer.
    """
    lowered = question.lower()
    for intent, groups in _FALLBACK_INTENTS:
        for group in groups:
            if all(keyword in lowered for keyword in group):
                return intent
    return "unhandled"


def _fallback_plan(intent: str, question: str) -> tuple[list[str], dict]:
    """Tool-call plan for a fallback intent (a small deterministic mapping)."""
    zone = _extract_zone(question)
    equipment = _extract_equipment(question)

    if intent == "why_production_falls":
        return ["shortfall_explain"], {}
    if intent == "mine_today":
        return ["mineability_all"], {}
    if intent == "rainfall_scenario":
        # Default to the currently-favorable high-prospectivity zone (B3):
        # A1 is already under the demo storm (110mm), so spiking it would
        # show no impact. B3 is dry today — the hypothetical is meaningful.
        zone = zone or "B3"
        return ["weather_scenario"], {"weather_scenario": {"zone_id": zone}}
    if intent == "resource_estimate":
        zone = zone or "B3"
        return ["resource_estimate"], {"resource_estimate": {"zone_id": zone}}
    if intent == "move_equipment":
        if equipment:
            return ["recommendation_for"], {"recommendation_for": {"equipment_id": equipment}}
        return ["recommendations"], {}
    if intent == "why_zone_postponed":
        plan = ["schedule_risks", "recommendations"]
        kwargs: dict[str, dict] = {}
        if zone:
            plan.append("mineability")
            kwargs["mineability"] = {"zone_id": zone}
        return plan, kwargs
    if intent == "zone_shortfall":
        zone = zone or "B3"
        return ["zone_shortfall"], {"zone_shortfall": {"zone_id": zone}}
    if intent == "current_state":
        return ["production_shortfall"], {}
    return [], {}


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _execute(tool: Tool, args: dict) -> dict:
    """Execute one tool, tolerating missing optional args."""
    try:
        return tool.function(**args) or {}
    except Exception as exc:  # pragma: no cover - defensive at the boundary
        logger.warning("assistant tool %s failed: %s", tool.name, exc)
        return {"error": f"{tool.name} failed: {exc.__class__.__name__}"}


def _tool_inputs(tool_name: str, args: dict, question: str) -> dict:
    """Backfill missing args from the question (zone/equipment extraction)."""
    tool = TOOLS[tool_name]
    inputs = dict(args or {})
    for param in tool.parameters:
        if param["name"] not in inputs or inputs[param["name"]] in (None, ""):
            if param["name"] == "zone_id":
                zone = _extract_zone(question)
                if zone:
                    inputs[param["name"]] = zone
            elif param["name"] == "equipment_id":
                equipment = _extract_equipment(question)
                if equipment:
                    inputs[param["name"]] = equipment
    return inputs


# ---------------------------------------------------------------------------
# Anthropic tool-use loop
# ---------------------------------------------------------------------------


def _llm_plan(client: Any, messages: list[dict]) -> tuple[list[dict], str | None]:
    """One tool-use round: let the LLM pick tools + args; return (calls, raw).

    A single round is enough for the small tool set; the formatter call
    happens in the caller.
    """
    system_blocks = [{"type": "text", "text": SYSTEM_PROMPT}]
    try:
        resp = client.messages.create(
            model=settings.llm_model,
            max_tokens=1024,
            system=system_blocks,
            messages=messages,
            tools=[_tool_schema(t) for t in TOOLS.values()],
        )
    except Exception as exc:
        logger.warning("assistant LLM call failed: %s", exc)
        return [], None

    calls: list[dict] = []
    for block in resp.content or []:
        if getattr(block, "type", None) == "tool_use":
            calls.append(
                {"name": block.name, "input": getattr(block, "input", {}) or {}}
            )
    return calls, json.dumps(
        [{"type": getattr(b, "type", None), "text": getattr(b, "text", None)} for b in (resp.content or [])]
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def chat(message: str, conversation_history: list[dict] | None = None) -> dict:
    """Full assistant turn: classify -> call backend functions -> answer.

    Returns {response, functions_called, data_sources_used}. The response
    is ALWAYS grounded in real tool results (LLM never sees raw model
    access). Falls back to the deterministic formatter when the LLM is not
    configured or fails.
    """
    history = _normalize_history(conversation_history)
    question = message.strip()
    if not question:
        return {
            "response": "Please ask a question about reserves, production, or the mining schedule.",
            "functions_called": [],
            "data_sources_used": [],
        }

    audit: dict[str, Any] = {
        "question": question,
        "timestamp": date.today().isoformat(),
        "functions_called": [],
        "data_sources_used": [],
        "grounded": False,
        "llm_used": False,
        "response": None,
    }

    client = _get_anthropic()
    results: dict[str, dict] = {}
    functions_called: list[str] = []
    data_sources: list[str] = []
    formatter_override: str | None = None

    if client is not None:
        messages = _llm_messages(history, question)
        calls, _raw = _llm_plan(client, messages)
        audit["llm_used"] = True

        valid_calls = []
        for call in calls:
            tool = TOOLS.get(call["name"])
            if tool is None:
                continue
            inputs = _tool_inputs(call["name"], call.get("input", {}), question)
            result = _execute(tool, inputs)
            results[tool.name] = result
            valid_calls.append({"name": tool.name, "input": inputs})
            data_sources.extend(tool.data_sources)

        if valid_calls:
            functions_called = [c["name"] for c in valid_calls]
            audit["functions_called"] = functions_called
            audit["tool_inputs"] = {c["name"]: c["input"] for c in valid_calls}
            data_sources = list(dict.fromkeys(data_sources))
            audit["data_sources_used"] = data_sources

            context = _context_for_formatter(results)
            formatter_messages = _llm_messages(history, question)
            formatter_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool results from this turn (ground your answer ONLY in these):\n"
                        + json.dumps(context, indent=2, default=str)
                    ),
                }
            )
            try:
                resp = client.messages.create(
                    model=settings.llm_model,
                    max_tokens=1024,
                    system=[
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT
                            + "\n\nYour final answer must be a plain-language response to the user's last question, "
                            "grounded only in the tool results provided. Do not mention internal tool names unless useful.",
                        }
                    ],
                    messages=formatter_messages,
                )
                answer = "".join(
                    getattr(b, "text", "") or ""
                    for b in (resp.content or [])
                    if getattr(b, "type", None) == "text"
                ).strip()
                if answer:
                    formatter_override = answer
            except Exception as exc:
                logger.warning("assistant LLM format call failed: %s", exc)

    if not functions_called:
        # No LLM (or the LLM produced no usable tool call): deterministic path.
        intent = _fallback_intent(question)
        audit["fallback_intent"] = intent
        plan, kwargs = _fallback_plan(intent, question)
        for tool_name in plan:
            tool = TOOLS[tool_name]
            result = _execute(tool, kwargs.get(tool_name, {}))
            results[tool_name] = result
            functions_called.append(tool_name)
            data_sources.extend(tool.data_sources)
        data_sources = list(dict.fromkeys(data_sources))
        audit["functions_called"] = functions_called
        audit["data_sources_used"] = data_sources

    # The response is grounded iff at least one backend function was called.
    grounded = bool(functions_called)
    audit["grounded"] = grounded

    if not grounded:
        response = (
            "I can't answer that from the mine data I have access to. I can help with "
            "production shortfalls and their causes, which zones to mine or move "
            "equipment to, resource estimates, and rainfall scenarios. For example, "
            "try 'Why is production expected to fall?' or 'Which equipment should be moved?'"
        )
    elif formatter_override is not None:
        response = formatter_override
    else:
        intent = _fallback_intent(question)
        zone = _extract_zone(question)
        response, _ = _fallback_answer(intent, {**results, "zone_id": zone})

    audit["response"] = response
    _append_audit(audit)

    return {
        "response": response,
        "functions_called": functions_called,
        "data_sources_used": data_sources,
    }


def _context_for_formatter(results: dict[str, dict]) -> dict:
    """Compact the raw tool results for the LLM formatter prompt."""
    compact: dict[str, Any] = {}
    for name, result in results.items():
        if name == "recommendations":
            compact[name] = {
                "count": result.get("count"),
                "recommendations": [
                    {
                        "equipment_id": r.get("equipment_id"),
                        "from_zone": r.get("from_zone"),
                        "to_zone": r.get("to_zone"),
                        "reason": r.get("reason"),
                        "expected_impact": r.get("expected_impact"),
                        "status": r.get("status"),
                    }
                    for r in (result.get("recommendations") or [])
                ],
            }
        elif name == "mineability" and isinstance(result, dict) and "zones" in result:
            compact[name] = {
                "zones": [
                    {
                        "zone_id": z.get("zone_id"),
                        "mineability_score": z.get("mineability_score"),
                        "classification": z.get("classification"),
                        "components": z.get("components"),
                        "current_rainfall_1d": z.get("current_rainfall_1d"),
                    }
                    for z in (result.get("zones") or [])[:5]
                ]
            }
        else:
            compact[name] = result
    return compact


def _append_audit(entry: dict) -> None:
    """Append one JSON line per assistant turn (grounding audit trail)."""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:  # pragma: no cover - audit must never break the chat
        logger.warning("assistant audit write failed")


def read_audit(limit: int = 50) -> list[dict]:
    """Recent assistant audit entries (endpoint for demo/debugging)."""
    if not AUDIT_LOG_PATH.exists():
        return []
    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-limit:]
