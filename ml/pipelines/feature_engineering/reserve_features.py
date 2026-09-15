"""Reserve feature builder — Phase 11.

One row per zone combining geological, geochemical, drilling (aggregated),
and satellite (latest) features for the Phase 12 Reserve Prospectivity
Model. Sparse/missing drilling is NOT dropped — it's flagged via
`has_drilling_data` so the model can treat undrilled zones as prospectivity
candidates rather than data errors.

Pure transformation functions: the caller supplies the source tables
(loaders.py provides DB- and synthetic-backed sources).
"""

from __future__ import annotations

import pandas as pd


def build_reserve_features(
    zones: pd.DataFrame,
    geological: pd.DataFrame,
    geochemical: pd.DataFrame,
    exploration: pd.DataFrame,
    satellite: pd.DataFrame,
) -> pd.DataFrame:
    """Join all reserve-relevant sources into one row per zone.

    Expected columns:
      zones:        [zone_id, mine_id, area_sq_m]
      geological:   [location_id, zone_id, lithology, geological_unit,
                     fault_distance, lineament_distance]
      geochemical:  [location_id, mn_concentration, fe_concentration, sio2,
                     other_elements]
      exploration:  [drill_id, zone_id, depth, ore_thickness, mn_grade]
      satellite:    [zone_id, date, ndvi, lst, soil_moisture, spectral_features]
    """
    features = zones[["zone_id", "mine_id", "area_sq_m"]].copy()

    # --- geological (join on zone_id; one row per zone expected) ---
    geo = geological[["zone_id", "lithology", "geological_unit", "fault_distance", "lineament_distance"]]
    features = features.merge(geo, on="zone_id", how="left", validate="one_to_one")

    # --- geochemical (join via geological location_id) ---
    geo_loc = geological[["zone_id", "location_id"]]
    chem = geochemical[["location_id", "mn_concentration", "fe_concentration", "sio2", "other_elements"]]
    chem = geo_loc.merge(chem, on="location_id", how="left").drop(columns=["location_id"])
    features = features.merge(chem, on="zone_id", how="left", validate="one_to_one")

    # Trace elements flattened from JSONB dict.
    trace_cols = ["Al2O3", "CaO", "P", "P2O5"]
    for col in trace_cols:
        features[f"trace_{col}"] = features["other_elements"].map(
            lambda d: d.get(col) if isinstance(d, dict) else None
        )
    features = features.drop(columns=["other_elements"])

    # --- drilling aggregates per zone + explicit missingness flag ---
    drill_agg = (
        exploration.groupby("zone_id")
        .agg(
            drill_hole_count=("drill_id", "count"),
            drill_avg_depth=("depth", "mean"),
            drill_avg_ore_thickness=("ore_thickness", "mean"),
            drill_avg_mn_grade=("mn_grade", "mean"),
        )
        .reset_index()
    )
    features = features.merge(drill_agg, on="zone_id", how="left")
    features["has_drilling_data"] = features["drill_hole_count"].notna()
    features["drill_hole_count"] = features["drill_hole_count"].fillna(0)

    # --- satellite: latest reading per zone ---
    sat = satellite.sort_values("date").groupby("zone_id").last().reset_index()
    sat = sat[
        ["zone_id", "ndvi", "lst", "soil_moisture", "spectral_features"]
    ].rename(
        columns={
            "ndvi": "sat_ndvi",
            "lst": "sat_lst",
            "soil_moisture": "sat_soil_moisture",
        }
    )
    features = features.merge(sat, on="zone_id", how="left")
    features["sat_iron_oxide_ratio"] = features["spectral_features"].map(
        lambda d: d.get("iron_oxide_ratio_b4_b2") if isinstance(d, dict) else None
    )
    features = features.drop(columns=["spectral_features"])

    # --- label encoding for categoricals (deterministic, order-stable) ---
    for col in ("lithology", "geological_unit"):
        if features[col].notna().any():
            features[f"{col}_encoded"] = features[col].astype("category").cat.codes

    return features
