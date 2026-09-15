"""Synthetic geochemical data generator — Phase 5.

Generates GEOCHEMICAL records (linked via location_id to GEOLOGICAL) with
values correlated to the documented ground-truth manganese-rich cluster:

- mn_concentration: HIGH zones ~30–46%, background ~8–24%
  (typical Indian manganese ore: 10–48% Mn)
- fe_concentration: loosely co-occurs with Mn (HIGH zones 4–9%,
  background 2–7%)
- sio2: inversely correlated with ore quality (HIGH zones 8–22%,
  background 25–55%)
- other_elements: JSONB trace elements (Al2O3, CaO, P) in plausible ranges
"""

from __future__ import annotations

import numpy as np
from numpy.random import Generator, default_rng

from app.services.synthetic.geological_generator import HIGH_PROSPECTIVITY_ZONES

# Realistic geochemical ranges (percent) for Indian manganese ore.
MN_RANGE_HIGH = (30.0, 46.0)
MN_RANGE_LOW = (8.0, 24.0)
FE_RANGE_HIGH = (4.0, 9.0)
FE_RANGE_LOW = (2.0, 7.0)
SIO2_RANGE_HIGH = (8.0, 22.0)
SIO2_RANGE_LOW = (25.0, 55.0)

AL2O3_RANGE = (1.0, 8.0)
CAO_RANGE = (0.1, 2.5)
P_RANGE = (0.05, 0.35)


def _trace_elements(rng: Generator, is_high: bool) -> dict:
    """Trace elements as JSONB dict (plausible ranges; slight signal too)."""
    return {
        "Al2O3": round(float(rng.uniform(*AL2O3_RANGE)), 2),
        "CaO": round(float(rng.uniform(*CAO_RANGE)), 2),
        "P": round(float(rng.uniform(*P_RANGE)), 3),
        "P2O5": round(float(rng.uniform(0.1, 0.8) if is_high else rng.uniform(0.05, 0.5)), 2),
    }


def generate_geochemical_records(
    geological_records: list[dict],
    rng_seed: int = 7,
) -> list[dict]:
    """Generate one GEOCHEMICAL record dict per geological record.

    Args:
        geological_records: list of dicts from geological_generator
            (each has location_id and zone_id).
        rng_seed: fixed seed for reproducibility (different from geological
            so the two streams stay independent).
    """
    rng: Generator = default_rng(rng_seed)

    records: list[dict] = []
    for geo in geological_records:
        zone_id = geo["zone_id"]
        is_high = zone_id in HIGH_PROSPECTIVITY_ZONES

        mn = float(rng.uniform(*(MN_RANGE_HIGH if is_high else MN_RANGE_LOW)))
        fe = float(rng.uniform(*(FE_RANGE_HIGH if is_high else FE_RANGE_LOW)))
        sio2 = float(rng.uniform(*(SIO2_RANGE_HIGH if is_high else SIO2_RANGE_LOW)))

        records.append(
            {
                "location_id": geo["location_id"],
                "mn_concentration": round(mn, 2),
                "fe_concentration": round(fe, 2),
                "sio2": round(sio2, 2),
                "other_elements": _trace_elements(rng, is_high),
            }
        )
    return records
