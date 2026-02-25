from __future__ import annotations

from pymongo import MongoClient

from .config import settings


def get_client() -> MongoClient:
    return MongoClient(settings.mongo_uri)


def get_collection():
    client = get_client()
    return client[settings.database_name][settings.collection_name]
