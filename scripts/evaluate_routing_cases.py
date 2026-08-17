#!/usr/bin/env python3
"""Export reproducible shortest-vs-lower-hazard research measurements to CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geosafe.server import create_application  # noqa: E402


FIELDS = (
    "test_case_id",
    "start_latitude",
    "start_longitude",
    "selected_destination",
    "shortest_route_distance_m",
    "hazard_aware_route_distance_m",
    "distance_difference_m",
    "distance_increase_percentage",
    "shortest_route_mean_hazard",
    "hazard_aware_route_mean_hazard",
    "shortest_route_maximum_hazard",
    "hazard_aware_route_maximum_hazard",
    "shortest_route_elevated_hazard_distance_m",
    "hazard_aware_route_elevated_hazard_distance_m",
    "route_computation_time_ms",
    "shortest_hazard_data_completeness",
    "hazard_aware_data_completeness",
    "status",
    "error_code",
    "error_message",
)


def route_value(route: dict, key: str):
    return (route or {}).get("routing", {}).get(key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", help="CSV with test_case_id, latitude, longitude")
    parser.add_argument("output_csv")
    parser.add_argument("--db", default=str(ROOT / "data" / "geosafe.db"))
    args = parser.parse_args()
    api, _, _ = create_application(
        database_path=args.db,
        enable_ulap=False,
        runtime_data_mode="snapshot",
    )
    rows: list[dict[str, object]] = []
    with Path(args.input_csv).open("r", encoding="utf-8-sig", newline="") as source:
        for index, item in enumerate(csv.DictReader(source), 1):
            case_id = item.get("test_case_id") or f"case-{index}"
            latitude = item.get("latitude")
            longitude = item.get("longitude")
            base: dict[str, object] = {
                "test_case_id": case_id,
                "start_latitude": latitude or "",
                "start_longitude": longitude or "",
            }
            try:
                result = api.service.calculate_route(
                    latitude,
                    longitude,
                    mode="hazard_aware",
                    scenario="multi_hazard",
                    include_comparison=True,
                )
                shortest = result["routes"].get("shortest", {})
                lower = result["routes"].get("lower_hazard", {})
                comparison = result.get("comparison") or {}
                base.update(
                    {
                        "selected_destination": result["destination"]["name"],
                        "shortest_route_distance_m": route_value(shortest, "distance_m"),
                        "hazard_aware_route_distance_m": route_value(lower, "distance_m"),
                        "distance_difference_m": comparison.get("distance_difference_m"),
                        "distance_increase_percentage": comparison.get("distance_increase_percent"),
                        "shortest_route_mean_hazard": route_value(shortest, "mean_hazard_exposure"),
                        "hazard_aware_route_mean_hazard": route_value(lower, "mean_hazard_exposure"),
                        "shortest_route_maximum_hazard": route_value(shortest, "maximum_hazard_exposure"),
                        "hazard_aware_route_maximum_hazard": route_value(lower, "maximum_hazard_exposure"),
                        "shortest_route_elevated_hazard_distance_m": route_value(shortest, "elevated_hazard_distance_m"),
                        "hazard_aware_route_elevated_hazard_distance_m": route_value(lower, "elevated_hazard_distance_m"),
                        "route_computation_time_ms": result["research_metrics"]["route_computation_time_ms"],
                        "shortest_hazard_data_completeness": route_value(shortest, "hazard_data_completeness"),
                        "hazard_aware_data_completeness": route_value(lower, "hazard_data_completeness"),
                        "status": "ok",
                        "error_code": "",
                        "error_message": "",
                    }
                )
            except Exception as exc:
                base.update(
                    {
                        "status": "error",
                        "error_code": getattr(exc, "code", type(exc).__name__),
                        "error_message": str(exc),
                    }
                )
            rows.append(base)
    with Path(args.output_csv).open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} routing evaluation case(s) to {args.output_csv}.")


if __name__ == "__main__":
    main()
