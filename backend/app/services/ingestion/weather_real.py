"""Real weather ingestion — Phase 8 (IMD gridded rainfall via imdlib).

Fetches IMD 0.25° daily rainfall for the AOI, then disaggregates the AOI
mean to zone level with correlated spatial noise (the AOI is ~1 IMD pixel,
so zone-to-zone variation is synthetic but anchored to real magnitudes and
timing — documented in docs/synthetic_data_assumptions.md §12).

Rolling aggregates (rainfall_1d/7d/30d) are computed from the daily series,
never independently randomized.
"""

from __future__ import annotations

from datetime import date, timedelta

import imdlib as imd
import numpy as np


def fetch_imd_rainfall(
    year: int,
    file_dir: str,
    aoi_bounds: tuple[float, float, float, float],
    shp_dir: str,
) -> dict[date, float]:
    """Download one year of IMD daily rainfall and clip to the AOI.

    Returns {date: aoi_mean_rainfall_mm}.
    """
    import geopandas as gpd
    from shapely.geometry import box

    lon_min, lat_min, lon_max, lat_max = aoi_bounds

    aoi = gpd.GeoDataFrame(
        {"name": ["aoi"]},
        geometry=[box(lon_min, lat_min, lon_max, lat_max)],
        crs="EPSG:4326",
    )
    aoi_path = f"{shp_dir}/aoi_bbox.shp"
    aoi.to_file(aoi_path)

    data = imd.get_data(
        var_type="rain",
        start_yr=year,
        end_yr=year,
        fn_format="yearwise",
        file_dir=file_dir,
    )
    data.clip(aoi_path)
    ds = data.get_xarray()

    daily = ds.rain.mean(dim=("lat", "lon"))
    times = ds.rain["time"].values
    out: dict[date, float] = {}
    for t, value in zip(times, daily.values):
        d = date.fromisoformat(str(t)[:10])
        v = float(value)
        out[d] = 0.0 if (v is None or np.isnan(v)) else v
    return out


def rolling_sum(series: dict[date, float], days: int, on_date: date) -> float:
    """Sum of the last `days` days ending on_date (inclusive)."""
    total = 0.0
    for i in range(days):
        total += series.get(on_date - timedelta(days=i), 0.0)
    return round(total, 1)


def build_zone_series(
    aoi_daily: dict[date, float],
    zones: list,
    rng_seed: int = 33,
    spatial_noise: float = 0.25,
) -> list[dict]:
    """Disaggregate AOI-level daily rainfall to zones with correlated noise.

    Each zone gets a persistent multiplicative factor ~N(1, spatial_noise),
    so adjacent zones are similar in expectation (shared AOI magnitude)
    but not identical. Returns weather record dicts with rolling aggregates.
    """
    rng = np.random.default_rng(rng_seed)
    zone_factors = {zone.zone_id: float(rng.normal(1.0, spatial_noise)) for zone in zones}

    records: list[dict] = []
    for zone in zones:
        zone_id = zone.zone_id
        factor = zone_factors[zone_id]
        daily = {
            d: round(v * factor, 1)
            for d, v in aoi_daily.items()
        }
        for d in sorted(daily):
            records.append(
                {
                    "zone_id": zone_id,
                    "date": d,
                    "latitude": None,
                    "longitude": None,
                    "rainfall_1d": daily[d],
                    "rainfall_7d": rolling_sum(daily, 7, d),
                    "rainfall_30d": rolling_sum(daily, 30, d),
                }
            )
    return records
