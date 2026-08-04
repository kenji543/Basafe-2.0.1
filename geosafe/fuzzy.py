"""Explainable, configuration-driven Mamdani fuzzy inference."""

from __future__ import annotations

import json
import hashlib
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ModelConfigurationError(ValueError):
    """Raised when a fuzzy-model configuration is internally inconsistent."""


def membership_value(kind: str, parameters: list[float], value: float) -> float:
    """Evaluate a triangular or trapezoidal membership function."""
    x = float(value)
    values = [float(parameter) for parameter in parameters]
    if kind == "triangular":
        if len(values) != 3:
            raise ModelConfigurationError("Triangular memberships require 3 parameters.")
        a, b, c = values
        if not a <= b <= c or a == c:
            raise ModelConfigurationError("Triangular parameters must satisfy a <= b <= c.")
        if x < a or x > c:
            return 0.0
        if x == b:
            return 1.0
        if x < b:
            return 1.0 if b == a else (x - a) / (b - a)
        return 1.0 if c == b else (c - x) / (c - b)

    if kind == "trapezoidal":
        if len(values) != 4:
            raise ModelConfigurationError(
                "Trapezoidal memberships require 4 parameters."
            )
        a, b, c, d = values
        if not a <= b <= c <= d or a == d:
            raise ModelConfigurationError(
                "Trapezoidal parameters must satisfy a <= b <= c <= d."
            )
        if x < a or x > d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if x < b:
            return 1.0 if b == a else (x - a) / (b - a)
        return 1.0 if d == c else (d - x) / (d - c)

    raise ModelConfigurationError(f"Unsupported membership type: {kind!r}.")


