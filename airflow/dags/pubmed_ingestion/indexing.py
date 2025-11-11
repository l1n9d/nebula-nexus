"""OpenSearch indexing tasks for PubMed papers."""
import asyncio
import logging
from typing import Dict, List

from .common import get_cached_services

logger = logging.getLogger(__name__)


async def index_papers_to_opensearch(paper_ids: List[str] = None, batch_size: int = 10) -> Dict:
    """
    Index papers from PostgreSQL to OpenSearch.

    :param paper_ids: List of paper PMIDs to index (if None, indexes all unindexed)
    :param batch_size: Number of papers to process in each batch
    :return: Dictionary with indexing statistics
    """
    from src.services.indexing.factory import get_hybrid_indexer
    
    _, _, database, _, _ = get_cached_services()
    indexer = get_hybrid_indexer()

    papers_indexed = 0
    papers_failed = 0

    with database.get_session() as session:
        from src.repositories.paper import PaperRepository

        repo = PaperRepository(session)

        if paper_ids:
            # Index specific papers
            papers = [repo.get_by_pmid(pmid) for pmid in paper_ids]
            papers = [p for p in papers if p is not None]
        else:
            # Index all papers with text content
            papers = repo.get_papers_with_raw_text(limit=1000)

        logger.info(f"Indexing {len(papers)} papers to OpenSearch")

        # Process papers in batches
        for i in range(0, len(papers), batch_size):
            batch = papers[i : i + batch_size]

            for paper in batch:
                try:
                    # Index paper chunks
                    await indexer.index_paper(
                        paper_id=paper.pmid,
                        title=paper.title,
                        authors=paper.authors,
                        abstract=paper.abstract,
                        full_text=paper.raw_text or "",
                        sections=paper.sections or [],
                        published_date=paper.published_date.isoformat(),
                        journal=paper.journal or "",
                        doi=paper.doi or "",
                    )
                    papers_indexed += 1
                    logger.debug(f"Indexed paper {paper.pmid}")

                except Exception as e:
                    logger.error(f"Failed to index paper {paper.pmid}: {e}")
                    papers_failed += 1

            logger.info(f"Indexed {papers_indexed}/{len(papers)} papers so far...")

    logger.info(f"Indexing complete: {papers_indexed} successful, {papers_failed} failed")

    return {
        "papers_indexed": papers_indexed,
        "papers_failed": papers_failed,
        "total_papers": len(papers) if paper_ids is None else len(paper_ids),
    }


def index_recent_papers(**context):
    """Index recently fetched papers to OpenSearch."""
    logger.info("Starting OpenSearch indexing task")

    # Get papers from previous task if available
    ti = context.get("ti")
    paper_ids = None

    if ti:
        try:
            fetch_results = ti.xcom_pull(key="fetch_results", task_ids="fetch_papers")
            if fetch_results:
                logger.info(f"Found {fetch_results.get('papers_fetched', 0)} papers from fetch task")
        except Exception as e:
            logger.warning(f"Could not retrieve fetch results: {e}")

    # Index papers
    results = asyncio.run(index_papers_to_opensearch(paper_ids=paper_ids))

    logger.info(f"Indexing complete: {results}")

    if ti:
        ti.xcom_push(key="index_results", value=results)

    return results




