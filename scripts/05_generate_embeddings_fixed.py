#!/usr/bin/env python3
"""Compatibility entrypoint for embedding generation."""

import argparse

from city_traffic_nlq.embeddings import generate_embeddings


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max docs for this session")
    arguments = parser.parse_args()
    generate_embeddings(arguments.limit)
