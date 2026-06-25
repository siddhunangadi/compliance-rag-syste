from pydantic import BaseModel, Field
from typing import List, Optional


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Question asked about uploaded compliance documents."
    )

    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of document IDs to search within."
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of relevant chunks to retrieve."
    )


class Citation(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    page_number: Optional[int] = None
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    retrieval_score: float
    grounded: bool