class FuzzyModel:
    """Validated fuzzy model that returns all intermediate reasoning values."""

    def __init__(self, configuration: Mapping[str, Any]):
        self.configuration = dict(configuration)
        self._validate()
        self.inputs = {
            variable["id"]: variable for variable in self.configuration["inputs"]
        }
        self.output = self.configuration["output"]

    @classmethod
    def from_file(cls, path: str | Path) -> "FuzzyModel":
        with Path(path).open("r", encoding="utf-8") as model_file:
            return cls(json.load(model_file))

    def _validate(self) -> None:
        required_keys = {
            "model_version",
            "inputs",
            "output",
            "rules",
            "inference",
            "disclaimer",
        }
        missing = required_keys.difference(self.configuration)
        if missing:
            raise ModelConfigurationError(
                f"Model configuration is missing: {', '.join(sorted(missing))}."
            )
        inputs = self.configuration["inputs"]
        if not isinstance(inputs, list) or not inputs:
            raise ModelConfigurationError("At least one fuzzy input is required.")
        input_ids: set[str] = set()
        terms_by_input: dict[str, set[str]] = {}
        for variable in inputs:
            variable_id = variable.get("id")
            if not variable_id or variable_id in input_ids:
                raise ModelConfigurationError("Fuzzy input IDs must be present and unique.")
            input_ids.add(variable_id)
            universe = variable.get("universe")
            if (
                not isinstance(universe, list)
                or len(universe) != 2
                or universe[0] >= universe[1]
            ):
                raise ModelConfigurationError(
                    f"Input {variable_id!r} has an invalid universe."
                )
            memberships = variable.get("memberships")
            if not memberships:
                raise ModelConfigurationError(
                    f"Input {variable_id!r} has no memberships."
                )
            terms: set[str] = set()
            for membership in memberships:
                term = membership.get("term")
                if not term or term in terms:
                    raise ModelConfigurationError(
                        f"Input {variable_id!r} has duplicate or missing terms."
                    )
                terms.add(term)
                membership_value(
                    membership.get("type", ""),
                    membership.get("parameters", []),
                    float(universe[0]),
                )
            terms_by_input[variable_id] = terms

        output = self.configuration["output"]
        output_universe = output.get("universe")
        if (
            not isinstance(output_universe, list)
            or len(output_universe) != 2
            or not all(isinstance(value, (int, float)) for value in output_universe)
            or output_universe[0] >= output_universe[1]
        ):
            raise ModelConfigurationError("The fuzzy output has an invalid universe.")
        output_terms: set[str] = set()
        for membership in output.get("memberships", []):
            term = membership.get("term")
            if not term or term in output_terms:
                raise ModelConfigurationError(
                    "Output membership terms must be present and unique."
                )
            output_terms.add(term)
            membership_value(
                membership.get("type", ""),
                membership.get("parameters", []),
                float(output["universe"][0]),
            )
        if not output_terms:
            raise ModelConfigurationError("Output memberships are required.")
        thresholds = output.get("category_thresholds")
        if (
            not isinstance(thresholds, list)
            or not thresholds
            or not all(isinstance(item, Mapping) for item in thresholds)
        ):
            raise ModelConfigurationError("Output category thresholds are required.")
        ordered_thresholds = sorted(thresholds, key=lambda item: item.get("minimum", 0))
        expected_minimum = output_universe[0]
        category_names: set[str] = set()
        for threshold in ordered_thresholds:
            category = threshold.get("category")
            minimum = threshold.get("minimum")
            maximum = threshold.get("maximum")
            if (
                not category
                or category in category_names
                or not isinstance(minimum, (int, float))
                or not isinstance(maximum, (int, float))
                or minimum > maximum
            ):
                raise ModelConfigurationError(
                    "Output category names and numeric thresholds must be valid and unique."
                )
            if minimum != expected_minimum:
                raise ModelConfigurationError(
                    "Output category thresholds must cover the output universe "
                    "contiguously without overlaps or gaps."
                )
            category_names.add(category)
            expected_minimum = maximum + 1
        if ordered_thresholds[-1]["maximum"] != output_universe[1]:
            raise ModelConfigurationError(
                "Output category thresholds must cover the full output universe."
            )

        rule_ids: set[str] = set()
        for rule in self.configuration["rules"]:
            rule_id = rule.get("id")
            if not rule_id or rule_id in rule_ids:
                raise ModelConfigurationError("Fuzzy rule IDs must be present and unique.")
            rule_ids.add(rule_id)
            if rule.get("operator") not in {"all", "any"}:
                raise ModelConfigurationError(
                    f"Rule {rule_id} must use the 'all' or 'any' operator."
                )
            if rule.get("consequent") not in output_terms:
                raise ModelConfigurationError(
                    f"Rule {rule_id} references an unknown output term."
                )
            weight = rule.get("weight")
            if not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
                raise ModelConfigurationError(
                    f"Rule {rule_id} weight must be between 0 and 1."
                )
            if not rule.get("statement") or not rule.get("conditions"):
                raise ModelConfigurationError(
                    f"Rule {rule_id} needs a documented statement and conditions."
                )
            for condition in rule["conditions"]:
                if not isinstance(condition, list) or len(condition) != 2:
                    raise ModelConfigurationError(
                        f"Rule {rule_id} contains an invalid condition."
                    )
                variable_id, term = condition
                if variable_id not in terms_by_input:
                    raise ModelConfigurationError(
                        f"Rule {rule_id} references unknown input {variable_id!r}."
                    )
                if term not in terms_by_input[variable_id]:
                    raise ModelConfigurationError(
                        f"Rule {rule_id} references unknown term {term!r}."
                    )

        inference = self.configuration["inference"]
        expected = {
            "type": "Mamdani",
            "and_operator": "minimum",
            "or_operator": "maximum",
            "implication": "minimum",
            "aggregation": "maximum",
            "defuzzification": "centroid",
        }
        if any(inference.get(key) != value for key, value in expected.items()):
            raise ModelConfigurationError(
                "This implementation supports the documented Mamdani min/max "
                "inference and centroid defuzzification only."
            )
        sampling_interval = inference.get("sampling_interval", 1)
        if not isinstance(sampling_interval, int) or sampling_interval < 1:
            raise ModelConfigurationError(
                "The inference sampling interval must be a positive integer."
            )

    @property
    def version(self) -> str:
        return str(self.configuration["model_version"])

    @property
    def checksum(self) -> str:
        """SHA-256 of the canonical model configuration for reproducibility."""
        canonical = json.dumps(
            self.configuration, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def describe(self) -> dict[str, Any]:
        """Return the public, versioned methodology configuration."""
        return self.configuration

    def _memberships_for(self, variable: Mapping[str, Any], value: float) -> dict[str, float]:
        lower, upper = map(float, variable["universe"])
        if not math.isfinite(value) or value < lower or value > upper:
            raise ValueError(
                f"{variable['id']} must be between {lower:g} and {upper:g}."
            )
        return {
            membership["term"]: round(
                membership_value(
                    membership["type"], membership["parameters"], value
                ),
                6,
            )
            for membership in variable["memberships"]
        }

    def evaluate(self, values: Mapping[str, float | int | None]) -> dict[str, Any]:
        """Evaluate inputs and expose memberships, rules, aggregation, and score."""
        missing_inputs = [
            variable_id
            for variable_id, variable in self.inputs.items()
            if variable.get("required", True) and values.get(variable_id) is None
        ]
        available_memberships: dict[str, dict[str, float]] = {}
        normalized_inputs: dict[str, float | None] = {}
        for variable_id, variable in self.inputs.items():
            raw_value = values.get(variable_id)
            if raw_value is None:
                normalized_inputs[variable_id] = None
                continue
            value = float(raw_value)
            normalized_inputs[variable_id] = value
            available_memberships[variable_id] = self._memberships_for(
                variable, value
            )

        base_result: dict[str, Any] = {
            "model_version": self.version,
            "model_checksum": self.checksum,
            "model_status": self.configuration.get("status"),
            "normalized_inputs": normalized_inputs,
            "memberships": available_memberships,
            "missing_inputs": missing_inputs,
            "inference": dict(self.configuration["inference"]),
            "validation_notes": list(
                self.configuration.get("validation_notes", [])
            ),
        }
        if missing_inputs:
            base_result.update(
                {
                    "status": "incomplete",
                    "score": None,
                    "category": "Incomplete",
                    "evaluated_rules": [],
                    "activated_rules": [],
                    "message": (
                        "Required hazard information is unavailable. Missing data "
                        "has not been interpreted as low vulnerability."
                    ),
                }
            )
            return base_result

        evaluated_rules: list[dict[str, Any]] = []
        for rule in self.configuration["rules"]:
            condition_values = [
                available_memberships[variable_id][term]
                for variable_id, term in rule["conditions"]
            ]
            raw_activation = (
                min(condition_values)
                if rule["operator"] == "all"
                else max(condition_values)
            )
            activation = raw_activation * float(rule["weight"])
            evaluated_rules.append(
                {
                    "id": rule["id"],
                    "statement": rule["statement"],
                    "operator": rule["operator"],
                    "conditions": [
                        {
                            "variable": variable_id,
                            "term": term,
                            "membership": available_memberships[variable_id][term],
                        }
                        for variable_id, term in rule["conditions"]
                    ],
                    "consequent": rule["consequent"],
                    "weight": float(rule["weight"]),
                    "raw_activation": round(raw_activation, 6),
                    "activation": round(activation, 6),
                    "rationale": rule.get("rationale", ""),
                }
            )

        lower, upper = map(int, self.output["universe"])
        interval = int(self.configuration["inference"].get("sampling_interval", 1))
        if interval < 1:
            raise ModelConfigurationError("Sampling interval must be at least 1.")
        samples = list(range(lower, upper + 1, interval))
        aggregated: list[float] = []
        output_memberships = {
            membership["term"]: membership
            for membership in self.output["memberships"]
        }
        for sample in samples:
            contributions = [
                min(
                    rule["activation"],
                    membership_value(
                        output_memberships[rule["consequent"]]["type"],
                        output_memberships[rule["consequent"]]["parameters"],
                        sample,
                    ),
                )
                for rule in evaluated_rules
                if rule["activation"] > 0
            ]
            aggregated.append(max(contributions, default=0.0))
        denominator = sum(aggregated)
        if denominator <= 0:
            raise ModelConfigurationError(
                "No fuzzy rule activated for the supplied complete input set."
            )
        centroid = sum(
            sample * degree for sample, degree in zip(samples, aggregated)
        ) / denominator
        score = max(lower, min(upper, int(round(centroid))))
        category = next(
            (
                threshold["category"]
                for threshold in self.output["category_thresholds"]
                if threshold["minimum"] <= score <= threshold["maximum"]
            ),
            None,
        )
        if category is None:
            raise ModelConfigurationError(
                f"No output category threshold includes score {score}."
            )
        activated_rules = [
            rule for rule in evaluated_rules if rule["activation"] > 0
        ]
        activated_rules.sort(key=lambda rule: (-rule["activation"], rule["id"]))
        base_result.update(
            {
                "status": "complete",
                "score": score,
                "centroid": round(centroid, 4),
                "category": category,
                "evaluated_rules": evaluated_rules,
                "activated_rules": activated_rules,
                "message": (
                    "The score is a normalized screening index from 1 to 100, "
                    "not a probability or engineering risk estimate."
                ),
            }
        )
        return base_result
