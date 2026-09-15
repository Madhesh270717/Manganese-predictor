"""Feature pipeline runner — Phase 11.

Runs both feature builders end-to-end and writes:
  ml/data/processed/reserve_features.parquet
  ml/data/processed/production_features.parquet
  ml/data/processed/feature_quality_report.json

Parquet chosen over CSV for typed columns (dates, dicts) and round-trip
fidelity. Idempotent: re-running overwrites the outputs.

Usage (from repo root):
  python -m ml.pipelines.feature_engineering.run_pipeline            # DB
  python -m ml.pipelines.feature_engineering.run_pipeline --synthetic  # no DB
  python -m ml.pipelines.feature_engineering.run_pipeline --synthetic --csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "ml" / "data" / "processed"

from ml.pipelines.feature_engineering.loaders import (  # noqa: E402
    load_from_db,
    load_from_synthetic,
)
from ml.pipelines.feature_engineering.production_features import (  # noqa: E402
    build_production_features,
)
from ml.pipelines.feature_engineering.reserve_features import (  # noqa: E402
    build_reserve_features,
)
from ml.pipelines.feature_engineering.feature_quality import (  # noqa: E402
    check_production_features,
    check_reserve_features,
    summary_report,
)


def run(source: str, fmt: str = "parquet") -> dict:
    loader = load_from_db if source == "db" else load_from_synthetic
    data = loader()

    reserve = build_reserve_features(
        zones=data["zones"],
        geological=data["geological"],
        geochemical=data["geochemical"],
        exploration=data["exploration"],
        satellite=data["satellite"],
    )
    production = build_production_features(
        production=data["production"],
        equipment=data["equipment"],
        equipment_history=data["equipment_history"],
        weather=data["weather"],
        blasting=data["blasting"],
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if fmt == "parquet":
        reserve_path = OUTPUT_DIR / "reserve_features.parquet"
        production_path = OUTPUT_DIR / "production_features.parquet"
        reserve.to_parquet(reserve_path, index=False)
        production.to_parquet(production_path, index=False)
    else:
        reserve_path = OUTPUT_DIR / "reserve_features.csv"
        production_path = OUTPUT_DIR / "production_features.csv"
        reserve.to_csv(reserve_path, index=False)
        production.to_csv(production_path, index=False)

    reserve_report = check_reserve_features(reserve)
    production_report = check_production_features(production)
    report = summary_report(reserve_report, production_report)

    report_path = OUTPUT_DIR / "feature_quality_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))

    return {
        "reserve_rows": len(reserve),
        "production_rows": len(production),
        "reserve_path": str(reserve_path),
        "production_path": str(production_path),
        "report_path": str(report_path),
        "quality": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the feature engineering pipeline.")
    parser.add_argument("--synthetic", action="store_true", help="use synthetic loader (no DB)")
    parser.add_argument("--csv", action="store_true", help="write CSV instead of parquet")
    args = parser.parse_args()

    source = "synthetic" if args.synthetic else "db"
    fmt = "csv" if args.csv else "parquet"
    result = run(source, fmt)

    print(f"Reserve features:     {result['reserve_rows']} rows -> {result['reserve_path']}")
    print(f"Production features:  {result['production_rows']} rows -> {result['production_path']}")
    print(f"Quality report:       {result['report_path']}")
    quality = result["quality"]
    print(f"  reserve issues:     {quality['reserve']['issues'] or 'none'}")
    print(f"  production issues:  {quality['production']['issues'] or 'none'}")
    print(f"  overall_ok:         {quality['overall_ok']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
