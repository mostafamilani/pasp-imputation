# Experiment 01: one missing attribute under MCAR

## Model

The schema is `Person(id, group, disease)`. `id` and `group` are fully
observed. `disease` is binary and may be missing.

The complete-data Bayesian network is:

```text
Group -> Disease     MissingDisease
             \          |
              \         v
               -> ObservedDisease
```

`MissingDisease` has no parents, so the mechanism is MCAR:

- `P(Disease=yes | Group=a) = 0.7`
- `P(Disease=yes | Group=b) = 0.2`
- `P(MissingDisease=1) = 0.35`

Under MCAR, observing that `disease` is missing provides no additional
information. Thus, for a missing row in group `g`:

```text
P(Disease=d | Group=g, ObservedDisease=na) = P(Disease=d | Group=g)
```

The committed sample was generated with seed 1. Rows 2 and 5 are missing, so
their BID blocks are `{yes: 0.7, no: 0.3}` and `{yes: 0.2, no: 0.8}`.

The Boolean conjunctive query is:

```text
Person(2,a,yes) AND Person(5,b,yes)
```

Its expected probability is `0.7 * 0.2 = 0.14`.

## Encodings

- `models/direct-bid.lp` generates exactly one completion per incomplete row and gives
  each selected completion its categorical log-weight.
- `models/conditioned-tid.plp` starts with independent Bernoulli candidate tuples.
  Their odds equal the desired BID probabilities. Hard evidence then conditions
  this TID on exactly one candidate per block.
- `scripts/enumerate_worlds.py` explicitly enumerates the four BID worlds and acts as a
  small independent oracle.

## Run

From the repository root:

```bash
PYTHONPATH=.vendor .vendor/bin/plingo \
  experiments/mcar-single-missing/models/direct-bid.lp

PYTHONPATH=.vendor .vendor/bin/plingo \
  --frontend=problog \
  experiments/mcar-single-missing/models/conditioned-tid.plp

python3 experiments/mcar-single-missing/scripts/enumerate_worlds.py
```

All three query probabilities should be `0.14`, modulo Plingo's printed
five-decimal rounding.


## Dataset sources

The person relation is only this experiment's configured example. The generator
uses the schema, domains, record count, and Bayesian-network nodes in
`config/experiment.json`.

For a synthetic dataset, set `dataset.source` to `synthetic`. The default
`iid` method samples every non-key attribute in topological node order from
the complete-data Bayesian network. This is the statistically natural method.
The example uses optional `stratified` sampling to guarantee three rows from
each group in a very small reproducible test.

To inject missingness into an existing complete CSV instead, use:

```json
"dataset": {
  "source": "csv",
  "input": "data/my-complete-data.csv"
}
```

In CSV mode no initial records are generated and `number_of_records` is not
used. The CSV is schema- and domain-validated, copied to the configured complete
artifact, and then the same missingness graph is applied. The missingness graph
is separate from the optional complete-data model: it controls which existing
values become `na`; the complete-data model controls synthetic sampling and
the posterior probabilities used later to construct BID blocks.
