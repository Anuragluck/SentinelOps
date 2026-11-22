"""Load local markdown runbooks and optionally persist chunk metadata to Postgres."""
import argparse
from pathlib import Path

from src.tools.hybrid_rag import HybridRetriever


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default="evals/dataset/runbooks")
    parser.add_argument("--database-url")
    args = parser.parse_args()
    retriever = HybridRetriever.from_directory(args.directory, args.database_url)
    print(f"Loaded {len(retriever.chunks)} chunks from {args.directory}")
    if args.database_url:
        print("Postgres persistence needs the optional pgvector backend configured; no rows were written.")


if __name__ == "__main__":
    main()
