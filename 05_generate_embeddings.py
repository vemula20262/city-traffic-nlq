#!/usr/bin/env python3
"""Generate embeddings with checkpoint support"""
from fastembed import TextEmbedding
from pymongo import MongoClient, UpdateOne
from bson import ObjectId
from tqdm import tqdm
import json
import os
import time
import argparse
from datetime import datetime

MONGO_URI = "mongodb://localhost:27017/?replicaSet=rs0"
CHECKPOINT_FILE = "/home/ubuntu/logs/embedding_checkpoint.json"
BATCH_SIZE = 500

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {"processed": 0, "last_id": None}

def save_checkpoint(checkpoint):
    checkpoint["last_updated"] = datetime.now().isoformat()
    # Convert ObjectId to string for JSON serialization
    if "last_id" in checkpoint and checkpoint["last_id"]:
        if not isinstance(checkpoint["last_id"], str):
            checkpoint["last_id"] = str(checkpoint["last_id"])
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2)

def create_crash_text(doc):
    parts = []
    for i in range(1, 6):
        factor = doc.get(f"CONTRIBUTING FACTOR VEHICLE {i}")
        if factor and str(factor) not in ["", "None", "Unspecified"]:
            parts.append(f"contributing factor: {factor}")
    for i in range(1, 6):
        vehicle = doc.get(f"VEHICLE TYPE CODE {i}")
        if vehicle and str(vehicle) not in ["", "None"]:
            parts.append(f"vehicle: {vehicle}")
    if doc.get("BOROUGH"):
        parts.append(f"borough: {doc['BOROUGH']}")
    if doc.get("ON STREET NAME"):
        parts.append(f"street: {doc['ON STREET NAME']}")
    injured = int(doc.get("NUMBER OF PERSONS INJURED", 0) or 0)
    killed = int(doc.get("NUMBER OF PERSONS KILLED", 0) or 0)
    if killed > 0:
        parts.append("fatal crash")
    elif injured > 0:
        parts.append(f"injury crash with {injured} injured")
    else:
        parts.append("property damage only")
    return " | ".join(parts) if parts else "traffic collision"

def generate_embeddings(limit=50000):
    print("="*70)
    print("EMBEDDING GENERATION")
    print("="*70)
    
    print("\nLoading FastEmbed model...")
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    print("✅ Model loaded!")
    
    client = MongoClient(MONGO_URI)
    db = client["traffic"]
    collection = db["traffic"]
    
    checkpoint = load_checkpoint()
    processed = checkpoint["processed"]
    
    print(f"\nTarget: {limit:,}")
    print(f"Already processed: {processed:,}")
    print(f"Remaining: {limit - processed:,}")
    
    if processed >= limit:
        print("✅ Target reached!")
        return
    
    query = {"$or": [{"crash_text_embedding": {"$exists": False}}, {"crash_text_embedding": None}]}
    if checkpoint.get("last_id"):
        # Convert string back to ObjectId for query
        last_id = checkpoint["last_id"]
        if isinstance(last_id, str):
            last_id = ObjectId(last_id)
        query["_id"] = {"$gt": last_id}
    
    remaining = limit - processed
    cursor = collection.find(query).sort("_id", 1).limit(remaining)
    
    batch_texts = []
    batch_ids = []
    start_time = time.time()
    
    for doc in tqdm(cursor, total=remaining, desc="Processing"):
        text = create_crash_text(doc)
        batch_texts.append(text)
        batch_ids.append(doc["_id"])
        
        if len(batch_texts) >= BATCH_SIZE:
            embeddings = list(model.embed(batch_texts))
            operations = [UpdateOne({"_id": doc_id}, {"$set": {"crash_text_embedding": emb.tolist(), "crash_text": txt}}) 
                         for doc_id, emb, txt in zip(batch_ids, embeddings, batch_texts)]
            collection.bulk_write(operations, ordered=False)
            processed += len(batch_ids)
            save_checkpoint({"processed": processed, "last_id": batch_ids[-1]})
            batch_texts = []
            batch_ids = []
    
    if batch_texts:
        embeddings = list(model.embed(batch_texts))
        operations = [UpdateOne({"_id": doc_id}, {"$set": {"crash_text_embedding": emb.tolist(), "crash_text": txt}}) 
                     for doc_id, emb, txt in zip(batch_ids, embeddings, batch_texts)]
        collection.bulk_write(operations, ordered=False)
        processed += len(batch_ids)
        save_checkpoint({"processed": processed, "last_id": batch_ids[-1]})
    
    elapsed = time.time() - start_time
    print(f"\n✅ Complete! Processed: {processed:,}")
    print(f"Time: {elapsed/60:.1f} min | Rate: {processed/elapsed:.1f} docs/sec")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50000)
    args = parser.parse_args()
    generate_embeddings(args.limit)
