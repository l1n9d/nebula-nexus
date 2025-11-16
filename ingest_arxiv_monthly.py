#!/usr/bin/env python3
"""
Ingest arXiv papers between two dates by iterating month-by-month.

This avoids huge `start` offsets (which trigger 500 errors on the arXiv API)
by limiting each query to a single month and paging only within that month.
"""
import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.config import get_settings
from src.db.factory import make_database
from src.repositories.paper import PaperRepository
from src.services.arxiv.factory import make_arxiv_client
from src.services.metadata_fetcher import MetadataFetcher
from src.services.pdf_parser.factory import make_pdf_parser_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonthRange:
    start: datetime
    end: datetime

    def format_start(self) -> str:
        return self.start.strftime("%Y%m%d")

    def format_end(self) -> str:
        return self.end.strftime("%Y%m%d")


def build_month_ranges(start_date: str, end_date: str) -> list[MonthRange]:
    """Create month ranges between two YYYYMMDD dates (inclusive)."""
    start_dt = datetime.strptime(start_date, "%Y%m%d").replace(day=1)
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    ranges: list[MonthRange] = []

    current = start_dt
    while current <= end_dt:
        next_month = current + relativedelta(months=1)
        month_end = min(end_dt, next_month - timedelta(days=1))
        ranges.append(MonthRange(start=current, end=month_end))
        current = next_month
    return ranges


async def process_month(
    metadata_fetcher: MetadataFetcher,
    db_session,
    month_range: MonthRange,
    batch_size: int,
    max_total: int,
    current_total: int,
) -> tuple[int, int]:
    """Ingest a single month, paging with the arXiv API."""
    stored_this_month = 0
    fetched_this_month = 0
    start_index = 0

    while current_total + stored_this_month < max_total:
        remaining_global = max_total - (current_total + stored_this_month)
        batch_limit = min(batch_size, remaining_global)

        logger.info("\n" + "=" * 80)
        logger.info(
            "📅 Month %s → %s • start_index=%s • batch_limit=%s",
            month_range.format_start(),
            month_range.format_end(),
            start_index,
            batch_limit,
        )
        logger.info("=" * 80)

        try:
            result = await metadata_fetcher.fetch_and_process_papers(
                max_results=batch_limit,
                from_date=month_range.format_start(),
                to_date=month_range.format_end(),
                start=start_index,
                process_pdfs=False,
                store_to_db=True,
                db_session=db_session,
            )
        except Exception as exc:
            logger.error("❌ Month ingest failed: %s", exc)
            # Advance start index to avoid infinite loops on the same failing window.
            start_index += batch_size
            await asyncio.sleep(3)
            continue

        fetched = result.get("papers_fetched", 0)
        stored = result.get("papers_stored", 0)
        fetched_this_month += fetched
        stored_this_month += stored

        logger.info("✅ Month batch stored=%s fetched=%s", stored, fetched)

        if fetched == 0 or fetched < batch_limit:
            logger.info(
                "Month %s complete (no more results). Stored %s papers.",
                month_range.start.strftime("%Y-%m"),
                stored_this_month,
            )
            break

        start_index += fetched
        await asyncio.sleep(2)  # gentle rate limit

    return fetched_this_month, stored_this_month


async def main():
    parser = argparse.ArgumentParser(description="Ingest arXiv papers month-by-month.")
    parser.add_argument("--start", default="20230101", help="Start date (YYYYMMDD)")
    parser.add_argument("--end", default="20241231", help="End date (YYYYMMDD)")
    parser.add_argument("--target", type=int, default=73_000, help="Target total paper count")
    parser.add_argument("--batch-size", type=int, default=2_000, help="Max papers per batch")
    args = parser.parse_args()

    target_count = args.target
    batch_size = args.batch_size
    start_date = args.start
    end_date = args.end

    settings = get_settings()
    database = make_database()
    metadata_fetcher = MetadataFetcher(
        arxiv_client=make_arxiv_client(),
        pdf_parser=make_pdf_parser_service(),
        settings=settings,
    )

    month_ranges = build_month_ranges(start_date, end_date)
    logger.info(
        "🗓️ Will ingest %s months (%s → %s)",
        len(month_ranges),
        start_date,
        end_date,
    )

    with database.get_session() as session:
        repo = PaperRepository(session)
        initial_total = repo.get_count()
        logger.info("📊 Starting paper count: %s", initial_total)

        if initial_total >= target_count:
            logger.info("✅ Already at target (%s)", initial_total)
            return

        fetched_total = 0
        stored_total = 0

        for idx, month in enumerate(month_ranges, start=1):
            logger.info("\n\n📦 Month %s/%s (%s → %s)", idx, len(month_ranges), month.format_start(), month.format_end())

            fetched, stored = await process_month(
                metadata_fetcher=metadata_fetcher,
                db_session=session,
                month_range=month,
                batch_size=batch_size,
                max_total=target_count,
                current_total=initial_total + stored_total,
            )

            fetched_total += fetched
            stored_total += stored

            current_total = initial_total + stored_total
            logger.info("📈 Progress: %s/%s (%0.1f%%)", current_total, target_count, current_total / target_count * 100)

            if current_total >= target_count:
                break

        logger.info("\n" + "=" * 80)
        logger.info("🎉 Ingestion complete: fetched=%s stored=%s total=%s", fetched_total, stored_total, initial_total + stored_total)
        logger.info("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("⚠️  Ingestion interrupted by user")
    except Exception as err:
        logger.exception("❌ Fatal error: %s", err)
        sys.exit(1)

