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
config/<scenario>.json   Experiment, schema, generation, and missingness
data/<scenario>/         Complete/observed data, BID blocks, and answers
models/<scenario>/       Reusable direct and MarkoView Plingo bases
queries/<scenario>.json  Reusable batches of Boolean conjunctive queries
scripts/                 Data preparation and query-answering tools
docs/scenarios/          Additional scenario-specific explanation
papers/                   Local references; ignored by Git
```

The working example is `mcar-single-missing`. Its full configuration is
[`config/mcar-single-missing.json`](config/mcar-single-missing.json).

## Legacy all-in-one scenario runner

The original end-to-end entry point remains available for compatibility and uses
the first query in `queries/<scenario>.json`:

```bash
python3 scripts/run_scenario.py config/mcar-single-missing.json
```

It generates `complete.csv`, `missingness-mask.csv`, `observed.csv`, `blocks.csv`, `stable-models.csv`, `tid-tuples.csv`, both Plingo models, full solver logs, and `docs/scenarios/<scenario>-report.md`. It also checks that explicit BID enumeration, direct BID Plingo inference, and conditioned-TID Plingo inference agree. For normal use, prefer the separate generation, missingness, preparation, and QA commands documented below.

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
| `missingness` | Missingness BN nodes, probabilities, and missing-value token. |
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
  "number_of_records": 6
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

When `sampling` is omitted, every modeled attribute is sampled IID from the
Bayesian network. This is the default used by the example.

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

The `missingness` section is a Bayesian network for missingness indicators:

```json
"missingness": {
  "missing_token": "na",
  "nodes": [
    {
      "name": "missing_disease",
      "attribute": "disease",
      "parents": [],
      "distribution": {"missing": 0.35, "observed": 0.65}
    }
  ]
}
```

It uses the same `parents`, `distribution`, and `conditional_distribution`
vocabulary as the complete-data BN. Nodes are topologically ordered and may
depend on data attributes or earlier missingness nodes. `attribute` identifies the value to mask.
An empty `parents` list makes this node MCAR; observed parents imply MAR, while
dependence on a possibly missing value implies MNAR. The classification is
inferred rather than stored. For each complete row, the generator draws the
indicator and replaces the configured attribute with `missing_token` when the
outcome is `missing`. The complete output is never modified.

## Run data preparation in two stages

Install dependencies from the repository root:

```bash
python3 -m pip install -r requirements.txt
```

### 1. Generate complete data

```bash
python3 scripts/generate_complete.py config/mcar-single-missing.json
```

This command reads the relation, dataset, generation BN, complete-data seed, and
output path from the experiment file. For `dataset.source = "synthetic"`, it
samples the configured number of IID records. For `dataset.source = "csv"`, it
validates and copies the supplied dataset. It writes only `files.complete`; it
does not inject missingness.

### 2. Inject missingness

```bash
python3 scripts/inject_missingness.py config/mcar-single-missing.json
```

This command reads `files.complete`, samples the missingness BN using
`sampling_seeds.missingness`, and writes `files.observed` and
`files.missingness_mask`. It never regenerates or modifies the complete data.
Running it repeatedly with the same input, configuration, and seed produces the
same observed data and mask.

## Prepare query answering

Preparation is query-independent and should be run once after `observed.csv` or
the probabilistic model changes:

```bash
python3 scripts/prepare_qa.py config/mcar-single-missing.json
```

It computes completion probabilities and writes:

- `data/<scenario>/blocks.csv`: BID alternatives and their probabilities;
- `models/<scenario>/direct-base.lp`: query-independent direct BID encoding;
- `models/<scenario>/markoview-base.plp`: query-independent MarkoView/TID encoding;
- `data/<scenario>/markoview-tuples.csv`: BID probabilities, transformed TID
  probabilities, and odds;
- `models/<scenario>/qa-manifest.json`: paths consumed by the QA command.

No query is compiled during preparation. Run preparation again only when the
observed data, schema, generation model, missingness model, or inference settings
change. Adding or changing queries does not require it.

### MarkoView transformation

For a BID alternative with probability `p`, the MarkoView base creates an
independent TID tuple with:

```text
q = p / (1 + p)
odds(q) = q / (1 - q) = p
```

It then conditions on exactly one selected alternative per block. The
`at-most-one` constraints are zero-weight denial MarkoViews; an additional
coverage constraint excludes the empty-block world. Under this evidence, a
block alternative has probability `p` because its unnormalized weight is its
odds, `p`, and the BID probabilities in each block sum to one. Complete rows are
deterministic Plingo facts and therefore have probability one.

This is the conditional form of the reduction in
[`papers/MarkoViewsVLDB12.pdf`](papers/MarkoViewsVLDB12.pdf):
`P(Q) = P0(Q | not W)`. Plingo performs the exact weighted stable-model
calculation over the independent tuples and hard evidence.

The direct base instead uses a categorical choice rule:

```prolog
1 { chosen(Block,1); chosen(Block,2) } 1.
```

and assigns each selected alternative the log-weight `log(p)`.

## Define queries separately

Queries do not belong in the experiment config. Put one or more named Boolean
conjunctive queries in `queries/<scenario>.json`:

```json
{
  "queries": [
    {
      "name": "disease_in_group_b",
      "type": "boolean_conjunctive_query",
      "atoms": [
        {"relation": "person", "arguments": ["?id", "b", "yes"]}
      ]
    },
    {
      "name": "person_2_has_disease",
      "type": "boolean_conjunctive_query",
      "atoms": [
        {"relation": "person", "arguments": [2, "?group", "yes"]}
      ]
    }
  ]
}
```

Variables start with `?`. Reusing a variable across atoms represents a join.
The current command supports Boolean conjunctive queries; each answer is the
probability that the query is true.

## Answer queries

MarkoView is the default method:

```bash
python3 scripts/answer_queries.py \
  config/mcar-single-missing.json \
  queries/mcar-single-missing.json
