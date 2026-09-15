# ERD — Spotter AI Core Schema (Phase 2)

> Matches the Master Data Model (PRD Section 29). Everything hangs off the
> central **zones** grid; per-dataset tables reference `zones.zone_id`.
> Geometry columns are PostGIS types in SRID 4326.

## Legend

- **FK** arrows point from referencing table → referenced table.
- Solid arrows = required FK (NOT NULL), dashed arrows = nullable FK.
- All tables carry `created_at` / `updated_at` (omitted from the diagram for readability).
- All `*_location` / `geometry` columns are PostGIS geometries with a GIST index.

## Diagram (Mermaid)

```mermaid
erDiagram
    ZONES ||--o{ GEOLOGICAL : "zone_id FK"
    ZONES ||--o{ GEOCHEMICAL : "via geological"
    ZONES ||--o{ EXPLORATION : "zone_id FK"
    ZONES ||--o{ SATELLITE : "zone_id FK"
    ZONES ||--o{ WEATHER : "zone_id FK"
    ZONES ||--o{ PRODUCTION : "zone_id FK (nullable)"
    ZONES ||--o{ EQUIPMENT : "current_zone_id FK (nullable)"
    ZONES ||--o{ BLASTING : "zone_id FK"
    ZONES ||--o{ MINING_SCHEDULE : "zone_id FK"
    EQUIPMENT ||--o{ MINING_SCHEDULE : "equipment_id FK"
    GEOLOGICAL ||--o| GEOCHEMICAL : "location_id FK"

    ZONES {
        int id PK
        varchar zone_id UK "e.g. 'B3'"
        varchar mine_id
        geometry geometry "PostGIS GEOMETRY, SRID 4326"
        varchar row_label
        varchar col_label
        float area_sq_m
        timestamptz created_at
        timestamptz updated_at
    }

    GEOLOGICAL {
        varchar location_id PK
        varchar zone_id FK
        float latitude
        float longitude
        geometry location "POINT, SRID 4326"
        varchar lithology
        varchar geological_unit
        float fault_distance
        float lineament_distance
    }

    GEOCHEMICAL {
        varchar location_id PK, FK "→ geological"
        float mn_concentration
        float fe_concentration
        float sio2
        jsonb other_elements
    }

    EXPLORATION {
        varchar drill_id PK
        varchar zone_id FK
        float latitude
        float longitude
        geometry location "POINT, SRID 4326"
        float depth
        float ore_thickness
        float mn_grade
    }

    SATELLITE {
        int id PK
        varchar zone_id FK
        float latitude
        float longitude
        geometry location "POINT, SRID 4326"
        date date "indexed"
        float ndvi
        float lst
        float soil_moisture
        jsonb spectral_features
    }

    WEATHER {
        int id PK
        varchar zone_id FK
        date date "indexed"
        float latitude
        float longitude
        geometry location "POINT, SRID 4326"
        float rainfall_1d
        float rainfall_7d
        float rainfall_30d
    }

    PRODUCTION {
        int id PK
        date date "indexed"
        varchar mine_id
        varchar zone_id FK "nullable"
        float planned_production
        float actual_production
        float ore_grade
    }

    EQUIPMENT {
        varchar equipment_id PK
        varchar mine_id
        varchar equipment_type
        varchar current_zone_id FK "nullable → zones"
        float availability
        float operating_hours
        float downtime_hours
        float maintenance_hours
        float capacity
    }

    BLASTING {
        varchar blast_id PK
        varchar zone_id FK
        timestamptz planned_time
        timestamptz actual_time
        float delay_hours
    }

    MINING_SCHEDULE {
        int id PK
        date date "indexed"
        varchar shift
        varchar equipment_id FK "→ equipment"
        varchar zone_id FK "→ zones"
        varchar operation
        timestamptz planned_start
        timestamptz planned_end
        float expected_output
        enum status "proposed/accepted/active/completed"
    }

    DATA_SOURCE_METADATA {
        int id PK
        varchar dataset_name UK
        enum source_type "real/synthetic"
        enum confidence_level "HIGH/MEDIUM/LOW/SYNTHETIC"
        varchar source_name
        timestamptz last_updated
    }
```

## Indexes

| Table | Index | Type | Purpose |
| --- | --- | --- | --- |
| zones | `zone_id`, `mine_id` | btree | lookups |
| zones | `geometry` | **GIST** | spatial queries |
| geological / exploration / satellite / weather | `zone_id` | btree | FK joins |
| geological / exploration / satellite / weather | `location` | **GIST** | spatial queries |
| satellite / weather / production / mining_schedule | `date` | btree | time-range queries |
| production | `mine_id`, `zone_id` | btree | aggregation |
| equipment | `mine_id`, `current_zone_id` | btree | fleet/zone lookups |
| blasting | `zone_id` | btree | FK joins |
| mining_schedule | `equipment_id`, `zone_id` | btree | FK joins |

## Notes

- **Geochemical** is 1:1 with **Geological** (same `location_id`); no own `zone_id`
  column — zone resolution goes through `geological.zone_id`.
- **Production.zone_id** and **Equipment.current_zone_id** are nullable by design
  (PRD: production is reported per mine, zone attribution may be unknown;
  equipment may be unassigned/in transit).
- Enum types: `source_type` (real/synthetic), `confidence_level`
  (HIGH/MEDIUM/LOW/SYNTHETIC), `schedule_status` (proposed/accepted/active/completed).
