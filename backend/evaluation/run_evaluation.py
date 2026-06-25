from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.services.retrieval_service import RetrievalService
from evaluation.metrics import evaluate_case, summarize_case_metrics


DEFAULT_DATASET_PATH = Path("backend/evaluation/golden_dataset.json")


def load_dataset(dataset_path: Path) -> dict[str, Any]:
    """Load and validate the golden evaluation dataset."""
    with dataset_path.open(encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)

    cases = dataset.get("cases")

    if not isinstance(cases, list) or not cases:
        raise ValueError("Golden dataset must contain at least one case.")

    return dataset


def validate_case(case: dict[str, Any]) -> None:
    """Reject placeholder cases before they produce misleading metrics."""
    required_fields = (
        "id",
        "question",
        "expected_document_id",
        "expected_chunk_indexes",
    )

    missing_fields = [
        field
        for field in required_fields
        if not case.get(field)
    ]

    if missing_fields:
        raise ValueError(
            f"Case '{case.get('id', 'unknown')}' is missing: "
            f"{', '.join(missing_fields)}."
        )

    if str(case["expected_document_id"]).startswith("replace-with-"):
        raise ValueError(
            f"Case '{case['id']}' still has a placeholder document ID."
        )


def run_evaluation(
    *,
    dataset: dict[str, Any],
    user_id: str,
    top_k: int,
) -> dict[str, Any]:
    """Run retrieval evaluation against one authenticated user's corpus."""
    retrieval_service = RetrievalService()
    case_metrics: list[dict[str, Any]] = []

    for case in dataset["cases"]:
        validate_case(case)

        started_at = time.perf_counter()

        results = retrieval_service.search(
            query=case["question"],
            user_id=user_id,
            top_k=top_k,
        )

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

        metric = evaluate_case(
            case=case,
            results=results,
            k=top_k,
        )

        metric["latency_ms"] = latency_ms
        metric["retrieved_results"] = [
            {
                "document_id": result["document_id"],
                "file_name": result["file_name"],
                "page_number": result.get("page_number", 1),
                "chunk_index": result["chunk_index"],
                "score": result["score"],
            }
            for result in results
        ]

        case_metrics.append(metric)

    summary = summarize_case_metrics(case_metrics)

    summary["average_latency_ms"] = round(
        sum(float(metric["latency_ms"]) for metric in case_metrics)
        / len(case_metrics),
        2,
    )

    return {
        "dataset_version": dataset.get("version", "unknown"),
        "top_k": top_k,
        "summary": summary,
        "cases": case_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Compliance RAG retrieval quality."
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="User ID that owns the golden evaluation documents.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the golden evaluation dataset JSON file.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieval results to evaluate.",
    )

    args = parser.parse_args()

    try:
        dataset = load_dataset(args.dataset)
        report = run_evaluation(
            dataset=dataset,
            user_id=args.user_id,
            top_k=args.top_k,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
