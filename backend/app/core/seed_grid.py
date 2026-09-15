"""Seed the ZONE grid for the configured mine AOI — Phase 4.

Idempotent: re-running upserts the same zone_ids in place, so no duplicate
zones are created. Generates a GeoJSON preview to the scratchpad so the
grid can be inspected without a database.

Usage:
    python -m app.core.seed_grid              # seed with defaults
    python -m app.core.seed_grid --rows 4 --cols 5
    python -m app.core.seed_grid --dry-run    # print summary without touching DB
"""

import argparse
import json
import os
import sys

from app.core.database import SessionLocal
from app.core.mine_config import DEFAULT_GRID_COLS, DEFAULT_GRID_ROWS, DEFAULT_MINE_AOI
from app.services.grid_generation import (
    cells_to_geojson_feature_collection,
    generate_grid_cells,
    seed_zones_for_aoi,
    validate_grid,
)

SCRATCHPAD_DIR = os.environ.get("COMMANDCODE_SCRATCHPAD")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the ZONE grid for the mine AOI.")
    parser.add_argument("--rows", type=int, default=DEFAULT_GRID_ROWS)
    parser.add_argument("--cols", type=int, default=DEFAULT_GRID_COLS)
    parser.add_argument("--dry-run", action="store_true", help="validate and print only")
    args = parser.parse_args()

    aoi = DEFAULT_MINE_AOI
    cells = generate_grid_cells(aoi, rows=args.rows, cols=args.cols)

    issues = validate_grid(cells, aoi)
    if issues:
        for issue in issues:
            print(f"[WARN] {issue}", file=sys.stderr)
        return 1

    print(
        f"AOI: {aoi.mine_name} ({aoi.mine_id}) "
        f"bbox=({aoi.min_lon}, {aoi.min_lat}) -> ({aoi.max_lon}, {aoi.max_lat})"
    )
    print(f"Grid: {args.rows} rows x {args.cols} cols = {len(cells)} zones "
          f"({cells[0].zone_id} ... {cells[-1].zone_id})")

    fc = cells_to_geojson_feature_collection(cells)
    if SCRATCHPAD_DIR:
        out_path = os.path.join(SCRATCHPAD_DIR, "zones_preview.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(fc, f)
        print(f"GeoJSON preview written to {out_path}")

    if args.dry_run:
        print("Dry run - no database changes.")
        return 0

    with SessionLocal() as session:
        count = seed_zones_for_aoi(session, aoi, rows=args.rows, cols=args.cols)
    print(f"Seeded {count} zone rows (idempotent upsert).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
