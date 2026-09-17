#!/usr/bin/env python3
"""Generate or import the complete dataset configured for an experiment."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_scenario import (
    ROOT,
    attributes,
    complete_records,
    hydrate_csv_schema,
    load_json,
    validate_config,
    write_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate complete data without injecting missingness."
    )
    parser.add_argument("config", type=Path, help="path to an experiment JSON file")
    args = parser.parse_args()

    config = load_json(args.config.resolve())
    hydrate_csv_schema(config)
    validate_config(config)
    rows = complete_records(config)
    output = ROOT / config["files"]["complete"]
    fields = [attribute["name"] for attribute in attributes(config)]
    write_csv(output, rows, fields)

    print(f"complete_data={output}")
    print(f"records={len(rows)}")


if __name__ == "__main__":
    main()
