from typing import List, Optional

from pydantic import BaseModel, Field


class ChunkInfo(BaseModel):
    """Information about a retrieved chunk."""
    arxiv_id: str = Field(..., description="arXiv ID of the paper")
    chunk_text: str = Field(..., description="The actual text passage retrieved")
    pdf_url: str = Field(..., description="PDF URL for the paper")
    chunk_index: int = Field(..., description="Index of this chunk (for citation [1], [2], etc.)")


class AskRequest(BaseModel):
    """Request model for RAG question answering."""

    query: str = Field(..., description="User's question", min_length=1, max_length=1000)
    top_k: int = Field(3, description="Number of top chunks to retrieve", ge=1, le=10)
    use_hybrid: bool = Field(True, description="Use hybrid search (BM25 + vector)")
    model: str = Field("llama3.2:1b", description="Ollama model to use for generation")
    categories: Optional[List[str]] = Field(None, description="Filter by arXiv categories")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "top_k": 3,
                "use_hybrid": True,
                "model": "llama3.2:1b",
                "categories": ["cs.AI", "cs.LG"],
            }
        }


class AskResponse(BaseModel):
    """Response model for RAG question answering."""

    query: str = Field(..., description="Original user question")
    answer: str = Field(..., description="Generated answer from LLM")
    sources: List[str] = Field(..., description="PDF URLs of source papers")
    chunks: List[ChunkInfo] = Field(..., description="Retrieved chunks with text passages")
    chunks_used: int = Field(..., description="Number of chunks used for generation")
    search_mode: str = Field(..., description="Search mode used: bm25 or hybrid")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "answer": "Transformers are a neural network architecture [1]...",
                "sources": ["https://arxiv.org/pdf/1706.03762.pdf", "https://arxiv.org/pdf/1810.04805.pdf"],
                "chunks": [
                    {
                        "arxiv_id": "1706.03762",
                        "chunk_text": "The transformer architecture...",
                        "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                        "chunk_index": 1
                    }
                ],
                "chunks_used": 3,
                "search_mode": "hybrid",
            }
        }
