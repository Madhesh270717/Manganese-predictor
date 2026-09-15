"""Synthetic satellite data generator — Phase 7 (gap-fill).

Fills the fields that real Sentinel-2 access cannot provide free-tier
(see satellite_real.py + docs/synthetic_data_assumptions.md §11):

- ndvi: REAL when Planetary Computer fetch succeeds; otherwise falls back
  to this generator's synthetic NDVI (lower vegetation cover on the
  ore-rich cluster — mining-disturbed ground).
- lst: SYNTHETIC — seasonal land surface temperature (°C) with a strong
  monsoon-season dip and a small elevation-free baseline.
- soil_moisture: SYNTHETIC — seasonal %, high during monsoon (Jun–Sep),
  lower outside; inversely related to terrain risk used later by the
  Mineability model.
- spectral_features: JSONB with plausible band-ratio indicators
  (iron-oxide ratio B04/B02 elevated over the ore cluster — a known
  lithology proxy for Fe/Mn alteration surfaces).

Seasonal model: a month-of-year sinusoid, the same one the Phase 8 weather
generator will share, so monsoon rainfall and soil moisture align.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
from numpy.random import Generator, default_rng

from app.services.synthetic.geological_generator import HIGH_PROSPECTIVITY_ZONES

# --- seasonal helpers ---


def _season_factor(month: int, peak: float, low: float) -> float:
    """Sinusoidal annual cycle peaking in August (monsoon), low in Feb."""
    # phase such that cos peaks around month 8, trough around month 2
    return (peak - low) / 2 * math.cos(2 * math.pi * (month - 8) / 12) + (peak + low) / 2


# --- LST (synthetic) ---

LST_BASE = 30.0  # °C annual mean for the Balaghat belt
LST_SEASON_AMPLITUDE = 5.0  # °C swing (warmer Apr-May, cooler Dec-Jan)
LST_NOISE = 1.2
LST_CLUSTER_OFFSET = 1.5  # °C: exposed/disturbed ore surfaces run hotter


def lst_for_month(month: int, is_cluster: bool, rng: Generator) -> float:
    seasonal = LST_BASE - _season_factor(month, LST_SEASON_AMPLITUDE, -LST_SEASON_AMPLITUDE)
    offset = LST_CLUSTER_OFFSET if is_cluster else 0.0
    return round(float(seasonal + offset + rng.normal(0, LST_NOISE)), 2)


# --- soil moisture (synthetic) ---

SM_BASE = 18.0  # % annual mean
SM_SEASON_AMPLITUDE = 12.0  # % monsoon boost
SM_NOISE = 2.5
SM_CLUSTER_OFFSET = -4.0  # % — disturbed, fast-draining surfaces stay drier


def soil_moisture_for_month(month: int, is_cluster: bool, rng: Generator) -> float:
    seasonal = SM_BASE + _season_factor(month, SM_SEASON_AMPLITUDE, -SM_SEASON_AMPLITUDE)
    offset = SM_CLUSTER_OFFSET if is_cluster else 0.0
    value = max(0.0, seasonal + offset + rng.normal(0, SM_NOISE))
    return round(float(value), 2)


# --- synthetic NDVI fallback (only used when real fetch fails) ---

NDVI_BASE = 0.45
NDVI_SEASON_AMPLITUDE = 0.15  # greener post-monsoon
NDVI_NOISE = 0.06
NDVI_CLUSTER_OFFSET = -0.25  # ore cluster: less vegetation


def ndvi_for_month(month: int, is_cluster: bool, rng: Generator) -> float:
    seasonal = NDVI_BASE + _season_factor(month, NDVI_SEASON_AMPLITUDE, -NDVI_SEASON_AMPLITUDE)
    offset = NDVI_CLUSTER_OFFSET if is_cluster else 0.0
    value = np.clip(seasonal + offset + rng.normal(0, NDVI_NOISE), -0.1, 0.9)
    return round(float(value), 4)


# --- spectral features (synthetic band-ratio proxies) ---

IRON_OXIDE_BASE = 1.1  # B04/B02 ratio
IRON_OXIDE_CLUSTER = 1.9  # elevated over Fe/Mn alteration
IRON_OXIDE_NOISE = 0.12
CLAY_RATIO_BASE = 1.3
CLAY_RATIO_NOISE = 0.15


def spectral_features(zone_id: str, rng: Generator) -> dict:
    is_cluster = zone_id in HIGH_PROSPECTIVITY_ZONES
    iron_base = IRON_OXIDE_CLUSTER if is_cluster else IRON_OXIDE_BASE
    return {
        "iron_oxide_ratio_b4_b2": round(float(rng.normal(iron_base, IRON_OXIDE_NOISE)), 3),
        "clay_mineral_ratio_b11_b12": round(float(rng.normal(CLAY_RATIO_BASE, CLAY_RATIO_NOISE)), 3),
    }


def generate_satellite_records(
    zones: list,
    dates: list[date],
    real_ndvi: dict[str, dict[str, float]] | None = None,
    rng_seed: int = 9,
) -> list[dict]:
    """Generate one SATELLITE record dict per zone per date.

    Args:
        zones: Zone ORM rows (zone_id + geometry).
        dates: time-series dates (monthly).
        real_ndvi: {date_iso: {zone_id: ndvi}} from satellite_real fetch;
            when provided for a date, its REAL ndvi replaces the synthetic
            fallback for every zone.
        rng_seed: fixed seed.
    """
    rng: Generator = default_rng(rng_seed)
    records: list[dict] = []

    for zone in sorted(zones, key=lambda z: z.zone_id):
        zone_id = zone.zone_id
        is_cluster = zone_id in HIGH_PROSPECTIVITY_ZONES

        from geoalchemy2.shape import to_shape

        centroid = to_shape(zone.geometry).centroid

        for d in sorted(dates):
            month = d.month
            fetched = (real_ndvi or {}).get(d.isoformat(), {})
            if zone_id in fetched:
                ndvi = round(float(fetched[zone_id]), 4)
                ndvi_source = "real"
            else:
                ndvi = ndvi_for_month(month, is_cluster, rng)
                ndvi_source = "synthetic"

            records.append(
                {
                    "zone_id": zone_id,
                    "latitude": round(centroid.y, 6),
                    "longitude": round(centroid.x, 6),
                    "location": f"SRID=4326;POINT({centroid.x:.6f} {centroid.y:.6f})",
                    "date": d,
                    "ndvi": ndvi,
                    "lst": lst_for_month(month, is_cluster, rng),
                    "soil_moisture": soil_moisture_for_month(month, is_cluster, rng),
                    "spectral_features": {
                        **spectral_features(zone_id, rng),
                        "ndvi_source": ndvi_source,
                    },
                }
            )
    return records
