#!/usr/bin/env python3
"""Inject configured missingness into an existing complete dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_scenario import (
    ROOT,
    attributes,
    hydrate_csv_schema,
    inject_missingness,
    load_json,
    read_csv,
    validate_config,
    validate_rows,
    write_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read complete data and write observed data plus its missingness mask."
    )
    parser.add_argument("config", type=Path, help="path to an experiment JSON file")
    args = parser.parse_args()

    config = load_json(args.config.resolve())
    hydrate_csv_schema(config)
    validate_config(config)

    complete_path = ROOT / config["files"]["complete"]
    if not complete_path.is_file():
        raise SystemExit(
            f"Complete data not found: {complete_path}. "
            "Run scripts/generate_complete.py first."
        )
    complete = read_csv(complete_path)
    validate_rows(complete, config)
    observed, mask = inject_missingness(complete, config)

    observed_path = ROOT / config["files"]["observed"]
    mask_path = ROOT / config["files"]["missingness_mask"]
    fields = [attribute["name"] for attribute in attributes(config)]
    mask_fields = [config["relation"]["key"][0]] + [
        node["name"] for node in config["missingness"]["nodes"]
    ]
    write_csv(observed_path, observed, fields)
    write_csv(mask_path, mask, mask_fields)

    missing_cells = sum(
        int(value)
        for row in mask
        for name, value in row.items()
        if name not in config["relation"]["key"]
    )
    print(f"observed_data={observed_path}")
    print(f"missingness_mask={mask_path}")
    print(f"records={len(observed)}")
    print(f"missing_cells={missing_cells}")


if __name__ == "__main__":
    main()
