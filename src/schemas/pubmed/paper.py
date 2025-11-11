from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PubMedPaper(BaseModel):
    """Schema for PubMed API response data."""

    pmid: str = Field(..., description="PubMed ID")
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(default_factory=list, description="List of author names")
    abstract: str = Field(default="", description="Paper abstract")
    journal: str = Field(default="", description="Journal name")
    published_date: str = Field(default="", description="Publication date")
    doi: str = Field(default="", description="DOI")
    pmc_id: str = Field(default="", description="PubMed Central ID")
    mesh_terms: List[str] = Field(default_factory=list, description="MeSH (Medical Subject Headings) terms")
    publication_types: List[str] = Field(default_factory=list, description="Publication types")
    full_text_url: str = Field(default="", description="URL to full text (if available)")


class PaperBase(BaseModel):
    # Core PubMed metadata
    pmid: str = Field(..., description="PubMed ID")
    title: str = Field(..., description="Paper title")
    authors: List[str] = Field(..., description="List of author names")
    abstract: str = Field(..., description="Paper abstract")
    journal: str = Field(default="", description="Journal name")
    published_date: datetime = Field(..., description="Publication date")
    doi: str = Field(default="", description="DOI")
    pmc_id: str = Field(default="", description="PubMed Central ID")
    mesh_terms: List[str] = Field(default_factory=list, description="MeSH terms")
    publication_types: List[str] = Field(default_factory=list, description="Publication types")
    full_text_url: str = Field(default="", description="URL to full text")


class PaperCreate(PaperBase):
    """Schema for creating a paper with optional parsed content."""

    # Parsed full-text content (optional - added when full text is processed)
    raw_text: Optional[str] = Field(None, description="Full raw text extracted from PDF/HTML")
    sections: Optional[List[Dict[str, Any]]] = Field(None, description="List of sections with titles and content")
    references: Optional[List[Dict[str, Any]]] = Field(None, description="List of references if extracted")

    # Processing metadata (optional)
    parser_used: Optional[str] = Field(None, description="Which parser was used (DOCLING, etc.)")
    parser_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional parser metadata")
    content_processed: Optional[bool] = Field(False, description="Whether content was successfully processed")
    content_processing_date: Optional[datetime] = Field(None, description="When content was processed")


class PaperResponse(PaperBase):
    """Schema for paper API responses with all content."""

    id: UUID

    # Parsed content (optional fields)
    raw_text: Optional[str] = Field(None, description="Full raw text extracted")
    sections: Optional[List[Dict[str, Any]]] = Field(None, description="List of sections with titles and content")
    references: Optional[List[Dict[str, Any]]] = Field(None, description="List of references if extracted")

    # Processing metadata
    parser_used: Optional[str] = Field(None, description="Which parser was used")
    parser_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional parser metadata")
    content_processed: bool = Field(False, description="Whether content was successfully processed")
    content_processing_date: Optional[datetime] = Field(None, description="When content was processed")

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperSearchResponse(BaseModel):
    papers: List[PaperResponse]
    total: int


