#!/usr/bin/env python3
"""
Bulk Paper Ingestion Script for RAG System
Fetches 10,000+ papers from PubMed and indexes them in OpenSearch

Usage:
    python bulk_ingest_papers.py --target 10000 --batch-size 100
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Set

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_settings
from src.database import get_database
from src.repositories.paper import PaperRepository
from src.schemas.pubmed.paper import PaperCreate
from src.services.pubmed.factory import get_pubmed_client
from src.services.indexing.factory import make_hybrid_indexing_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkPaperIngestion:
    """Handles bulk ingestion of papers from PubMed."""
    
    def __init__(self, target_count: int = 10000, batch_size: int = 100):
        self.target_count = target_count
        self.batch_size = batch_size
        self.settings = get_settings()
        self.pubmed_client = get_pubmed_client()
        self.database = get_database()
        self.indexer = make_hybrid_indexing_service()
        
        # Statistics
        self.stats = {
            'papers_fetched': 0,
            'papers_stored': 0,
            'papers_updated': 0,
            'papers_indexed': 0,
            'papers_failed': 0,
            'batches_processed': 0
        }
        
        # Track processed PMIDs to avoid duplicates
        self.processed_pmids: Set[str] = set()
    
    def get_current_paper_count(self) -> int:
        """Get current number of papers in database."""
        with self.database.get_session() as session:
            repo = PaperRepository(session)
            return repo.get_count()
    
    async def fetch_papers_batch(self, query: str, max_results: int) -> List:
        """Fetch a batch of papers from PubMed."""
        try:
            papers = await self.pubmed_client.fetch_papers(
                query=query,
                max_results=max_results
            )
            return papers
        except Exception as e:
            logger.error(f"Error fetching papers: {e}")
            return []
    
    def store_papers(self, papers: List) -> tuple:
        """Store papers in database."""
        stored = 0
        updated = 0
        failed = 0
        
        with self.database.get_session() as session:
            repo = PaperRepository(session)
            
            for paper in papers:
                try:
                    # Skip if already processed
                    if paper.pmid in self.processed_pmids:
                        continue
                    
                    # Parse publication date
                    pub_date = None
                    if paper.published_date:
                        for fmt in ["%Y-%m-%d", "%Y-%m", "%Y", "%Y %b %d", "%Y %b"]:
                            try:
                                pub_date = datetime.strptime(paper.published_date, fmt)
                                break
                            except ValueError:
                                continue
                    
                    if not pub_date:
                        pub_date = datetime.now()
                    
                    # Create paper object
                    paper_create = PaperCreate(
                        pmid=paper.pmid,
                        title=paper.title,
                        authors=paper.authors,
                        abstract=paper.abstract or "",
                        journal=paper.journal,
                        published_date=pub_date,
                        doi=paper.doi,
                        pmc_id=paper.pmc_id,
                        mesh_terms=paper.mesh_terms,
                        publication_types=paper.publication_types,
                        full_text_url=paper.full_text_url,
                        raw_text=paper.abstract or ""  # Use abstract as content
                    )
                    
                    # Check if exists
                    existing = repo.get_by_pmid(paper.pmid)
                    if existing:
                        updated += 1
                    else:
                        stored += 1
                    
                    repo.upsert(paper_create)
                    self.processed_pmids.add(paper.pmid)
                    
                except Exception as e:
                    logger.error(f"Failed to store paper {paper.pmid}: {e}")
                    failed += 1
        
        return stored, updated, failed
    
    async def index_papers(self, papers: List) -> tuple:
        """Index papers in OpenSearch."""
        indexed = 0
        failed = 0
        
        with self.database.get_session() as session:
            repo = PaperRepository(session)
            
            for paper in papers:
                try:
                    # Get from database
                    db_paper = repo.get_by_pmid(paper.pmid)
                    if not db_paper:
                        continue
                    
                    # Index the paper
                    await self.indexer.index_paper(
                        paper_id=db_paper.pmid,
                        title=db_paper.title,
                        authors=db_paper.authors,
                        abstract=db_paper.abstract or "",
                        full_text=db_paper.raw_text or db_paper.abstract or "",
                        sections=[],
                        published_date=db_paper.published_date.isoformat(),
                        journal=db_paper.journal or "",
                        doi=db_paper.doi or "",
                    )
                    indexed += 1
                    
                except Exception as e:
                    logger.error(f"Failed to index paper {paper.pmid}: {e}")
                    failed += 1
        
        return indexed, failed
    
    async def run_ingestion(self, search_queries: List[str]):
        """Run the bulk ingestion process."""
        logger.info("=" * 80)
        logger.info("🔬 BULK PAPER INGESTION STARTED")
        logger.info("=" * 80)
        
        # Check current count
        current_count = self.get_current_paper_count()
        logger.info(f"📊 Current papers in database: {current_count}")
        logger.info(f"🎯 Target: {self.target_count} papers")
        logger.info(f"📦 Batch size: {self.batch_size}")
        logger.info(f"🔍 Search queries: {len(search_queries)}")
        logger.info("=" * 80)
        
        if current_count >= self.target_count:
            logger.info(f"✅ Already have {current_count} papers (target: {self.target_count})")
            return
        
        papers_needed = self.target_count - current_count
        logger.info(f"📥 Need to fetch: {papers_needed} more papers\n")
        
        # Process each query
        for query_idx, query in enumerate(search_queries, 1):
            if current_count >= self.target_count:
                break
            
            logger.info(f"\n{'='*80}")
            logger.info(f"🔍 Query {query_idx}/{len(search_queries)}: {query}")
            logger.info(f"{'='*80}")
            
            # Fetch papers for this query
            try:
                papers = await self.fetch_papers_batch(
                    query=query,
                    max_results=min(self.batch_size * 10, papers_needed)
                )
                
                self.stats['papers_fetched'] += len(papers)
                logger.info(f"📥 Fetched {len(papers)} papers")
                
                if not papers:
                    logger.warning(f"⚠️  No papers found for query: {query}")
                    continue
                
                # Process in batches
                for i in range(0, len(papers), self.batch_size):
                    batch = papers[i:i + self.batch_size]
                    batch_num = i // self.batch_size + 1
                    
                    logger.info(f"\n  📦 Processing batch {batch_num} ({len(batch)} papers)...")
                    
                    # Store papers
                    stored, updated, failed = self.store_papers(batch)
                    self.stats['papers_stored'] += stored
                    self.stats['papers_updated'] += updated
                    self.stats['papers_failed'] += failed
                    logger.info(f"     💾 Stored: {stored} new, {updated} updated, {failed} failed")
                    
                    # Index papers
                    indexed, index_failed = await self.index_papers(batch)
                    self.stats['papers_indexed'] += indexed
                    logger.info(f"     🔍 Indexed: {indexed}, failed: {index_failed}")
                    
                    self.stats['batches_processed'] += 1
                    current_count = self.get_current_paper_count()
                    logger.info(f"     📊 Total papers in DB: {current_count}/{self.target_count}")
                    
                    if current_count >= self.target_count:
                        logger.info(f"\n✅ Target reached! {current_count} papers in database")
                        break
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error processing query '{query}': {e}")
                continue
        
        # Final report
        self.print_final_report()
    
    def print_final_report(self):
        """Print final ingestion statistics."""
        final_count = self.get_current_paper_count()
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 BULK INGESTION COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   Papers in database: {final_count}")
        logger.info(f"   Papers fetched: {self.stats['papers_fetched']}")
        logger.info(f"   Papers stored (new): {self.stats['papers_stored']}")
        logger.info(f"   Papers updated: {self.stats['papers_updated']}")
        logger.info(f"   Papers indexed: {self.stats['papers_indexed']}")
        logger.info(f"   Failed: {self.stats['papers_failed']}")
        logger.info(f"   Batches processed: {self.stats['batches_processed']}")
        logger.info("=" * 80)
        
        if final_count >= self.target_count:
            logger.info(f"✅ SUCCESS: Reached target of {self.target_count} papers!")
        else:
            logger.info(f"⚠️  Only reached {final_count}/{self.target_count} papers")
            logger.info(f"   Consider adding more search queries or running again")
        
        logger.info("\n🌐 Your RAG system is ready at: http://localhost:7860")
        logger.info("=" * 80)


def get_diverse_search_queries() -> List[str]:
    """Generate diverse search queries to get 10k+ papers."""
    queries = [
        # AI and Machine Learning in Medicine
        "artificial intelligence[Title/Abstract] AND medical[Title/Abstract]",
        "machine learning[Title/Abstract] AND diagnosis[Title/Abstract]",
        "deep learning[Title/Abstract] AND healthcare[Title/Abstract]",
        "neural network[Title/Abstract] AND medical imaging[Title/Abstract]",
        "computer vision[Title/Abstract] AND radiology[Title/Abstract]",
        
        # Medical Imaging
        "medical imaging[Title/Abstract]",
        "radiology[Title/Abstract] AND (MRI OR CT OR ultrasound)[Title/Abstract]",
        "image analysis[Title/Abstract] AND clinical[Title/Abstract]",
        
        # Common Diseases
        "diabetes[Title/Abstract] AND treatment[Title/Abstract]",
        "cancer[Title/Abstract] AND therapy[Title/Abstract]",
        "cardiovascular disease[Title/Abstract]",
        "alzheimer[Title/Abstract] OR dementia[Title/Abstract]",
        
        # COVID-19 (lots of recent papers)
        "COVID-19[Title/Abstract]",
        "SARS-CoV-2[Title/Abstract]",
        
        # General Medical Research
        "clinical trial[Title/Abstract]",
        "randomized controlled trial[Publication Type]",
        "meta-analysis[Publication Type]",
        "systematic review[Publication Type]",
        
        # More specific AI applications
        "predictive model[Title/Abstract] AND patient[Title/Abstract]",
        "risk prediction[Title/Abstract] AND clinical[Title/Abstract]",
        
        # Additional broad queries to reach 10k
        "immunotherapy[Title/Abstract]",
        "precision medicine[Title/Abstract]",
        "genomics[Title/Abstract] AND disease[Title/Abstract]",
        "biomarker[Title/Abstract] AND diagnosis[Title/Abstract]",
    ]
    return queries


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Bulk ingest papers for RAG system")
    parser.add_argument(
        "--target",
        type=int,
        default=10000,
        help="Target number of papers (default: 10000)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Papers per batch (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Create ingestion instance
    ingestion = BulkPaperIngestion(
        target_count=args.target,
        batch_size=args.batch_size
    )
    
    # Get search queries
    queries = get_diverse_search_queries()
    
    # Run ingestion
    await ingestion.run_ingestion(queries)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

