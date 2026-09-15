#!/usr/bin/env python3
"""Load or sample complete records, then inject configured missingness."""

import argparse
import csv
import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def draw(rng, probabilities):
    if abs(sum(probabilities.values()) - 1.0) > 1e-12:
        raise ValueError(f"distribution does not sum to one: {probabilities}")
    point, cumulative = rng.random(), 0.0
    for value, probability in probabilities.items():
        cumulative += probability
        if point < cumulative:
            return value
    return next(reversed(probabilities))


def node_distribution(node, row):
    parents = node.get("parents", [])
    if not parents:
        return node["distribution"]
    key = ",".join(f"{parent}={row[parent]}" for parent in parents)
    return node["conditional_distribution"][key]


def validate(rows, config):
    attributes = config["relation"]["attributes"]
    names = [a["name"] if isinstance(a, dict) else a for a in attributes]
    domains = {a["name"]: {str(v) for v in a["domain"]}
               for a in attributes if isinstance(a, dict) and "domain" in a}
    for number, row in enumerate(rows, 1):
        if list(row) != names:
            raise ValueError(f"row {number}: expected columns {names}, got {list(row)}")
        for name, domain in domains.items():
            if row[name] not in domain:
                raise ValueError(f"row {number}: {name}={row[name]!r} is outside its domain")


def complete_records(config, rng):
    dataset = config["dataset"]
    if dataset["source"] == "csv":
        rows = read_csv((PROJECT_ROOT / dataset["input"]).resolve())
        validate(rows, config)
        return rows
    if dataset["source"] != "synthetic":
        raise ValueError("dataset.source must be 'synthetic' or 'csv'")

    count = dataset["number_of_records"]
    key = config["relation"]["key"][0]
    sampling = dataset.get("sampling", {"method": "iid"})
    strata = None
    if sampling["method"] == "stratified":
        strata = [value for value, amount in sampling["counts"].items()
                  for _ in range(amount)]
        if len(strata) != count:
            raise ValueError("stratified counts must sum to number_of_records")
    elif sampling["method"] != "iid":
        raise ValueError("sampling.method must be 'iid' or 'stratified'")

    rows = []
    for index in range(count):
        row = {key: str(index + 1)}
        for node in config["generation"]["nodes"]:
            name = node["name"]
            if strata is not None and name == sampling["attribute"]:
                row[name] = strata[index]
            else:
                row[name] = draw(rng, node_distribution(node, row))
        rows.append(row)
    validate(rows, config)
    return rows


def probability_missing(rule, row):
    parents = rule.get("parents", [])
    if not parents:
        return rule["probability_missing"]
    key = ",".join(f"{parent}={row[parent]}" for parent in parents)
    return rule["conditional_probability_missing"][key]


def inject_missingness(complete, graph, rng):
    token = graph.get("missing_token", "na")
    observed = [row.copy() for row in complete]
    for source, target in zip(complete, observed):
        for rule in graph["missingness"]:
            if rng.random() < probability_missing(rule, source):
                target[rule["attribute"]] = token
    return observed


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config = json.loads((PROJECT_ROOT / "config" / "mcar-single-missing" / "experiment.json").read_text())
    graph = json.loads((PROJECT_ROOT / config["files"]["missingness_graph"]).read_text())
    seeds = config.get("sampling_seeds", {})
    data_rng = random.Random(seeds.get("complete_data", config["seed"]))
    missing_rng = random.Random(seeds.get("missingness", config["seed"]))
    complete = complete_records(config, data_rng)
    observed = inject_missingness(complete, graph, missing_rng)

    if args.check:
        assert complete == read_csv(PROJECT_ROOT / config["files"]["complete"])
        assert observed == read_csv(PROJECT_ROOT / config["files"]["observed"])
        print("complete and observed data match the configured pipeline")
    else:
        write_csv(PROJECT_ROOT / config["files"]["complete"], complete)
        write_csv(PROJECT_ROOT / config["files"]["observed"], observed)


if __name__ == "__main__":
    main()
