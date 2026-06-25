import pytest

from app.services.text_extraction_service import (
    TextExtractionService,
    UnsupportedDocumentTypeError,
)


def test_extracts_text_from_txt_file() -> None:
    service = TextExtractionService()

    result = service.extract_text(
        file_name="policy.txt",
        file_bytes=b"Employees must complete annual compliance training.",
    )

    assert result == "Employees must complete annual compliance training."


def test_extract_document_returns_page_one_for_txt_file() -> None:
    service = TextExtractionService()

    result = service.extract_document(
        file_name="policy.txt",
        file_bytes=b"Employees must complete annual compliance training.",
    )

    assert result.page_count == 1
    assert result.pages == [
        {
            "page_number": 1,
            "text": "Employees must complete annual compliance training.",
        }
    ]


def test_replaces_invalid_utf8_bytes_in_txt_file() -> None:
    service = TextExtractionService()

    result = service.extract_text(
        file_name="policy.txt",
        file_bytes=b"Compliance policy: \xff",
    )

    assert "Compliance policy:" in result


def test_rejects_unsupported_file_type() -> None:
    service = TextExtractionService()

    with pytest.raises(UnsupportedDocumentTypeError):
        service.extract_text(
            file_name="spreadsheet.xlsx",
            file_bytes=b"not a real spreadsheet",
        )
