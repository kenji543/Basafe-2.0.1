from __future__ import annotations

import json
import unittest

from tests.helpers import DemoApplication, polygon


class AssessmentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DemoApplication()

    def tearDown(self) -> None:
        self.application.close()

    def test_spatial_layers_and_identification(self) -> None:
        boundary = self.application.api.dispatch("GET", "/api/v1/boundary")
        self.assertEqual(boundary.status, 200)
        boundary_json = json.loads(boundary.body)
        self.assertEqual(boundary_json["type"], "FeatureCollection")
        self.assertTrue(boundary_json["features"])
        self.assertTrue(boundary_json["features"][0]["properties"]["is_demo"])

        response = self.application.api.dispatch(
            "GET",
            "/api/v1/location/identify",
            {"lat": ["11.5"], "lon": ["125.25"]},
        )
        location = json.loads(response.body)
        self.assertTrue(location["inside_basey"])
        self.assertEqual(location["barangay"]["name"], "Test West")
        self.assertTrue(
            any("DEMONSTRATION" in notice for notice in location["notices"])
        )

        sources = json.loads(
            self.application.api.dispatch("GET", "/api/v1/data-sources").body
        )
        self.assertTrue(sources["items"])
        self.assertTrue(
            all(
                item["status"] == "not_configured"
                for item in sources["official_data_availability"]
            )
        )

    def test_loaded_official_boundary_suppresses_demo_extent(self) -> None:
        with self.application.repository.connection() as connection:
            connection.execute(
                """
                INSERT INTO municipal_boundary (
                    name, geometry_geojson, source_metadata_json,
                    is_official, is_demo
                ) VALUES ('Official test extent', ?, '{"source_name":"Official fixture"}',
                          1, 0)
                """,
                (polygon(125.0, 11.0, 125.5, 12.0),),
            )
            connection.commit()
        boundary = json.loads(
            self.application.api.dispatch("GET", "/api/v1/boundary").body
        )
        self.assertEqual(len(boundary["features"]), 1)
        self.assertTrue(boundary["features"][0]["properties"]["is_official"])
        east = json.loads(
            self.application.api.dispatch(
                "GET",
                "/api/v1/location/identify",
                {"latitude": ["11.5"], "longitude": ["125.75"]},
            ).body
        )
        self.assertFalse(east["inside_basey"])

    def test_complete_assessment_persists_all_explanations(self) -> None:
        response = self.application.api.dispatch(
            "POST",
            "/api/v1/assessments",
            body=json.dumps(
                {
                    "latitude": 11.5,
                    "longitude": 125.25,
                    "location_label": "Test point",
                }
            ).encode(),
        )
        self.assertEqual(response.status, 201)
        assessment = json.loads(response.body)
        self.assertEqual(assessment["status"], "complete")
        self.assertEqual(assessment["location"]["barangay"]["name"], "Test West")
        self.assertEqual(len(assessment["hazards"]), 3)
        self.assertTrue(
            all(
                hazard["availability_status"] == "available"
                for hazard in assessment["hazards"]
            )
        )
        self.assertIsInstance(assessment["result"]["score"], int)
        self.assertTrue(assessment["result"]["memberships"])
        self.assertTrue(assessment["result"]["activated_rules"])
        self.assertTrue(assessment["historical_incidents"])
        self.assertTrue(assessment["clup_references"])
        self.assertTrue(assessment["data_sources"])
        self.assertTrue(
            all("data_status" in source for source in assessment["data_sources"])
        )
        self.assertTrue(assessment["recommendations"])
        self.assertIn(
            "preliminary decision-support screening result",
            assessment["disclaimer"],
        )
        self.assertTrue(
            any(
                "DEMONSTRATION" in notice
                for notice in assessment["data_quality_notices"]
            )
        )

        saved = self.application.api.dispatch(
            "GET", assessment["links"]["self"]
        )
        self.assertEqual(saved.status, 200)
        self.assertEqual(json.loads(saved.body)["id"], assessment["id"])

        explanation = self.application.api.dispatch(
            "GET", assessment["links"]["explanation"]
        )
        explanation_json = json.loads(explanation.body)
        self.assertEqual(explanation_json["score"], assessment["result"]["score"])
        self.assertEqual(len(explanation_json["evaluated_rules"]), 12)

    def test_required_missing_hazard_makes_assessment_incomplete(self) -> None:
        response = self.application.api.dispatch(
            "POST",
            "/api/v1/assessments",
            body=json.dumps({"latitude": 11.5, "longitude": 125.75}).encode(),
        )
        self.assertEqual(response.status, 201)
        assessment = json.loads(response.body)
        self.assertEqual(assessment["status"], "incomplete")
        self.assertIsNone(assessment["result"]["score"])
        self.assertEqual(assessment["result"]["category"], "Incomplete")
        self.assertIn("liquefaction", assessment["result"]["missing_inputs"])
        liquefaction = next(
            item
            for item in assessment["hazards"]
            if item["hazard_type"] == "liquefaction"
        )
        self.assertEqual(liquefaction["availability_status"], "missing")
        self.assertIn("not low vulnerability", liquefaction["quality_notice"])

    def test_outside_basey_is_rejected(self) -> None:
        response = self.application.api.dispatch(
            "POST",
            "/api/v1/assessments",
            body=json.dumps({"latitude": 10, "longitude": 124}).encode(),
        )
        self.assertEqual(response.status, 422)
        error = json.loads(response.body)["error"]
        self.assertEqual(error["code"], "outside_basey")

    def test_pdf_report_is_generated_and_recorded(self) -> None:
        created = self.application.api.dispatch(
            "POST",
            "/api/v1/assessments",
            body=json.dumps({"latitude": 11.5, "longitude": 125.25}).encode(),
        )
        assessment = json.loads(created.body)
        report = self.application.api.dispatch(
            "GET", assessment["links"]["report"]
        )
        self.assertEqual(report.status, 200)
        self.assertEqual(report.headers["Content-Type"], "application/pdf")
        self.assertTrue(report.body.startswith(b"%PDF-1.4"))
        self.assertIn(b"GeoSafe-FIS Assessment Report", report.body)
        self.assertIn(b"DISCLAIMER", report.body)
        self.assertIn(b"screening prototype", report.body)
        self.assertIn(b"DEMONSTRATION", report.body)
        self.assertIn("X-Report-SHA256", report.headers)
        with self.application.repository.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM generated_reports"
            ).fetchone()["count"]
        self.assertEqual(count, 1)

    def test_incomplete_pdf_does_not_report_a_low_score(self) -> None:
        created = self.application.api.dispatch(
            "POST",
            "/api/v1/assessments",
            body=json.dumps({"latitude": 11.5, "longitude": 125.75}).encode(),
        )
        assessment = json.loads(created.body)
        report = self.application.api.dispatch(
            "GET", assessment["links"]["report"]
        )
        self.assertIn(b"Assessment incomplete", report.body)
        self.assertIn(
            b"Missing information was not interpreted as low vulnerability",
            report.body,
        )
        self.assertNotIn(b"Normalized screening score: 1", report.body)

    def test_history_is_unified_and_not_user_scoped(self) -> None:
        self.application.api.dispatch(
            "POST",
            "/api/v1/assessments",
            body=json.dumps({"latitude": 11.5, "longitude": 125.25}).encode(),
        )
        response = self.application.api.dispatch(
            "GET", "/api/v1/assessments"
        )
        history = json.loads(response.body)
        self.assertEqual(history["count"], 1)
        self.assertNotIn("user_id", history["items"][0])
        self.assertNotIn("role", history["items"][0])

    def test_invalid_pagination_is_not_silently_defaulted(self) -> None:
        response = self.application.api.dispatch(
            "GET", "/api/v1/assessments", {"limit": ["0"]}
        )
        self.assertEqual(response.status, 422)
        self.assertEqual(json.loads(response.body)["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
