#!/usr/bin/env python3
"""Validate the MCAR example against its materialized artifacts and answers."""

from __future__ import annotations

import json
import math
from pathlib import Path

from run_scenario import (
    ROOT,
    complete_records,
    derive_blocks,
    enumerate_worlds,
    inject_missingness,
    load_json,
    read_csv,
    validate_config,
)


def main() -> None:
    config_path = ROOT / "config" / "mcar-single-missing.json"
    query_path = ROOT / "queries" / "mcar-single-missing.json"
    config = load_json(config_path)
    validate_config(config)

    complete = complete_records(config)
    observed, mask = inject_missingness(complete, config)
    files = config["files"]
    assert complete == read_csv(ROOT / files["complete"])
    assert observed == read_csv(ROOT / files["observed"])
    assert [
        {name: str(value) for name, value in row.items()} for row in mask
    ] == read_csv(ROOT / files["missingness_mask"])

    expected_blocks = derive_blocks(observed, config)
    actual_blocks = read_csv(ROOT / files["blocks"])
    assert len(expected_blocks) == len(actual_blocks)
    for expected, actual in zip(expected_blocks, actual_blocks):
        for name, value in expected.items():
            if name == "probability":
                assert math.isclose(float(actual[name]), float(value), abs_tol=1e-12)
            else:
                assert actual[name] == str(value)

    queries = load_json(query_path)["queries"]
    config["query"] = queries[0]
    worlds = enumerate_worlds(observed, expected_blocks, config)
    query_probability = sum(
        world["probability"] for world in worlds if world["query"]
    )

    answers_path = ROOT / "data" / config["experiment"] / "answers.json"
    answers = load_json(answers_path)["answers"]
    matching = [
        answer for answer in answers if answer["query"] == queries[0]["name"]
    ]
    assert matching
    assert all(
        math.isclose(answer["probability"], query_probability, abs_tol=5e-5)
        for answer in matching
    )

    missing_rows = [
        row[config["relation"]["key"][0]]
        for row in observed
        if config["missingness"]["missing_token"] in row.values()
    ]
    print(f"records={len(observed)}")
    print("missing_rows=" + ",".join(missing_rows))
    print(f"uncertain_blocks={len({row['block_id'] for row in expected_blocks})}")
    print(f"query_probability={query_probability:.6f}")
    print("configuration, artifacts, and answers agree")


if __name__ == "__main__":
    main()
