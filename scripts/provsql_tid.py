#!/usr/bin/env python3
"""Generate and optionally run the MarkoView/TID query in ProvSQL.

The source BID probability p is represented by an independent Bernoulli tuple
with q=p/(1+p).  Conditioning on exactly one alternative per block recovers
the original BID distribution.  ProvSQL evaluates P(E), P(Q and E), and
P(Q|E), where E is the exactly-one evidence event.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def literal(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def table_name(scenario: str) -> str:
    return "tid_" + re.sub(r"[^a-zA-Z0-9_]", "_", scenario).lower()


def sql_type(attribute: dict[str, Any]) -> str:
    return "BIGINT" if attribute.get("type") == "integer" else "TEXT"


def query_token_sql(config: dict[str, Any], table: str) -> str:
    """Translate the configured BCQ to a ProvSQL query returning one token."""
    attrs = config["relation"]["attributes"]
    atoms = config["query"]["atoms"]
    aliases = [f"q{i}" for i in range(len(atoms))]
    conditions: list[str] = []
    first_variable: dict[str, str] = {}
    for alias, atom in zip(aliases, atoms):
        for attribute, term in zip(attrs, atom["arguments"]):
            column = f"{alias}.{ident(attribute['name'])}"
            if isinstance(term, str) and term.startswith("?"):
                variable = term[1:]
            elif isinstance(term, dict) and "variable" in term:
                variable = str(term["variable"])
            else:
                variable = ""
            if variable:
                if variable in first_variable:
                    conditions.append(f"{column} = {first_variable[variable]}")
                else:
                    first_variable[variable] = column
            else:
                value = term.get("constant") if isinstance(term, dict) else term
                if attribute.get("type") == "integer":
                    conditions.append(f"{column} = {int(value)}")
                else:
                    conditions.append(f"{column} = {literal(value)}")
    sources = ", ".join(f"{ident(table)} {alias}" for alias in aliases)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    return f"SELECT provenance() FROM {sources}{where} GROUP BY ()"


def generate_sql(config: dict[str, Any], observed: list[dict[str, str]],
                 blocks: list[dict[str, str]]) -> str:
    scenario = config["experiment"]
    table = table_name(scenario)
    attrs = config["relation"]["attributes"]
    names = [attribute["name"] for attribute in attrs]
    key = config["relation"]["key"][0]
    token = config["missingness"].get("missing_token", "na")
    uncertain_ids = {row["block_id"] for row in blocks}

    columns = [f"{ident('block_id')} TEXT NOT NULL",
               f"{ident('candidate_id')} INTEGER NOT NULL"]
    columns += [f"{ident(a['name'])} {sql_type(a)} NOT NULL" for a in attrs]
    columns += [f"{ident('source_p')} DOUBLE PRECISION NOT NULL",
                f"{ident('tid_q')} DOUBLE PRECISION NOT NULL"]

    values: list[str] = []
    for row in blocks:
        p = float(row["probability"])
        q = p / (1.0 + p)
        data = [literal(row["block_id"]), str(int(row["candidate_id"]))]
        for attribute in attrs:
            value = row[attribute["name"]]
            data.append(str(int(value)) if attribute.get("type") == "integer"
                        else literal(value))
        data += [format(p, ".17g"), format(q, ".17g")]
        values.append("(" + ", ".join(data) + ")")
    for row in observed:
        if row[key] in uncertain_ids or token in row.values():
            continue
        data = [literal("certain:" + row[key]), "1"]
        for attribute in attrs:
            value = row[attribute["name"]]
            data.append(str(int(value)) if attribute.get("type") == "integer"
                        else literal(value))
        data += ["1.0", "1.0"]
        values.append("(" + ", ".join(data) + ")")

    block_ids = sorted(uncertain_ids, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    coverage = [
        "COALESCE((SELECT provenance() FROM " + ident(table) +
        " WHERE block_id = " + literal(block) + " GROUP BY ()), gate_zero())"
        for block in block_ids
    ]
    violation = (
        "COALESCE((SELECT provenance() FROM " + ident(table) + " a JOIN " +
        ident(table) + " b ON a.block_id = b.block_id AND "
        "a.candidate_id < b.candidate_id WHERE a.block_id NOT LIKE 'certain:%' "
        "GROUP BY ()), gate_zero())"
    )
    evidence_children = coverage + [f"provenance_not({violation})"]
    evidence = "provenance_times(ARRAY[" + ", ".join(evidence_children) + "])"
    query = "COALESCE((" + query_token_sql(config, table) + "), gate_zero())"

    return rf"""-- Generated MarkoView/TID program for {scenario}.
-- The base table is deliberately registered as TID, not with repair_key.
\set ON_ERROR_STOP on
SET search_path TO public, provsql;
CREATE EXTENSION IF NOT EXISTS provsql CASCADE;
DROP TABLE IF EXISTS {ident(table)} CASCADE;
CREATE TABLE {ident(table)} ({', '.join(columns)});
INSERT INTO {ident(table)} VALUES
  {',\n  '.join(values)};
SELECT add_provenance({literal(table)});
SELECT set_prob(provenance(), tid_q) FROM {ident(table)};

-- E says: at least one candidate and no pair of candidates in every block.
WITH events AS (
  SELECT {query} AS q, {evidence} AS e
)
SELECT
  probability_evaluate(e) AS p_evidence,
  probability_evaluate(provenance_times(ARRAY[q,e])) AS p_query_and_evidence,
  probability_evaluate(cond(q,e)) AS p_query_given_evidence
FROM events;
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--dsn", help="psql connection string; omit to only generate SQL")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scenario = config["experiment"]
    data_dir = ROOT / "data" / scenario
    observed_path = data_dir / "observed.csv"
    blocks_path = data_dir / "blocks.csv"
    if not observed_path.exists() or not blocks_path.exists():
        raise SystemExit("Run scripts/run_scenario.py first to create observed.csv and blocks.csv")

    sql = generate_sql(config, read_csv(observed_path), read_csv(blocks_path))
    output = args.output or ROOT / "models" / scenario / "provsql-tid.sql"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sql, encoding="utf-8")
    print(f"sql={output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")

    dsn = args.dsn or os.environ.get("PASPI_PROVSQL_DSN")
    if not dsn:
        print("status=generated (set PASPI_PROVSQL_DSN or pass --dsn to execute)")
        return
    log = data_dir / "logs" / "provsql-tid.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["psql", dsn, "-X", "-f", str(output)], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    log.write_text(result.stdout, encoding="utf-8")
    print(result.stdout, end="")
    if result.returncode:
        raise SystemExit(f"ProvSQL failed; see {log.relative_to(ROOT)}")
    print(f"log={log.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
