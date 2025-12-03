#!/usr/bin/env python3
"""Import NYC crash data from CSV to MongoDB"""
from pymongo import MongoClient
import csv
from tqdm import tqdm
import sys

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"
CSV_FILE = "/home/ubuntu/data/Motor_Vehicle_Collisions_Crashes.csv"

def import_csv():
    print("="*70)
    print("IMPORTING NYC CRASH DATA")
    print("="*70)
    
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]
    
    # Check existing
    existing = collection.count_documents({})
    print(f"\nExisting documents: {existing:,}")
    
    if existing > 0:
        response = input("Database has data. Continue? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Count lines
    print(f"\nCounting lines in {CSV_FILE}...")
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        total = sum(1 for _ in f) - 1
    
    print(f"Total records: {total:,}")
    
    # Import
    batch = []
    batch_size = 1000
    imported = 0
    
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in tqdm(reader, total=total, desc="Importing"):
            try:
                doc = {k: v for k, v in row.items() if v}
                
                # Convert numbers
                for field in ["NUMBER OF PERSONS INJURED", "NUMBER OF PERSONS KILLED",
                            "NUMBER OF PEDESTRIANS INJURED", "NUMBER OF PEDESTRIANS KILLED",
                            "NUMBER OF CYCLIST INJURED", "NUMBER OF CYCLIST KILLED",
                            "NUMBER OF MOTORIST INJURED", "NUMBER OF MOTORIST KILLED"]:
                    if field in doc:
                        try:
                            doc[field] = int(float(doc[field]))
                        except:
                            doc[field] = 0
                
                if "COLLISION_ID" in doc:
                    try:
                        doc["COLLISION_ID"] = int(doc["COLLISION_ID"])
                    except:
                        pass
                
                if "LATITUDE" in doc and doc["LATITUDE"]:
                    try:
                        doc["LATITUDE"] = float(doc["LATITUDE"])
                    except:
                        doc["LATITUDE"] = None
                
                if "LONGITUDE" in doc and doc["LONGITUDE"]:
                    try:
                        doc["LONGITUDE"] = float(doc["LONGITUDE"])
                    except:
                        doc["LONGITUDE"] = None
                
                batch.append(doc)
                
                if len(batch) >= batch_size:
                    collection.insert_many(batch, ordered=False)
                    imported += len(batch)
                    batch = []
            except:
                continue
        
        if batch:
            collection.insert_many(batch, ordered=False)
            imported += len(batch)
    
    print(f"\n✅ Import complete! Imported: {imported:,}")
    print(f"Total in database: {collection.count_documents({}):,}")

if __name__ == "__main__":
    import_csv()
