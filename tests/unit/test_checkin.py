import pytest

from app.core.exceptions import BusinessRuleError
from app.services.checkin_service import next_free_seat, validate_seat


def test_next_free_seat_skips_taken():
    assert next_free_seat(set(), 180) == "1A"
    assert next_free_seat({"1A", "1B"}, 180) == "1C"
    assert next_free_seat({"1A", "1B", "1C", "1D", "1E", "1F"}, 180) == "2A"


def test_no_seat_when_full():
    taken = {f"{r}{c}" for r in range(1, 3) for c in "ABCDEF"}
    assert next_free_seat(taken, 12) is None


def test_validate_seat_bounds():
    assert validate_seat("12c", 180) == "12C"
    with pytest.raises(BusinessRuleError):
        validate_seat("31A", 180)  # 180 seats -> 30 rows
    with pytest.raises(BusinessRuleError):
        validate_seat("10K", 180)  # only A-F
