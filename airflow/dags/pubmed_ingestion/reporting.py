"""Reporting tasks for PubMed ingestion pipeline."""
import logging
from typing import Dict

from .common import get_cached_services

logger = logging.getLogger(__name__)


def generate_ingestion_report(**context) -> Dict:
    """Generate a report of the ingestion pipeline execution."""
    logger.info("Generating ingestion report...")

    ti = context.get("ti")
    report = {
        "execution_date": str(context.get("execution_date")),
        "dag_run_id": context.get("dag_run", {}).get("run_id", "unknown"),
    }

    # Get fetch results
    try:
        if ti:
            fetch_results = ti.xcom_pull(key="fetch_results", task_ids="fetch_papers")
            if fetch_results:
                report["fetch"] = fetch_results
    except Exception as e:
        logger.warning(f"Could not retrieve fetch results: {e}")

    # Get index results
    try:
        if ti:
            index_results = ti.xcom_pull(key="index_results", task_ids="index_papers")
            if index_results:
                report["index"] = index_results
    except Exception as e:
        logger.warning(f"Could not retrieve index results: {e}")

    # Get database stats
    try:
        _, _, database, _, _ = get_cached_services()
        with database.get_session() as session:
            from src.repositories.paper import PaperRepository

            repo = PaperRepository(session)
            stats = repo.get_processing_stats()
            report["database_stats"] = stats
    except Exception as e:
        logger.warning(f"Could not retrieve database stats: {e}")

    logger.info("=" * 60)
    logger.info("PUBMED INGESTION REPORT")
    logger.info("=" * 60)
    logger.info(f"Execution Date: {report.get('execution_date')}")
    logger.info(f"DAG Run ID: {report.get('dag_run_id')}")

    if "fetch" in report:
        logger.info("\nFetch Results:")
        for key, value in report["fetch"].items():
            logger.info(f"  {key}: {value}")

    if "index" in report:
        logger.info("\nIndex Results:")
        for key, value in report["index"].items():
            logger.info(f"  {key}: {value}")

    if "database_stats" in report:
        logger.info("\nDatabase Stats:")
        for key, value in report["database_stats"].items():
            logger.info(f"  {key}: {value}")

    logger.info("=" * 60)

    return report




