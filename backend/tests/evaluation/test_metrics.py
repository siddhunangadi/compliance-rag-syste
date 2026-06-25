from evaluation.metrics import (
    evaluate_case,
    recall_at_k,
    reciprocal_rank,
    summarize_case_metrics,
)


def make_result(
    document_id: str,
    chunk_index: int,
) -> dict:
    return {
        "document_id": document_id,
        "chunk_index": chunk_index,
    }


def test_recall_at_k_returns_one_when_expected_chunk_is_retrieved() -> None:
    results = [
        make_result("document-a", 2),
        make_result("document-a", 7),
    ]

    assert recall_at_k(
        results,
        expected_document_id="document-a",
        expected_chunk_indexes=[7],
        k=5,
    ) == 1.0


def test_recall_at_k_returns_zero_when_expected_chunk_is_not_retrieved() -> None:
    results = [
        make_result("document-a", 2),
        make_result("document-b", 7),
    ]

    assert recall_at_k(
        results,
        expected_document_id="document-a",
        expected_chunk_indexes=[9],
        k=5,
    ) == 0.0


def test_reciprocal_rank_uses_first_relevant_result_rank() -> None:
    results = [
        make_result("document-a", 1),
        make_result("document-a", 2),
        make_result("document-a", 7),
    ]

    assert reciprocal_rank(
        results,
        expected_document_id="document-a",
        expected_chunk_indexes=[7],
    ) == 1 / 3


def test_evaluate_case_returns_case_metrics() -> None:
    case = {
        "id": "case-1",
        "question": "What is the retention period?",
        "expected_document_id": "document-a",
        "expected_chunk_indexes": [3],
        "category": "policy_requirement",
    }

    results = [
        make_result("document-a", 3),
    ]

    metrics = evaluate_case(
        case=case,
        results=results,
        k=5,
    )

    assert metrics["id"] == "case-1"
    assert metrics["recall_at_k"] == 1.0
    assert metrics["reciprocal_rank"] == 1.0


def test_summarize_case_metrics_calculates_average_metrics() -> None:
    summary = summarize_case_metrics(
        [
            {
                "recall_at_k": 1.0,
                "reciprocal_rank": 1.0,
            },
            {
                "recall_at_k": 0.0,
                "reciprocal_rank": 0.5,
            },
        ]
    )

    assert summary == {
        "case_count": 2,
        "recall_at_5": 0.5,
        "mrr": 0.75,
    }
