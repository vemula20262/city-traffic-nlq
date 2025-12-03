#!/usr/bin/env python3
"""Check database status"""
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"

def check_status():
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]
    
    print("="*70)
    print("DATABASE STATUS")
    print("="*70)
    
    total = collection.count_documents({})
    with_geohash = collection.count_documents({"geohash": {"$exists": True}})
    with_geojson = collection.count_documents({"LOCATION.type": "Point"})
    with_embedding = collection.count_documents({"crash_text_embedding": {"$exists": True}})
    
    print(f"\n📊 DOCUMENTS:")
    print(f"   Total: {total:,}")
    print(f"   With geohash: {with_geohash:,} ({100*with_geohash/total:.1f}%)")
    print(f"   With GeoJSON: {with_geojson:,} ({100*with_geojson/total:.1f}%)")
    print(f"   With embeddings: {with_embedding:,} ({100*with_embedding/total:.1f}%)")
    
    print(f"\n📋 INDEXES:")
    for idx in collection.list_indexes():
        unique = " [UNIQUE]" if idx.get('unique') else ""
        geo = " [GEO]" if '2dsphere' in str(idx.get('key')) else ""
        print(f"   ✅ {idx['name']}{unique}{geo}")
    
    stats = db.command("collStats", "traffic")
    print(f"\n💾 STORAGE:")
    print(f"   Data: {stats['size']/(1024**2):.1f} MB")
    print(f"   Indexes: {stats['totalIndexSize']/(1024**2):.1f} MB")
    print(f"   Total: {(stats['size']+stats['totalIndexSize'])/(1024**2):.1f} MB")
    
    print(f"\n🔄 REPLICA SET:")
    rs_status = client.admin.command("replSetGetStatus")
    for member in rs_status['members']:
        print(f"   {member['name']}: {member['stateStr']}")
    
    print("="*70)

if __name__ == "__main__":
    check_status()
