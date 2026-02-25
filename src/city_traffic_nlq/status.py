from __future__ import annotations

from .db import get_client, get_collection


def check_status() -> None:
    collection = get_collection()
    client = get_client()

    print("=" * 70)
    print("DATABASE STATUS")
    print("=" * 70)

    total = collection.count_documents({})
    with_geohash = collection.count_documents({"geohash": {"$exists": True}})
    with_geojson = collection.count_documents({"LOCATION.type": "Point"})
    with_embedding = collection.count_documents({"crash_text_embedding": {"$exists": True}})

    print(f"Total docs: {total:,}")
    if total:
        print(f"With geohash: {with_geohash:,} ({100 * with_geohash / total:.1f}%)")
        print(f"With GeoJSON: {with_geojson:,} ({100 * with_geojson / total:.1f}%)")
        print(f"With embeddings: {with_embedding:,} ({100 * with_embedding / total:.1f}%)")

    print("\nIndexes:")
    for index in collection.list_indexes():
        print(f" - {index['name']}")

    db = client[collection.database.name]
    stats = db.command("collStats", collection.name)
    print(f"\nData size: {stats['size'] / (1024**2):.1f} MB")
    print(f"Index size: {stats['totalIndexSize'] / (1024**2):.1f} MB")
