from datetime import datetime, timedelta, timezone

import pytest

from app.services.ingestion_job_service import (
    MAX_RETRY_JOBS_PER_DOCUMENT,
    RETRY_COOLDOWN_SECONDS,
    STALE_PROCESSING_AFTER_MINUTES,
    IngestionJobService,
    RetryNotAllowedError,
)


class FakeQuery:
    def __init__(self, response_data: list[dict]) -> None:
        self.response_data = response_data
        self.filters: list[tuple[str, str, str]] = []

    def select(self, columns: str) -> "FakeQuery":
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        self.filters.append(("eq", column, value))
        return self

    def lt(self, column: str, value: str) -> "FakeQuery":
        self.filters.append(("lt", column, value))
        return self

    def order(self, column: str, desc: bool = False) -> "FakeQuery":
        return self

    def limit(self, count: int) -> "FakeQuery":
        return self

    def maybe_single(self) -> "FakeQuery":
        return self

    def execute(self):
        class Response:
            def __init__(self, data: list[dict]) -> None:
                self.data = data

        return Response(self.response_data)


class FakeSupabaseClient:
    def __init__(
        self,
        queued_jobs: list[dict],
        stale_processing_jobs: list[dict],
    ) -> None:
        self.queued_query = FakeQuery(queued_jobs)
        self.stale_processing_query = FakeQuery(stale_processing_jobs)
        self.table_call_count = 0

    def table(self, table_name: str):
        assert table_name == "ingestion_jobs"

        self.table_call_count += 1

        if self.table_call_count == 1:
            return self.queued_query

        return self.stale_processing_query


def make_job(
    *,
    job_id: str,
    status: str,
    created_at: datetime,
) -> dict:
    return {
        "id": job_id,
        "document_id": "document-1",
        "user_id": "user-1",
        "status": status,
        "attempt_count": 1,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "created_at": created_at.isoformat(),
        "updated_at": created_at.isoformat(),
    }


def test_get_recoverable_jobs_returns_queued_and_stale_processing_jobs(
    monkeypatch,
) -> None:
    queued_job = {
        "id": "queued-job",
        "document_id": "document-1",
        "user_id": "user-1",
        "status": "queued",
    }

    stale_processing_job = {
        "id": "stale-job",
        "document_id": "document-2",
        "user_id": "user-2",
        "status": "processing",
    }

    fake_client = FakeSupabaseClient(
        queued_jobs=[queued_job],
        stale_processing_jobs=[stale_processing_job],
    )

    monkeypatch.setattr(
        "app.services.ingestion_job_service.get_supabase_service_client",
        lambda: fake_client,
    )

    service = IngestionJobService()

    recoverable_jobs = service.get_recoverable_jobs()

    assert recoverable_jobs == [
        queued_job,
        stale_processing_job,
    ]

    assert fake_client.queued_query.filters == [
        ("eq", "status", "queued"),
    ]

    assert fake_client.stale_processing_query.filters[0] == (
        "eq",
        "status",
        "processing",
    )

    assert fake_client.stale_processing_query.filters[1][0] == "lt"
    assert fake_client.stale_processing_query.filters[1][1] == "started_at"

    stale_before = datetime.fromisoformat(
        fake_client.stale_processing_query.filters[1][2]
    )

    expected_lower_bound = (
        datetime.now(timezone.utc)
        - timedelta(minutes=STALE_PROCESSING_AFTER_MINUTES + 1)
    )

    expected_upper_bound = (
        datetime.now(timezone.utc)
        - timedelta(minutes=STALE_PROCESSING_AFTER_MINUTES - 1)
    )

    assert expected_lower_bound <= stale_before <= expected_upper_bound


def test_get_recoverable_jobs_returns_empty_list_when_nothing_is_stuck(
    monkeypatch,
) -> None:
    fake_client = FakeSupabaseClient(
        queued_jobs=[],
        stale_processing_jobs=[],
    )

    monkeypatch.setattr(
        "app.services.ingestion_job_service.get_supabase_service_client",
        lambda: fake_client,
    )

    service = IngestionJobService()

    recoverable_jobs = service.get_recoverable_jobs()

    assert recoverable_jobs == []


def test_create_retry_job_rejects_when_an_active_job_exists(
    monkeypatch,
) -> None:
    service = IngestionJobService()

    monkeypatch.setattr(
        service,
        "get_jobs_for_document",
        lambda **kwargs: [
            make_job(
                job_id="active-job",
                status="processing",
                created_at=datetime.now(timezone.utc)
                - timedelta(minutes=5),
            )
        ],
    )

    with pytest.raises(
        RetryNotAllowedError,
        match="already has an active ingestion job",
    ):
        service.create_retry_job(
            document_id="document-1",
            user_id="user-1",
        )


def test_create_retry_job_rejects_when_retry_limit_is_reached(
    monkeypatch,
) -> None:
    service = IngestionJobService()

    old_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    jobs = [
        make_job(
            job_id="retry-3",
            status="failed",
            created_at=old_time,
        ),
        make_job(
            job_id="retry-2",
            status="failed",
            created_at=old_time - timedelta(minutes=1),
        ),
        make_job(
            job_id="retry-1",
            status="failed",
            created_at=old_time - timedelta(minutes=2),
        ),
        make_job(
            job_id="original",
            status="failed",
            created_at=old_time - timedelta(minutes=3),
        ),
    ]

    monkeypatch.setattr(
        service,
        "get_jobs_for_document",
        lambda **kwargs: jobs,
    )

    with pytest.raises(
        RetryNotAllowedError,
        match="Retry limit reached",
    ):
        service.create_retry_job(
            document_id="document-1",
            user_id="user-1",
        )


def test_create_retry_job_rejects_during_cooldown(
    monkeypatch,
) -> None:
    service = IngestionJobService()

    latest_job_time = datetime.now(timezone.utc) - timedelta(
        seconds=RETRY_COOLDOWN_SECONDS - 5
    )

    monkeypatch.setattr(
        service,
        "get_jobs_for_document",
        lambda **kwargs: [
            make_job(
                job_id="latest-failed-job",
                status="failed",
                created_at=latest_job_time,
            )
        ],
    )

    with pytest.raises(
        RetryNotAllowedError,
        match="Please wait",
    ):
        service.create_retry_job(
            document_id="document-1",
            user_id="user-1",
        )


def test_create_retry_job_creates_job_when_policy_allows(
    monkeypatch,
) -> None:
    service = IngestionJobService()

    old_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    monkeypatch.setattr(
        service,
        "get_jobs_for_document",
        lambda **kwargs: [
            make_job(
                job_id="original-failed-job",
                status="failed",
                created_at=old_time,
            )
        ],
    )

    created_jobs: list[dict] = []

    def fake_create_job(*, document_id: str, user_id: str) -> dict:
        created_job = {
            "id": "new-retry-job",
            "document_id": document_id,
            "user_id": user_id,
            "status": "queued",
        }
        created_jobs.append(created_job)
        return created_job

    monkeypatch.setattr(
        service,
        "create_job",
        fake_create_job,
    )

    job = service.create_retry_job(
        document_id="document-1",
        user_id="user-1",
    )

    assert job == {
        "id": "new-retry-job",
        "document_id": "document-1",
        "user_id": "user-1",
        "status": "queued",
    }

    assert created_jobs == [job]


def test_retry_policy_constants_are_safe_defaults() -> None:
    assert MAX_RETRY_JOBS_PER_DOCUMENT == 3
    assert RETRY_COOLDOWN_SECONDS == 30