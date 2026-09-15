#!/usr/bin/env python3
"""Validate the configured MCAR experiment against its materialized artifacts."""

import csv
import json
import random
from itertools import product
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    config = json.loads((EXPERIMENT_DIR / "config" / "experiment.json").read_text(encoding="utf-8"))
    files = config["files"]
    generation = config["generation"]
    missingness = config["missingness"]
    rng = random.Random(config["seed"])

    generated_complete: list[dict[str, str]] = []
    generated_observed: list[dict[str, str]] = []
    row_id = 0
    for group, count in generation["rows_by_group"].items():
        probability_yes = generation["disease_given_group"][group]["yes"]
        for _ in range(count):
            row_id += 1
            disease = "yes" if rng.random() < probability_yes else "no"
            is_missing = rng.random() < missingness["probability"]
            generated_complete.append({"id": str(row_id), "group": group, "disease": disease})
            generated_observed.append({
                "id": str(row_id),
                "group": group,
                "disease": missingness["missing_token"] if is_missing else disease,
            })

    assert generated_complete == read_csv(EXPERIMENT_DIR / files["complete"])
    assert generated_observed == read_csv(EXPERIMENT_DIR / files["observed"])

    observed = generated_observed
    materialized_blocks = read_csv(EXPERIMENT_DIR / files["blocks"])
    expected_blocks: list[dict[str, str]] = []
    for row in observed:
        if row["disease"] != missingness["missing_token"]:
            continue
        for disease, probability in generation["disease_given_group"][row["group"]].items():
            expected_blocks.append({
                "block_id": row["id"], "row_id": row["id"], "group": row["group"],
                "disease": disease, "probability": str(probability),
            })
    assert expected_blocks == materialized_blocks

    blocks: dict[int, dict[str, float]] = {}
    for row in materialized_blocks:
        blocks.setdefault(int(row["block_id"]), {})[row["disease"]] = float(row["probability"])
    requirements = {int(atom["arguments"][0]): atom["arguments"][2]
                    for atom in config["query"]["atoms"]}
    query_probability = 0.0
    block_ids = list(blocks)
    for choices in product(*(blocks[block_id] for block_id in block_ids)):
        world = dict(zip(block_ids, choices))
        probability = 1.0
        for block_id, choice in world.items():
            probability *= blocks[block_id][choice]
        if all(world[row] == value for row, value in requirements.items()):
            query_probability += probability

    print(f"records={len(observed)}")
    print("missing_rows=" + ",".join(row["id"] for row in observed
                                           if row["disease"] == missingness["missing_token"]))
    print(f"query_atoms={len(config['query']['atoms'])}")
    print(f"query_probability={query_probability:.6f}")
    print("configuration and materialized artifacts agree")


if __name__ == "__main__":
    main()
