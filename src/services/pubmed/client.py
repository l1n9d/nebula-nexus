import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

import httpx
from src.config import PubMedSettings
from src.exceptions import PubMedAPIException, PubMedAPITimeoutError, PubMedParseError, PDFDownloadException, PDFDownloadTimeoutError
from src.schemas.pubmed.paper import PubMedPaper

logger = logging.getLogger(__name__)


class PubMedClient:
    """Client for fetching medical papers from PubMed via NCBI Entrez E-utilities API."""

    def __init__(self, settings: PubMedSettings):
        self._settings = settings
        self._last_request_time: Optional[float] = None

    @cached_property
    def pdf_cache_dir(self) -> Path:
        """PDF cache directory."""
        cache_dir = Path(self._settings.pdf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @property
    def base_url(self) -> str:
        return self._settings.base_url

    @property
    def rate_limit_delay(self) -> float:
        return self._settings.rate_limit_delay

    @property
    def timeout_seconds(self) -> int:
        return self._settings.timeout_seconds

    @property
    def max_results(self) -> int:
        return self._settings.max_results

    @property
    def search_term(self) -> str:
        return self._settings.search_term

    @property
    def email(self) -> str:
        return self._settings.email

    @property
    def api_key(self) -> str:
        return self._settings.api_key

    async def _enforce_rate_limit(self):
        """Enforce NCBI rate limiting (3 requests/sec without API key, 10/sec with key)."""
        if self._last_request_time is not None:
            time_since_last = time.time() - self._last_request_time
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                await asyncio.sleep(sleep_time)
        self._last_request_time = time.time()

    def _build_params(self, additional_params: Dict) -> Dict:
        """Build common parameters for E-utilities API calls."""
        params = {
            "email": self.email,
            "tool": "MedicalPaperRAG",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        params.update(additional_params)
        return params

    async def search_papers(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        start: int = 0,
        sort: str = "relevance",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> List[str]:
        """
        Search PubMed using ESearch API and return list of PMIDs.

        Args:
            query: Search query (uses default search term if None)
            max_results: Maximum number of results (uses settings default if None)
            start: Starting index for pagination (retstart)
            sort: Sort order (relevance, pub_date, etc.)
            min_date: Minimum publication date (YYYY/MM/DD format)
            max_date: Maximum publication date (YYYY/MM/DD format)

        Returns:
            List of PubMed IDs (PMIDs)
        """
        if max_results is None:
            max_results = self.max_results

        if query is None:
            query = self.search_term

        params = self._build_params({
            "db": "pubmed",
            "term": query,
            "retmax": min(max_results, 10000),
            "retstart": start,
            "sort": sort,
            "retmode": "xml",
        })

        if min_date:
            params["mindate"] = min_date
        if max_date:
            params["maxdate"] = max_date

        url = f"{self.base_url}/esearch.fcgi?{urlencode(params)}"

        try:
            logger.info(f"Searching PubMed: '{query}' (max_results={max_results}, start={start})")
            await self._enforce_rate_limit()

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_data = response.text

            pmids = self._parse_esearch_response(xml_data)
            logger.info(f"Found {len(pmids)} PMIDs")
            return pmids

        except httpx.TimeoutException as e:
            logger.error(f"PubMed API timeout: {e}")
            raise PubMedAPITimeoutError(f"PubMed API request timed out: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"PubMed API HTTP error: {e}")
            raise PubMedAPIException(f"PubMed API returned error {e.response.status_code}: {e}")
        except Exception as e:
            logger.error(f"Failed to search PubMed: {e}")
            raise PubMedAPIException(f"Unexpected error searching PubMed: {e}")

    async def fetch_papers_by_ids(self, pmids: List[str]) -> List[PubMedPaper]:
        """
        Fetch detailed paper information using EFetch API.

        Args:
            pmids: List of PubMed IDs to fetch

        Returns:
            List of PubMedPaper objects with full metadata
        """
        if not pmids:
            return []

        # Split into batches (EFetch can handle up to ~200 IDs at once)
        batch_size = 200
        all_papers = []

        for i in range(0, len(pmids), batch_size):
            batch = pmids[i:i + batch_size]
            papers = await self._fetch_batch(batch)
            all_papers.extend(papers)

        return all_papers

    async def _fetch_batch(self, pmids: List[str]) -> List[PubMedPaper]:
        """Fetch a batch of papers using EFetch."""
        id_list = ",".join(pmids)
        params = self._build_params({
            "db": "pubmed",
            "id": id_list,
            "retmode": "xml",
        })

        url = f"{self.base_url}/efetch.fcgi?{urlencode(params)}"

        try:
            logger.info(f"Fetching {len(pmids)} papers from PubMed")
            await self._enforce_rate_limit()

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_data = response.text

            papers = self._parse_efetch_response(xml_data)
            logger.info(f"Successfully parsed {len(papers)} papers")
            return papers

        except httpx.TimeoutException as e:
            logger.error(f"PubMed API timeout: {e}")
            raise PubMedAPITimeoutError(f"PubMed API request timed out: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"PubMed API HTTP error: {e}")
            raise PubMedAPIException(f"PubMed API returned error {e.response.status_code}: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch papers from PubMed: {e}")
            raise PubMedAPIException(f"Unexpected error fetching papers from PubMed: {e}")

    async def fetch_papers(
        self,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        start: int = 0,
        sort: str = "relevance",
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
    ) -> List[PubMedPaper]:
        """
        High-level method to search and fetch papers in one call.

        Args:
            query: Search query
            max_results: Maximum number of papers to fetch
            start: Starting index for pagination
            sort: Sort order
            min_date: Minimum publication date (YYYY/MM/DD format)
            max_date: Maximum publication date (YYYY/MM/DD format)

        Returns:
            List of PubMedPaper objects with full metadata
        """
        # Step 1: Search for PMIDs
        pmids = await self.search_papers(
            query=query,
            max_results=max_results,
            start=start,
            sort=sort,
            min_date=min_date,
            max_date=max_date,
        )

        if not pmids:
            logger.info("No papers found")
            return []

        # Step 2: Fetch full details for the PMIDs
        papers = await self.fetch_papers_by_ids(pmids)
        return papers

    async def fetch_paper_by_id(self, pmid: str) -> Optional[PubMedPaper]:
        """
        Fetch a single paper by its PMID.

        Args:
            pmid: PubMed ID

        Returns:
            PubMedPaper object or None if not found
        """
        papers = await self.fetch_papers_by_ids([pmid])
        return papers[0] if papers else None

    async def get_summaries(self, pmids: List[str]) -> List[Dict]:
        """
        Fetch paper summaries using ESummary API (lighter weight than EFetch).

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of summary dictionaries
        """
        if not pmids:
            return []

        id_list = ",".join(pmids)
        params = self._build_params({
            "db": "pubmed",
            "id": id_list,
            "retmode": "xml",
        })

        url = f"{self.base_url}/esummary.fcgi?{urlencode(params)}"

        try:
            logger.info(f"Fetching summaries for {len(pmids)} papers")
            await self._enforce_rate_limit()

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_data = response.text

            summaries = self._parse_esummary_response(xml_data)
            logger.info(f"Retrieved {len(summaries)} summaries")
            return summaries

        except httpx.TimeoutException as e:
            logger.error(f"PubMed API timeout: {e}")
            raise PubMedAPITimeoutError(f"PubMed API request timed out: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"PubMed API HTTP error: {e}")
            raise PubMedAPIException(f"PubMed API returned error {e.response.status_code}: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch summaries from PubMed: {e}")
            raise PubMedAPIException(f"Unexpected error fetching summaries from PubMed: {e}")

    def _parse_esearch_response(self, xml_data: str) -> List[str]:
        """Parse ESearch XML response to extract PMIDs."""
        try:
            root = ET.fromstring(xml_data)
            id_list = root.find("IdList")
            if id_list is None:
                return []

            pmids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]
            return pmids

        except ET.ParseError as e:
            logger.error(f"Failed to parse ESearch XML response: {e}")
            raise PubMedParseError(f"Failed to parse ESearch XML response: {e}")

    def _parse_efetch_response(self, xml_data: str) -> List[PubMedPaper]:
        """Parse EFetch XML response to extract full paper details."""
        try:
            root = ET.fromstring(xml_data)
            articles = root.findall(".//PubmedArticle")

            papers = []
            for article in articles:
                paper = self._parse_pubmed_article(article)
                if paper:
                    papers.append(paper)

            return papers

        except ET.ParseError as e:
            logger.error(f"Failed to parse EFetch XML response: {e}")
            raise PubMedParseError(f"Failed to parse EFetch XML response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing EFetch response: {e}")
            raise PubMedParseError(f"Unexpected error parsing EFetch response: {e}")

    def _parse_pubmed_article(self, article: ET.Element) -> Optional[PubMedPaper]:
        """Parse a single PubmedArticle XML element."""
        try:
            medline_citation = article.find("MedlineCitation")
            if medline_citation is None:
                return None

            # PMID
            pmid_elem = medline_citation.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None and pmid_elem.text else None
            if not pmid:
                return None

            # Article metadata
            article_elem = medline_citation.find("Article")
            if article_elem is None:
                return None

            # Title
            title_elem = article_elem.find("ArticleTitle")
            title = title_elem.text if title_elem is not None and title_elem.text else ""

            # Abstract
            abstract_elem = article_elem.find("Abstract/AbstractText")
            abstract = ""
            if abstract_elem is not None:
                # Handle structured abstracts
                abstract_parts = article_elem.findall("Abstract/AbstractText")
                if len(abstract_parts) > 1:
                    # Structured abstract
                    abstract_texts = []
                    for part in abstract_parts:
                        label = part.get("Label", "")
                        text = part.text or ""
                        if label:
                            abstract_texts.append(f"{label}: {text}")
                        else:
                            abstract_texts.append(text)
                    abstract = " ".join(abstract_texts)
                else:
                    abstract = abstract_elem.text or ""

            # Authors
            authors = []
            author_list = article_elem.find("AuthorList")
            if author_list is not None:
                for author_elem in author_list.findall("Author"):
                    lastname = author_elem.find("LastName")
                    forename = author_elem.find("ForeName")
                    if lastname is not None and lastname.text:
                        name = lastname.text
                        if forename is not None and forename.text:
                            name = f"{forename.text} {name}"
                        authors.append(name)

            # Journal
            journal_elem = article_elem.find("Journal/Title")
            journal = journal_elem.text if journal_elem is not None and journal_elem.text else ""

            # Publication date
            pub_date_elem = article_elem.find("Journal/JournalIssue/PubDate")
            pub_date = self._extract_pub_date(pub_date_elem)

            # DOI
            doi = ""
            article_id_list = article.find("PubmedData/ArticleIdList")
            if article_id_list is not None:
                for article_id in article_id_list.findall("ArticleId"):
                    if article_id.get("IdType") == "doi" and article_id.text:
                        doi = article_id.text
                        break

            # PMC ID (for potential full-text access)
            pmc_id = ""
            if article_id_list is not None:
                for article_id in article_id_list.findall("ArticleId"):
                    if article_id.get("IdType") == "pmc" and article_id.text:
                        pmc_id = article_id.text
                        break

            # MeSH terms (Medical Subject Headings - useful categories)
            mesh_terms = []
            mesh_list = medline_citation.find("MeshHeadingList")
            if mesh_list is not None:
                for mesh_heading in mesh_list.findall("MeshHeading"):
                    descriptor = mesh_heading.find("DescriptorName")
                    if descriptor is not None and descriptor.text:
                        mesh_terms.append(descriptor.text)

            # Publication types
            pub_types = []
            pub_type_list = article_elem.find("PublicationTypeList")
            if pub_type_list is not None:
                for pub_type in pub_type_list.findall("PublicationType"):
                    if pub_type.text:
                        pub_types.append(pub_type.text)

            # Build full-text URL if PMC ID is available
            full_text_url = ""
            if pmc_id:
                full_text_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/"

            return PubMedPaper(
                pmid=pmid,
                title=title,
                authors=authors,
                abstract=abstract,
                journal=journal,
                published_date=pub_date,
                doi=doi,
                pmc_id=pmc_id,
                mesh_terms=mesh_terms,
                publication_types=pub_types,
                full_text_url=full_text_url,
            )

        except Exception as e:
            logger.error(f"Failed to parse PubmedArticle: {e}")
            return None

    def _extract_pub_date(self, pub_date_elem: Optional[ET.Element]) -> str:
        """Extract publication date from PubDate element."""
        if pub_date_elem is None:
            return ""

        year = pub_date_elem.find("Year")
        month = pub_date_elem.find("Month")
        day = pub_date_elem.find("Day")

        # Try MedlineDate if structured date not available
        if year is None:
            medline_date = pub_date_elem.find("MedlineDate")
            if medline_date is not None and medline_date.text:
                return medline_date.text

        # Build structured date
        date_parts = []
        if year is not None and year.text:
            date_parts.append(year.text)
        if month is not None and month.text:
            date_parts.append(month.text)
        if day is not None and day.text:
            date_parts.append(day.text)

        return "-".join(date_parts) if date_parts else ""

    def _parse_esummary_response(self, xml_data: str) -> List[Dict]:
        """Parse ESummary XML response to extract paper summaries."""
        try:
            root = ET.fromstring(xml_data)
            doc_sums = root.findall(".//DocSum")

            summaries = []
            for doc_sum in doc_sums:
                summary = {}
                id_elem = doc_sum.find("Id")
                if id_elem is not None and id_elem.text:
                    summary["pmid"] = id_elem.text

                for item in doc_sum.findall("Item"):
                    name = item.get("Name")
                    value = item.text
                    if name and value:
                        summary[name] = value

                if summary:
                    summaries.append(summary)

            return summaries

        except ET.ParseError as e:
            logger.error(f"Failed to parse ESummary XML response: {e}")
            raise PubMedParseError(f"Failed to parse ESummary XML response: {e}")

    async def download_pdf(self, paper: PubMedPaper, force_download: bool = False) -> Optional[Path]:
        """
        Download full-text PDF if available (from PMC or publisher).

        Note: Not all papers have PDFs available through open access.
        For papers with PMC IDs, we can try to get the PDF from PMC OA.

        Args:
            paper: PubMedPaper object
            force_download: Force re-download even if file exists

        Returns:
            Path to downloaded PDF file or None if download failed or not available
        """
        if not paper.pmc_id:
            logger.info(f"No PMC ID for paper {paper.pmid}, cannot download PDF")
            return None

        pdf_path = self._get_pdf_path(paper.pmid)

        # Return cached PDF if exists
        if pdf_path.exists() and not force_download:
            logger.info(f"Using cached PDF: {pdf_path.name}")
            return pdf_path

        # Try PMC Open Access PDF
        pmc_pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{paper.pmc_id}/pdf/"

        if await self._download_with_retry(pmc_pdf_url, pdf_path):
            return pdf_path
        else:
            logger.info(f"PDF not available for paper {paper.pmid}")
            return None

    def _get_pdf_path(self, pmid: str) -> Path:
        """Get the local path for a PDF file."""
        safe_filename = pmid.replace("/", "_") + ".pdf"
        return self.pdf_cache_dir / safe_filename

    async def _download_with_retry(self, url: str, path: Path, max_retries: Optional[int] = None) -> bool:
        """Download a file with retry logic."""
        if max_retries is None:
            max_retries = self._settings.download_max_retries

        logger.info(f"Attempting to download PDF from {url}")

        # Respect rate limits
        await asyncio.sleep(self.rate_limit_delay)

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout_seconds), follow_redirects=True) as client:
                    async with client.stream("GET", url) as response:
                        # PMC may return 404 or other errors if PDF not available
                        if response.status_code == 404:
                            logger.info(f"PDF not found at {url}")
                            return False

                        response.raise_for_status()

                        with open(path, "wb") as f:
                            async for chunk in response.aiter_bytes():
                                f.write(chunk)

                logger.info(f"Successfully downloaded to {path.name}")
                return True

            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    wait_time = self._settings.download_retry_delay_base * (attempt + 1)
                    logger.warning(f"PDF download timeout (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"PDF download failed after {max_retries} attempts due to timeout: {e}")
                    return False

            except httpx.HTTPStatusError as e:
                # Don't retry on 404 or similar errors
                if e.response.status_code in [404, 403]:
                    logger.info(f"PDF not accessible (status {e.response.status_code})")
                    return False

                if attempt < max_retries - 1:
                    wait_time = self._settings.download_retry_delay_base * (attempt + 1)
                    logger.warning(f"Download failed (attempt {attempt + 1}/{max_retries}): {e}")
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed after {max_retries} attempts: {e}")
                    return False

            except Exception as e:
                logger.error(f"Unexpected download error: {e}")
                return False

        # Clean up partial download
        if path.exists():
            path.unlink()

        return False


