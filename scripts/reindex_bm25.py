#!/usr/bin/env python3
"""
Rebuild the OpenSearch chunk index using BM25-only documents (no embeddings).

This is a stop-gap solution so we can immediately search over the entire
arXiv corpus without waiting for embedding generation.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

# Make local modules importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Settings
from src.services.opensearch.index_config_hybrid import ARXIV_PAPERS_CHUNKS_MAPPING  # noqa: E402


def format_authors(authors: Any) -> str:
    if isinstance(authors, list):
        return ", ".join(authors)
    if isinstance(authors, str):
        return authors
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild BM25-only OpenSearch index from PostgreSQL.")
    parser.add_argument("--batch-size", type=int, default=500, help="Number of papers per batch.")
    parser.add_argument(
        "--reset-index",
        action="store_true",
        help="Delete and recreate the OpenSearch index before indexing.",
    )
    args = parser.parse_args()

    settings = Settings()
    index_name = f"{settings.opensearch.index_name}-{settings.opensearch.chunk_index_suffix}"

    # Connect to Postgres
    print("📊 Connecting to PostgreSQL...")
    conn = psycopg2.connect(settings.postgres_database_url)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM papers WHERE arxiv_id IS NOT NULL;")
    total_papers = cur.fetchone()[0]
    print(f"✅ Found {total_papers:,} arXiv papers")

    # Connect to OpenSearch
    print("\n🔍 Connecting to OpenSearch...")
    opensearch = OpenSearch(
        hosts=[settings.opensearch.host],
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )

    if args.reset_index and opensearch.indices.exists(index=index_name):
        print(f"🧹 Deleting existing index {index_name}")
        opensearch.indices.delete(index=index_name)

    if not opensearch.indices.exists(index=index_name):
        print(f"🆕 Creating index {index_name}")
        opensearch.indices.create(index=index_name, body=ARXIV_PAPERS_CHUNKS_MAPPING)
    else:
        print(f"ℹ️  Index already exists: {index_name}")

    batch_size = args.batch_size
    indexed = 0
    failed = 0

    print("\n📝 Indexing papers...")
    for offset in range(0, total_papers, batch_size):
        cur.execute(
            """
            SELECT arxiv_id, title, abstract, authors, published_date
            FROM papers
            WHERE arxiv_id IS NOT NULL
            ORDER BY published_date DESC
            LIMIT %s OFFSET %s;
            """,
            (batch_size, offset),
        )

        for arxiv_id, title, abstract, authors, published_date in cur.fetchall():
            if not arxiv_id:
                continue

            chunk_text = f"Title: {title or ''}\n\nAbstract: {abstract or ''}"
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            doc = {
                "chunk_id": f"{arxiv_id}_0",
                "arxiv_id": arxiv_id,
                "paper_id": arxiv_id,
                "chunk_index": 0,
                "chunk_text": chunk_text,
                "chunk_word_count": len(chunk_text.split()),
                "start_char": 0,
                "end_char": len(chunk_text),
                "title": title or "",
                "authors": format_authors(authors),
                "abstract": abstract or "",
                "categories": ["cs.AI"],
                "published_date": published_date.isoformat() if published_date else None,
                "section_title": "Abstract",
                "embedding_model": "none",
                "pdf_url": pdf_url,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            try:
                opensearch.index(index=index_name, id=doc["chunk_id"], body=doc, refresh=False)
                indexed += 1
                if indexed % 1000 == 0:
                    pct = indexed / total_papers * 100
                    print(f"  ✅ {indexed:,}/{total_papers:,} papers indexed ({pct:.1f}%)")
            except Exception as exc:  # pragma: no cover - operational script
                failed += 1
                if failed <= 5:
                    print(f"  ⚠️  Failed to index {arxiv_id}: {exc}")

    print("\n🔄 Refreshing index...")
    opensearch.indices.refresh(index=index_name)

    stats = opensearch.count(index=index_name)
    doc_count = stats["count"]

    print("\n🎉 Completed BM25 indexing!")
    print(f"   Indexed: {indexed:,}")
    print(f"   Failed : {failed:,}")
    print(f"   Docs in index: {doc_count:,}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

