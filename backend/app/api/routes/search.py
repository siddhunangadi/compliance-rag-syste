from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.auth import CurrentUser
from app.models.search import SearchRequest, SearchResponse, SearchResult
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "",
    response_model=SearchResponse,
    summary="Search my compliance documents",
)
def search_documents(
    payload: SearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> SearchResponse:
    """Return semantic matches from the current user's documents."""
    results = retrieval_service.search(
        user_id=current_user.id,
        query=payload.query,
        top_k=payload.top_k,
    )

    return SearchResponse(
        query=payload.query,
        results=[SearchResult(**result) for result in results],
    )