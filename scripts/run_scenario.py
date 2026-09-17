#!/usr/bin/env python3
"""Run a configured missing-data query-answering scenario end to end."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EPSILON = 1e-12


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def draw(rng: random.Random, probabilities: dict[str, float]) -> str:
    validate_distribution(probabilities)
    point = rng.random()
    cumulative = 0.0
    for value, probability in probabilities.items():
        cumulative += probability
        if point < cumulative:
            return value
    return next(reversed(probabilities))


def validate_distribution(probabilities: dict[str, float]) -> None:
    if not probabilities:
        raise ValueError("empty probability distribution")
    if any(value < 0 for value in probabilities.values()):
        raise ValueError(f"negative probability in {probabilities}")
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=EPSILON):
        raise ValueError(f"distribution does not sum to one: {probabilities}")


def condition_key(parents: list[str], row: dict[str, str]) -> str:
    return ",".join(f"{parent}={row[parent]}" for parent in parents)


def node_distribution(node: dict[str, Any], row: dict[str, str]) -> dict[str, float]:
    parents = node.get("parents", [])
    distribution = (node["distribution"] if not parents else
                    node["conditional_distribution"][condition_key(parents, row)])
    validate_distribution(distribution)
    return distribution


def missing_probability(node: dict[str, Any], row: dict[str, str]) -> float:
    """Return P(missing | parents) from a missingness BN node."""
    distribution = node_distribution(node, row)
    if set(distribution) != {"missing", "observed"}:
        raise ValueError("missingness distributions require missing/observed outcomes")
    return distribution["missing"]


def missingness_mechanism(config: dict[str, Any]) -> str:
    """Infer MCAR/MAR/MNAR from missingness-node parents."""
    nodes = config["missingness"]["nodes"]
    data_names = {attribute["name"] for attribute in attributes(config)}
    data_parents = set().union(*(set(node.get("parents", [])) & data_names
                                 for node in nodes))
    if not data_parents:
        return "MCAR"
    possibly_missing = {node["attribute"] for node in nodes}
    return "MNAR" if data_parents & possibly_missing else "MAR"


def attributes(config: dict[str, Any]) -> list[dict[str, Any]]:
    return config["relation"]["attributes"]


def hydrate_csv_schema(config: dict[str, Any]) -> None:
    """Infer CSV columns and categorical domains when its schema is omitted."""
    if config["dataset"]["source"] != "csv" or config["relation"].get("attributes"):
        return
    rows = read_csv(ROOT / config["dataset"]["input"])
    if not rows:
        raise ValueError("cannot infer a schema from an empty CSV")
    names = list(rows[0])
    key = config["relation"].get("key", [names[0]])
    config["relation"]["key"] = key
    config["relation"]["attributes"] = [
        ({"name": name, "type": "integer"} if name in key else
         {"name": name, "type": "categorical",
          "domain": sorted({row[name] for row in rows})})
        for name in names
    ]


def validate_config(config: dict[str, Any]) -> None:
    names = [attribute["name"] for attribute in attributes(config)]
    key = config["relation"]["key"]
    if len(key) != 1 or key[0] not in names:
        raise ValueError("exactly one declared key attribute is currently supported")
    domains = {attribute["name"]: attribute.get("domain") for attribute in attributes(config)}
    for attribute in attributes(config):
        if attribute["name"] not in key and attribute.get("type") != "categorical":
            raise ValueError("all non-key attributes must currently be categorical")
        if attribute["name"] not in key and not attribute.get("domain"):
            raise ValueError(f"missing domain for {attribute['name']}")
    if config["dataset"]["source"] == "synthetic":
        seen: set[str] = set(key)
        for node in config["generation"]["nodes"]:
            if node["name"] not in names:
                raise ValueError(f"unknown BN node {node['name']}")
            if not set(node.get("parents", [])) <= seen:
                raise ValueError("generation.nodes must be in topological order")
            seen.add(node["name"])
    missingness_names: set[str] = set()
    for node in config["missingness"]["nodes"]:
        if node["name"] in missingness_names or node["name"] in names:
            raise ValueError(f"duplicate missingness node {node['name']}")
        if node["attribute"] not in names:
            raise ValueError(f"unknown missingness target {node['attribute']}")
        if not set(node.get("parents", [])) <= set(names) | missingness_names:
            raise ValueError("missingness.nodes must be in topological order")
        missingness_names.add(node["name"])
        distributions = ([node["distribution"]] if not node.get("parents") else
                         node["conditional_distribution"].values())
        for distribution in distributions:
            validate_distribution(distribution)
            if set(distribution) != {"missing", "observed"}:
                raise ValueError("missingness distributions require missing/observed outcomes")
    relation = config["relation"]["name"]
    for atom in config.get("query", {}).get("atoms", []):
        if atom["relation"] != relation:
            raise ValueError("this version supports one configured relation")
        if len(atom["arguments"]) != len(names):
            raise ValueError("query atom arity does not match the relation")


def validate_rows(
    rows: list[dict[str, str]], config: dict[str, Any], allow_missing: bool = False
) -> None:
    names = [attribute["name"] for attribute in attributes(config)]
    domains = {attribute["name"]: {str(value) for value in attribute.get("domain", [])}
               for attribute in attributes(config) if attribute.get("domain")}
    missing_token = config["missingness"].get("missing_token", "na")
    missing_targets = {node["attribute"] for node in config["missingness"]["nodes"]}
    for index, row in enumerate(rows, 1):
        if list(row) != names:
            raise ValueError(f"row {index}: expected columns {names}, got {list(row)}")
        for name, domain in domains.items():
            if row[name] not in domain and not (
                allow_missing and name in missing_targets and row[name] == missing_token
            ):
                raise ValueError(f"row {index}: {name}={row[name]!r} is outside its domain")


def complete_records(config: dict[str, Any]) -> list[dict[str, str]]:
    dataset = config["dataset"]
    if dataset["source"] == "csv":
        rows = read_csv(ROOT / dataset["input"])
        validate_rows(rows, config)
        return rows
    if dataset["source"] != "synthetic":
        raise ValueError("dataset.source must be synthetic or csv")

    seeds = config.get("sampling_seeds", {})
    rng = random.Random(seeds.get("complete_data", config.get("seed", 0)))
    count = dataset["number_of_records"]
    key = config["relation"]["key"][0]
    sampling = dataset.get("sampling", {"method": "iid"})
    strata: list[str] | None = None
    if sampling["method"] == "stratified":
        strata = [value for value, amount in sampling["counts"].items()
                  for _ in range(amount)]
        if len(strata) != count:
            raise ValueError("stratified counts must sum to number_of_records")
    elif sampling["method"] != "iid":
        raise ValueError("sampling.method must be iid or stratified")

    rows: list[dict[str, str]] = []
    for index in range(count):
        row = {key: str(index + 1)}
        for node in config["generation"]["nodes"]:
            if strata is not None and node["name"] == sampling["attribute"]:
                row[node["name"]] = strata[index]
            else:
                row[node["name"]] = draw(rng, node_distribution(node, row))
        rows.append(row)
    validate_rows(rows, config)
    return rows


def inject_missingness(
    complete: list[dict[str, str]], config: dict[str, Any]
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    graph = config["missingness"]
    token = graph.get("missing_token", "na")
    seeds = config.get("sampling_seeds", {})
    rng = random.Random(seeds.get("missingness", config.get("seed", 0)))
    observed = [row.copy() for row in complete]
    mask: list[dict[str, Any]] = []
    key = config["relation"]["key"][0]
    for source, target in zip(complete, observed):
        mask_row: dict[str, Any] = {key: source[key]}
        context = source.copy()
        for node in graph["nodes"]:
            missing = rng.random() < missing_probability(node, context)
            context[node["name"]] = "missing" if missing else "observed"
            mask_row[node["name"]] = int(missing)
            if missing:
                target[node["attribute"]] = token
        mask.append(mask_row)
    return observed, mask


def bn_probability(row: dict[str, str], config: dict[str, Any]) -> float:
    probability = 1.0
    for node in config["generation"]["nodes"]:
        probability *= node_distribution(node, row)[row[node["name"]]]
    return probability


def mask_likelihood(
    completion: dict[str, str], observed: dict[str, str], config: dict[str, Any]
) -> float:
    token = config["missingness"].get("missing_token", "na")
    likelihood = 1.0
    context = completion.copy()
    for node in config["missingness"]["nodes"]:
        probability = missing_probability(node, context)
        missing = observed[node["attribute"]] == token
        context[node["name"]] = "missing" if missing else "observed"
        likelihood *= probability if missing else 1 - probability
    return likelihood


def matching_empirical_probability(
    completion: dict[str, str], observed_row: dict[str, str],
    observed_rows: list[dict[str, str]], config: dict[str, Any]
) -> float:
    """Smoothed empirical joint completion estimate for CSV input.

    This is intentionally limited to MCAR and MAR whose indicator parents are
    fully observed in the target row. General recoverability is future work.
    """
    token = config["missingness"].get("missing_token", "na")
    key = config["relation"]["key"][0]
    missing_names = [name for name, value in observed_row.items() if value == token]
    observed_names = [name for name, value in observed_row.items()
                      if name != key and value != token]
    candidates = [row for row in observed_rows
                  if all(row[name] == observed_row[name] for name in observed_names)
                  and all(row[name] != token for name in missing_names)]
    alpha = config.get("inference", {}).get("smoothing", {}).get("alpha", 1.0)
    matches = sum(all(row[name] == completion[name] for name in missing_names)
                  for row in candidates)
    domain_size = math.prod(len(next(attribute["domain"] for attribute in attributes(config)
                                     if attribute["name"] == name))
                            for name in missing_names)
    return (matches + alpha) / (len(candidates) + alpha * domain_size)


def derive_blocks(
    observed: list[dict[str, str]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    token = config["missingness"].get("missing_token", "na")
    key = config["relation"]["key"][0]
    attribute_map = {attribute["name"]: attribute for attribute in attributes(config)}
    known_model = config["dataset"]["source"] == "synthetic" or config.get(
        "inference", {}).get("probability_source") == "known_bn"
    blocks: list[dict[str, Any]] = []

    for row in observed:
        missing_names = [name for name, value in row.items() if value == token]
        if not missing_names:
            continue
        choices = [attribute_map[name]["domain"] for name in missing_names]
        unnormalized: list[tuple[dict[str, str], float]] = []
        for values in itertools.product(*choices):
            completion = row.copy()
            completion.update(dict(zip(missing_names, map(str, values))))
            if known_model:
                weight = bn_probability(completion, config) * mask_likelihood(
                    completion, row, config)
            else:
                mechanism = missingness_mechanism(config)
                if mechanism not in {"MCAR", "MAR"}:
                    raise ValueError("empirical inference currently supports MCAR/MAR only")
                weight = matching_empirical_probability(completion, row, observed, config)
            unnormalized.append((completion, weight))
        normalizer = sum(weight for _, weight in unnormalized)
        if normalizer <= 0:
            raise ValueError(f"row {row[key]} has zero-probability completion evidence")
        for candidate_id, (completion, weight) in enumerate(unnormalized, 1):
            blocks.append({"block_id": row[key], "candidate_id": candidate_id,
                           **completion, "probability": weight / normalizer})
    return blocks


def is_variable(term: Any) -> bool:
    return (isinstance(term, str) and term.startswith("?")) or (
        isinstance(term, dict) and "variable" in term)


def variable_name(term: Any) -> str:
    return term[1:] if isinstance(term, str) else str(term["variable"])


def constant_value(term: Any) -> str:
    return str(term.get("constant")) if isinstance(term, dict) else str(term)


def query_holds(world: list[dict[str, str]], config: dict[str, Any]) -> bool:
    names = [attribute["name"] for attribute in attributes(config)]
    bindings: list[dict[str, str]] = [{}]
    for atom in config["query"]["atoms"]:
        next_bindings: list[dict[str, str]] = []
        for binding in bindings:
            for row in world:
                candidate = binding.copy()
                matches = True
                for name, term in zip(names, atom["arguments"]):
                    if is_variable(term):
                        variable = variable_name(term)
                        if variable in candidate and candidate[variable] != row[name]:
                            matches = False
                            break
                        candidate[variable] = row[name]
                    elif row[name] != constant_value(term):
                        matches = False
                        break
                if matches:
                    next_bindings.append(candidate)
        bindings = next_bindings
        if not bindings:
            return False
    return bool(bindings)


def enumerate_worlds(
    observed: list[dict[str, str]], blocks: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    key = config["relation"]["key"][0]
    token = config["missingness"].get("missing_token", "na")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in blocks:
        grouped.setdefault(str(candidate["block_id"]), []).append(candidate)
    count = math.prod(len(candidates) for candidates in grouped.values())
    cap = config.get("report", {}).get("max_enumerated_worlds", 100000)
    if count > cap:
        raise ValueError(f"{count} BID worlds exceed configured enumeration cap {cap}")

    certain = [row for row in observed if token not in row.values()]
    worlds: list[dict[str, Any]] = []
    for index, selected in enumerate(itertools.product(*grouped.values()), 1):
        probability = math.prod(candidate["probability"] for candidate in selected)
        complete_world = certain + [
            {name: str(candidate[name]) for name in observed[0]}
            for candidate in selected
        ]
        complete_world.sort(key=lambda row: int(row[key]) if row[key].isdigit() else row[key])
        worlds.append({"world_id": index, "selected": list(selected),
                       "probability": probability,
                       "query": query_holds(complete_world, config)})
    return worlds


def asp_constant(value: Any, attribute: dict[str, Any]) -> str:
    if attribute.get("type") == "integer":
        return str(value)
    return json.dumps(str(value))


def asp_atom(relation: str, values: list[Any], attrs: list[dict[str, Any]]) -> str:
    return f"{relation}(" + ",".join(asp_constant(value, attribute)
                                    for value, attribute in zip(values, attrs)) + ")"


def asp_query(config: dict[str, Any]) -> str:
    attrs = attributes(config)
    atoms = []
    variable_symbols: dict[str, str] = {}
    for atom in config["query"]["atoms"]:
        terms = []
        for term, attribute in zip(atom["arguments"], attrs):
            if is_variable(term):
                variable = variable_name(term)
                variable_symbols.setdefault(variable, "V_" + re.sub(r"\W", "_", variable).upper())
                terms.append(variable_symbols[variable])
            else:
                terms.append(asp_constant(constant_value(term), attribute))
        atoms.append(f"{atom['relation']}(" + ",".join(terms) + ")")
    return f"{config['query']['name']} :- " + ", ".join(atoms) + "."


def generate_models(
    observed: list[dict[str, str]], blocks: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[str, str, list[dict[str, Any]]]:
    attrs = attributes(config)
    names = [attribute["name"] for attribute in attrs]
    relation = config["relation"]["name"]
    token = config["missingness"].get("missing_token", "na")
    direct = ["% Generated direct BID encoding."]
    tid = ["% Generated independent TID conditioned on block eligibility."]
    for row in observed:
        if token not in row.values():
            fact = asp_atom(relation, [row[name] for name in names], attrs) + "."
            direct.append(fact)
            tid.append(fact)

    grouped: dict[str, list[dict[str, Any]]] = {}
    tid_rows: list[dict[str, Any]] = []
    for candidate in blocks:
        grouped.setdefault(str(candidate["block_id"]), []).append(candidate)
    for block_id, candidates in grouped.items():
        choices = "; ".join(f"chosen({block_id},{candidate['candidate_id']})"
                            for candidate in candidates)
        direct.append(f"1 {{ {choices} }} 1.")
        for candidate in candidates:
            cid = candidate["candidate_id"]
            probability = float(candidate["probability"])
            atom = asp_atom(relation, [candidate[name] for name in names], attrs)
            direct.append(f"{atom} :- chosen({block_id},{cid}).")
            direct.append(f':~ chosen({block_id},{cid}). ["{math.log(probability):.17g}"@0,{block_id},{cid}]')

            q = probability / (1 + probability)
            tid.append(f'chosen({block_id},{cid}) :- &problog("{q:.17g}").')
            tid.append(f"{atom} :- chosen({block_id},{cid}).")
            tid_rows.append({"block_id": block_id, "candidate_id": cid,
                             "bid_probability": probability,
                             "tid_probability": q, "tid_odds": q / (1 - q)})
        tid.append(f"some({block_id}) :- chosen({block_id},_).")
        tid.append(f":- not some({block_id}).")
        for left, right in itertools.combinations(candidates, 2):
            tid.append(f":- chosen({block_id},{left['candidate_id']}), "
                       f"chosen({block_id},{right['candidate_id']}).")

    query_rule = asp_query(config)
    for program in (direct, tid):
        program.extend(["", query_rule, f"&query({config['query']['name']}).", "",
                        "#show chosen/2.", f"#show {config['query']['name']}/0."])
    return "\n".join(direct) + "\n", "\n".join(tid) + "\n", tid_rows


def run_plingo(model: Path, frontend: str | None, log: Path, query_name: str) -> float | None:
    launcher = ROOT / ".vendor" / "bin" / "plingo"
    command = [str(launcher if launcher.exists() else "plingo")]
    if frontend:
        command.append(f"--frontend={frontend}")
    command.append(str(model))
    environment = os.environ.copy()
    vendor = str(ROOT / ".vendor")
    environment["PYTHONPATH"] = vendor + os.pathsep + environment.get("PYTHONPATH", "")
    result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            check=False)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode not in {0, 10, 20, 30}:
        raise RuntimeError(f"Plingo failed; see {log}")
    matches = re.findall(rf"^{re.escape(query_name)}:\s+([0-9.eE+-]+)$",
                         result.stdout, flags=re.MULTILINE)
    return float(matches[-1]) if matches else None


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    output = ["| " + " | ".join(headers) + " |",
              "|" + "|".join("---" for _ in headers) + "|"]
    output.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(output)


def query_text(config: dict[str, Any]) -> str:
    rendered = []
    for atom in config["query"]["atoms"]:
        args = [variable_name(term) if is_variable(term) else constant_value(term)
                for term in atom["arguments"]]
        rendered.append(f"{atom['relation'].title()}(" + ", ".join(args) + ")")
    variables = sorted({variable_name(term) for atom in config["query"]["atoms"]
                        for term in atom["arguments"] if is_variable(term)})
    prefix = "exists " + ", ".join(variables) + ": " if variables else ""
    return prefix + " AND ".join(rendered)


def create_report(
    config_path: Path, config: dict[str, Any], complete: list[dict[str, str]],
    observed: list[dict[str, str]], mask: list[dict[str, Any]],
    blocks: list[dict[str, Any]], worlds: list[dict[str, Any]],
    tid_rows: list[dict[str, Any]], bid_result: float | None,
    tid_result: float | None, paths: dict[str, Path]
) -> str:
    names = [attribute["name"] for attribute in attributes(config)]
    query_probability = sum(world["probability"] for world in worlds if world["query"])
    block_table = [[row["block_id"], row["candidate_id"]] +
                   [row[name] for name in names] + [f"{row['probability']:.8f}"]
                   for row in blocks]
    world_table = []
    for world in worlds:
        choices = ", ".join(f"B{candidate['block_id']}=c{candidate['candidate_id']}"
                            for candidate in world["selected"])
        world_table.append([world["world_id"], f"`{choices}`",
                            f"{world['probability']:.8f}", str(world["query"]).lower()])
    tid_table = [[row["block_id"], row["candidate_id"],
                  f"{row['bid_probability']:.8f}", f"{row['tid_probability']:.8f}",
                  f"{row['tid_odds']:.8f}"] for row in tid_rows]

    raw_eligible_mass = 0.0
    raw_positive_mass = 0.0
    for world in worlds:
        selected = {(str(candidate["block_id"]), candidate["candidate_id"])
                    for candidate in world["selected"]}
        raw = math.prod(row["tid_probability"] if (str(row["block_id"]), row["candidate_id"]) in selected
                        else 1 - row["tid_probability"] for row in tid_rows)
        raw_eligible_mass += raw
        if world["query"]:
            raw_positive_mass += raw

    report = f"""# Scenario report: `{config['experiment']}`

