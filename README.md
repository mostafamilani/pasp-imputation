# PASP Imputation

PASP Imputation is a prototype for probabilistic conjunctive-query answering
over incomplete relational data. A probabilistic model describes the complete
data, a missingness model hides selected values, and each possible completion
of a missing row becomes an alternative in a block-independent-disjoint (BID)
database. Plingo then computes the probability that a Boolean conjunctive query
is true across those possible worlds.

The current scenario has one relation:

```text
Person(id, group, disease)
```

`id` and `group` are observed, while `disease` may be missing. The example uses
an MCAR mechanism, so observing that `disease` is missing does not change its
distribution given `group`.

## Repository structure

```text
config/<scenario>/       Experiment, schema, generation, missingness, and query
data/<scenario>/         Complete data, observed data, and derived BID blocks
models/<scenario>/       Plingo and ProbLog encodings
scripts/                 Data-generation, block-building, and checking tools
docs/scenarios/          Additional scenario-specific explanation
papers/                   Local references; ignored by Git
```

The working example is `mcar-single-missing`. Its full configuration is
[`config/mcar-single-missing/experiment.json`](config/mcar-single-missing/experiment.json).

## Configuration format

The experiment JSON is the single source for the data-generation and
missingness pipeline. Its top-level fields are:

| Field | Purpose |
| --- | --- |
| `experiment` | Scenario identifier. |
| `seed` | Fallback random seed. |
| `sampling_seeds` | Separate seeds for complete-data sampling and missingness injection. |
| `relation` | Relation name, ordered attributes, domains, and key. |
| `dataset` | Selects synthetic generation or an existing CSV. |
| `generation` | Bayesian network used to sample complete synthetic records. |
| `missingness` | Missingness graph, rules, probabilities, and missing-value token. |
| `query` | Boolean conjunctive query to evaluate. |
| `files` | Output paths, relative to the repository root. |

### Relation schema

Attributes must appear in CSV column order. Categorical attributes declare
their domains, and an attribute that can be hidden uses
`"may_be_missing": true`.

```json
"relation": {
  "name": "person",
  "attributes": [
    {"name": "id", "type": "integer"},
    {"name": "group", "type": "categorical", "domain": ["a", "b"]},
    {
      "name": "disease",
      "type": "categorical",
      "domain": ["yes", "no"],
      "may_be_missing": true
    }
  ],
  "key": ["id"]
}
```

### Synthetic input settings

Set `dataset.source` to `synthetic`, choose the number of records, and define a
Bayesian-network node for every generated non-key attribute. Nodes must be in
topological order: every parent must already have been assigned when its child
is sampled.

```json
"dataset": {
  "source": "synthetic",
  "number_of_records": 6,
  "sampling": {
    "method": "stratified",
    "attribute": "group",
    "counts": {"a": 3, "b": 3}
  }
},
"generation": {
  "model": "bayesian_network",
  "nodes": [
    {"name": "group", "parents": [], "distribution": {"a": 0.5, "b": 0.5}},
    {
      "name": "disease",
      "parents": ["group"],
      "conditional_distribution": {
        "group=a": {"yes": 0.7, "no": 0.3},
        "group=b": {"yes": 0.2, "no": 0.8}
      }
    }
  ]
}
```

Supported sampling methods are:

- `iid`: sample every modeled attribute from its distribution.
- `stratified`: fix counts for one attribute, then sample the remaining nodes.
  The counts must sum to `number_of_records`.

For reproducibility, `sampling_seeds.complete_data` controls complete-data
generation and `sampling_seeds.missingness` controls missingness injection.

### Existing CSV input

To inject missingness into an existing complete dataset instead, use:

```json
"dataset": {
  "source": "csv",
  "input": "data/mcar-single-missing/my-complete-data.csv"
}
```

The CSV header must exactly match the configured attribute order, and every
categorical value must belong to its declared domain. `number_of_records` and
synthetic sampling settings are not used in CSV mode.

### Missingness settings

The `missingness` section contains both the qualitative graph and quantitative
rules:

