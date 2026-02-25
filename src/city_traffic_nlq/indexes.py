from __future__ import annotations

import time

from pymongo import ASCENDING, DESCENDING

from .db import get_collection


def create_indexes() -> None:
    print("=" * 70)
    print("INDEX CREATION")
    print("=" * 70)

    collection = get_collection()

    index_specs = [
        ([ ("geohash", ASCENDING), ("CRASH DATE", ASCENDING) ], "idx_shard_key_geohash_date", {}),
        ([ ("CRASH DATE", DESCENDING) ], "idx_crash_date_desc", {}),
        ([ ("COLLISION_ID", ASCENDING) ], "idx_collision_id_unique", {"unique": True, "sparse": True}),
        ([ ("BOROUGH", ASCENDING) ], "idx_borough", {}),
    ]

    for idx, (keys, name, kwargs) in enumerate(index_specs, start=1):
        print(f"\n{idx}. Creating {name}...")
        start = time.time()
        try:
            collection.create_index(keys, name=name, **kwargs)
            print(f"   ✅ Done in {time.time() - start:.2f}s")
        except Exception as error:
            print(f"   ⚠️ {error}")

    print("\n5. Creating idx_location_2dsphere...")
    try:
        collection.drop_index("idx_location_2dsphere")
    except Exception:
        pass
    start = time.time()
    collection.create_index([("LOCATION", "2dsphere")], name="idx_location_2dsphere")
    print(f"   ✅ Done in {time.time() - start:.2f}s")

    print("\nCurrent indexes:")
    for index in collection.list_indexes():
        print(f" - {index['name']}: {index['key']}")
