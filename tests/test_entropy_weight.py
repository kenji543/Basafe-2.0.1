from __future__ import annotations

import unittest

from geosafe.entropy_weight import EntropyWeightError, entropy_weights


class EntropyWeightTests(unittest.TestCase):
    def test_weights_are_normalized_and_more_variable_indicator_is_heavier(self) -> None:
        weights = entropy_weights(
            {
                "flood": [0, 0, 0, 100],
                "liquefaction": [0, 30, 60, 100],
                "ground_shaking": [0, 50, 50, 100],
            }
        )
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertGreater(weights["flood"], weights["liquefaction"])
        self.assertTrue(all(weight >= 0 for weight in weights.values()))

    def test_constant_dataset_requires_explicit_equal_fallback(self) -> None:
        observations = {"flood": [4, 4], "liquefaction": [7, 7]}
        with self.assertRaises(EntropyWeightError):
            entropy_weights(observations)
        self.assertEqual(
            entropy_weights(observations, allow_equal_fallback=True),
            {"flood": 0.5, "liquefaction": 0.5},
        )

    def test_invalid_observation_shapes_are_rejected(self) -> None:
        with self.assertRaises(EntropyWeightError):
            entropy_weights({"flood": [0, 1], "liquefaction": [0]})
        with self.assertRaises(EntropyWeightError):
            entropy_weights({"flood": [0, -1]})


if __name__ == "__main__":
    unittest.main()
