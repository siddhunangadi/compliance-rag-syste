from app.services.supabase_service import SupabaseService


class FakeResponse:
    """Fake response returned by the Supabase query chain."""

    def __init__(self, data: list[dict[str, str]] | None) -> None:
        self.data = data


class FakeQuery:
    """Fake query builder that mimics the methods we use."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def select(self, columns: str) -> "FakeQuery":
        return self

    def limit(self, count: int) -> "FakeQuery":
        return self

    def execute(self) -> FakeResponse:
        return self.response


class FakeSupabaseClient:
    """Fake Supabase client used only in tests."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.table_name: str | None = None

    def table(self, table_name: str) -> FakeQuery:
        self.table_name = table_name
        return FakeQuery(self.response)


def test_check_connection_returns_true_when_query_returns_data() -> None:
    fake_client = FakeSupabaseClient(FakeResponse(data=[]))

    service = SupabaseService(client=fake_client)  # type: ignore[arg-type]

    assert service.check_connection() is True
    assert fake_client.table_name == "documents"


def test_check_connection_returns_false_when_query_returns_no_data() -> None:
    fake_client = FakeSupabaseClient(FakeResponse(data=None))

    service = SupabaseService(client=fake_client)  # type: ignore[arg-type]

    assert service.check_connection() is False