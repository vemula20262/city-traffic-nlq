from pymongo import MongoClient, UpdateOne
from tqdm import tqdm
import re

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"

def fix_all_data():
    print("="*70)
    print("COMPLETE DATA CLEANUP")
    print("="*70)
    
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]
    
    total_docs = collection.count_documents({})
    print(f"\nTotal documents: {total_docs:,}")
    
    # ========================================================================
    # STEP 1: Fix LOCATION field (convert strings to GeoJSON)
    # ========================================================================
    print("\n" + "="*70)
    print("STEP 1: Fixing LOCATION field")
    print("="*70)
    
    # Find documents with bad LOCATION
    bad_location_query = {
        "$or": [
            {"LOCATION": {"$type": "string"}},  # String like "(0.0, 0.0)"
            {"LOCATION": {"$type": "int"}},     # Number
            {"LOCATION": {"$type": "double"}},  # Float
            {"LOCATION": {"$exists": False}},   # Missing
            {"LOCATION": None}                  # Null
        ]
    }
    
    bad_location_count = collection.count_documents(bad_location_query)
    print(f"Documents with bad LOCATION: {bad_location_count:,}")
    
    if bad_location_count > 0:
        print("Fixing LOCATION fields...")
        
        operations = []
        batch_size = 500
        processed = 0
        
        cursor = collection.find(bad_location_query, {"_id": 1, "LATITUDE": 1, "LONGITUDE": 1, "LOCATION": 1})
        
        for doc in tqdm(cursor, total=bad_location_count, desc="Converting"):
            try:
                lat = doc.get("LATITUDE")
                lon = doc.get("LONGITUDE")
                
                # Try to parse string LOCATION if it exists
                location = doc.get("LOCATION")
                if isinstance(location, str) and location:
                    # Parse "(40.7, -73.9)" format
                    match = re.match(r'\(([^,]+),\s*([^)]+)\)', location)
                    if match:
                        try:
                            lat = float(match.group(1))
                            lon = float(match.group(2))
                        except:
                            pass
                
                # Convert to float if needed
                if lat and not isinstance(lat, (int, float)):
                    try:
                        lat = float(lat)
                    except:
                        lat = None
                
                if lon and not isinstance(lon, (int, float)):
                    try:
                        lon = float(lon)
                    except:
                        lon = None
                
                # Validate coordinates (NYC bounds + exclude 0,0)
                if lat and lon:
                    if 40.0 <= lat <= 41.5 and -74.5 <= lon <= -73.5:
                        # Valid NYC coordinates
                        geojson = {
                            "type": "Point",
                            "coordinates": [float(lon), float(lat)]
                        }
                        operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"LOCATION": geojson}}))
                    else:
                        # Invalid coordinates (including 0,0)
                        operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"LOCATION": None}}))
                else:
                    # No valid coordinates
                    operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"LOCATION": None}}))
                
                if len(operations) >= batch_size:
                    collection.bulk_write(operations, ordered=False)
                    processed += len(operations)
                    operations = []
            
            except Exception as e:
                # Set to null on error
                operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"LOCATION": None}}))
        
        # Final batch
        if operations:
            collection.bulk_write(operations, ordered=False)
            processed += len(operations)
        
        print(f"✅ Fixed {processed:,} LOCATION fields")
    else:
        print("✅ All LOCATION fields are already GeoJSON")
    
    # Verify
    with_geojson = collection.count_documents({"LOCATION.type": "Point"})
    with_null = collection.count_documents({"LOCATION": None})
    print(f"\nResults:")
    print(f"   Valid GeoJSON: {with_geojson:,}")
    print(f"   Null locations: {with_null:,}")
    
    # ========================================================================
    # STEP 2: Clean COLLISION_ID issues
    # ========================================================================
    print("\n" + "="*70)
    print("STEP 2: Cleaning COLLISION_ID")
    print("="*70)
    
    # Delete documents with null/invalid COLLISION_ID
    null_query = {
        "$or": [
            {"COLLISION_ID": None},
            {"COLLISION_ID": ""},
            {"COLLISION_ID": {"$exists": False}}
        ]
    }
    
    null_count = collection.count_documents(null_query)
    if null_count > 0:
        print(f"Removing {null_count:,} documents with invalid COLLISION_ID...")
        result = collection.delete_many(null_query)
        print(f"✅ Deleted {result.deleted_count:,} documents")
    else:
        print("✅ No invalid COLLISION_ID found")
    
    # Remove duplicates
    print("Checking for duplicate COLLISION_IDs...")
    pipeline = [
        {"$group": {"_id": "$COLLISION_ID", "ids": {"$push": "$_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    
    dups = list(collection.aggregate(pipeline))
    if dups:
        print(f"Found {len(dups):,} duplicate COLLISION_ID groups")
        deleted = 0
        for dup in tqdm(dups, desc="Removing duplicates"):
            # Keep first, delete rest
            for extra_id in dup["ids"][1:]:
                collection.delete_one({"_id": extra_id})
                deleted += 1
        print(f"✅ Removed {deleted:,} duplicate documents")
    else:
        print("✅ No duplicates found")
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "="*70)
    print("CLEANUP SUMMARY")
    print("="*70)
    
    final_count = collection.count_documents({})
    with_geojson = collection.count_documents({"LOCATION.type": "Point"})
    with_geohash = collection.count_documents({"geohash": {"$exists": True}})
    
    print(f"\nFinal document count: {final_count:,}")
    print(f"With valid GeoJSON: {with_geojson:,} ({100*with_geojson/final_count:.1f}%)")
    print(f"With geohash: {with_geohash:,} ({100*with_geohash/final_count:.1f}%)")
    
    print("\n✅ Data cleanup complete! Ready for index creation.")
    print("\nNext step: python3 scripts/04_create_indexes.py")

if __name__ == "__main__":
    fix_all_data()
