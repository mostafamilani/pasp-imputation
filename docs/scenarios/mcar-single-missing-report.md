# Scenario report: `mcar-single-missing`

This file is generated from `config/mcar-single-missing.json` by
`scripts/run_scenario.py`.

## Query

The Boolean conjunctive query is:

```text
exists id: Person(id, b, yes)
```

The computed probability of a positive answer is **0.20000000**.

## Input and missingness

- Relation: `person(id, group, disease)`
- Complete-data source: `synthetic`
- Records: 6
- Missingness mechanism: `MCAR`
- Injected missing cells: 2
- Missing token: `na`

`complete.csv` is simulation ground truth and is not read during query inference.
The block probabilities below are computed from `observed.csv` and the configured
probability source. For this synthetic scenario, the supplied quantitative BN is
assumed known to inference.

### Complete table (evaluation only)

| id | group | disease |
|---|---|---|
| 1 | a | yes |
| 2 | a | no |
| 3 | a | yes |
| 4 | b | no |
| 5 | b | yes |
| 6 | b | no |

### Realized missingness mask

| id | missing_disease |
|---|---|
| 1 | 0 |
| 2 | 1 |
| 3 | 0 |
| 4 | 0 |
| 5 | 1 |
| 6 | 0 |

### Observed table

| id | group | disease |
|---|---|---|
| 1 | a | yes |
| 2 | a | na |
| 3 | a | yes |
| 4 | b | no |
| 5 | b | na |
| 6 | b | no |

## Derived BID

Each incomplete observed row is one block. Its alternatives are all joint row
completions consistent with the observed cells. Probabilities within every block
sum to one. Fully observed rows are deterministic singleton blocks and are emitted
as facts rather than listed here.

| block | candidate | id | group | disease | probability |
|---|---|---|---|---|---|
| 2 | 1 | 2 | a | yes | 0.70000000 |
| 2 | 2 | 2 | a | no | 0.30000000 |
| 5 | 1 | 5 | b | yes | 0.20000000 |
| 5 | 2 | 5 | b | no | 0.80000000 |

## Approach 1: direct BID and stable models

The generated Plingo model uses an exactly-one choice rule per uncertain block.
A stable model therefore selects one completed tuple from every block. Its weight
is the product of the selected categorical probabilities.

| world/stable model | selected completions | probability | query |
|---|---|---|---|
| 1 | `B2=c1, B5=c1` | 0.14000000 | true |
| 2 | `B2=c1, B5=c2` | 0.56000000 | false |
| 3 | `B2=c2, B5=c1` | 0.06000000 | true |
| 4 | `B2=c2, B5=c2` | 0.24000000 | false |

The positive stable-model probabilities sum to:

```text
P_BID(Q) = 0.20000000
```

Plingo reported `0.2`. Full output: `data/mcar-single-missing/logs/direct-bid.log`.

## Approach 2: independent TID plus block constraints

For each completion with categorical probability `p`, the independent tuple uses
`q = p/(1+p)`. Hence its odds `q/(1-q)` equal `p`.

| block | candidate | BID p | TID q | TID odds |
|---|---|---|---|---|
| 2 | 1 | 0.70000000 | 0.41176471 | 0.70000000 |
| 2 | 2 | 0.30000000 | 0.23076923 | 0.30000000 |
| 5 | 1 | 0.20000000 | 0.16666667 | 0.20000000 |
| 5 | 2 | 0.80000000 | 0.44444444 | 0.80000000 |

With 4 independent candidate tuples, the raw TID has
`2^4 = 16` assignments. Some choose zero or multiple
completions for a row and are invalid. Let `E` mean exactly one completion per
block. The raw independent masses are:

```text
P_TID(E)       = 0.209485503603
P_TID(Q and E) = 0.041897100721
P_TID(Q | E)   = 0.20000000
```

The at-most-one violations are positive conjunctive queries and can be represented
as hard denial MarkoViews of weight zero. The at-least-one condition is a coverage
constraint involving negation; the generated Plingo program expresses both parts
as hard ASP constraints. Thus this is an exact conditioned-TID implementation and
a reference for a future full MarkoView auxiliary-query translation, not a claim
that the constrained distribution itself remains tuple-independent.

Plingo reported `0.2`. Full output: `data/mcar-single-missing/logs/conditioned-tid.log`.

## Agreement

```text
explicit BID enumeration : 0.20000000
direct BID in Plingo      : 0.2
conditioned TID in Plingo : 0.2
```

All approaches agree within Plingo's five-decimal output precision.
