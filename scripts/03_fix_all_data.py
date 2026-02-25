#!/usr/bin/env python3
"""Fix geo fields and ID consistency issues in MongoDB records."""

from city_traffic_nlq.data_cleanup import fix_all_data


if __name__ == "__main__":
    fix_all_data()
