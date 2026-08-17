from __future__ import annotations

import unittest

from geosafe.geometry import GeometryError, point_in_geometry
from geosafe.study_area import (
    TOWN_PROPER_BARANGAYS,
    combine_polygon_geometries,
    normalized_barangay_name,
)


class TownProperStudyAreaTests(unittest.TestCase):
    def test_expected_barangays_are_explicit(self) -> None:
        self.assertEqual(
            TOWN_PROPER_BARANGAYS,
            ("Mercado", "Palaypay", "Baybay", "Sulod", "Loyo", "Buscada", "Lawa-an"),
        )
        self.assertEqual(normalized_barangay_name("Mercado (Pob.)"), "mercado")

    def test_polygon_and_multipolygon_members_are_preserved(self) -> None:
        first = {
            "type": "Polygon",
            "coordinates": [[[125.0, 11.0], [125.1, 11.0], [125.1, 11.1], [125.0, 11.0]]],
        }
        second_polygon = [
            [[125.2, 11.2], [125.3, 11.2], [125.3, 11.3], [125.2, 11.2]]
        ]
        combined = combine_polygon_geometries(
            [first, {"type": "MultiPolygon", "coordinates": [second_polygon]}]
        )
        self.assertEqual(combined["type"], "MultiPolygon")
        self.assertEqual(len(combined["coordinates"]), 2)
        self.assertTrue(point_in_geometry(11.02, 125.02, combined))
        self.assertTrue(point_in_geometry(11.22, 125.22, combined))
        self.assertFalse(point_in_geometry(11.15, 125.15, combined))

    def test_non_polygon_component_is_rejected(self) -> None:
        with self.assertRaises(GeometryError):
            combine_polygon_geometries([{"type": "Point", "coordinates": [125, 11]}])


if __name__ == "__main__":
    unittest.main()
