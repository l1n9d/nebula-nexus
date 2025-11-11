import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from src.db.interfaces.postgresql import Base


class Paper(Base):
    __tablename__ = "papers"

    # Core paper metadata (now using PubMed fields)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pmid = Column(String, unique=True, nullable=False, index=True)  # Changed from arxiv_id
    title = Column(String, nullable=False)
    authors = Column(JSON, nullable=False)
    abstract = Column(Text, nullable=False)
    journal = Column(String, nullable=True)  # Journal name
    published_date = Column(DateTime, nullable=False)
    doi = Column(String, nullable=True)
    pmc_id = Column(String, nullable=True)  # PubMed Central ID
    mesh_terms = Column(JSON, nullable=True)  # Medical Subject Headings
    publication_types = Column(JSON, nullable=True)  # Publication types
    full_text_url = Column(String, nullable=True)  # URL to full text
    
    # Legacy field for backward compatibility (can be removed if not needed)
    arxiv_id = Column(String, unique=True, nullable=True, index=True)

    # Parsed content (PDF or HTML)
    raw_text = Column(Text, nullable=True)
    sections = Column(JSON, nullable=True)
    references = Column(JSON, nullable=True)

    # Content processing metadata
    parser_used = Column(String, nullable=True)
    parser_metadata = Column(JSON, nullable=True)
    content_processed = Column(Boolean, default=False, nullable=False)
    content_processing_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
