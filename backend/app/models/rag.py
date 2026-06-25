from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=2_000,
        description="Question to answer from uploaded compliance documents.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of document chunks to retrieve.",
    )


class Citation(BaseModel):
    source_number: int
    file_name: str
    page_number: int
    chunk_index: int
    score: float
    excerpt: str


class AskQuestionResponse(BaseModel):
    answer: str
    citations: list[Citation]