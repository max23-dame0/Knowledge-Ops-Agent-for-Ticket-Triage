"""Offline unit tests for ticket lookup tools (reads local data/tickets.json)."""

from __future__ import annotations

import pytest

from src.tools.ticket_tools import get_ticket_status, normalize_ticket_id


class TestNormalizeTicketId:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("TKT-1004", "TKT-1004"),
            ("tkt-1004", "TKT-1004"),
            ("TKT1004", "TKT-1004"),
            ("TKT 1004", "TKT-1004"),
            ("TKT_1004", "TKT-1004"),
            ("TKT:1004", "TKT-1004"),
            ("1004", "TKT-1004"),
            ("", None),
            ("hello", None),
        ],
    )
    def test_variants(self, value: str, expected: str | None) -> None:
        assert normalize_ticket_id(value) == expected

    def test_bare_numeric_disabled(self) -> None:
        assert normalize_ticket_id("1004", allow_bare_numeric=False) is None


class TestGetTicketStatus:
    def test_found_ticket(self) -> None:
        result = get_ticket_status("TKT-1004")
        assert result["found"] is True
        assert result["ticket"]["ticket_id"] == "TKT-1004"
        assert result["ticket"]["status"] == "resolved"
        assert result["error"] is None

    def test_found_with_variant(self) -> None:
        result = get_ticket_status("tkt1004")
        assert result["found"] is True

    def test_not_found_returns_structured_error(self) -> None:
        result = get_ticket_status("TKT-9999")
        assert result["found"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    def test_missing_file_returns_structured_error(self, monkeypatch) -> None:
        class FakePath:
            def __init__(self, value: str) -> None:
                self.value = value

            def exists(self) -> bool:
                return False

        monkeypatch.setattr("src.tools.ticket_tools.Path", FakePath)
        result = get_ticket_status("TKT-1001")
        assert result["found"] is False
        assert "not found" in result["error"].lower()
