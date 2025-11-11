#!/usr/bin/env python3
"""
Index existing papers from PostgreSQL into OpenSearch
This will enable the RAG system to search through the 64k papers
"""
import sys
import os
import asyncio
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import Settings
from src.services.opensearch.factory import make_opensearch_client
from src.services.embeddings.factory import make_embeddings_client
from src.services.indexing.text_chunker import TextChunker
import psycopg2
import json

async def main():
    print("=" * 60)
    print("🔍 Indexing Papers into OpenSearch")
    print("=" * 60)
    
    # Load settings
    settings = Settings()
    
    # Connect to PostgreSQL using database URL
    print("\n📊 Connecting to PostgreSQL...")
    # Parse the database URL to extract connection details
    # Format: postgresql://user:password@host:port/database
    db_url = settings.postgres_database_url
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Get paper count
    cur.execute("SELECT COUNT(*) FROM papers;")
    total_papers = cur.fetchone()[0]
    print(f"✅ Found {total_papers:,} papers in database")
    
    # Initialize OpenSearch
    print("\n🔍 Connecting to OpenSearch...")
    opensearch_client = make_opensearch_client()
    
    # Initialize embeddings client
    print("🤖 Initializing embeddings client...")
    embeddings_client = make_embeddings_client()
    
    # Initialize chunker
    chunker = TextChunker()
    
    print(f"\n📝 Starting indexing (this will take a while for {total_papers:,} papers)...")
    print("⚡ Processing in batches for efficiency...\n")
    
    # Fetch papers in batches
    batch_size = 50
    indexed_count = 0
    failed_count = 0
    
    for offset in range(0, min(1000, total_papers), batch_size):  # Limit to 1000 papers for now
        cur.execute("""
            SELECT arxiv_id, title, abstract, published_date, categories
            FROM papers
            ORDER BY published_date DESC
            LIMIT %s OFFSET %s;
        """, (batch_size, offset))
        
        papers = cur.fetchall()
        
        for paper in papers:
            arxiv_id, title, abstract, published_date, categories = paper
            
            try:
                # Create simple chunks from title and abstract
                full_text = f"{title}\n\n{abstract}"
                
                # Simple chunking - just use the abstract as one chunk for now
                chunk_text = f"Title: {title}\n\nAbstract: {abstract}"
                
                # Get embedding
                embedding = await embeddings_client.embed_query(chunk_text)
                
                # Create document
                doc = {
                    "chunk_id": f"{arxiv_id}_0",
                    "arxiv_id": arxiv_id,
                    "paper_id": arxiv_id,
                    "chunk_index": 0,
                    "chunk_text": chunk_text,
                    "chunk_word_count": len(chunk_text.split()),
                    "start_char": 0,
                    "end_char": len(chunk_text),
                    "embedding": embedding,
                    "title": title,
                    "authors": "",
                    "abstract": abstract or "",
                    "categories": categories if isinstance(categories, list) else [categories] if categories else [],
                    "published_date": published_date.isoformat() if published_date else None,
                    "section_title": "Abstract",
                    "embedding_model": "jina-embeddings-v3",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                
                # Index document
                index_name = f"{settings.opensearch.index_name}-{settings.opensearch.chunk_index_suffix}"
                opensearch_client.client.index(
                    index=index_name,
                    id=doc["chunk_id"],
                    body=doc,
                    refresh=False  # Don't refresh after each doc for performance
                )
                
                indexed_count += 1
                
                if indexed_count % 10 == 0:
                    print(f"✅ Indexed {indexed_count}/{min(1000, total_papers)} papers ({(indexed_count/min(1000, total_papers)*100):.1f}%)")
                    
            except Exception as e:
                failed_count += 1
                if failed_count <= 5:  # Only show first 5 errors
                    print(f"⚠️  Error indexing {arxiv_id}: {e}")
    
    # Refresh index to make documents searchable
    print("\n🔄 Refreshing index...")
    index_name = f"{settings.opensearch.index_name}-{settings.opensearch.chunk_index_suffix}"
    opensearch_client.client.indices.refresh(index=index_name)
    
    # Final stats
    print("\n" + "=" * 60)
    print("📊 Indexing Complete!")
    print("=" * 60)
    print(f"✅ Successfully indexed: {indexed_count:,} papers")
    print(f"⚠️  Failed: {failed_count}")
    print(f"📈 Success rate: {(indexed_count/(indexed_count+failed_count)*100):.1f}%")
    print("\n🎉 OpenSearch is now ready for RAG queries!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())

