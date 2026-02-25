#!/usr/bin/env python3
"""Import NYC crash data from CSV to MongoDB."""

from city_traffic_nlq.import_data import import_csv


if __name__ == "__main__":
    import_csv()
