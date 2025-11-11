"""Setup and health check tasks for PubMed ingestion pipeline."""
import logging
from typing import Dict

from .common import get_cached_services

logger = logging.getLogger(__name__)


def check_database_connection(**context) -> Dict:
    """Check if PostgreSQL database is accessible."""
    logger.info("Checking database connection...")

    try:
        _, _, database, _, _ = get_cached_services()

        with database.get_session() as session:
            # Try a simple query
            from src.repositories.paper import PaperRepository

            repo = PaperRepository(session)
            count = repo.get_count()
            logger.info(f"✅ Database connection successful. Papers in DB: {count}")

            return {"status": "success", "paper_count": count}

    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise


def check_pubmed_api(**context) -> Dict:
    """Check if PubMed API is accessible."""
    import asyncio

    logger.info("Checking PubMed API connection...")

    try:
        pubmed_client, _, _, _, _ = get_cached_services()

        async def test_api():
            # Try to search with a simple query
            pmids = await pubmed_client.search_papers(
                query="artificial intelligence",
                max_results=1,
            )
            return len(pmids)

        result_count = asyncio.run(test_api())
        logger.info(f"✅ PubMed API connection successful. Test search returned {result_count} result(s)")

        return {"status": "success", "test_results": result_count}

    except Exception as e:
        logger.error(f"❌ PubMed API connection failed: {e}")
        raise


def verify_services(**context) -> Dict:
    """Verify all required services are available."""
    logger.info("Verifying all services...")

    results = {
        "database": False,
        "pubmed_api": False,
    }

    # Check database
    try:
        db_result = check_database_connection(**context)
        results["database"] = True
        logger.info("✅ Database verified")
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")

    # Check PubMed API
    try:
        api_result = check_pubmed_api(**context)
        results["pubmed_api"] = True
        logger.info("✅ PubMed API verified")
    except Exception as e:
        logger.error(f"❌ PubMed API verification failed: {e}")

    # Raise error if any service is not available
    if not all(results.values()):
        raise RuntimeError(f"Service verification failed: {results}")

    logger.info("✅ All services verified successfully")
    return results




