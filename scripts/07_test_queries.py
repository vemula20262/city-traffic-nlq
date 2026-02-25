#!/usr/bin/env python3
"""Run a few benchmark sanity queries against MongoDB."""

from city_traffic_nlq.query_tests import test_queries


if __name__ == "__main__":
    test_queries()
