from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def is_relevant(
    result: dict[str, Any],
    expected_document_id: str,
    expected_chunk_indexes: Sequence[int],
) -> bool:
    """Return whether one retrieved result matches expected evidence."""
    return (
        str(result.get("document_id")) == expected_document_id
        and int(result.get("chunk_index", -1)) in expected_chunk_indexes
    )


def recall_at_k(
    results: Sequence[dict[str, Any]],
    *,
    expected_document_id: str,
    expected_chunk_indexes: Sequence[int],
    k: int,
) -> float:
    """Return 1.0 when any expected chunk appears in the first k results."""
    return float(
        any(
            is_relevant(
                result,
                expected_document_id,
                expected_chunk_indexes,
            )
            for result in results[:k]
        )
    )


def reciprocal_rank(
    results: Sequence[dict[str, Any]],
    *,
    expected_document_id: str,
    expected_chunk_indexes: Sequence[int],
) -> float:
    """Return reciprocal rank of the first expected evidence chunk."""
    for rank, result in enumerate(results, start=1):
        if is_relevant(
            result,
            expected_document_id,
            expected_chunk_indexes,
        ):
            return 1.0 / rank

    return 0.0


def evaluate_case(
    *,
    case: dict[str, Any],
    results: Sequence[dict[str, Any]],
    k: int = 5,
) -> dict[str, Any]:
    """Calculate retrieval metrics for one golden evaluation case."""
    expected_document_id = str(case["expected_document_id"])
    expected_chunk_indexes = [
        int(chunk_index)
        for chunk_index in case["expected_chunk_indexes"]
    ]

    return {
        "id": case["id"],
        "question": case["question"],
        "category": case.get("category", "uncategorized"),
        "recall_at_k": recall_at_k(
            results,
            expected_document_id=expected_document_id,
            expected_chunk_indexes=expected_chunk_indexes,
            k=k,
        ),
        "reciprocal_rank": reciprocal_rank(
            results,
            expected_document_id=expected_document_id,
            expected_chunk_indexes=expected_chunk_indexes,
        ),
        "retrieved_count": len(results),
    }


def summarize_case_metrics(
    case_metrics: Sequence[dict[str, Any]],
) -> dict[str, float | int]:
    """Aggregate retrieval metrics across all evaluated cases."""
    if not case_metrics:
        return {
            "case_count": 0,
            "recall_at_5": 0.0,
            "mrr": 0.0,
        }

    case_count = len(case_metrics)

    return {
        "case_count": case_count,
        "recall_at_5": round(
            sum(float(metric["recall_at_k"]) for metric in case_metrics)
            / case_count,
            4,
        ),
        "mrr": round(
            sum(float(metric["reciprocal_rank"]) for metric in case_metrics)
            / case_count,
            4,
        ),
    }
