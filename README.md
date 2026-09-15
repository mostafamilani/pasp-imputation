# PASP Imputation

This repository prototypes query answering over incomplete relational data whose
missing values are governed by a quantitative missingness graph.

The first scenario is documented in
[`docs/scenarios/mcar-single-missing.md`](docs/scenarios/mcar-single-missing.md).
It uses a three-attribute table, one potentially missing binary attribute, and
an MCAR mechanism.  The same query is evaluated in three ways:

1. explicit enumeration of BID possible worlds;
2. a direct BID encoding in Plingo;
3. independent TID choices conditioned on exactly one completion per block.

See the experiment README for the model and commands.

## Repository structure

```text
config/                 # Scenario configuration
data/                   # Scenario datasets and generated artifacts
models/                 # Scenario-specific PASP encodings
scripts/                # Shared generation and validation utilities
docs/scenarios/         # Scenario documentation
```
