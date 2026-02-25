#!/usr/bin/env python3
"""Create required MongoDB indexes for the pipeline."""

from city_traffic_nlq.indexes import create_indexes


if __name__ == "__main__":
    create_indexes()
