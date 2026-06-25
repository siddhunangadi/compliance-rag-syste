from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """A semantic search request over the current user's documents."""

    query: str = Field(
        min_length=3,
        max_length=1000,
        description="Natural-language search query.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of matching chunks to return.",
    )


class SearchResult(BaseModel):
    """One retrieved document chunk."""

    document_id: str
    file_name: str
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    """Semantic search results for one query."""

    query: str
    results: list[SearchResult]