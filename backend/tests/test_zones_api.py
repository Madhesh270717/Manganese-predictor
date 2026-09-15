"""API tests for the zones endpoints (dependency override, no live DB)."""

from geoalchemy2.elements import WKBElement
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.mine_config import DEFAULT_MINE_AOI
from app.main import app
from app.services.grid_generation import generate_grid_cells


def _fake_zone_orm(zone_id):
    cells = {c.zone_id: c for c in generate_grid_cells(DEFAULT_MINE_AOI, rows=4, cols=5)}
    cell = cells[zone_id]

    class ZoneRow:
        def __init__(self):
            self.zone_id = cell.zone_id
            self.mine_id = DEFAULT_MINE_AOI.mine_id
            self.row_label = cell.row_label
            self.col_label = cell.col_label
            self.area_sq_m = 5_000_000.0
            self.geometry = WKBElement(cell.geometry.wkb, srid=4326)

    return ZoneRow()


class ScalarResultStub:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, zones):
        self._zones = zones

    def scalar(self, stmt):
        zone_id = stmt._where_criteria[0].right.value
        return self._zones.get(zone_id)

    def scalars(self, stmt):
        return ScalarResultStub(list(self._zones.values()))

    def close(self):
        pass


def _client(zones):
    app.dependency_overrides[get_db] = lambda: FakeSession(zones)
    return TestClient(app)


def test_list_zones_returns_feature_collection():
    zones = {z: _fake_zone_orm(z) for z in [f"{r}{c}" for r in "ABCD" for c in "12345"]}
    client = _client(zones)
    resp = client.get("/api/v1/zones")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 20
    first = payload["features"][0]
    assert first["geometry"]["type"] == "Polygon"
    assert first["properties"]["zone_id"] == "A1"
    assert first["properties"]["mine_id"] == DEFAULT_MINE_AOI.mine_id


def test_get_single_zone_returns_feature():
    zones = {"B3": _fake_zone_orm("B3")}
    client = _client(zones)
    resp = client.get("/api/v1/zones/B3")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["type"] == "Feature"
    assert payload["id"] == "B3"
    assert payload["properties"]["zone_id"] == "B3"
    assert payload["geometry"]["type"] == "Polygon"


def test_get_unknown_zone_returns_404():
    client = _client({})
    resp = client.get("/api/v1/zones/ZZ9")
    assert resp.status_code == 404


class FakeGeological:
    def __init__(self):
        self.location_id = "SYN-GEO-B3"
        self.zone_id = "B3"
        self.latitude = 21.66
        self.longitude = 79.72
        self.lithology = "gondite"
        self.geological_unit = "Sausar Group - Mansar Formation (gondite)"
        self.fault_distance = 320.0
        self.lineament_distance = 450.0


class FakeGeochemical:
    def __init__(self):
        self.location_id = "SYN-GEO-B3"
        self.mn_concentration = 38.4
        self.fe_concentration = 6.1
        self.sio2 = 14.2
        self.other_elements = {"Al2O3": 3.2, "CaO": 0.8, "P": 0.15, "P2O5": 0.4}


class FakeMetaRow:
    def __init__(self, dataset_name, source_type, confidence_level, source_name, last_updated):
        self.dataset_name = dataset_name
        self.source_type = source_type
        self.confidence_level = confidence_level
        self.source_name = source_name
        self.last_updated = last_updated


class FakeZoneWithData:
    def __init__(self):
        self.zone_id = "B3"
        self.mine_id = DEFAULT_MINE_AOI.mine_id
        self.area_sq_m = 4_583_399.0


def _fake_meta(dataset_name):
    from datetime import datetime, timezone

    from app.models.enums import ConfidenceLevel, SourceType

    if dataset_name == "Exploration/Drilling":
        confidence, source_type = ConfidenceLevel.MEDIUM, SourceType.SYNTHETIC
    else:
        confidence, source_type = ConfidenceLevel.SYNTHETIC, SourceType.SYNTHETIC

    return FakeMetaRow(
        dataset_name=dataset_name,
        source_type=source_type,
        confidence_level=confidence,
        source_name="synthetic-generated",
        last_updated=datetime(2026, 8, 27, tzinfo=timezone.utc),
    )


class FakeGeoSession:
    def __init__(self):
        self._geological = FakeGeological()
        self._geochemical = FakeGeochemical()
        self._zone = FakeZoneWithData()

    def scalar(self, stmt):
        from app.models import DataSourceMetadata, Geochemical, Geological, Zone

        entity = stmt.column_descriptions[0]["entity"]
        if entity is Zone:
            return self._zone
        if entity is Geological:
            return self._geological
        if entity is Geochemical:
            return self._geochemical
        if entity is DataSourceMetadata:
            dataset = stmt._where_criteria[0].right.value
            return _fake_meta(dataset)
        return None

    def close(self):
        pass


def test_get_zone_geological_returns_combined_data():
    app.dependency_overrides[get_db] = lambda: FakeGeoSession()
    client = TestClient(app)
    resp = client.get("/api/v1/zones/B3/geological")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["zone_id"] == "B3"
    assert payload["geological"]["lithology"] == "gondite"
    assert payload["geochemical"]["mn_concentration"] == 38.4
    assert payload["confidence"]["geological"]["confidence_level"] == "SYNTHETIC"
    assert payload["confidence"]["geochemical"]["source_type"] == "synthetic"


