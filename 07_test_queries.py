#!/usr/bin/env python3
"""Test geospatial queries"""
from pymongo import MongoClient
import time

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"

def test_queries():
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]
    
    print("="*70)
    print("QUERY TESTS")
    print("="*70)
    
    # Test 1: Near Times Square
    print("\n[TEST 1] Crashes near Times Square (500m)")
    start = time.time()
    results = list(collection.find({
        "LOCATION": {
            "$nearSphere": {
                "$geometry": {"type": "Point", "coordinates": [-73.9855, 40.7580]},
                "$maxDistance": 500
            }
        }
    }).limit(5))
    print(f"✅ Found {len(results)} in {(time.time()-start)*1000:.2f}ms")
    
    # Test 2: Borough filter
    print("\n[TEST 2] Crashes in Manhattan")
    start = time.time()
    count = collection.count_documents({"BOROUGH": "MANHATTAN"})
    print(f"✅ Found {count:,} in {(time.time()-start)*1000:.2f}ms")
    
    # Test 3: Date range
    print("\n[TEST 3] Recent crashes (2024)")
    start = time.time()
    count = collection.count_documents({"CRASH DATE": {"$regex": "^.*/2024$"}})
    print(f"✅ Found {count:,} in {(time.time()-start)*1000:.2f}ms")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    test_queries()
