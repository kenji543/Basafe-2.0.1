from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from geosafe.fuzzy import FuzzyModel, ModelConfigurationError, membership_value


MODEL_PATH = Path(__file__).resolve().parent.parent / "config" / "fuzzy_model.json"


class MembershipFunctionTests(unittest.TestCase):
    def test_triangular_membership(self) -> None:
        self.assertEqual(membership_value("triangular", [0, 50, 100], 50), 1)
        self.assertEqual(membership_value("triangular", [0, 50, 100], 0), 0)
        self.assertAlmostEqual(
            membership_value("triangular", [0, 50, 100], 25), 0.5
        )

    def test_trapezoidal_shoulder_membership(self) -> None:
        self.assertEqual(
            membership_value("trapezoidal", [0, 0, 25, 45], 0), 1
        )
        self.assertEqual(
            membership_value("trapezoidal", [55, 75, 100, 100], 100), 1
        )


class FuzzyModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = FuzzyModel.from_file(MODEL_PATH)

    def test_complete_assessment_is_explainable_and_bounded(self) -> None:
        result = self.model.evaluate(
            {"flood": 82, "liquefaction": 55, "ground_shaking": 76}
        )
        self.assertEqual(result["status"], "complete")
        self.assertGreaterEqual(result["score"], 1)
        self.assertLessEqual(result["score"], 100)
        self.assertIn(
            result["category"], {"Low", "Moderate", "High", "Very High"}
        )
        self.assertEqual(set(result["memberships"]), set(result["normalized_inputs"]))
        self.assertTrue(result["activated_rules"])
        self.assertTrue(
            all(0 < rule["activation"] <= 1 for rule in result["activated_rules"])
        )
        self.assertEqual(len(result["evaluated_rules"]), 12)

    def test_missing_input_never_becomes_low(self) -> None:
        result = self.model.evaluate(
            {"flood": 10, "liquefaction": None, "ground_shaking": 10}
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["score"])
        self.assertEqual(result["category"], "Incomplete")
        self.assertEqual(result["missing_inputs"], ["liquefaction"])
        self.assertIn("not been interpreted as low", result["message"])
        self.assertEqual(result["activated_rules"], [])

    def test_demonstration_model_spans_output_categories(self) -> None:
        low = self.model.evaluate(
            {"flood": 0, "liquefaction": 0, "ground_shaking": 0}
        )
        high = self.model.evaluate(
            {"flood": 100, "liquefaction": 100, "ground_shaking": 100}
        )
        self.assertEqual(low["category"], "Low")
        self.assertEqual(high["category"], "Very High")
        self.assertGreater(high["score"], low["score"])

    def test_category_threshold_gap_is_rejected(self) -> None:
        configuration = deepcopy(self.model.configuration)
        configuration["output"]["category_thresholds"][1]["minimum"] = 27
        with self.assertRaises(ModelConfigurationError):
            FuzzyModel(configuration)


if __name__ == "__main__":
    unittest.main()
