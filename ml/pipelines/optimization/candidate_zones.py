"""Candidate zone selection — Phase 19 (PRD Section 19).

Given an at-risk equipment/zone pair, identify PLAUSIBLE alternative zones
(a handful, not all 20 — matching the PRD's "evaluates Zone B, C, D"
framing). Filtering logic (documented):

1. exclude the equipment's current zone
2. require ore access: zone prospectivity >= 40% (Phase 12) — the PRD's
   alternative-evaluation framing is prospectivity-driven ("evaluates
   Zone B, C, D"), which yields a handful of candidates (B2/B3/C2/C3)
   rather than all 20 zones
3. require reasonable haul distance: <= 12 km from the zone's terrain data
   (Phase 14) — the equipment's travel-time feasibility bound

Zones passing all three filters are returned for multi-criteria evaluation.
"""

from __future__ import annotations

PROSPECTIVITY_MIN = 40.0
HAUL_MAX_KM = 12.0


def select_candidate_zones(
    equipment_id: str,
    current_zone_id: str,
) -> list[str]:
    """Filtered alternative zones for one at-risk equipment."""
    from app.services.mineability_service import _terrain_by_zone
    from app.services.reserve_model_service import get_prospectivity

    terrain = _terrain_by_zone()
    candidates = []
    for zone_id, t in terrain.items():
        if zone_id == current_zone_id:
            continue

        # Filter 2: ore access (prospectivity-driven, PRD §19 framing).
        prospectivity = get_prospectivity(zone_id)
        if prospectivity is None or prospectivity["prospectivity_score"] < PROSPECTIVITY_MIN:
            continue

        # Filter 3: haul distance bound.
        haul = t.get("haul_km")
        if haul is not None and haul > HAUL_MAX_KM:
            continue

        candidates.append(zone_id)

    return sorted(candidates)
