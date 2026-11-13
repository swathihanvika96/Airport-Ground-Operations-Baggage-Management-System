from datetime import datetime

import pytest

from app.core.exceptions import BusinessRuleError
from app.services.dashboard_service import on_time_performance
from app.services.delay_service import calculate_delay, delay_severity, total_delay_minutes
from app.utils.enums import Severity

T0 = datetime(2030, 1, 1, 10, 0)


def test_delay_from_minutes():
    minutes, updated = calculate_delay(T0, delay_minutes=45)
    assert minutes == 45 and updated == datetime(2030, 1, 1, 10, 45)


def test_delay_from_updated_departure():
    minutes, updated = calculate_delay(T0, updated_departure=datetime(2030, 1, 1, 12, 30))
    assert minutes == 150 and updated.hour == 12


def test_delay_consistency_and_validation():
    calculate_delay(T0, 30, datetime(2030, 1, 1, 10, 30))
    with pytest.raises(BusinessRuleError):
        calculate_delay(T0, 20, datetime(2030, 1, 1, 10, 30))  # mismatch
    with pytest.raises(BusinessRuleError):
        calculate_delay(T0, updated_departure=datetime(2030, 1, 1, 9, 0))  # earlier
    with pytest.raises(BusinessRuleError):
        calculate_delay(T0)


def test_cumulative_delay_and_severity():
    assert total_delay_minutes(T0, datetime(2030, 1, 1, 11, 15)) == 75
    assert total_delay_minutes(T0, datetime(2030, 1, 1, 9, 0)) == 0
    assert delay_severity(10) == Severity.LOW
    assert delay_severity(30) == Severity.MEDIUM
    assert delay_severity(90) == Severity.HIGH
    assert delay_severity(200) == Severity.CRITICAL


def test_on_time_performance():
    rows = [(T0, datetime(2030, 1, 1, 10, 10)), (T0, datetime(2030, 1, 1, 10, 40)), (T0, T0)]
    assert on_time_performance(rows) == pytest.approx(66.67)
    assert on_time_performance([]) is None
