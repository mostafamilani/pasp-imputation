#!/usr/bin/env python3
"""Answer a batch of Boolean conjunctive queries using prepared Plingo bases."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from run_scenario import (
    ROOT, asp_query, attributes, hydrate_csv_schema, load_json, validate_config
)


METHODS = {
    "direct": {"manifest_key": "direct", "frontend": None},
    "markoview": {"manifest_key": "markoview", "frontend": "problog"},
}


def load_queries(path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    payload = load_json(path)
    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("query file requires a non-empty 'queries' array")
    relation = config["relation"]["name"]
    arity = len(attributes(config))
    names: set[str] = set()
    for query in queries:
        name = query.get("name", "")
        if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", name):
            raise ValueError(f"invalid query name {name!r}; use a lowercase ASP identifier")
        if name in names:
            raise ValueError(f"duplicate query name {name!r}")
        names.add(name)
        if query.get("type") != "boolean_conjunctive_query":
            raise ValueError(f"query {name}: only boolean_conjunctive_query is supported")
        atoms = query.get("atoms")
        if not isinstance(atoms, list) or not atoms:
            raise ValueError(f"query {name}: atoms must be a non-empty array")
        for atom in atoms:
            if atom.get("relation") != relation:
                raise ValueError(f"query {name}: expected relation {relation!r}")
            if len(atom.get("arguments", [])) != arity:
                raise ValueError(f"query {name}: atom arity does not match the relation")
    return queries


def query_program(query: dict[str, Any], config: dict[str, Any]) -> str:
    query_config = dict(config)
    query_config["query"] = query
    return "\n".join(
        [
            "% Per-query fragment.",
            asp_query(query_config),
            f"&query({query['name']}).",
            f"#show {query['name']}/0.",
            "",
        ]
    )


def run_plingo(
    base: Path,
    fragment: Path,
    frontend: str | None,
    query_name: str,
    log: Path,
) -> float:
    launcher = ROOT / ".vendor" / "bin" / "plingo"
    command = [str(launcher if launcher.exists() else "plingo")]
    if frontend:
        command.append(f"--frontend={frontend}")
    command.extend([str(base), str(fragment)])
    environment = os.environ.copy()
    vendor = str(ROOT / ".vendor")
    environment["PYTHONPATH"] = vendor + os.pathsep + environment.get("PYTHONPATH", "")
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode not in {0, 10, 20, 30}:
        raise RuntimeError(f"Plingo failed; see {log}")
    matches = re.findall(
        rf"^{re.escape(query_name)}:\s+([0-9.eE+-]+)$",
        result.stdout,
        flags=re.MULTILINE,
    )
    if not matches:
        raise RuntimeError(f"Plingo did not report {query_name!r}; see {log}")
    return float(matches[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer prepared probabilistic queries.")
    parser.add_argument("config", type=Path, help="path to an experiment JSON file")
    parser.add_argument("queries", type=Path, help="path to a batch query JSON file")
    parser.add_argument(
        "--method",
        choices=["direct", "markoview", "both"],
        default="markoview",
        help="QA encoding to run (default: markoview)",
    )
    parser.add_argument("--output", type=Path, help="answer JSON path")
    args = parser.parse_args()

    config = load_json(args.config.resolve())
    hydrate_csv_schema(config)
    validate_config(config)
    scenario = config["experiment"]
    queries = load_queries(args.queries.resolve(), config)
    manifest_path = ROOT / "models" / scenario / "qa-manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(
            f"QA manifest not found: {manifest_path}. Run scripts/prepare_qa.py first."
        )
    manifest = load_json(manifest_path)
    selected_methods = list(METHODS) if args.method == "both" else [args.method]
    log_dir = ROOT / "data" / scenario / "logs"
    answers: list[dict[str, Any]] = []

    for query in queries:
        temporary = tempfile.NamedTemporaryFile(
            mode="w", suffix=".lp", prefix=f"{query['name']}-", delete=False
        )
        fragment_path = Path(temporary.name)
        try:
            with temporary:
                temporary.write(query_program(query, config))
            probabilities: dict[str, float] = {}
            for method in selected_methods:
                settings = METHODS[method]
                base = ROOT / manifest[settings["manifest_key"]]
                if not base.is_file():
                    raise SystemExit(
                        f"Prepared base not found: {base}. Run scripts/prepare_qa.py first."
                    )
                log = log_dir / f"{query['name']}-{method}.log"
                started = time.perf_counter()
                probability = run_plingo(
                    base, fragment_path, settings["frontend"], query["name"], log
                )
                runtime_seconds = time.perf_counter() - started
                probabilities[method] = probability
                answers.append(
                    {
                        "query": query["name"],
                        "method": method,
                        "probability": probability,
                        "runtime_seconds": runtime_seconds,
                        "log": str(log.relative_to(ROOT)),
                    }
                )
            if len(probabilities) == 2 and not math.isclose(
                probabilities["direct"], probabilities["markoview"], abs_tol=5e-5
            ):
                raise RuntimeError(
                    f"methods disagree for {query['name']}: {probabilities}"
                )
        finally:
            fragment_path.unlink(missing_ok=True)

    method_totals = {
        method: sum(answer["runtime_seconds"] for answer in answers
                    if answer["method"] == method)
        for method in selected_methods
    }
    output = args.output or ROOT / "data" / scenario / "answers.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({
            "scenario": scenario,
            "answers": answers,
            "method_totals_seconds": method_totals,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    print("query\tmethod\tprobability\truntime_seconds")
    for answer in answers:
        print(
            f"{answer['query']}\t{answer['method']}\t"
            f"{answer['probability']:.8f}\t{answer['runtime_seconds']:.6f}"
        )
    print("method\ttotal_runtime_seconds")
    for method, total in method_totals.items():
        print(f"{method}\t{total:.6f}")
    print(f"answers={output}")


if __name__ == "__main__":
    main()
