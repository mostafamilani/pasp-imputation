#!/usr/bin/env python3
"""Derive BID blocks from the observed table and quantitative MCAR graph."""

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def derive_blocks(observed_path: Path, config_path: Path) -> list[dict[str, object]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    missingness = config["missingness"]
    if missingness["mechanism"] != "MCAR":
        raise ValueError("This milestone intentionally supports MCAR only")
    distributions = config["generation"]["disease_given_group"]
    missing_token = missingness["missing_token"]
    blocks: list[dict[str, object]] = []
    with observed_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["disease"] != missing_token:
                continue
            conditional = distributions[row["group"]]
            if abs(sum(conditional.values()) - 1.0) > 1e-12:
                raise ValueError(f"probabilities do not sum to one for row {row['id']}")
            for disease, probability in conditional.items():
                blocks.append({"block_id": int(row["id"]), "row_id": int(row["id"]),
                               "group": row["group"], "disease": disease,
                               "probability": probability})
    return blocks


def render_csv(blocks: list[dict[str, object]]) -> str:
    fields = ("block_id", "row_id", "group", "disease", "probability")
    lines = [",".join(fields)]
    lines.extend(",".join(str(row[field]) for field in fields) for row in blocks)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_csv(derive_blocks(PROJECT_ROOT / "data" / "mcar-single-missing" / "observed.csv", PROJECT_ROOT / "config" / "mcar-single-missing" / "experiment.json"))
    if args.check:
        if rendered != (PROJECT_ROOT / "data" / "mcar-single-missing" / "blocks.csv").read_text(encoding="utf-8"):
            raise SystemExit("derived blocks differ from blocks.csv")
        print("blocks.csv matches the observed table and MCAR graph")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