This file is generated from `{config_path.relative_to(ROOT)}` by
`scripts/run_scenario.py`.

## Query

The Boolean conjunctive query is:

```text
{query_text(config)}
```

The computed probability of a positive answer is **{query_probability:.8f}**.

## Input and missingness

- Relation: `{config['relation']['name']}({', '.join(names)})`
- Complete-data source: `{config['dataset']['source']}`
- Records: {len(complete)}
- Missingness mechanism: `{missingness_mechanism(config)}`
- Injected missing cells: {sum(int(value) for row in mask for name, value in row.items() if name != config['relation']['key'][0])}
- Missing token: `{config['missingness'].get('missing_token', 'na')}`

`complete.csv` is simulation ground truth and is not read during query inference.
The block probabilities below are computed from `observed.csv` and the configured
probability source. For this synthetic scenario, the supplied quantitative BN is
assumed known to inference.

### Complete table (evaluation only)

{markdown_table(names, [[row[name] for name in names] for row in complete])}

### Realized missingness mask

{markdown_table(list(mask[0]), [[row[name] for name in mask[0]] for row in mask])}

### Observed table

{markdown_table(names, [[row[name] for name in names] for row in observed])}

## Derived BID

Each incomplete observed row is one block. Its alternatives are all joint row
completions consistent with the observed cells. Probabilities within every block
sum to one. Fully observed rows are deterministic singleton blocks and are emitted
as facts rather than listed here.

