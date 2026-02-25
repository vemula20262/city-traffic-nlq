from __future__ import annotations

import json
import time
from datetime import datetime

from fastembed import TextEmbedding
from pymongo import UpdateOne
from tqdm import tqdm

from .config import settings
from .db import get_collection
from .text_builder import create_crash_text


def _load_checkpoint() -> dict:
    if settings.checkpoint_path.exists():
        try:
            return json.loads(settings.checkpoint_path.read_text())
        except json.JSONDecodeError:
            return {"skip": 0, "processed": 0}
    return {"skip": 0, "processed": 0}


def _save_checkpoint(checkpoint: dict) -> None:
    checkpoint["updated"] = datetime.now().isoformat()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    settings.checkpoint_path.write_text(json.dumps(checkpoint, indent=2))


def generate_embeddings(limit: int | None = None) -> None:
    print("=" * 70)
    print("EMBEDDING GENERATION")
    print("=" * 70)

    model = TextEmbedding(model_name=settings.embedding_model)
    print(f"✅ Model loaded: {settings.embedding_model}")

    collection = get_collection()
    checkpoint = _load_checkpoint()
    skip = int(checkpoint.get("skip", 0))
    processed = int(checkpoint.get("processed", 0))

    missing_query = {
        "$or": [
            {"crash_text_embedding": {"$exists": False}},
            {"crash_text_embedding": None},
        ]
    }

    missing_total = collection.count_documents(missing_query)
    target = min(limit, missing_total) if limit else missing_total

    print(f"Missing embeddings: {missing_total:,}")
    print(f"Resuming from skip={skip:,}")
    print(f"Target this run: {target:,}")

    cursor = collection.find(missing_query).sort("_id", 1).skip(skip).limit(target)

    batch_ids: list = []
    batch_texts: list[str] = []
    start_time = time.time()

    for doc in tqdm(cursor, total=target, desc="Embedding"):
        batch_ids.append(doc["_id"])
        batch_texts.append(create_crash_text(doc))

        if len(batch_texts) >= settings.embedding_batch_size:
            _flush_batch(collection, model, batch_ids, batch_texts)
            processed += len(batch_texts)
            skip += len(batch_texts)
            _save_checkpoint({"skip": skip, "processed": processed})
            batch_ids, batch_texts = [], []

    if batch_texts:
        _flush_batch(collection, model, batch_ids, batch_texts)
        processed += len(batch_texts)
        skip += len(batch_texts)
        _save_checkpoint({"skip": skip, "processed": processed})

    elapsed = max(time.time() - start_time, 1e-6)
    print(f"\n✅ Embedding complete. Session processed: {processed:,}")
    print(f"Elapsed: {elapsed / 60:.1f} min | Rate: {processed / elapsed:.1f} docs/sec")


def _flush_batch(collection, model, batch_ids, batch_texts) -> None:
    vectors = list(model.embed(batch_texts))
    ops = [
        UpdateOne(
            {"_id": doc_id},
            {"$set": {"crash_text": text, "crash_text_embedding": vector.tolist()}},
        )
        for doc_id, text, vector in zip(batch_ids, batch_texts, vectors)
    ]
    collection.bulk_write(ops, ordered=False)
