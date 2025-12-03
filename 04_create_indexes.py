#!/usr/bin/env python3
"""Create all indexes with correct naming"""
from pymongo import MongoClient, ASCENDING, DESCENDING
import time

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"

def create_indexes():
    print("="*70)
    print("INDEX CREATION")
    print("="*70)

    # CONNECT
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]

    # 1. Compound shard key
    print("\n1. Compound shard key index...")
    try:
        start = time.time()
        collection.create_index(
            [("geohash", ASCENDING), ("CRASH DATE", ASCENDING)],
            name="idx_shard_key_geohash_date"
        )
        print(f"   ✅ Created in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # 2. Temporal index
    print("\n2. Temporal index...")
    try:
        start = time.time()
        collection.create_index(
            [("CRASH DATE", DESCENDING)],
            name="idx_crash_date_desc"
        )
        print(f"   ✅ Created in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # 3. Unique COLLISION_ID
    print("\n3. Unique COLLISION_ID index...")

    try:
        pipeline = [
            {"$group": {"_id": "$COLLISION_ID", "docs": {"$push": "$_id"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}}
        ]
        dups = list(collection.aggregate(pipeline))
        for d in dups:
            collection.delete_many({"_id": {"$in": d["docs"][1:]}})

        if dups:
            print(f"   Removed {len(dups)} duplicates")

        start = time.time()
        collection.create_index(
            [("COLLISION_ID", ASCENDING)],
            name="idx_collision_id_unique",
            unique=True,
            sparse=True
        )
        print(f"   ✅ Created in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # 4. Borough index
    print("\n4. Borough index...")
    try:
        start = time.time()
        collection.create_index(
            [("BOROUGH", ASCENDING)],
            name="idx_borough"
        )
        print(f"   ✅ Created in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # 5. Geospatial 2dsphere index
    print("\n5. 2dsphere index...")

    try:
        collection.drop_index("idx_location_2dsphere")
    except:
        pass

    start = time.time()
    collection.create_index(
        [("LOCATION", "2dsphere")],
        name="idx_location_2dsphere"
    )
    print(f"   ✅ Created in {time.time() - start:.2f}s")

    # Summary
    print("\n" + "="*70)
    print("INDEX SUMMARY")
    print("="*70)
    for idx in collection.list_indexes():
        print(f"   • {idx['name']}   {idx['key']}")

    stats = db.command("collStats", "traffic")
    print(f"\nIndex size: {stats['totalIndexSize']/(1024**2):.2f} MB")
    print(f"Data size: {stats['size']/(1024**2):.2f} MB")

if __name__ == "__main__":
    create_indexes()
