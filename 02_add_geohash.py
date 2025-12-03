#!/usr/bin/env python3
"""Add geohash to documents with coordinates"""
from pymongo import MongoClient, UpdateOne
import pygeohash as pgh
from tqdm import tqdm

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"

def add_geohash():
    print("="*70)
    print("GEOHASH GENERATION")
    print("="*70)
    
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]
    
    query = {
        "$and": [
            {"LATITUDE": {"$exists": True, "$ne": None}},
            {"LONGITUDE": {"$exists": True, "$ne": None}},
            {"geohash": {"$exists": False}}
        ]
    }
    
    total = collection.count_documents(query)
    print(f"\nDocuments needing geohash: {total:,}")
    
    if total == 0:
        print("✅ All documents have geohash!")
        return
    
    batch_size = 500
    operations = []
    processed = 0
    
    cursor = collection.find(query, {"_id": 1, "LATITUDE": 1, "LONGITUDE": 1})
    
    for doc in tqdm(cursor, total=total, desc="Generating"):
        try:
            lat = float(doc["LATITUDE"])
            lon = float(doc["LONGITUDE"])
            
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                geohash = pgh.encode(lat, lon, precision=6)
                operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"geohash": geohash}}))
                
                if len(operations) >= batch_size:
                    collection.bulk_write(operations, ordered=False)
                    processed += len(operations)
                    operations = []
        except:
            continue
    
    if operations:
        collection.bulk_write(operations, ordered=False)
        processed += len(operations)
    
    print(f"\n✅ Complete! Updated: {processed:,}")
    print(f"Total with geohash: {collection.count_documents({'geohash': {'$exists': True}}):,}")

if __name__ == "__main__":
    add_geohash()
