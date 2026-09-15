"""Feature → PRD-category mapping — Phase 17.

Rolls granular model features into the readable categories PRD Section 16
presents (Equipment downtime, Rainfall, Blasting delays, Ore grade, ...).

Mapping design decision (documented): SHAP values measure how much each
feature MOVED this instance's prediction away from the model's expected
value. Within a category we sum the ABSOLUTE SHAP contributions, so
categories aggregate the total influence of their member features on the
shortfall. Percentages are normalized across categories so they sum to
~100% for the top contributors — matching the PRD's presentation format.
"""

from __future__ import annotations

# category -> (label, list of raw feature names)
CATEGORY_MAP: dict[str, tuple[str, list[str]]] = {
    "equipment": (
        "Equipment downtime",
        ["fleet_downtime", "fleet_availability", "fleet_maintenance", "active_units", "fleet_capacity"],
    ),
    "rainfall": (
        "Rainfall",
        ["rainfall_1d", "rainfall_7d", "rainfall_30d"],
    ),
    "blasting": (
        "Blasting delays",
        ["blast_delay_same_day", "blast_delay_last_3d"],
    ),
    "ore_grade": (
        "Ore grade",
        ["ore_grade"],
    ),
    "planned": (
        "Planned production",
        ["planned_production"],
    ),
}

# Categories shown in PRD §16's shortfall-contributor format. "Planned
# production" is excluded: it is the target baseline, not a shortfall
# CAUSE — the PRD's contributor list explains why actual fell short, and
# planned is the reference it fell short of.
SHORTFALL_CONTRIBUTOR_CATEGORIES = ["equipment", "rainfall", "blasting", "ore_grade"]


def rollup_to_categories(shap_rows: list[dict]) -> list[dict]:
    """Aggregate ranked raw SHAP rows into PRD categories.

    Returns [{category, label, total_shap_value, contribution_percentage}]
    sorted by contribution desc, normalized to sum ~100%.
    """
    by_feature = {row["feature_name"]: row["shap_value"] for row in shap_rows}

    categories = []
    for category, (label, features) in CATEGORY_MAP.items():
        total = sum(abs(by_feature.get(f, 0.0)) for f in features)
        categories.append(
            {
                "category": category,
                "label": label,
                "total_shap_value": round(total, 3),
            }
        )

    grand = sum(c["total_shap_value"] for c in categories) or 1.0
    for c in categories:
        c["contribution_percentage"] = round(c["total_shap_value"] / grand * 100.0, 1)

    categories.sort(key=lambda c: c["contribution_percentage"], reverse=True)
    return categories


def shortfall_contributors(shap_rows: list[dict]) -> list[dict]:
    """PRD §16-format contributor list: only shortfall-cause categories,
    normalized to sum ~100%.
    """
    rolled = rollup_to_categories(shap_rows)
    contributors = [c for c in rolled if c["category"] in SHORTFALL_CONTRIBUTOR_CATEGORIES]
    total = sum(c["contribution_percentage"] for c in contributors) or 1.0
    for c in contributors:
        c["contribution_percentage"] = round(c["contribution_percentage"] / total * 100.0, 1)
    return contributors