```json
"missingness": {
  "mechanism": "MCAR",
  "missing_token": "na",
  "variables": ["group", "disease", "missing_disease", "observed_disease"],
  "edges": [
    ["group", "disease"],
    ["disease", "observed_disease"],
    ["missing_disease", "observed_disease"]
  ],
  "rules": [
    {
      "attribute": "disease",
      "indicator": "missing_disease",
      "parents": [],
      "probability_missing": 0.35
    }
  ]
}
```

An empty `parents` list makes this rule MCAR. For each complete row, the
generator independently draws the missingness indicator. If it is true, the
configured attribute is replaced by `missing_token` in the observed output.
The complete output is never modified.

## Generate data and inject missingness

Install dependencies from the repository root:

```bash
python3 -m pip install -r requirements.txt
```

Generate `complete.csv` and `observed.csv` using the configured seeds:

```bash
python3 scripts/generate_data.py
```

The pipeline performs these steps:

1. Samples complete rows from the Bayesian network, or loads and validates the
   configured CSV.
2. Copies every complete row.
3. Samples each configured missingness rule using the missingness seed.
4. Replaces selected observed values with `na`.
5. Writes the paths configured in `files.complete` and `files.observed`.

Check that committed artifacts are reproducible without rewriting them:

```bash
python3 scripts/generate_data.py --check
```

Derive the BID alternatives for incomplete rows:

```bash
python3 scripts/build_blocks.py > data/mcar-single-missing/blocks.csv
```

Or verify the committed block file:

```bash
python3 scripts/build_blocks.py --check
```

In this example, rows 2 and 5 have missing disease values. Their BID blocks are
`{yes: 0.7, no: 0.3}` and `{yes: 0.2, no: 0.8}`.

## Specify a conjunctive query

The query input belongs in the `query` section of `experiment.json`:

```json
"query": {
  "name": "answer",
  "type": "boolean_conjunctive_query",
  "atoms": [
    {"relation": "person", "arguments": [2, "a", "yes"]},
    {"relation": "person", "arguments": [5, "b", "yes"]}
  ]
}
```

This represents the Boolean CQ:

```text
Person(2, a, yes) AND Person(5, b, yes)
```

The corresponding solver rule is currently written in each model file:

```prolog
answer :- person(2,a,yes), person(5,b,yes).
&query(answer).
```

When changing a query, update `query.atoms` and the `answer` rule in both
[`models/mcar-single-missing/direct-bid.lp`](models/mcar-single-missing/direct-bid.lp)
and
[`models/mcar-single-missing/conditioned-tid.plp`](models/mcar-single-missing/conditioned-tid.plp).
The configuration checker reads `query.atoms`, but the current prototype does
not yet generate the solver rule automatically.

The current implementation supports ground Boolean CQs: each atom must contain
concrete arguments, and the output is the probability that their conjunction is
true. Variable-bearing CQs and tuple-result enumeration are not yet generated
from the JSON format.

## Answer the query

There are three equivalent paths for the example query.

### Explicit possible-world oracle

```bash
python3 scripts/enumerate_worlds.py
```

This enumerates all four BID worlds and prints:

```text
total_probability=1.000000
query_probability=0.140000
```

This script is currently specialized to the example and acts as a small
independent correctness oracle.

### Direct BID encoding in Plingo

```bash
plingo \
  models/mcar-single-missing/direct-bid.lp
```

The model chooses exactly one completion per missing row and assigns each
choice the logarithm of its categorical probability. Expected output:

```text
answer: 0.14000
```

### Conditioned TID encoding in Plingo

```bash
plingo \
  --frontend=problog \
  models/mcar-single-missing/conditioned-tid.plp
```

This model begins with independent candidate tuples and conditions on exactly
one selected completion per block. It must produce the same result:

```text
answer: 0.14000
```

Run the end-to-end consistency check with:

```bash
python3 scripts/check_experiment.py
```

More details about the example are available in
[`docs/scenarios/mcar-single-missing.md`](docs/scenarios/mcar-single-missing.md).
