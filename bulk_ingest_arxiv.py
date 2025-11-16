#!/usr/bin/env python3
"""
Bulk arXiv Paper Ingestion Script
Fetches and indexes 73,000+ arXiv papers for RAG system

Usage:
    python bulk_ingest_arxiv.py --target 73000 --batch-size 1000
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_settings
from src.db.factory import make_database
from src.repositories.paper import PaperRepository
from src.services.metadata_fetcher import MetadataFetcher
from src.services.indexing.factory import make_hybrid_indexing_service
from src.services.arxiv.factory import make_arxiv_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkArxivIngestion:
    """Handles bulk ingestion of papers from arXiv."""
    
    def __init__(self, target_count: int = 73000, batch_size: int = 1000):
        self.target_count = target_count
        self.batch_size = batch_size
        self.settings = get_settings()
        self.database = make_database()
        self.metadata_fetcher = MetadataFetcher(
            arxiv_client=make_arxiv_client(),
            database=self.database
        )
        self.indexer = make_hybrid_indexing_service()
        
        # Statistics
        self.stats = {
            'papers_fetched': 0,
            'papers_stored': 0,
            'papers_indexed': 0,
            'papers_failed': 0,
            'batches_processed': 0,
            'start_time': datetime.now()
        }
    
    def get_current_paper_count(self) -> int:
        """Get current number of papers in database."""
        try:
            with self.database.get_session() as session:
                repo = PaperRepository(session)
                return repo.get_count()
        except Exception as e:
            logger.warning(f"Could not get paper count: {e}")
            return 0
    
    async def fetch_papers_by_date_range(
        self, 
        from_date: str, 
        to_date: str,
        max_results: int = 2000
    ) -> Dict[str, Any]:
        """Fetch papers from arXiv for a date range."""
        try:
            logger.info(f"Fetching papers from {from_date} to {to_date}")
            result = await self.metadata_fetcher.fetch_and_process_papers(
                max_results=max_results,
                from_date=from_date,
                to_date=to_date,
                process_pdfs=True,
                store_to_db=True,
                db_session=None  # Will create session internally
            )
            return result
        except Exception as e:
            logger.error(f"Error fetching papers for {from_date}-{to_date}: {e}")
            return {'papers_fetched': 0, 'papers_stored': 0, 'errors': [str(e)]}
    
    async def index_papers_from_db(self, limit: int = None) -> int:
        """Index papers from database to OpenSearch."""
        try:
            with self.database.get_session() as session:
                repo = PaperRepository(session)
                
                # Get papers that haven't been indexed yet
                papers = repo.get_unindexed_papers(limit=limit or self.batch_size)
                
                if not papers:
                    logger.info("No unindexed papers found")
                    return 0
                
                logger.info(f"Indexing {len(papers)} papers...")
                indexed_count = 0
                
                for paper in papers:
                    try:
                        # Index paper with chunks
                        success = await self.indexer.index_paper(paper)
                        if success:
                            indexed_count += 1
                            # Mark as indexed
                            repo.mark_as_indexed(paper.id)
                    except Exception as e:
                        logger.error(f"Failed to index paper {paper.arxiv_id}: {e}")
                        self.stats['papers_failed'] += 1
                
                return indexed_count
        except Exception as e:
            logger.error(f"Error indexing papers: {e}")
            return 0
    
    async def run_ingestion(self):
        """Run the full ingestion process."""
        logger.info("=" * 80)
        logger.info(f"🚀 Starting Bulk arXiv Paper Ingestion")
        logger.info(f"   Target: {self.target_count:,} papers")
        logger.info(f"   Batch size: {self.batch_size:,}")
        logger.info("=" * 80)
        
        # Check current count
        current_count = self.get_current_paper_count()
        logger.info(f"📊 Current papers in database: {current_count:,}")
        
        if current_count >= self.target_count:
            logger.info(f"✅ Already have {current_count:,} papers (target: {self.target_count:,})")
            logger.info("📝 Proceeding to index existing papers...")
        else:
            # Fetch papers by date ranges
            # arXiv has papers going back many years, we'll fetch recent ones first
            # then go back in time
            papers_needed = self.target_count - current_count
            logger.info(f"📥 Need to fetch {papers_needed:,} more papers")
            
            # Start from today and go back
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * 5)  # Go back 5 years
            
            # Fetch in monthly batches
            current_date = end_date
            fetched_total = 0
            
            while fetched_total < papers_needed and current_date > start_date:
                # Calculate date range for this batch
                batch_end = current_date
                batch_start = current_date - timedelta(days=30)  # Monthly batches
                
                from_date_str = batch_start.strftime("%Y%m%d")
                to_date_str = batch_end.strftime("%Y%m%d")
                
                logger.info(f"\n📅 Fetching batch: {from_date_str} to {to_date_str}")
                
                # Fetch papers for this date range
                result = await self.fetch_papers_by_date_range(
                    from_date=from_date_str,
                    to_date=to_date_str,
                    max_results=self.batch_size
                )
                
                fetched = result.get('papers_fetched', 0)
                stored = result.get('papers_stored', 0)
                fetched_total += stored
                
                self.stats['papers_fetched'] += fetched
                self.stats['papers_stored'] += stored
                self.stats['batches_processed'] += 1
                
                logger.info(f"   ✅ Fetched: {fetched}, Stored: {stored}")
                logger.info(f"   📊 Total so far: {fetched_total:,} / {papers_needed:,}")
                
                # Check if we have enough
                current_count = self.get_current_paper_count()
                if current_count >= self.target_count:
                    logger.info(f"✅ Reached target of {self.target_count:,} papers!")
                    break
                
                # Move to next month
                current_date = batch_start
                
                # Rate limiting - be nice to arXiv API
                await asyncio.sleep(3)
        
        # Now index all papers to OpenSearch
        logger.info("\n" + "=" * 80)
        logger.info("📝 Starting indexing to OpenSearch...")
        logger.info("=" * 80)
        
        total_indexed = 0
        batch_num = 0
        
        while True:
            batch_num += 1
            logger.info(f"\n📦 Indexing batch {batch_num}...")
            
            indexed = await self.index_papers_from_db(limit=self.batch_size)
            
            if indexed == 0:
                logger.info("✅ All papers indexed!")
                break
            
            total_indexed += indexed
            self.stats['papers_indexed'] += indexed
            
            logger.info(f"   ✅ Indexed: {indexed} papers")
            logger.info(f"   📊 Total indexed: {total_indexed:,}")
            
            # Progress update
            current_count = self.get_current_paper_count()
            progress = (total_indexed / current_count * 100) if current_count > 0 else 0
            logger.info(f"   📈 Progress: {progress:.1f}% ({total_indexed:,} / {current_count:,})")
        
        # Final statistics
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 Ingestion Complete!")
        logger.info("=" * 80)
        logger.info(f"📊 Statistics:")
        logger.info(f"   Papers fetched: {self.stats['papers_fetched']:,}")
        logger.info(f"   Papers stored: {self.stats['papers_stored']:,}")
        logger.info(f"   Papers indexed: {self.stats['papers_indexed']:,}")
        logger.info(f"   Papers failed: {self.stats['papers_failed']:,}")
        logger.info(f"   Batches processed: {self.stats['batches_processed']:,}")
        logger.info(f"   Total time: {elapsed/60:.1f} minutes")
        logger.info("=" * 80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Bulk ingest arXiv papers for RAG system")
    parser.add_argument(
        "--target",
        type=int,
        default=73000,
        help="Target number of papers (default: 73000)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Papers per batch (default: 1000)"
    )
    
    args = parser.parse_args()
    
    # Create ingestion instance
    ingestion = BulkArxivIngestion(
        target_count=args.target,
        batch_size=args.batch_size
    )
    
    # Run ingestion
    await ingestion.run_ingestion()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Ingestion interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

