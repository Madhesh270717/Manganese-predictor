"""Tests for the grid generation service — Phase 4."""

import pytest

from app.core.mine_config import DEFAULT_GRID_COLS, DEFAULT_GRID_ROWS, DEFAULT_MINE_AOI
from app.services.grid_generation import (
    generate_grid_cells,
    validate_grid,
    zones_to_geojson_feature_collection,
)


def test_default_grid_has_20_cells():
    cells = generate_grid_cells(DEFAULT_MINE_AOI, rows=DEFAULT_GRID_ROWS, cols=DEFAULT_GRID_COLS)
    assert len(cells) == 20


def test_zone_labels_follow_row_letter_col_number():
    cells = generate_grid_cells(DEFAULT_MINE_AOI, rows=4, cols=5)
    assert [c.zone_id for c in cells[:5]] == ["A1", "A2", "A3", "A4", "A5"]
    assert cells[5].zone_id == "B1"
    assert cells[-1].zone_id == "D5"
    assert {c.row_label for c in cells} == {"A", "B", "C", "D"}
    assert {c.col_label for c in cells} == {"1", "2", "3", "4", "5"}


def test_configurable_rows_cols():
    cells = generate_grid_cells(DEFAULT_MINE_AOI, rows=3, cols=7)
    assert len(cells) == 21
    assert cells[-1].zone_id == "C7"


def test_rows_above_26_rejected():
    with pytest.raises(ValueError):
        generate_grid_cells(DEFAULT_MINE_AOI, rows=27, cols=5)


def test_grid_tiles_aoi_without_overlap_or_gaps():
    cells = generate_grid_cells(DEFAULT_MINE_AOI, rows=4, cols=5)
    assert validate_grid(cells, DEFAULT_MINE_AOI) == []


def test_geojson_feature_collection_has_expected_shape():
    cells = generate_grid_cells(DEFAULT_MINE_AOI, rows=4, cols=5)

    class FakeZone:
        def __init__(self, cell):
            from geoalchemy2.elements import WKBElement

            self.zone_id = cell.zone_id
            self.mine_id = DEFAULT_MINE_AOI.mine_id
            self.row_label = cell.row_label
            self.col_label = cell.col_label
            self.area_sq_m = 123_456.0
            self.geometry = WKBElement(cell.geometry.wkb, srid=4326)

    fc = zones_to_geojson_feature_collection([FakeZone(c) for c in cells])
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 20
    first = fc["features"][0]
    assert first["type"] == "Feature"
    assert first["geometry"]["type"] == "Polygon"
    assert first["properties"]["zone_id"] == "A1"
