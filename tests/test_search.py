from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from geosafe.search import normalize_search_text
from tests.helpers import DemoApplication


class LocalSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()
        rows = [
            ("osm-street-1", "street", "Rizal Street", "Rizal St", 11.5000, 125.2000,
             {"type": "LineString", "coordinates": [[125.19, 11.49], [125.21, 11.51]]}, "road", "residential"),
            ("osm-street-2", "street", "Rizal Street", None, 11.5100, 125.2100,
             {"type": "LineString", "coordinates": [[125.20, 11.50], [125.22, 11.52]]}, "road", "footway"),
            ("osm-street-3", "street", "San Juanico Road", None, 11.5200, 125.2200,
             {"type": "LineString", "coordinates": [[125.21, 11.51], [125.23, 11.53]]}, "road", "primary"),
            ("osm-node-4", "poi", "Basey Public Market", None, 11.5005, 125.2005,
             {"type": "Point", "coordinates": [125.2005, 11.5005]}, "amenity", "marketplace"),
        ]
        with self.application.repository.connection() as connection:
            connection.executemany(
                """
                INSERT INTO searchable_locations (
                    source_id, source_type, result_type, name, normalized_name,
                    alternate_name, normalized_alternate_name, barangay,
                    latitude, longitude, geometry_geojson, category, subtype,
                    source_name, snapshot_date, metadata_json, study_area_version
                ) VALUES (?, 'openstreetmap', ?, ?, ?, ?, ?, 'Test West', ?, ?, ?, ?, ?,
                          '© OpenStreetMap contributors', '2026-08-16', '{}', 'test-v1')
                """,
                [
                    (
                        source_id, kind, name, normalize_search_text(name), alternate,
                        normalize_search_text(alternate or "") or None, latitude, longitude,
                        json.dumps(geometry), category, subtype,
                    )
                    for source_id, kind, name, alternate, latitude, longitude, geometry, category, subtype in rows
                ],
            )
            connection.commit()

    def tearDown(self) -> None:
        self.application.close()

    def search(self, query: str, result_type: str | None = None) -> dict:
        return self.application.service.search_locations(query, result_type=result_type)

    def test_exact_street_match_ranks_first(self) -> None:
        items = self.search("Rizal Street")["items"]
        self.assertEqual(items[0]["name"], "Rizal Street")
        self.assertEqual(items[0]["relevance"], 0)

    def test_case_insensitive_and_punctuation_normalization(self) -> None:
        self.assertEqual(self.search("  RIZAL-street  ")["items"][0]["name"], "Rizal Street")

    def test_prefix_and_partial_matching(self) -> None:
        self.assertEqual(self.search("san j")["items"][0]["name"], "San Juanico Road")
        self.assertEqual(self.search("juanico")["items"][0]["name"], "San Juanico Road")

    def test_result_type_filter_and_poi(self) -> None:
        items = self.search("basey", "poi")["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "poi")
        self.assertEqual(items[0]["subtype"], "marketplace")

    def test_barangay_search_regression(self) -> None:
        items = self.search("Test West")["items"]
        self.assertTrue(any(item["kind"] == "barangay" for item in items))

    def test_coordinate_search_regression_and_coordinate_order(self) -> None:
        item = self.search("11.5, 125.25")["items"][0]
        self.assertEqual(item["kind"], "coordinate")
        self.assertEqual(item["latitude"], 11.5)
        self.assertEqual(item["longitude"], 125.25)

    def test_duplicate_road_names_are_preserved(self) -> None:
        streets = [item for item in self.search("Rizal", "street")["items"] if item["name"] == "Rizal Street"]
        self.assertEqual(len(streets), 2)
        self.assertNotEqual(streets[0]["source_id"], streets[1]["source_id"])

    def test_invalid_query_and_type(self) -> None:
        with self.assertRaisesRegex(Exception, "at least two"):
            self.search("r")
        with self.assertRaisesRegex(Exception, "type must be"):
            self.search("rizal", "house")

    def test_empty_result(self) -> None:
        self.assertEqual(self.search("not-in-the-index")["items"], [])

    def test_street_geometry_is_valid_geojson_longitude_latitude(self) -> None:
        geometry = self.search("Rizal", "street")["items"][0]["geometry"]
        self.assertEqual(geometry["type"], "LineString")
        self.assertGreater(geometry["coordinates"][0][0], 120)
        self.assertLess(geometry["coordinates"][0][1], 20)

    def test_search_api_alias(self) -> None:
        response = self.application.api.dispatch(
            "GET", "/api/search", {"q": ["Rizal"], "type": ["street"]}
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body)["items"][0]["kind"], "street")

    def test_runtime_search_makes_no_network_request(self) -> None:
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")) as call:
            self.assertTrue(self.search("Rizal")["items"])
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