```

Select a method explicitly with one of:

```bash
--method markoview
--method direct
--method both
```

For example, run both methods and verify their results agree:

```bash
python3 scripts/answer_queries.py \
  config/mcar-single-missing.json \
  queries/mcar-single-missing.json \
  --method both
```

The command prints probability and Plingo wall-clock runtime for every query-method pair, plus aggregate runtime per method, and writes all timing fields to `data/<scenario>/answers.json`. Timings depend on machine load and should be treated as benchmark observations, not fixed expected values. Solver
output for each query and method is retained under `data/<scenario>/logs/`. An
alternative answer path can be supplied with `--output`.

For the included query batch, the current prepared data produces:

```text
query                    method      probability
disease_in_group_b       direct      0.20000000
disease_in_group_b       markoview   0.20000000
person_2_has_disease     direct      0.70000000
person_2_has_disease     markoview   0.70000000
```

## MAR example with multiple missing attributes

[`config/mar-multiple-missing.json`](config/mar-multiple-missing.json) defines an
18-row relation with two attributes that may be missing:

```text
Person(id, group, disease, treatment)
```

The complete-data BN contains `group -> disease` and
`(group, disease) -> treatment`. The missingness BN contains:

```text
group -> missing_disease
(group, missing_disease) -> missing_treatment
```

This is MAR: missingness depends on the always-observed `group` and on a
missingness indicator, but never on an unobserved `disease` or `treatment`
value. Depending on `missing_disease` also allows the two missingness events to
be correlated. With the configured seed, rows 5, 6, 7, 9, 10, 16, and 17 have both
`disease` and `treatment` missing.

Run the complete workflow with:

```bash
python3 scripts/generate_complete.py config/mar-multiple-missing.json
python3 scripts/inject_missingness.py config/mar-multiple-missing.json
python3 scripts/prepare_qa.py config/mar-multiple-missing.json
python3 scripts/answer_queries.py \
  config/mar-multiple-missing.json \
  queries/mar-multiple-missing.json \
  --method both
```

Rows with two missing attributes receive a BID block containing the Cartesian
product of both domains. In this example that means four candidate completions
per such row. The included query batch produces:

```text
query                         method      probability   runtime_seconds
person_5_has_disease          direct      0.20000000    2.472829
person_5_has_disease          markoview   0.20000000    2.172548
person_5_treated_disease      direct      0.12000000    2.264319
person_5_treated_disease      markoview   0.12000000    2.076885
person_4_treated              direct      0.30000000    2.416162
person_4_treated              markoview   0.30000000    2.077031

method      total_runtime_seconds
direct      7.153311
markoview   6.326464
```
