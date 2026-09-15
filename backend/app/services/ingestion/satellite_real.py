"""Real satellite ingestion pipeline — Phase 7 (Sentinel-2 via Planetary Computer).

Fetches Sentinel-2 L2A scenes for the AOI, computes NDVI (B04 red / B08 NIR),
and aggregates pixel values to zone-level averages via rasterio zonal stats
against the Phase 4 ZONE polygons.

Real-data coverage (documented in docs/synthetic_data_assumptions.md §11):
- NDVI: REAL (Sentinel-2 B04/B08, free-tier Planetary Computer STAC API)
- LST: NOT AVAILABLE free-tier (needs Landsat thermal bands or MODIS L3
  processing) -> synthetic gap-fill by satellite_generator.py
- soil_moisture: NOT AVAILABLE free-tier (no direct Sentinel-2 product;
  NASA SMAP needs auth) -> synthetic gap-fill
- spectral_features: partially real (band ratios computed from Sentinel-2
  bands B02/B04/B08/B11) + synthetic iron-oxide proxy values

Requires rasterio (installed as 1.5.1 — newer wheel for Python 3.14).
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from shapely.geometry import mapping
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.mine_config import DEFAULT_MINE_AOI
from app.models import Zone

STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
COLLECTION = "sentinel-2-l2a"
BANDS = {"B02", "B04", "B08", "B11"}

# Sentinel-2 L2A: scaled surface reflectance (offset -1000, scale 0.0001).
REFLECTANCE_OFFSET = -1000
REFLECTANCE_SCALE = 0.0001


def search_scenes(
    start: str,
    end: str,
    limit: int = 8,
    aoi=None,
) -> list[dict]:
    """Query Planetary Computer STAC for Sentinel-2 scenes over the AOI."""
    aoi = aoi or DEFAULT_MINE_AOI
    bbox = f"{aoi.min_lon},{aoi.min_lat},{aoi.max_lon},{aoi.max_lat}"
    resp = httpx.get(
        STAC_SEARCH_URL,
        params={
            "collections": COLLECTION,
            "bbox": bbox,
            "datetime": f"{start}/{end}",
            "limit": limit,
        },
        timeout=60,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json().get("features", [])


def pick_best_scene(features: list[dict]) -> dict | None:
    """Least-cloudy scene among the STAC results."""
    candidates = [f for f in features if f.get("properties", {}).get("eo:cloud_cover") is not None]
    if not candidates:
        return features[0] if features else None
    return min(candidates, key=lambda f: f["properties"]["eo:cloud_cover"])


def _signed_href(asset: dict) -> str:
    """Append a Planetary Computer SAS token to a storage href.

    The underlying Azure blobs are private; account/container are parsed
    from the href (https://{account}.blob.core.windows.net/{container}/...)
    and a short-lived read token is fetched for them.
    """
    href = asset["href"]
    prefix = "https://"
    if not href.startswith(prefix):
        return href
    rest = href[len(prefix):]
    host, _, path = rest.partition("/")
    account = host.split(".")[0]
    container = path.split("/")[0]

    token_resp = httpx.get(
        f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{account}/{container}",
        timeout=30,
        follow_redirects=True,
    )
    token_resp.raise_for_status()
    token = token_resp.json()["token"]
    return f"{href}?{token}"


def download_band(feature: dict, band: str) -> bytes:
    """Download one band's COG bytes via the item's asset href (SAS-signed)."""
    signed = _signed_href(feature["assets"][band])
    resp = httpx.get(signed, timeout=180, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def compute_ndvi(red_bytes: bytes, nir_bytes: bytes) -> tuple[np.ndarray, dict]:
    """NDVI from B04 (red) and B08 (NIR) COGs. Returns (ndvi_array, transform+shape)."""
    with MemoryFile(red_bytes) as red_file, MemoryFile(nir_bytes) as nir_file:
        with red_file.open() as red_src, nir_file.open() as nir_src:
            red = red_src.read(1).astype(np.float32)
            nir = nir_src.read(1).astype(np.float32)
            transform = red_src.transform
            crs = red_src.crs

    red_r = (red + REFLECTANCE_OFFSET) * REFLECTANCE_SCALE
    nir_r = (nir + REFLECTANCE_OFFSET) * REFLECTANCE_SCALE
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir_r - red_r) / (nir_r + red_r)
    ndvi = np.nan_to_num(ndvi, nan=0.0, posinf=0.0, neginf=0.0)
    return ndvi, {"transform": transform, "crs": crs}


def zonal_mean_ndvi(ndvi_array: np.ndarray, zones: list[Zone], transform, crs) -> dict[str, float]:
    """Zone-level mean NDVI via rasterized polygon masks.

    Zone polygons are EPSG:4326; the Sentinel-2 tile is in its UTM CRS, so
    polygons are reprojected with pyproj before rasterizing.
    """
    from pyproj import Transformer
    from geoalchemy2.shape import to_shape

    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)

    results: dict[str, float] = {}
    for zone in zones:
        try:
            polygon = to_shape(zone.geometry)
            reprojected = _reproject_polygon(polygon, transformer)
            mask = rasterize(
                [(mapping(reprojected), 1)],
                out_shape=ndvi_array.shape,
                transform=transform,
                fill=0,
                dtype="uint8",
            )
            if mask.sum() == 0:
                results[zone.zone_id] = 0.0
                continue
            results[zone.zone_id] = float(ndvi_array[mask == 1].mean())
        except Exception:
            results[zone.zone_id] = 0.0
    return results


def _reproject_polygon(polygon, transformer):
    """Reproject a shapely polygon via pyproj coordinate transform."""
    from shapely.ops import transform as shapely_transform

    return shapely_transform(transformer.transform, polygon)


def fetch_ndvi_for_date(scene_date: date | str, zones: list[Zone]) -> dict[str, float] | None:
    """End-to-end: search, pick least-cloudy scene, compute zone NDVI means.

    The STAC API returns no features for equal start/end datetime, so the
    window is widened to ±3 days around the target date.

    Returns {zone_id: mean_ndvi} or None if no scene found.
    """
    target = date.fromisoformat(str(scene_date))
    start = (target - timedelta(days=3)).isoformat()
    end = (target + timedelta(days=3)).isoformat()
    features = search_scenes(start, end, limit=8)
    best = pick_best_scene(features)
    if best is None:
        return None

    red = download_band(best, "B04")
    nir = download_band(best, "B08")
    ndvi_array, meta = compute_ndvi(red, nir)
    return zonal_mean_ndvi(ndvi_array, zones, meta["transform"], meta["crs"])


def query_available_scene_dates(start: str, end: str) -> list[str]:
    """Distinct scene dates in a range (for building the time series)."""
    features = search_scenes(start, end, limit=50)
    dates = sorted({f["properties"]["datetime"][:10] for f in features})
    return dates


def load_zones_from_db() -> list[Zone]:
    """Zones from the database (used by the seed script)."""
    with SessionLocal() as session:
        return list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())


if __name__ == "__main__":
    # Manual probe: fetch one recent scene's NDVI and print per-zone means.
    zones = load_zones_from_db()
    scene_date = "2025-09-29"
    print(f"Probing Sentinel-2 for {scene_date} over {len(zones)} zones...")
    result = fetch_ndvi_for_date(scene_date, zones)
    if result is None:
        print("No scene found.")
    else:
        for zone_id, mean in sorted(result.items()):
            print(f"  {zone_id}: NDVI {mean:.4f}")
