#!/usr/bin/env python3
"""Explicit possible-world oracle for the first MCAR/BID experiment."""

from itertools import product
from math import isclose


BLOCKS = {
    2: {"yes": 0.7, "no": 0.3},
    5: {"yes": 0.2, "no": 0.8},
}


def main() -> None:
    total_mass = 0.0
    query_mass = 0.0

    print("row_2,row_5,world_probability,query")
    for disease_2, disease_5 in product(BLOCKS[2], BLOCKS[5]):
        probability = BLOCKS[2][disease_2] * BLOCKS[5][disease_5]
        query = disease_2 == "yes" and disease_5 == "yes"
        total_mass += probability
        if query:
            query_mass += probability
        print(f"{disease_2},{disease_5},{probability:.6f},{str(query).lower()}")

    assert isclose(total_mass, 1.0)
    assert isclose(query_mass, 0.14)
    print(f"total_probability={total_mass:.6f}")
    print(f"query_probability={query_mass:.6f}")


if __name__ == "__main__":
    main()
