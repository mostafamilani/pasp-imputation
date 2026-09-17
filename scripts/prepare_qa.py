#!/usr/bin/env python3
"""Prepare query-independent direct-BID and MarkoView Plingo programs."""

from __future__ import annotations

import argparse
import csv
import json
import itertools
import math
from pathlib import Path
from typing import Any

from run_scenario import (
    ROOT,
    asp_atom,
    attributes,
    derive_blocks,
    hydrate_csv_schema,
    load_json,
    read_csv,
    validate_config,
    validate_rows,
    write_csv,
)


def build_bases(
    observed: list[dict[str, str]],
    blocks: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[str, str, list[dict[str, Any]]]:
    attrs = attributes(config)
    names = [attribute["name"] for attribute in attrs]
    relation = config["relation"]["name"]
    token = config["missingness"].get("missing_token", "na")

    direct = [
        "% Query-independent direct BID encoding.",
        "% Each block chooses exactly one alternative with categorical weight p.",
    ]
    markoview = [
        "% Query-independent MarkoView encoding over an independent TID.",
        "% BID p becomes TID q=p/(1+p), whose odds are p.",
        "% Hard constraints condition each block on exactly one alternative.",
    ]
    for row in observed:
        if token not in row.values():
            fact = asp_atom(relation, [row[name] for name in names], attrs) + "."
            direct.append(fact)
            markoview.append(fact)

    grouped: dict[str, list[dict[str, Any]]] = {}
    markoview_rows: list[dict[str, Any]] = []
    for candidate in blocks:
        grouped.setdefault(str(candidate["block_id"]), []).append(candidate)

    for block_id, candidates in grouped.items():
        choices = "; ".join(
            f"chosen({block_id},{candidate['candidate_id']})" for candidate in candidates
        )
        direct.append(f"1 {{ {choices} }} 1.")
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            probability = float(candidate["probability"])
            if not 0 < probability <= 1:
                raise ValueError(
                    f"block {block_id}, candidate {candidate_id}: expected 0 < p <= 1"
                )
            atom = asp_atom(
                relation, [candidate[name] for name in names], attrs
            )
            direct.append(f"{atom} :- chosen({block_id},{candidate_id}).")
            direct.append(
                f':~ chosen({block_id},{candidate_id}). '
                f'["{math.log(probability):.17g}"@0,{block_id},{candidate_id}]'
            )

            tid_probability = probability / (1.0 + probability)
            markoview.append(
                f'chosen({block_id},{candidate_id}) :- '
                f'&problog("{tid_probability:.17g}").'
            )
            markoview.append(f"{atom} :- chosen({block_id},{candidate_id}).")
            markoview_rows.append(
                {
                    "block_id": block_id,
                    "candidate_id": candidate_id,
                    "bid_probability": probability,
                    "tid_probability": tid_probability,
                    "tid_odds": tid_probability / (1.0 - tid_probability),
                }
            )

        markoview.append(f"selected({block_id}) :- chosen({block_id},_).")
        markoview.append(f":- not selected({block_id}).")
        for left, right in itertools.combinations(candidates, 2):
            markoview.append(
                f":- chosen({block_id},{left['candidate_id']}), "
                f"chosen({block_id},{right['candidate_id']})."
            )

    direct.extend(["", "#show chosen/2."])
    markoview.extend(["", "#show chosen/2."])
    return "\n".join(direct) + "\n", "\n".join(markoview) + "\n", markoview_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare reusable QA artifacts without compiling a query."
    )
    parser.add_argument("config", type=Path, help="path to an experiment JSON file")
    args = parser.parse_args()

    config = load_json(args.config.resolve())
    hydrate_csv_schema(config)
    validate_config(config)
    scenario = config["experiment"]

    observed_path = ROOT / config["files"]["observed"]
    if not observed_path.is_file():
        raise SystemExit(
            f"Observed data not found: {observed_path}. "
            "Run scripts/inject_missingness.py first."
        )
    observed = read_csv(observed_path)
    validate_rows(observed, config, allow_missing=True)
    blocks = derive_blocks(observed, config)
    direct, markoview, markoview_rows = build_bases(observed, blocks, config)

    blocks_path = ROOT / config["files"]["blocks"]
    block_fields = ["block_id", "candidate_id"] + [
        attribute["name"] for attribute in attributes(config)
    ] + ["probability"]
    write_csv(blocks_path, blocks, block_fields)

    model_dir = ROOT / "models" / scenario
    model_dir.mkdir(parents=True, exist_ok=True)
    direct_path = model_dir / "direct-base.lp"
    markoview_path = model_dir / "markoview-base.plp"
    direct_path.write_text(direct, encoding="utf-8")
    markoview_path.write_text(markoview, encoding="utf-8")

    tuples_path = ROOT / "data" / scenario / "markoview-tuples.csv"
    write_csv(
        tuples_path,
        markoview_rows,
        ["block_id", "candidate_id", "bid_probability", "tid_probability", "tid_odds"],
    )
    manifest_path = model_dir / "qa-manifest.json"
    manifest = {
        "scenario": scenario,
        "observed": str(observed_path.relative_to(ROOT)),
        "blocks": str(blocks_path.relative_to(ROOT)),
        "direct": str(direct_path.relative_to(ROOT)),
        "markoview": str(markoview_path.relative_to(ROOT)),
        "markoview_tuples": str(tuples_path.relative_to(ROOT)),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"scenario={scenario}")
    print(f"uncertain_blocks={len({row['block_id'] for row in blocks})}")
    print(f"candidates={len(blocks)}")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
