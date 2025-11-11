import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .common import get_cached_services

logger = logging.getLogger(__name__)


async def run_paper_ingestion_pipeline(
    search_query: Optional[str] = None,
    process_content: bool = True,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> dict:
    """Async wrapper for the PubMed paper ingestion pipeline.

    :param search_query: PubMed search query (uses default from config if None)
    :param process_content: Whether to download and process full text
    :param min_date: Minimum publication date (YYYY/MM/DD format)
    :param max_date: Maximum publication date (YYYY/MM/DD format)
    :returns: Dictionary with ingestion statistics
    """
    pubmed_client, _, database, metadata_fetcher, _ = get_cached_services()

    max_results = pubmed_client.max_results
    logger.info(f"Using default max_results from config: {max_results}")

    # Fetch papers from PubMed
    papers = await pubmed_client.fetch_papers(
        query=search_query,
        max_results=max_results,
        min_date=min_date,
        max_date=max_date,
    )

    logger.info(f"Fetched {len(papers)} papers from PubMed")

    # Store papers in database
    papers_stored = 0
    papers_updated = 0
    papers_failed = 0

    with database.get_session() as session:
        from src.repositories.paper import PaperRepository
        from src.schemas.pubmed.paper import PaperCreate
        
        repo = PaperRepository(session)
        
        for paper in papers:
            try:
                # Convert published_date string to datetime
                pub_date = None
                if paper.published_date:
                    # Try various date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m", "%Y", "%Y %b %d", "%Y %b"]:
                        try:
                            pub_date = datetime.strptime(paper.published_date, fmt)
                            break
                        except ValueError:
                            continue
                
                if not pub_date:
                    # Default to current date if parsing fails
                    pub_date = datetime.now()
                
                # Create PaperCreate object
                paper_create = PaperCreate(
                    pmid=paper.pmid,
                    title=paper.title,
                    authors=paper.authors,
                    abstract=paper.abstract,
                    journal=paper.journal,
                    published_date=pub_date,
                    doi=paper.doi,
                    pmc_id=paper.pmc_id,
                    mesh_terms=paper.mesh_terms,
                    publication_types=paper.publication_types,
                    full_text_url=paper.full_text_url,
                )
                
                # Upsert paper
                existing_paper = repo.get_by_pmid(paper.pmid)
                if existing_paper:
                    papers_updated += 1
                else:
                    papers_stored += 1
                
                repo.upsert(paper_create)
                
            except Exception as e:
                logger.error(f"Failed to store paper {paper.pmid}: {e}")
                papers_failed += 1

    return {
        "papers_fetched": len(papers),
        "papers_stored": papers_stored,
        "papers_updated": papers_updated,
        "papers_failed": papers_failed,
    }


def fetch_daily_papers(**context):
    """Fetch daily medical papers from PubMed and store in PostgreSQL.

    This task:
    1. Determines the target date range (defaults to recent papers)
    2. Fetches papers from PubMed API
    3. Downloads and processes full text if available
    4. Stores metadata and parsed content in PostgreSQL

    Note: OpenSearch indexing is handled by a separate dedicated task
    """
    logger.info("Starting daily PubMed paper fetching task")

    execution_date = context.get("execution_date")
    if execution_date:
        # Get papers from the last 7 days
        end_date = execution_date
        start_date = end_date - timedelta(days=7)
        min_date = start_date.strftime("%Y/%m/%d")
        max_date = end_date.strftime("%Y/%m/%d")
    else:
        # Default to last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        min_date = start_date.strftime("%Y/%m/%d")
        max_date = end_date.strftime("%Y/%m/%d")

    logger.info(f"Fetching papers from {min_date} to {max_date}")

    results = asyncio.run(
        run_paper_ingestion_pipeline(
            min_date=min_date,
            max_date=max_date,
            process_content=True,
        )
    )

    logger.info(f"Daily fetch complete: {results['papers_fetched']} papers")

    results["date_range"] = f"{min_date} to {max_date}"
    ti = context.get("ti")
    if ti:
        ti.xcom_push(key="fetch_results", value=results)

    return results




