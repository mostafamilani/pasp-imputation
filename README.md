# PASP Imputation

This repository prototypes query answering over incomplete relational data whose
missing values are governed by a quantitative missingness graph.

The first milestone is in [`experiments/mcar-single-missing`](experiments/mcar-single-missing).
It uses a three-attribute table, one potentially missing binary attribute, and
an MCAR mechanism.  The same query is evaluated in three ways:

1. explicit enumeration of BID possible worlds;
2. a direct BID encoding in Plingo;
3. independent TID choices conditioned on exactly one completion per block.

See the experiment README for the model and commands.

## Repository structure

```text
experiments/
└── mcar-single-missing/
    ├── config/   # Experiment and missingness configuration
    ├── data/     # Reproducible data artifacts
    ├── models/   # Plingo and ProbLog encodings
    └── scripts/  # Generation and validation utilities
```
