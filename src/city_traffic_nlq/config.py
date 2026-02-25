from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/?replicaSet=rs0")
    database_name: str = os.getenv("MONGO_DATABASE", "traffic")
    collection_name: str = os.getenv("MONGO_COLLECTION", "traffic")
    csv_file: str = os.getenv("CSV_FILE", "./data/Motor_Vehicle_Collisions_Crashes.csv")
    checkpoint_file: str = os.getenv("EMBEDDING_CHECKPOINT", "./logs/embedding_checkpoint.json")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "500"))

    @property
    def csv_path(self) -> Path:
        return Path(self.csv_file).expanduser().resolve()

    @property
    def checkpoint_path(self) -> Path:
        return Path(self.checkpoint_file).expanduser().resolve()


settings = Settings()
