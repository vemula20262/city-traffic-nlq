from __future__ import annotations

import csv

from tqdm import tqdm

from .config import settings
from .db import get_collection


_NUMERIC_FIELDS = [
    "NUMBER OF PERSONS INJURED",
    "NUMBER OF PERSONS KILLED",
    "NUMBER OF PEDESTRIANS INJURED",
    "NUMBER OF PEDESTRIANS KILLED",
    "NUMBER OF CYCLIST INJURED",
    "NUMBER OF CYCLIST KILLED",
    "NUMBER OF MOTORIST INJURED",
    "NUMBER OF MOTORIST KILLED",
]


def import_csv(confirm_overwrite: bool = True) -> None:
    print("=" * 70)
    print("IMPORTING NYC CRASH DATA")
    print("=" * 70)

    collection = get_collection()
    existing = collection.count_documents({})
    print(f"\nExisting documents: {existing:,}")

    if confirm_overwrite and existing > 0:
        response = input("Database has data. Continue? (y/n): ").strip().lower()
        if response != "y":
            print("Import cancelled.")
            return

    if not settings.csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {settings.csv_path}")

    with settings.csv_path.open("r", encoding="utf-8") as handle:
        total = sum(1 for _ in handle) - 1

    print(f"\nSource file: {settings.csv_path}")
    print(f"Total records: {total:,}")

    imported = 0
    batch: list[dict] = []
    batch_size = 1_000

    with settings.csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in tqdm(reader, total=total, desc="Importing"):
            doc = {key: value for key, value in row.items() if value not in (None, "")}

            for field in _NUMERIC_FIELDS:
                if field in doc:
                    try:
                        doc[field] = int(float(doc[field]))
                    except (TypeError, ValueError):
                        doc[field] = 0

            if "COLLISION_ID" in doc:
                try:
                    doc["COLLISION_ID"] = int(doc["COLLISION_ID"])
                except (TypeError, ValueError):
                    pass

            for coordinate in ("LATITUDE", "LONGITUDE"):
                if coordinate in doc:
                    try:
                        doc[coordinate] = float(doc[coordinate])
                    except (TypeError, ValueError):
                        doc[coordinate] = None

            batch.append(doc)
            if len(batch) >= batch_size:
                collection.insert_many(batch, ordered=False)
                imported += len(batch)
                batch = []

    if batch:
        collection.insert_many(batch, ordered=False)
        imported += len(batch)

    print(f"\n✅ Import complete. Imported: {imported:,}")
    print(f"Total in database: {collection.count_documents({}):,}")
