from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

from geosafe.routing import (
    HazardAwareRouter,
    RoutingConfig,
    RoutingError,
    generalized_edge_cost,
)
from tests.helpers import DemoApplication, polygon


def routing_config(graph_path: Path, risk_factor: float = 2.0) -> RoutingConfig:
    return RoutingConfig(
        config_version="test-1",
        algorithm="astar",
        network_type="walk",
        risk_factor=risk_factor,
        walking_speed_kph=4.5,
        elevated_hazard_threshold=0.6,
        maximum_snap_distance_m=500.0,
        minimum_hazard_completeness=1.0,
        missing_hazard_policy="reject_edge",
        study_area_version="test-area-v1",
        road_network_source="Synthetic test graph",
        road_network_date="2026-08-16",
        road_graph_path=graph_path,
        fuzzy_model_version="test-model",
        hazard_dataset_versions={"multi_hazard": "test"},
        evacuation_center_dataset_version="test-centers-v1",
        planning_disclaimer="Planning aid only; not a guarantee of safety.",
    )


def edge(length: float, hazard: float | None) -> dict[str, object]:
    result: dict[str, object] = {
        "length_m": length,
        "hazard_complete": hazard is not None,
        "hazard_data_completeness": 1.0 if hazard is not None else 0.0,
    }
    if hazard is not None:
        result["multi_hazard_score"] = hazard * 100.0
    return result


def alternative_graph() -> nx.DiGraph:
    graph = nx.DiGraph(
        snapshot_version="test-graph-v1",
        source="Synthetic test graph",
        acquisition_date="2026-08-16",
        model_version="test-model",
    )
    graph.add_node("A", x=125.0000, y=11.5000)
    graph.add_node("B", x=125.0009, y=11.5000)
    graph.add_node("C", x=125.0009, y=11.5009)
    graph.add_node("D", x=125.0018, y=11.5000)
    graph.add_edge("A", "B", **edge(110, 0.9))
    graph.add_edge("B", "D", **edge(110, 0.9))
    graph.add_edge("A", "C", **edge(160, 0.05))
    graph.add_edge("C", "D", **edge(160, 0.05))
    return graph


class RoutingAlgorithmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()
        self.temp = tempfile.TemporaryDirectory()
        self.graph_path = Path(self.temp.name) / "walk.graphml"
        with self.application.repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO routing_study_areas (
                    name, version, geometry_geojson, source_name,
                    source_metadata_json, is_official, is_active
                ) VALUES ('Town proper test area', 'test-area-v1', ?,
                          'Synthetic test fixture', '{}', 0, 1)
                """,
                (polygon(124.99, 11.49, 125.02, 11.52),),
            )
            connection.execute(
                """
                INSERT INTO evacuation_centers (
                    external_id, name, latitude, longitude, designation,
                    source_name, source_metadata_json, dataset_version, is_official, active
                ) VALUES ('D', 'Center D', 11.5000, 125.0018,
                          'Designated Evacuation Center', 'Synthetic test fixture',
                          '{}', 'test-centers-v1', 1, 1)
                """
            )
            connection.commit()

    def tearDown(self) -> None:
        self.temp.cleanup()
        self.application.close()

    def router(self, graph: nx.Graph | None = None, risk_factor: float = 2.0) -> HazardAwareRouter:
        return HazardAwareRouter(
            self.application.repository,
            routing_config(self.graph_path, risk_factor),
            graph=graph,
        )

    def test_basic_shortest_route(self) -> None:
        graph = nx.DiGraph()
        graph.add_node("A", x=125.0000, y=11.5000)
        graph.add_node("B", x=125.0009, y=11.5000)
        graph.add_node("D", x=125.0018, y=11.5000)
        graph.add_edge("A", "B", **edge(110, 0.2))
        graph.add_edge("B", "D", **edge(110, 0.2))
        result = self.router(graph).route(
            11.5, 125.0, mode="shortest", include_comparison=False
        )
        self.assertEqual(result["route"]["coordinates"], [
            [125.0, 11.5], [125.0009, 11.5], [125.0018, 11.5]
        ])
        self.assertEqual(result["routing"]["distance_m"], 220.0)

    def test_lower_hazard_route_can_be_longer(self) -> None:
        graph = alternative_graph()
        shortest = self.router(graph).route(
            11.5, 125.0, mode="shortest", include_comparison=False
        )
        lower = self.router(graph).route(
            11.5, 125.0, mode="hazard_aware", include_comparison=False
        )
        self.assertEqual(shortest["routing"]["distance_m"], 220.0)
        self.assertEqual(shortest["routing"]["maximum_hazard_exposure"], 90.0)
        self.assertEqual(lower["routing"]["distance_m"], 320.0)
        self.assertEqual(lower["routing"]["maximum_hazard_exposure"], 5.0)
        self.assertIn([125.0009, 11.5009], lower["route"]["coordinates"])

    def test_equal_hazard_reduces_to_distance_preference(self) -> None:
        graph = alternative_graph()
        for _, _, data in graph.edges(data=True):
            data["multi_hazard_score"] = 30.0
        result = self.router(graph).route(
            11.5, 125.0, mode="hazard_aware", include_comparison=False
        )
        self.assertEqual(result["routing"]["distance_m"], 220.0)

    def test_multidigraph_parallel_edges_use_lowest_valid_cost(self) -> None:
        graph = nx.MultiDiGraph()
        graph.add_node("A", x=125.0000, y=11.5000)
        graph.add_node("D", x=125.0018, y=11.5000)
        graph.add_edge("A", "D", key="short-high", **edge(220, 0.9))
        graph.add_edge("A", "D", key="long-low", **edge(300, 0.05))
        shortest = self.router(graph).route(
            11.5, 125.0, mode="shortest", include_comparison=False
        )
        lower = self.router(graph).route(
            11.5, 125.0, mode="hazard_aware", include_comparison=False
        )
        self.assertEqual(shortest["routing"]["distance_m"], 220.0)
        self.assertEqual(lower["routing"]["distance_m"], 300.0)
        self.assertEqual(lower["routing"]["maximum_hazard_exposure"], 5.0)

    def test_hazard_cost_is_monotonic(self) -> None:
        costs = [generalized_edge_cost(100, hazard, 2.0) for hazard in (0, .2, .7, 1)]
        self.assertEqual(costs, sorted(costs))
        self.assertEqual(costs[0], 100)
        self.assertEqual(costs[-1], 300)

    def test_missing_hazard_is_never_zero(self) -> None:
        graph = alternative_graph()
        for _, _, data in graph.edges(data=True):
            data["hazard_complete"] = False
            data.pop("multi_hazard_score", None)
        with self.assertRaises(RoutingError) as caught:
            self.router(graph).route(
                11.5, 125.0, mode="hazard_aware", include_comparison=False
            )
        self.assertEqual(caught.exception.code, "incomplete_hazard_data")

    def test_disconnected_center_is_not_recommended(self) -> None:
        graph = alternative_graph()
        graph.add_node("Z", x=125.01, y=11.51)
        with self.application.repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO evacuation_centers (
                    external_id, name, latitude, longitude, designation,
                    source_name, source_metadata_json, dataset_version, is_official, active
                ) VALUES ('Z', 'Disconnected Center', 11.51, 125.01,
                          'Designated Evacuation Center', 'Synthetic test fixture',
                          '{}', 'test-centers-v1', 1, 1)
                """
            )
            connection.commit()
        result = self.router(graph).route(
            11.5, 125.0, mode="shortest", include_comparison=False
        )
        self.assertEqual(result["destination"]["name"], "Center D")
        self.assertEqual(result["candidate_centers_evaluated"], 1)

    def test_multiple_centers_are_ranked_by_route_cost(self) -> None:
        graph = alternative_graph()
        with self.application.repository.connection() as connection:
            connection.execute("UPDATE evacuation_centers SET active = 0")
            connection.executemany(
                """
                INSERT INTO evacuation_centers (
                    external_id, name, latitude, longitude, designation,
                    source_name, source_metadata_json, dataset_version, is_official, active
                ) VALUES (?, ?, ?, ?, 'Designated Evacuation Center',
                          'Synthetic test fixture', '{}', 'test-centers-v2', 1, 1)
                """,
                [
                    ("B2", "Near high-exposure center", 11.5000, 125.0009),
                    ("C2", "Farther low-exposure center", 11.5009, 125.0009),
                ],
            )
            connection.commit()
        result = self.router(graph).route(
            11.5, 125.0, mode="hazard_aware", include_comparison=False
        )
        self.assertEqual(result["destination"]["name"], "Farther low-exposure center")
        self.assertEqual(result["candidate_centers_evaluated"], 2)

    def test_outside_town_proper_returns_structured_error(self) -> None:
        with self.assertRaises(RoutingError) as caught:
            self.router(alternative_graph()).route(11.7, 125.2)
        self.assertEqual(caught.exception.code, "outside_routing_area")

    def test_no_route_is_handled(self) -> None:
        graph = alternative_graph()
        graph.remove_edges_from(list(graph.edges))
        with self.assertRaises(RoutingError) as caught:
            self.router(graph).route(
                11.5, 125.0, mode="shortest", include_comparison=False
            )
        self.assertEqual(caught.exception.code, "no_reachable_center")

    def test_geojson_is_longitude_latitude_and_valid_linestring(self) -> None:
        result = self.router(alternative_graph()).route(
            11.5, 125.0, mode="shortest", include_comparison=False
        )
        self.assertEqual(result["route"]["type"], "LineString")
        self.assertEqual(result["route"]["coordinates"][0], [125.0, 11.5])
        self.assertGreater(len(result["route"]["coordinates"]), 1)

    def test_runtime_uses_local_graph_without_network_download(self) -> None:
        nx.write_graphml(alternative_graph(), self.graph_path)
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")) as call:
            result = self.router().route(
                11.5, 125.0, mode="hazard_aware", include_comparison=False
            )
        self.assertEqual(result["status"], "ok")
        call.assert_not_called()

    def test_non_persistent_point_evaluation_does_not_create_history(self) -> None:
        result = self.application.service.evaluate_point(
            11.5, 125.25, persist=False, local_only=True
        )
        self.assertEqual(result["result"]["status"], "complete")
        with self.application.repository.connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
        self.assertEqual(count, 0)


class RoutingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()
        self.temp = tempfile.TemporaryDirectory()
        graph_path = Path(self.temp.name) / "walk.graphml"
        with self.application.repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO routing_study_areas (
                    name, version, geometry_geojson, source_name,
                    source_metadata_json, is_official, is_active
                ) VALUES ('Town proper test area', 'test-area-v1', ?,
                          'Synthetic test fixture', '{}', 0, 1)
                """,
                (polygon(125.0, 11.0, 126.0, 12.0),),
            )
            connection.execute(
                """
                INSERT INTO evacuation_centers (
                    external_id, name, latitude, longitude, designation,
                    source_name, source_metadata_json, dataset_version, is_official, active
                ) VALUES ('D', 'Center D', 11.5000, 125.0018,
                          'Designated Evacuation Center', 'Synthetic test fixture',
                          '{}', 'test-centers-v1', 1, 1)
                """
            )
            connection.commit()
        self.application.service.router = HazardAwareRouter(
            self.application.repository,
            routing_config(graph_path),
            graph=alternative_graph(),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()
        self.application.close()

    def test_center_and_route_endpoints(self) -> None:
        centers = self.application.api.dispatch("GET", "/api/v1/evacuation-centers")
        self.assertEqual(centers.status, 200)
        self.assertEqual(json.loads(centers.body)["count"], 1)
        route = self.application.api.dispatch(
            "POST",
            "/api/v1/route",
            body=json.dumps(
                {
                    "latitude": 11.5,
                    "longitude": 125.0,
                    "mode": "shortest",
                    "scenario": "multi_hazard",
                    "include_comparison": False,
                }
            ).encode(),
        )
        payload = json.loads(route.body)
        self.assertEqual(route.status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertIn("shortest", payload["routes"])
        self.assertNotIn("lower_hazard", payload["routes"])
        self.assertIn("research_metrics", payload)
        self.assertEqual(
            payload["destination"]["destination_mapped_hazard_screening"]["status"],
            "not_screened",
        )

    def test_public_route_endpoint_rejects_lower_hazard_mode(self) -> None:
        route = self.application.api.dispatch(
            "POST",
            "/api/v1/route",
            body=json.dumps({"latitude": 11.5, "longitude": 125.0, "mode": "invalid"}).encode(),
        )
        payload = json.loads(route.body)
        self.assertEqual(route.status, 422)
        self.assertEqual(payload["error"]["code"], "validation_error")
        self.assertIn("standard evacuation route", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