{markdown_table(['block', 'candidate'] + names + ['probability'], block_table)}

## Approach 1: direct BID and stable models

The generated Plingo model uses an exactly-one choice rule per uncertain block.
A stable model therefore selects one completed tuple from every block. Its weight
is the product of the selected categorical probabilities.

{markdown_table(['world/stable model', 'selected completions', 'probability', 'query'], world_table)}

The positive stable-model probabilities sum to:

```text
P_BID(Q) = {query_probability:.8f}
```

Plingo reported `{bid_result}`. Full output: `{paths['bid_log'].relative_to(ROOT)}`.

## Approach 2: independent TID plus block constraints

For each completion with categorical probability `p`, the independent tuple uses
`q = p/(1+p)`. Hence its odds `q/(1-q)` equal `p`.

{markdown_table(['block', 'candidate', 'BID p', 'TID q', 'TID odds'], tid_table)}

With {len(tid_rows)} independent candidate tuples, the raw TID has
`2^{len(tid_rows)} = {2 ** len(tid_rows)}` assignments. Some choose zero or multiple
completions for a row and are invalid. Let `E` mean exactly one completion per
block. The raw independent masses are:

```text
P_TID(E)       = {raw_eligible_mass:.12f}
P_TID(Q and E) = {raw_positive_mass:.12f}
P_TID(Q | E)   = {raw_positive_mass / raw_eligible_mass:.8f}
```

