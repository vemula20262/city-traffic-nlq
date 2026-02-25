from __future__ import annotations

import re

from pymongo import UpdateOne
from tqdm import tqdm

from .db import get_collection


def _to_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fix_all_data() -> None:
    print("=" * 70)
    print("COMPLETE DATA CLEANUP")
    print("=" * 70)

    collection = get_collection()

    total_docs = collection.count_documents({})
    print(f"\nTotal documents: {total_docs:,}")

    bad_location_query = {
        "$or": [
            {"LOCATION": {"$type": "string"}},
            {"LOCATION": {"$type": "int"}},
            {"LOCATION": {"$type": "double"}},
            {"LOCATION": {"$exists": False}},
            {"LOCATION": None},
        ]
    }

    bad_location_count = collection.count_documents(bad_location_query)
    print(f"Documents with bad LOCATION: {bad_location_count:,}")

    if bad_location_count > 0:
        operations: list[UpdateOne] = []
        cursor = collection.find(
            bad_location_query,
            {"_id": 1, "LATITUDE": 1, "LONGITUDE": 1, "LOCATION": 1},
        )

        for doc in tqdm(cursor, total=bad_location_count, desc="Fixing LOCATION"):
            lat = _to_float(doc.get("LATITUDE"))
            lon = _to_float(doc.get("LONGITUDE"))

            location = doc.get("LOCATION")
            if isinstance(location, str):
                match = re.match(r"\(([^,]+),\s*([^)]+)\)", location)
                if match:
                    lat = _to_float(match.group(1))
                    lon = _to_float(match.group(2))

            if lat is not None and lon is not None and 40.0 <= lat <= 41.5 and -74.5 <= lon <= -73.5:
                value = {"type": "Point", "coordinates": [lon, lat]}
            else:
                value = None

            operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"LOCATION": value}}))

            if len(operations) >= 500:
                collection.bulk_write(operations, ordered=False)
                operations = []

        if operations:
            collection.bulk_write(operations, ordered=False)

    null_query = {
        "$or": [
            {"COLLISION_ID": None},
            {"COLLISION_ID": ""},
            {"COLLISION_ID": {"$exists": False}},
        ]
    }
    deleted_invalid = collection.delete_many(null_query).deleted_count

    pipeline = [
        {"$group": {"_id": "$COLLISION_ID", "ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]
    duplicates = list(collection.aggregate(pipeline))

    removed_dups = 0
    for group in tqdm(duplicates, desc="Removing duplicates"):
        ids = group.get("ids", [])[1:]
        if ids:
            removed_dups += collection.delete_many({"_id": {"$in": ids}}).deleted_count

    final_count = collection.count_documents({})
    with_geojson = collection.count_documents({"LOCATION.type": "Point"})

    print("\n✅ Data cleanup complete")
    print(f"Removed invalid COLLISION_ID docs: {deleted_invalid:,}")
    print(f"Removed duplicate docs: {removed_dups:,}")
    print(f"Final docs: {final_count:,}")
    print(f"Valid GeoJSON docs: {with_geojson:,}")