class FakeHole:
    def __init__(self, drill_id, zone_id, mn_grade=38.0, ore_thickness=3.2):
        self.drill_id = drill_id
        self.zone_id = zone_id
        self.latitude = 21.66
        self.longitude = 79.72
        self.depth = 110.0
        self.ore_thickness = ore_thickness
        self.mn_grade = mn_grade


class FakeDrillingSession:
    def __init__(self):
        self._holes = {
            ("B3", "SYN-DH-B3-01"): FakeHole("SYN-DH-B3-01", "B3", 38.0, 3.2),
            ("B3", "SYN-DH-B3-02"): FakeHole("SYN-DH-B3-02", "B3", 41.0, 3.5),
        }
        self._zone = FakeZoneWithData()

    def scalar(self, stmt):
        from app.models import DataSourceMetadata, Exploration, Zone

        entity = stmt.column_descriptions[0]["entity"]
        if entity is Zone:
            return self._zone
        if entity is DataSourceMetadata:
            dataset = stmt._where_criteria[0].right.value
            return _fake_meta(dataset)
        if entity is Exploration:
            drill_id = stmt._where_criteria[0].right.value
            zone_id = stmt._where_criteria[1].right.value
            return self._holes.get((zone_id, drill_id))
        return None

    def scalars(self, stmt):
        return ScalarResultStub(sorted(self._holes.values(), key=lambda h: h.drill_id))

    def close(self):
        pass


def test_get_zone_drilling_returns_holes_and_density():
    app.dependency_overrides[get_db] = lambda: FakeDrillingSession()
    client = TestClient(app)
    resp = client.get("/api/v1/zones/B3/drilling")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["zone_id"] == "B3"
    assert len(payload["drill_holes"]) == 2
    assert payload["drill_holes"][0]["drill_id"] == "SYN-DH-B3-01"
    assert payload["drill_holes"][0]["mn_grade"] == 38.0
    assert payload["density"]["hole_count"] == 2
    assert payload["density"]["label"] in {"NONE", "SPARSE", "MODERATE", "DENSE"}
    assert payload["confidence"]["confidence_level"] == "MEDIUM"


def test_get_single_drill_hole():
    app.dependency_overrides[get_db] = lambda: FakeDrillingSession()
    client = TestClient(app)
    resp = client.get("/api/v1/zones/B3/drilling/SYN-DH-B3-01")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["drill_id"] == "SYN-DH-B3-01"
    assert payload["zone_id"] == "B3"
    assert payload["mn_grade"] == 38.0
    assert payload["confidence"]["confidence_level"] == "MEDIUM"


def test_get_unknown_drill_hole_404():
    app.dependency_overrides[get_db] = lambda: FakeDrillingSession()
    client = TestClient(app)
    resp = client.get("/api/v1/zones/B3/drilling/SYN-DH-NOPE")
    assert resp.status_code == 404


class FakeSatelliteRow:
    def __init__(self, row_id, zone_id, date_str, ndvi, lst, sm):
        from datetime import date as date_cls

        self.id = row_id
        self.zone_id = zone_id
        self.date = date_cls.fromisoformat(date_str)
        self.ndvi = ndvi
        self.lst = lst
        self.soil_moisture = sm
        self.spectral_features = {"ndvi_source": "synthetic"}


class FakeSatelliteSession:
    def __init__(self):
        self._rows = [
            FakeSatelliteRow(1, "B3", "2026-06-01", 0.35, 31.2, 8.5),
            FakeSatelliteRow(2, "B3", "2026-07-01", 0.42, 28.9, 22.4),
            FakeSatelliteRow(3, "B3", "2026-08-01", 0.51, 25.6, 30.1),
        ]
        self._zone = FakeZoneWithData()

    def scalar(self, stmt):
        from app.models import DataSourceMetadata, Satellite, Zone

        entity = stmt.column_descriptions[0]["entity"]
        if entity is Zone:
            return self._zone
        if entity is DataSourceMetadata:
            dataset = stmt._where_criteria[0].right.value
            return _fake_meta(dataset)
        if entity is Satellite:
            return self._rows[-1]
        return None

    def scalars(self, stmt):
        return ScalarResultStub(self._rows)

    def close(self):
        pass


def test_get_zone_satellite_returns_time_series():
    app.dependency_overrides[get_db] = lambda: FakeSatelliteSession()
    client = TestClient(app)
    resp = client.get("/api/v1/zones/B3/satellite")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["zone_id"] == "B3"
    assert payload["count"] == 3
    dates = [r["date"] for r in payload["series"]]
    assert dates == ["2026-06-01", "2026-07-01", "2026-08-01"]
    assert payload["series"][0]["soil_moisture"] == 8.5
    assert payload["confidence"]["confidence_level"] == "SYNTHETIC"


def test_get_zone_satellite_latest():
    app.dependency_overrides[get_db] = lambda: FakeSatelliteSession()
    client = TestClient(app)
    resp = client.get("/api/v1/zones/B3/satellite/latest")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["date"] == "2026-08-01"
    assert payload["ndvi"] == 0.51
    assert payload["lst"] == 25.6
