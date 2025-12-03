#!/usr/bin/env python3
"""
PRODUCTION EMBEDDING GENERATION (Correct Resume Logic)
- Only processes documents WITHOUT embeddings
- Uses skip-offset checkpoint (auto-fix old checkpoints)
- Respects --limit flag
"""

from fastembed import TextEmbedding
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm
import json, os, time, socket
from datetime import datetime
import argparse

# Auto-detect private IP for replica set
private_ip = socket.gethostbyname(socket.gethostname())
MONGO_URI = f"mongodb://{private_ip}:27017/?replicaSet=rs0"
CHECKPOINT_FILE = "/home/ubuntu/logs/embedding_checkpoint.json"
BATCH_SIZE = 500

# -------------------------------------------------------------------
# LOAD CHECKPOINT (BACKWARD COMPATIBLE)
# -------------------------------------------------------------------
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                cp = json.load(f)

            # Auto-fix missing "skip" key
            if "skip" not in cp:
                print("⚠️  Old checkpoint detected — repairing to new format.")
                cp["skip"] = cp.get("processed", 0)

            if "processed" not in cp:
                cp["processed"] = 0

            return cp

        except Exception as e:
            print(f"⚠️  Failed to load checkpoint ({e}), creating new one.")
    
    return {"skip": 0, "processed": 0}

# -------------------------------------------------------------------
def save_checkpoint(cp):
    cp["updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(cp, f, indent=2)

# -------------------------------------------------------------------
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

    injured = int(float(doc.get("NUMBER OF PERSONS INJURED", 0) or 0))
    killed = int(float(doc.get("NUMBER OF PERSONS KILLED", 0) or 0))

    if killed > 0:
        parts.append("fatal crash")
    elif injured > 0:
        parts.append(f"injury crash with {injured} injured")
    else:
        parts.append("property damage only")

    return " | ".join(parts)

# -------------------------------------------------------------------
def generate_embeddings(limit=None):
    print("="*70)
    print("EMBEDDING GENERATION (RESUMABLE, SAFE)")
    print("="*70)

    print(f"\n📡 Connecting to MongoDB at {private_ip}:27017")
    
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    print("✅ Model loaded!")

    client = MongoClient(MONGO_URI)
    coll = client["traffic"]["traffic"]

    cp = load_checkpoint()
    skip = cp["skip"]
    processed = cp["processed"]

    print(f"\n📊 Resuming at skip={skip:,}, processed={processed:,}")

    missing_query = {
        "$or": [
            {"crash_text_embedding": {"$exists": False}},
            {"crash_text_embedding": None}
        ]
    }

    missing_total = coll.count_documents(missing_query)
    print(f"Missing embeddings: {missing_total:,}")

    target = min(limit, missing_total) if limit else missing_total
    print(f"Target this session: {target:,}")

    cursor = coll.find(missing_query).sort("_id", 1).skip(skip).limit(target)

    batch_docs, batch_ids = [], []
    start_time = time.time()

    for doc in tqdm(cursor, total=target, desc="Embedding"):
        text = create_crash_text(doc)
        batch_docs.append(text)
        batch_ids.append(doc["_id"])

        if len(batch_docs) >= BATCH_SIZE:
            embeddings = list(model.embed(batch_docs))

            ops = [
                UpdateOne({"_id": _id}, {"$set": {
                    "crash_text_embedding": emb.tolist(),
                    "crash_text": txt
                }})
                for _id, emb, txt in zip(batch_ids, embeddings, batch_docs)
            ]

            coll.bulk_write(ops, ordered=False)
            processed += len(batch_docs)
            skip += len(batch_docs)

            save_checkpoint({"skip": skip, "processed": processed})

            batch_docs, batch_ids = [], []

    if batch_docs:
        embeddings = list(model.embed(batch_docs))
        ops = [
            UpdateOne({"_id": _id}, {"$set": {
                "crash_text_embedding": emb.tolist(),
                "crash_text": txt
            }})
            for _id, emb, txt in zip(batch_ids, embeddings, batch_docs)
        ]
        coll.bulk_write(ops, ordered=False)
        processed += len(batch_docs)
        skip += len(batch_docs)
        save_checkpoint({"skip": skip, "processed": processed})

    elapsed = time.time() - start_time

    final_count = coll.count_documents({"crash_text_embedding": {"$exists": True}})

    print("\n" + "="*70)
    print("✅ EMBEDDING GENERATION COMPLETE")
    print("="*70)
    print(f"Processed this session: {processed:,}")
    print(f"Total embeddings now: {final_count:,}")
    print(f"Coverage: {100*final_count/2210190:.2f}%")
    print(f"Elapsed: {elapsed/60:.1f} min ({processed/elapsed:.1f} docs/sec)")
    print(f"Checkpoint: skip={skip:,}")
    print("="*70)

# -------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Max docs for this session")
    args = parser.parse_args()
    generate_embeddings(args.limit)