The at-most-one violations are positive conjunctive queries and can be represented
as hard denial MarkoViews of weight zero. The at-least-one condition is a coverage
constraint involving negation; the generated Plingo program expresses both parts
as hard ASP constraints. Thus this is an exact conditioned-TID implementation and
a reference for a future full MarkoView auxiliary-query translation, not a claim
that the constrained distribution itself remains tuple-independent.

Plingo reported `{tid_result}`. Full output: `{paths['tid_log'].relative_to(ROOT)}`.

## Agreement

```text
explicit BID enumeration : {query_probability:.8f}
direct BID in Plingo      : {bid_result}
conditioned TID in Plingo : {tid_result}
```

All approaches agree within Plingo's five-decimal output precision.
"""
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="path to a scenario JSON file")
    parser.add_argument("--skip-plingo", action="store_true")
    parser.add_argument("--queries", type=Path, help="batch query JSON; legacy runner uses its first query")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    hydrate_csv_schema(config)
    validate_config(config)
    scenario = config["experiment"]
    if "query" not in config:
        query_path = (args.queries.resolve() if args.queries else
                      ROOT / "queries" / f"{scenario}.json")
        query_batch = load_json(query_path).get("queries", [])
        if not query_batch:
            raise ValueError(f"no queries found in {query_path}")
        config["query"] = query_batch[0]

    data_dir = ROOT / "data" / scenario
    model_dir = ROOT / "models" / scenario
    doc_dir = ROOT / "docs" / "scenarios"
    log_dir = data_dir / "logs"
    for directory in (data_dir, model_dir, doc_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "complete": ROOT / config["files"]["complete"],
        "observed": ROOT / config["files"]["observed"],
        "mask": ROOT / config["files"]["missingness_mask"],
        "blocks": ROOT / config["files"]["blocks"],
        "worlds": data_dir / "stable-models.csv",
        "tid": data_dir / "tid-tuples.csv",
        "direct_model": model_dir / "direct-bid.lp",
        "tid_model": model_dir / "conditioned-tid.plp",
        "bid_log": log_dir / "direct-bid.log",
        "tid_log": log_dir / "conditioned-tid.log",
        "report": doc_dir / f"{scenario}-report.md",
    }

    complete = complete_records(config)
    observed, mask = inject_missingness(complete, config)
    blocks = derive_blocks(observed, config)
    worlds = enumerate_worlds(observed, blocks, config)
    direct_model, tid_model, tid_rows = generate_models(observed, blocks, config)

    names = [attribute["name"] for attribute in attributes(config)]
    write_csv(paths["complete"], complete, names)
    write_csv(paths["observed"], observed, names)
    write_csv(paths["mask"], mask, list(mask[0]))
    block_fields = ["block_id", "candidate_id"] + names + ["probability"]
    write_csv(paths["blocks"], blocks, block_fields)
    world_rows = [{"world_id": world["world_id"],
                   "selected_completions": ";".join(
                       f"{candidate['block_id']}:{candidate['candidate_id']}"
                       for candidate in world["selected"]),
                   "probability": world["probability"], "query": world["query"]}
                  for world in worlds]
    write_csv(paths["worlds"], world_rows,
              ["world_id", "selected_completions", "probability", "query"])
    write_csv(paths["tid"], tid_rows,
              ["block_id", "candidate_id", "bid_probability", "tid_probability", "tid_odds"])
    paths["direct_model"].write_text(direct_model, encoding="utf-8")
    paths["tid_model"].write_text(tid_model, encoding="utf-8")

    bid_result = tid_result = None
    if not args.skip_plingo:
        query_name = config["query"]["name"]
        bid_result = run_plingo(paths["direct_model"], None, paths["bid_log"], query_name)
        tid_result = run_plingo(paths["tid_model"], "problog", paths["tid_log"], query_name)
        oracle = sum(world["probability"] for world in worlds if world["query"])
        if bid_result is None or tid_result is None:
            raise RuntimeError("Plingo did not print the configured answer probability")
        if not (math.isclose(oracle, bid_result, abs_tol=5e-5) and
                math.isclose(oracle, tid_result, abs_tol=5e-5)):
            raise RuntimeError("oracle, BID, and TID probabilities disagree")

    report = create_report(config_path, config, complete, observed, mask, blocks,
                           worlds, tid_rows, bid_result, tid_result, paths)
    paths["report"].write_text(report, encoding="utf-8")
    print(f"scenario={scenario}")
    print(f"records={len(complete)}")
    print(f"uncertain_blocks={len({row['block_id'] for row in blocks})}")
    print(f"stable_models={len(worlds)}")
    print(f"query_probability={sum(w['probability'] for w in worlds if w['query']):.8f}")
    print(f"report={paths['report'].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
