"""Grid generation service — Phase 4.

Splits the mine AOI into a regular row×column grid of cells, labels them
A1, A2, ... (row letters north→south, column numbers west→east), computes
geodesic area per cell, and upserts them into the ZONE table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from shapely.geometry import Polygon, box, mapping
from shapely.ops import unary_union

from app.core.mine_config import MineAOI
from app.models import Zone

WGS84_SRID = 4326


@dataclass(frozen=True)
class GridCell:
    zone_id: str
    row_label: str
    col_label: str
    geometry: Polygon  # shapely polygon, lon/lat (EPSG:4326)


def _row_letter(index: int) -> str:
    return chr(ord("A") + index)


def _geodesic_area_sq_m(polygon: Polygon) -> float:
    """Area of a lon/lat polygon in square metres (WGS84 geodesic).

    Uses pyproj when available; otherwise falls back to an equirectangular
    approximation scaled by the latitude cosine (good enough for AOI-scale
    cells in the tropics).
    """
    coords = list(polygon.exterior.coords)
    try:
        from pyproj import Geod

        geod = Geod(ellps="WGS84")
        area_sq_m, _ = geod.geometry_area_perimeter(polygon)
        return float(abs(area_sq_m))
    except ImportError:
        pass

    import math

    mid_lat = math.radians((polygon.bounds[1] + polygon.bounds[3]) / 2)
    scale_lon = 111_320.0 * math.cos(mid_lat)  # metres per degree longitude
    scale_lat = 110_540.0  # metres per degree latitude
    # Shoelace formula on scaled planar coordinates.
    area_deg = 0.0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        area_deg += x1 * y2 - x2 * y1
    return abs(area_deg / 2) * scale_lon * scale_lat


def generate_grid_cells(
    aoi: MineAOI,
    rows: int,
    cols: int,
) -> list[GridCell]:
    """Split the AOI into rows×cols labelled cells (A1.., north→south rows).

    Cells are lon/lat polygons (EPSG:4326), stored as WKT with SRID on insert.
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be positive integers")
    if rows > 26:
        raise ValueError("row count cannot exceed 26 (A–Z labelling)")

    minx, miny, maxx, maxy = aoi.bounds
    dx = (maxx - minx) / cols
    dy = (maxy - miny) / rows

    cells: list[GridCell] = []
    for r in range(rows):
        row_label = _row_letter(r)
        y0 = maxy - (r + 1) * dy  # north → south
        y1 = maxy - r * dy
        for c in range(cols):
            col_label = str(c + 1)
            x0 = minx + c * dx
            x1 = minx + (c + 1) * dx
            polygon = box(x0, y0, x1, y1)
            zone_id = f"{row_label}{col_label}"
            cells.append(GridCell(zone_id, row_label, col_label, polygon))
    return cells


def seed_zones_for_aoi(
    session: Session,
    aoi: MineAOI,
    rows: int,
    cols: int,
) -> int:
    """Generate cells for the AOI and upsert them into ZONE. Returns row count."""
    cells = generate_grid_cells(aoi, rows, cols)
    stmt = insert(Zone).values(
        [
            {
                "zone_id": cell.zone_id,
                "mine_id": aoi.mine_id,
                "geometry": f"SRID={WGS84_SRID};{cell.geometry.wkt}",
                "row_label": cell.row_label,
                "col_label": cell.col_label,
                "area_sq_m": _geodesic_area_sq_m(cell.geometry),
            }
            for cell in cells
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Zone.zone_id],
        set_={
            "mine_id": stmt.excluded.mine_id,
            "geometry": stmt.excluded.geometry,
            "row_label": stmt.excluded.row_label,
            "col_label": stmt.excluded.col_label,
            "area_sq_m": stmt.excluded.area_sq_m,
            "updated_at": Zone.updated_at,
        },
    )
    result = session.execute(stmt)
    session.commit()
    return result.rowcount


def zone_to_geojson_feature(zone: Zone) -> dict[str, Any]:
    """Convert one Zone row to a GeoJSON Feature (geometry parsed via shapely)."""
    from geoalchemy2.shape import to_shape

    geometry_geojson = mapping(to_shape(zone.geometry))
    return {
        "type": "Feature",
        "id": zone.zone_id,
        "geometry": geometry_geojson,
        "properties": {
            "zone_id": zone.zone_id,
            "mine_id": zone.mine_id,
            "row_label": zone.row_label,
            "col_label": zone.col_label,
            "area_sq_m": zone.area_sq_m,
        },
    }


def zones_to_geojson_feature_collection(zones: list[Zone]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": [zone_to_geojson_feature(z) for z in zones]}


def cells_to_geojson_feature_collection(cells: list[GridCell]) -> dict[str, Any]:
    features = [
        {
            "type": "Feature",
            "id": cell.zone_id,
            "geometry": mapping(cell.geometry),
            "properties": {
                "zone_id": cell.zone_id,
                "row_label": cell.row_label,
                "col_label": cell.col_label,
                "area_sq_m": _geodesic_area_sq_m(cell.geometry),
            },
        }
        for cell in cells
    ]
    return {"type": "FeatureCollection", "features": features}


def validate_grid(cells: list[GridCell], aoi: MineAOI) -> list[str]:
    """Basic geometric sanity checks. Returns a list of issue strings (empty = OK).

    Checks:
      1. cells fully tile the AOI (union == AOI bbox, no internal gaps),
      2. no two cells overlap with non-negligible area.
    """
    issues: list[str] = []
    expected = box(*aoi.bounds)
    union = unary_union([cell.geometry for cell in cells])

    gap = expected.difference(union).area
    excess = union.difference(expected).area
    # Tolerance: tiny numeric slivers only.
    if gap > 1e-9:
        issues.append(f"grid does not fully tile AOI: gap area {gap:.3e} deg^2")
    if excess > 1e-9:
        issues.append(f"grid extends beyond AOI: excess area {excess:.3e} deg^2")

    for i, cell_i in enumerate(cells):
        for cell_j in cells[i + 1 :]:
            overlap = cell_i.geometry.intersection(cell_j.geometry).area
            if overlap > 1e-9:
                issues.append(
                    f"cells {cell_i.zone_id} and {cell_j.zone_id} overlap by {overlap:.3e} deg^2"
                )

    return issues
