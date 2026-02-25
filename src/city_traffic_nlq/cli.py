from __future__ import annotations

import argparse

from .data_cleanup import fix_all_data
from .embeddings import generate_embeddings
from .geohash_enrichment import add_geohash
from .import_data import import_csv
from .indexes import create_indexes
from .query_tests import test_queries
from .status import check_status


def main() -> None:
    parser = argparse.ArgumentParser(description="City Traffic NLQ data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import CSV into MongoDB")
    import_parser.add_argument("--no-confirm", action="store_true", help="Skip overwrite confirmation")

    subparsers.add_parser("geohash", help="Generate geohash for coordinate records")
    subparsers.add_parser("cleanup", help="Fix geo fields and deduplicate by COLLISION_ID")
    subparsers.add_parser("indexes", help="Create indexes")

    embedding_parser = subparsers.add_parser("embeddings", help="Generate text embeddings")
    embedding_parser.add_argument("--limit", type=int, default=None, help="Max docs for this run")

    subparsers.add_parser("status", help="Show pipeline status")
    subparsers.add_parser("test-queries", help="Run sample query benchmarks")

    args = parser.parse_args()

    if args.command == "import":
        import_csv(confirm_overwrite=not args.no_confirm)
    elif args.command == "geohash":
        add_geohash()
    elif args.command == "cleanup":
        fix_all_data()
    elif args.command == "indexes":
        create_indexes()
    elif args.command == "embeddings":
        generate_embeddings(limit=args.limit)
    elif args.command == "status":
        check_status()
    elif args.command == "test-queries":
        test_queries()


if __name__ == "__main__":
    main()
