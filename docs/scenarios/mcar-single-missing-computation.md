# MCAR single-missing computation walkthrough

## Question

The Boolean conjunctive query is

```text
Q := exists Id: Person(Id, b, yes)
```

In words: **Is there at least one person in group B who has the disease?**

The query mentions only the underlying relation `Person`. Missingness indicators
and block identifiers belong to the inference machinery, not to the user query.

## Observed data and BID

The six-row observed table is:

| id | group | disease |
|---:|:-----:|:-------:|
| 1 | a | yes |
| 2 | a | na |
| 3 | a | yes |
| 4 | b | no |
| 5 | b | na |
| 6 | b | no |

Under MCAR, missingness conveys no information about disease. The conditional
completion distribution is therefore the complete-data distribution for the
observed group. The two BID blocks are:

```text
B2 = { Person(2,a,yes): 0.7, Person(2,a,no): 0.3 }
B5 = { Person(5,b,yes): 0.2, Person(5,b,no): 0.8 }
```

The blocks are independent, and exactly one tuple is selected from each block.

The four observed rows are singleton certain blocks. They are omitted from the
choice tables below because they do not contribute uncertainty.

## Approach 1: direct BID in Plingo

The direct encoding uses an exactly-one rule for each block. Its four stable
models, probabilities, and query values are:

| Stable model's choices | Probability | Q |
|---|---:|:---:|
| `chosen(2,yes), chosen(5,yes)` | `0.7 * 0.2 = 0.14` | true |
| `chosen(2,yes), chosen(5,no)`  | `0.7 * 0.8 = 0.56` | false |
| `chosen(2,no), chosen(5,yes)`  | `0.3 * 0.2 = 0.06` | true |
| `chosen(2,no), chosen(5,no)`   | `0.3 * 0.8 = 0.24` | false |

The four probabilities sum to one. Summing the two positive stable models gives

```text
P_BID(Q) = 0.14 + 0.06 = 0.20.
```

## Approach 2: TID conditioned on valid blocks

The TID begins with four independent Boolean candidate tuples. A desired BID
probability `p` is converted to a Bernoulli probability

```text
q = p / (1 + p),  so that q / (1-q) = p.
```

Thus the independent TID is:

| Candidate tuple | BID p | TID q |
|---|---:|---:|
| `Person(2,a,yes)` | 0.7 | 7/17 |
| `Person(2,a,no)`  | 0.3 | 3/13 |
| `Person(5,b,yes)` | 0.2 | 1/6 |
| `Person(5,b,no)`  | 0.8 | 4/9 |

Before conditioning, these four independent variables generate 16 assignments,
including invalid cases with zero or two completions for a row. The hard
exactly-one conditions retain the same four choices as the BID.

For block 2, the unnormalized masses of its valid alternatives are

```text
yes only: (7/17)(1-3/13) = 70/221
no only:  (1-7/17)(3/13) = 30/221
```

After conditioning within the block, these are `0.7` and `0.3`. For block 5:

```text
yes only: (1/6)(1-4/9) = 5/54
no only:  (1-1/6)(4/9) = 20/54
```

After conditioning, these are `0.2` and `0.8`. Because the eligibility event
factorizes by block, the four conditioned stable-model probabilities are again
`0.14`, `0.56`, `0.06`, and `0.24`. Therefore,

```text
P_TID(Q | exactly one completion per block) = 0.20.
```

## Result

The explicit possible-world oracle, direct BID encoding, and conditioned-TID
encoding all compute the same positive-answer probability:

```text
P(Q) = 0.20.
```

This second encoding demonstrates independent tuple choices plus conditioning.
It is not yet Sucius full MarkoView-to-TID UCQ transformation: Plingo applies
the eligibility conditions as hard ASP constraints and normalizes the retained
stable models. A later milestone should implement the explicit transformed
query and compare it against this reference result.

The corresponding executable files are:

- `models/mcar-single-missing/direct-bid.lp`
- `models/mcar-single-missing/conditioned-tid.plp`
- `scripts/enumerate_worlds.py`
