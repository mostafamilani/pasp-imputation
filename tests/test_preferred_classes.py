import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from preferred_classes import (  # noqa: E402
    answer_preferred_query,
    enumerate_classes,
    preferred_classes,
)


CONFIG = {
    "relation": {
        "name": "r",
        "key": ["id"],
        "attributes": [
            {"name": "id", "type": "integer"},
            {"name": "value", "type": "categorical", "domain": ["a", "b"]},
        ],
    },
    "generation": {
        "nodes": [{"name": "value", "parents": [],
                   "distribution": {"a": 0.5, "b": 0.5}}],
    },
    "missingness": {"missing_token": "na"},
    "preferred_classes": {
        "enabled_semantics": ["mcc", "mpc"],
        "mcc_distance": "squared_euclidean",
        "max_enumerated_worlds": 10,
    },
}
OBSERVED = [{"id": "1", "value": "na"}, {"id": "2", "value": "na"}]
BLOCKS = [
    {"block_id": "1", "id": "1", "value": "a", "probability": 0.8},
    {"block_id": "1", "id": "1", "value": "b", "probability": 0.2},
    {"block_id": "2", "id": "2", "value": "a", "probability": 0.8},
    {"block_id": "2", "id": "2", "value": "b", "probability": 0.2},
]


class PreferredClassTests(unittest.TestCase):
    def test_matching_worlds_are_grouped_as_bags(self):
        classes = enumerate_classes(OBSERVED, BLOCKS, CONFIG)
        self.assertEqual(len(classes), 3)
        mixed = next(c for c in classes if len(c["worlds"]) == 2)
        self.assertAlmostEqual(mixed["probability"], 0.32)

    def test_mpc_sums_world_probabilities_and_mcc_keeps_all_ties(self):
        classes = enumerate_classes(OBSERVED, BLOCKS, CONFIG)
        self.assertEqual(len(preferred_classes(classes, "mpc", CONFIG)), 1)
        mcc = preferred_classes(classes, "mcc", CONFIG)
        self.assertEqual(len(mcc), 1)
        self.assertEqual(len(mcc[0]["worlds"]), 2)

    def test_preferred_answers_are_not_renormalized(self):
        classes = enumerate_classes(OBSERVED, BLOCKS, CONFIG)
        query = {"name": "has_b", "atoms": [
            {"relation": "r", "arguments": ["?id", "b"]},
        ]}
        answers = answer_preferred_query(
            query, preferred_classes(classes, "mcc", CONFIG), CONFIG
        )
        self.assertEqual(len(answers), 1)
        self.assertIs(answers[0]["answer"], True)
        self.assertAlmostEqual(answers[0]["class_probability"], 0.32)

    def test_key_specific_query_is_rejected_when_not_class_invariant(self):
        classes = enumerate_classes(OBSERVED, BLOCKS, CONFIG)
        query = {"name": "first_has_b", "atoms": [
            {"relation": "r", "arguments": [1, "b"]},
        ]}
        with self.assertRaisesRegex(ValueError, "not invariant"):
            answer_preferred_query(
                query, preferred_classes(classes, "mcc", CONFIG), CONFIG
            )


if __name__ == "__main__":
    unittest.main()
