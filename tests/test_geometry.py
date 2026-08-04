from __future__ import annotations

import unittest

from geosafe.geometry import (
    GeometryError,
    geometry_bbox,
    haversine_km,
    point_in_geometry,
    validate_wgs84_point,
)


class GeometryTests(unittest.TestCase):
    polygon_with_hole = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
            [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
        ],
    }

    def test_point_in_polygon_and_hole(self) -> None:
        self.assertTrue(point_in_geometry(2, 2, self.polygon_with_hole))
        self.assertFalse(point_in_geometry(5, 5, self.polygon_with_hole))
        self.assertFalse(point_in_geometry(20, 20, self.polygon_with_hole))

    def test_boundary_is_inside(self) -> None:
        self.assertTrue(point_in_geometry(0, 5, self.polygon_with_hole))

    def test_point_can_match_line_and_geometry_collection_context(self) -> None:
        collection = {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "LineString", "coordinates": [[0, 0], [10, 10]]},
                {"type": "Point", "coordinates": [20, 20]},
            ],
        }
        self.assertTrue(point_in_geometry(5, 5, collection))
        self.assertTrue(point_in_geometry(20, 20, collection))
        self.assertFalse(point_in_geometry(4, 5, collection))

    def test_bbox_and_distance(self) -> None:
        self.assertEqual(geometry_bbox(self.polygon_with_hole), [0, 0, 10, 10])
        self.assertAlmostEqual(haversine_km(0, 0, 0, 1), 111.195, places=2)

    def test_invalid_coordinate_rejected(self) -> None:
        with self.assertRaises(GeometryError):
            validate_wgs84_point(91, 0)


if __name__ == "__main__":
    unittest.main()
