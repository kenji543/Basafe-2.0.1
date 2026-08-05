from __future__ import annotations

import unittest
from copy import deepcopy
from itertools import product
import json
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
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)
        self.assertIn(
            result["category"], {"Very Low", "Low", "Moderate", "High", "Very High"}
        )
        self.assertEqual(set(result["memberships"]), set(result["normalized_inputs"]))
        self.assertTrue(result["activated_rules"])
        self.assertTrue(
            all(0 < rule["activation"] <= 1 for rule in result["activated_rules"])
        )
        self.assertEqual(len(result["evaluated_rules"]), 27)
        self.assertAlmostEqual(
            sum(result["indicator_weights"]["values"].values()), 1, places=5
        )

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
        self.assertEqual(low["category"], "Very Low")
        self.assertEqual(high["category"], "Very High")
        self.assertGreater(high["score"], low["score"])

    def test_category_threshold_gap_is_rejected(self) -> None:
        configuration = deepcopy(self.model.configuration)
        configuration["output"]["category_thresholds"][1]["minimum"] = 27
        with self.assertRaises(ModelConfigurationError):
            FuzzyModel(configuration)

    def test_rule_grid_has_complete_coverage(self) -> None:
        combinations = {
            tuple(condition[1] for condition in rule["conditions"])
            for rule in self.model.configuration["rules"]
        }
        expected = set(product(("low", "moderate", "high"), repeat=3))
        self.assertEqual(combinations, expected)

    def test_source_configuration_has_one_rule_authority(self) -> None:
        raw = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("rules", raw)
        self.assertEqual(
            raw["rule_generation"]["method"],
            "complete_monotonic_ordinal_grid",
        )
        self.assertEqual(len(self.model.configuration["rules"]), 27)

    def test_scores_are_monotonic_on_representative_grid(self) -> None:
        values = (0, 25, 50, 75, 100)
        input_ids = ("flood", "liquefaction", "ground_shaking")
        scores = {
            point: self.model.evaluate(dict(zip(input_ids, point)))["score"]
            for point in product(values, repeat=3)
        }
        for point, score in scores.items():
            for index, value in enumerate(point):
                if value == values[-1]:
                    continue
                comparison = list(point)
                comparison[index] = values[values.index(value) + 1]
                self.assertGreaterEqual(scores[tuple(comparison)], score)


if __name__ == "__main__":
    unittest.main()
