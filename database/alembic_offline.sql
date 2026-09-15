BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE zones (
    id SERIAL NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    mine_id VARCHAR(64) NOT NULL, 
    geometry geometry(GEOMETRY,4326) NOT NULL, 
    row_label VARCHAR(8), 
    col_label VARCHAR(8), 
    area_sq_m FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_zones PRIMARY KEY (id), 
    CONSTRAINT uq_zones_zone_id UNIQUE (zone_id)
);

CREATE INDEX ix_zones_mine_id ON zones (mine_id);

CREATE INDEX ix_zones_zone_id ON zones (zone_id);

CREATE INDEX ix_zones_geometry_gist ON zones USING gist (geometry);

CREATE TABLE geological (
    location_id VARCHAR(64) NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    latitude FLOAT, 
    longitude FLOAT, 
    location geometry(POINT,4326), 
    lithology VARCHAR(128), 
    geological_unit VARCHAR(128), 
    fault_distance FLOAT, 
    lineament_distance FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_geological PRIMARY KEY (location_id), 
    CONSTRAINT fk_geological_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_geological_zone_id ON geological (zone_id);

CREATE INDEX ix_geological_location_gist ON geological USING gist (location);

CREATE TABLE geochemical (
    location_id VARCHAR(64) NOT NULL, 
    mn_concentration FLOAT, 
    fe_concentration FLOAT, 
    sio2 FLOAT, 
    other_elements JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_geochemical PRIMARY KEY (location_id), 
    CONSTRAINT fk_geochemical_location_id_geological FOREIGN KEY(location_id) REFERENCES geological (location_id)
);

CREATE TABLE exploration (
    drill_id VARCHAR(64) NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    latitude FLOAT, 
    longitude FLOAT, 
    location geometry(POINT,4326), 
    depth FLOAT, 
    ore_thickness FLOAT, 
    mn_grade FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_exploration PRIMARY KEY (drill_id), 
    CONSTRAINT fk_exploration_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_exploration_zone_id ON exploration (zone_id);

CREATE INDEX ix_exploration_location_gist ON exploration USING gist (location);

CREATE TABLE satellite (
    id SERIAL NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    latitude FLOAT, 
    longitude FLOAT, 
    location geometry(POINT,4326), 
    date DATE NOT NULL, 
    ndvi FLOAT, 
    lst FLOAT, 
    soil_moisture FLOAT, 
    spectral_features JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_satellite PRIMARY KEY (id), 
    CONSTRAINT fk_satellite_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_satellite_date ON satellite (date);

CREATE INDEX ix_satellite_zone_id ON satellite (zone_id);

CREATE INDEX ix_satellite_location_gist ON satellite USING gist (location);

CREATE TABLE weather (
    id SERIAL NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    date DATE NOT NULL, 
    latitude FLOAT, 
    longitude FLOAT, 
    location geometry(POINT,4326), 
    rainfall_1d FLOAT, 
    rainfall_7d FLOAT, 
    rainfall_30d FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_weather PRIMARY KEY (id), 
    CONSTRAINT fk_weather_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_weather_date ON weather (date);

CREATE INDEX ix_weather_zone_id ON weather (zone_id);

CREATE INDEX ix_weather_location_gist ON weather USING gist (location);

CREATE TABLE production (
    id SERIAL NOT NULL, 
    date DATE NOT NULL, 
    mine_id VARCHAR(64) NOT NULL, 
    zone_id VARCHAR(16), 
    planned_production FLOAT, 
    actual_production FLOAT, 
    ore_grade FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_production PRIMARY KEY (id), 
    CONSTRAINT fk_production_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_production_date ON production (date);

CREATE INDEX ix_production_mine_id ON production (mine_id);

CREATE INDEX ix_production_zone_id ON production (zone_id);

CREATE TABLE equipment (
    equipment_id VARCHAR(64) NOT NULL, 
    mine_id VARCHAR(64) NOT NULL, 
    equipment_type VARCHAR(64), 
    current_zone_id VARCHAR(16), 
    availability FLOAT, 
    operating_hours FLOAT, 
    downtime_hours FLOAT, 
    maintenance_hours FLOAT, 
    capacity FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_equipment PRIMARY KEY (equipment_id), 
    CONSTRAINT fk_equipment_current_zone_id_zones FOREIGN KEY(current_zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_equipment_current_zone_id ON equipment (current_zone_id);

CREATE INDEX ix_equipment_mine_id ON equipment (mine_id);

CREATE TABLE blasting (
    blast_id VARCHAR(64) NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    planned_time TIMESTAMP WITH TIME ZONE, 
    actual_time TIMESTAMP WITH TIME ZONE, 
    delay_hours FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_blasting PRIMARY KEY (blast_id), 
    CONSTRAINT fk_blasting_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_blasting_zone_id ON blasting (zone_id);

CREATE TYPE schedule_status AS ENUM ('proposed', 'accepted', 'active', 'completed');

CREATE TABLE mining_schedule (
    id SERIAL NOT NULL, 
    date DATE NOT NULL, 
    shift VARCHAR(16), 
    equipment_id VARCHAR(64) NOT NULL, 
    zone_id VARCHAR(16) NOT NULL, 
    operation VARCHAR(64), 
    planned_start TIMESTAMP WITH TIME ZONE, 
    planned_end TIMESTAMP WITH TIME ZONE, 
    expected_output FLOAT, 
    status schedule_status DEFAULT 'proposed' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_mining_schedule PRIMARY KEY (id), 
    CONSTRAINT fk_mining_schedule_equipment_id_equipment FOREIGN KEY(equipment_id) REFERENCES equipment (equipment_id), 
    CONSTRAINT fk_mining_schedule_zone_id_zones FOREIGN KEY(zone_id) REFERENCES zones (zone_id)
);

CREATE INDEX ix_mining_schedule_date ON mining_schedule (date);

CREATE INDEX ix_mining_schedule_equipment_id ON mining_schedule (equipment_id);

CREATE INDEX ix_mining_schedule_zone_id ON mining_schedule (zone_id);

CREATE TYPE source_type AS ENUM ('real', 'synthetic');

CREATE TYPE confidence_level AS ENUM ('HIGH', 'MEDIUM', 'LOW', 'SYNTHETIC');

CREATE TABLE data_source_metadata (
    id SERIAL NOT NULL, 
    dataset_name VARCHAR(64) NOT NULL, 
    source_type source_type NOT NULL, 
    confidence_level confidence_level NOT NULL, 
    source_name VARCHAR(128) NOT NULL, 
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_data_source_metadata PRIMARY KEY (id), 
    CONSTRAINT uq_data_source_metadata_dataset_name UNIQUE (dataset_name)
);

CREATE INDEX ix_data_source_metadata_dataset_name ON data_source_metadata (dataset_name);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

CREATE UNIQUE INDEX uq_satellite_zone_id_date ON satellite (zone_id, date);

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

ALTER TABLE weather ADD COLUMN scenario VARCHAR(16) DEFAULT 'historical' NOT NULL;

CREATE UNIQUE INDEX uq_weather_zone_id_date ON weather (zone_id, date);

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

CREATE TABLE equipment_status_history (
    id SERIAL NOT NULL, 
    equipment_id VARCHAR(64) NOT NULL, 
    date DATE NOT NULL, 
    availability FLOAT, 
    operating_hours FLOAT, 
    downtime_hours FLOAT, 
    maintenance_hours FLOAT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_equipment_status_history PRIMARY KEY (id), 
    CONSTRAINT fk_equipment_status_history_equipment_id_equipment FOREIGN KEY(equipment_id) REFERENCES equipment (equipment_id)
);

CREATE UNIQUE INDEX uq_equip_hist_equipment_date ON equipment_status_history (equipment_id, date);

CREATE INDEX ix_equipment_status_history_equipment_id ON equipment_status_history (equipment_id);

CREATE INDEX ix_equipment_status_history_date ON equipment_status_history (date);

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

-- Running upgrade 0004 -> 0005

CREATE UNIQUE INDEX uq_production_date_zone_id ON production (date, zone_id);

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

COMMIT;

