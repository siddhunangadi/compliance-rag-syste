import re

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import ClientError

from app.api.dependencies import get_current_user
from app.api.rate_limit import enforce_user_rate_limit
from app.models.auth import CurrentUser
from app.models.rag import AskQuestionRequest, AskQuestionResponse, Citation
from app.services.rag_answer_service import RAGAnswerService
from app.services.retrieval_service import retrieval_service


router = APIRouter(prefix="/rag", tags=["RAG"])

rag_answer_service = RAGAnswerService()

NOT_FOUND_ANSWER = "I could not find an answer in your uploaded documents."
GENERATION_RATE_LIMIT_MESSAGE = (
    "The AI answer service is temporarily rate-limited. "
    "Please wait a moment and try again."
)

CITATION_PATTERN = re.compile(r"\[(\d+)\]")
RETRY_DELAY_PATTERN = re.compile(
    r"(?:retry in|retryDelay['\"]?\s*:\s*['\"]?)(\d+)(?:\.\d+)?s",
    re.IGNORECASE,
)


def extract_citation_numbers(answer: str) -> list[int]:
    """Return citation numbers in first-appearance order without duplicates."""
    seen_numbers = set()
    citation_numbers = []

    for match in CITATION_PATTERN.finditer(answer):
        source_number = int(match.group(1))

        if source_number not in seen_numbers:
            seen_numbers.add(source_number)
            citation_numbers.append(source_number)

    return citation_numbers


def answer_has_valid_citations(
    *,
    answer: str,
    source_count: int,
) -> bool:
    """Return True only when the answer cites valid retrieved source numbers."""
    citation_numbers = extract_citation_numbers(answer)

    if not citation_numbers:
        return False

    return all(
        1 <= source_number <= source_count
        for source_number in citation_numbers
    )


def get_retry_after_seconds(error: ClientError) -> int | None:
    """
    Extract Gemini's suggested retry delay when it is present.

    Gemini errors commonly include text such as:
    "Please retry in 49.19s."
    """
    match = RETRY_DELAY_PATTERN.search(str(error))

    if not match:
        return None

    return max(int(match.group(1)), 1)


def is_gemini_rate_limit_error(error: ClientError) -> bool:
    """Return True when Gemini rejected the request because of quota/rate limits."""
    error_text = str(error).upper()

    return (
        getattr(error, "code", None) == 429
        or "RESOURCE_EXHAUSTED" in error_text
        or "QUOTA EXCEEDED" in error_text
        or "TOO MANY REQUESTS" in error_text
    )


@router.post(
    "/ask",
    response_model=AskQuestionResponse,
    summary="Ask a question about my compliance documents",
)
def ask_question(
    payload: AskQuestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> AskQuestionResponse:
    """Retrieve evidence and generate a grounded answer."""
    enforce_user_rate_limit(
        user_id=current_user.id,
        action="rag_ask",
        limit=30,
        window_seconds=600,
    )

    sources = retrieval_service.search(
        user_id=current_user.id,
        query=payload.question,
        top_k=payload.top_k,
    )

    if not sources:
        return AskQuestionResponse(
            answer=NOT_FOUND_ANSWER,
            citations=[],
        )

    try:
        answer = rag_answer_service.generate_answer(
            question=payload.question,
            sources=sources,
        )
    except ClientError as error:
        if is_gemini_rate_limit_error(error):
            retry_after_seconds = get_retry_after_seconds(error)

            headers = {}

            if retry_after_seconds is not None:
                headers["Retry-After"] = str(retry_after_seconds)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=GENERATION_RATE_LIMIT_MESSAGE,
                headers=headers,
            ) from error

        raise

    if not answer_has_valid_citations(
        answer=answer,
        source_count=len(sources),
    ):
        return AskQuestionResponse(
            answer=NOT_FOUND_ANSWER,
            citations=[],
        )

    used_source_numbers = extract_citation_numbers(answer)

    citations = [
        Citation(
            source_number=source_number,
            file_name=sources[source_number - 1]["file_name"],
            page_number=int(sources[source_number - 1].get("page_number", 1)),
            chunk_index=sources[source_number - 1]["chunk_index"],
            score=sources[source_number - 1]["score"],
            excerpt=sources[source_number - 1]["content"][:500],
        )
        for source_number in used_source_numbers
    ]

    return AskQuestionResponse(
        answer=answer,
        citations=citations,
    )