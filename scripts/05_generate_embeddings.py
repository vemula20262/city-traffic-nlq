#!/usr/bin/env python3
"""Generate embeddings with checkpoint support."""

import argparse

from city_traffic_nlq.embeddings import generate_embeddings


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    arguments = parser.parse_args()
    generate_embeddings(arguments.limit)
