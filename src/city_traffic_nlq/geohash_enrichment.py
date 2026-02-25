from __future__ import annotations

from pymongo import UpdateOne
from tqdm import tqdm
import pygeohash as pgh

from .db import get_collection


def add_geohash() -> None:
    print("=" * 70)
    print("GEOHASH GENERATION")
    print("=" * 70)

    collection = get_collection()

    query = {
        "$and": [
            {"LATITUDE": {"$exists": True, "$ne": None}},
            {"LONGITUDE": {"$exists": True, "$ne": None}},
            {"geohash": {"$exists": False}},
        ]
    }

    total = collection.count_documents(query)
    print(f"\nDocuments needing geohash: {total:,}")

    if total == 0:
        print("✅ All documents already have geohash.")
        return

    operations: list[UpdateOne] = []
    batch_size = 500
    processed = 0

    cursor = collection.find(query, {"_id": 1, "LATITUDE": 1, "LONGITUDE": 1})

    for doc in tqdm(cursor, total=total, desc="Generating"):
        try:
            lat = float(doc["LATITUDE"])
            lon = float(doc["LONGITUDE"])
        except (TypeError, ValueError):
            continue

        if -90 <= lat <= 90 and -180 <= lon <= 180:
            operations.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {"geohash": pgh.encode(lat, lon, precision=6)}},
                )
            )

        if len(operations) >= batch_size:
            collection.bulk_write(operations, ordered=False)
            processed += len(operations)
            operations = []

    if operations:
        collection.bulk_write(operations, ordered=False)
        processed += len(operations)

    print(f"\n✅ Complete. Updated: {processed:,}")
