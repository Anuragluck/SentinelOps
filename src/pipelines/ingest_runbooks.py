"""Load local markdown runbooks and optionally persist chunk metadata to Postgres."""
import argparse
import os
from pathlib import Path

from src.tools.hybrid_rag import Chunk, HybridRetriever, split_document


def load_gcs_markdown(bucket_name: str, prefix: str) -> list[Chunk]:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError("Install sentinelops[cloud] to read Google Cloud Storage") from exc
    client = storage.Client()
    chunks = []
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        if not blob.name.lower().endswith(".md"):
            continue
        text = blob.download_as_text(encoding="utf-8")
        for index, content in enumerate(split_document(text)):
            chunks.append(Chunk(f"{Path(blob.name).stem}#{index}", content, blob.name,
                                {"gcs_bucket": bucket_name, "gcs_object": blob.name}))
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default="evals/dataset/runbooks")
    parser.add_argument("--database-url")
    parser.add_argument("--gcs-bucket", default=os.getenv("GCS_RUNBOOK_BUCKET"))
    parser.add_argument("--gcs-prefix", default="")
    args = parser.parse_args()
    retriever = HybridRetriever.from_directory(args.directory, args.database_url)
    chunks = list(retriever.chunks)
    if args.gcs_bucket:
        chunks.extend(load_gcs_markdown(args.gcs_bucket, args.gcs_prefix))
    retriever.chunks = chunks
    print(f"Loaded {len(chunks)} chunks")
    if args.database_url or os.getenv("DATABASE_URL"):
        print(f"Indexed {retriever.index()} chunks into pgvector")
    else:
        print("Set DATABASE_URL to persist embeddings to PostgreSQL/pgvector")


if __name__ == "__main__":
    main()
