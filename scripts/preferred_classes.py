#!/usr/bin/env python3
"""Enumerate matching-world classes and select MCC/MPC preferred classes."""

from __future__ import annotations

from collections import Counter
import itertools
import math
from typing import Any

from run_scenario import attributes, bn_probability, query_holds


def enumerate_classes(observed: list[dict[str, str]], blocks: list[dict[str, Any]],
                      config: dict[str, Any]) -> list[dict[str, Any]]:
    """Group BID worlds by their non-key tuple multiset."""
    key = config["relation"]["key"][0]
    names = [attribute["name"] for attribute in attributes(config)]
    value_names = [name for name in names if name != key]
    token = config["missingness"].get("missing_token", "na")
    certain = [dict(row) for row in observed if token not in row.values()]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in blocks:
        grouped.setdefault(str(candidate["block_id"]), []).append(candidate)
    alternatives = list(grouped.values())
    world_count = math.prod(map(len, alternatives)) if alternatives else 1
    cap = config.get("preferred_classes", {}).get(
        "max_enumerated_worlds",
        config.get("report", {}).get("max_enumerated_worlds", 100000),
    )
    if world_count > cap:
        raise ValueError(f"{world_count} BID worlds exceed configured enumeration cap {cap}")

    classes: dict[tuple[tuple[tuple[str, ...], int], ...], dict[str, Any]] = {}
    selections = itertools.product(*alternatives) if alternatives else [()]
    for world_id, selected in enumerate(selections, 1):
        world = certain + [{name: str(candidate[name]) for name in names}
                           for candidate in selected]
        probability = math.prod(float(candidate["probability"]) for candidate in selected)
        counts = Counter(tuple(row[name] for name in value_names) for row in world)
        signature = tuple(sorted(counts.items()))
        matched = classes.setdefault(signature, {
            "signature": signature, "multiplicities": counts,
            "probability": 0.0, "worlds": [],
        })
        matched["probability"] += probability
        matched["worlds"].append({"world_id": world_id, "rows": world})
    result = list(classes.values())
    support = set().union(*(set(class_["multiplicities"]) for class_ in result))
    for class_ in result:
        class_["support"] = support
    return result


def euclidean_compliance(class_: dict[str, Any], config: dict[str, Any]) -> float:
    """Squared Euclidean distance between empirical and MG distributions."""
    key = config["relation"]["key"][0]
    names = [attribute["name"] for attribute in attributes(config)
             if attribute["name"] != key]
    size = sum(class_["multiplicities"].values())
    return sum(
        (class_["multiplicities"].get(values, 0) / size
         - bn_probability(dict(zip(names, values)), config)) ** 2
        for values in class_["support"]
    ) if size else 0.0


def preferred_classes(classes: list[dict[str, Any]], semantics: str,
                      config: dict[str, Any]) -> list[dict[str, Any]]:
    """Select every class tied for the MCC or MPC optimum."""
    settings = config.get("preferred_classes", {})
    enabled = settings.get("enabled_semantics", ["mcc", "mpc"])
    if semantics not in enabled:
        raise ValueError(
            f"preferred-class semantics {semantics!r} is not enabled; expected one of {enabled}"
        )
    if not classes:
        return []
    if semantics == "mpc":
        optimum = max(class_["probability"] for class_ in classes)
        return [class_ for class_ in classes
                if math.isclose(class_["probability"], optimum, abs_tol=1e-12)]
    if semantics == "mcc":
        distance = settings.get("mcc_distance", "squared_euclidean")
        if distance != "squared_euclidean":
            raise ValueError(
                "preferred_classes.mcc_distance currently supports only "
                "'squared_euclidean'"
            )
        if not config.get("generation", {}).get("nodes"):
            raise ValueError("MCC requires a configured generation BN")
        for class_ in classes:
            class_["compliance"] = euclidean_compliance(class_, config)
        optimum = min(class_["compliance"] for class_ in classes)
        return [class_ for class_ in classes
                if math.isclose(class_["compliance"], optimum, abs_tol=1e-12)]
    raise ValueError(f"unknown preferred-class semantics {semantics!r}")


def answer_preferred_query(query: dict[str, Any], classes: list[dict[str, Any]],
                           config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the set of (query answer, unnormalized class probability) pairs."""
    query_config = dict(config)
    query_config["query"] = query
    answers: set[tuple[bool, float]] = set()
    for class_ in classes:
        values = {query_holds(world["rows"], query_config)
                  for world in class_["worlds"]}
        if len(values) != 1:
            raise ValueError(
                f"query {query['name']}: answer is not invariant within preferred class; "
                "tuple-key-specific queries are outside preferred-class semantics"
            )
        answers.add((values.pop(), class_["probability"]))
    return [{"answer": answer, "class_probability": probability}
            for answer, probability in sorted(answers, key=lambda item: (item[0], item[1]))]
