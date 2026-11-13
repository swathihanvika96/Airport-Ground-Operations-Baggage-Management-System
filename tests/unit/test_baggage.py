import pytest

from app.core.exceptions import BusinessRuleError, InvalidTransitionError
from app.services.baggage_service import validate_weight
from app.services.baggage_tracking_service import validate_baggage_transition
from app.utils.enums import BaggageCategory as BC
from app.utils.enums import BaggageStatus as BS
from app.utils.reference_generator import baggage_tag_number


def test_happy_path_lifecycle_is_valid():
    path = [BS.REGISTERED, BS.CHECKIN_COMPLETED, BS.SECURITY_SCREENING, BS.SORTING, BS.LOADED, BS.IN_TRANSIT,
            BS.UNLOADED, BS.DELIVERED]
    for a, b in zip(path, path[1:]):
        validate_baggage_transition(a, b)


@pytest.mark.parametrize("cur,target", [(BS.REGISTERED, BS.LOADED), (BS.DELIVERED, BS.SORTING),
                                        (BS.SORTING, BS.REGISTERED), (BS.CHECKIN_COMPLETED, BS.DELIVERED)])
def test_invalid_baggage_transitions(cur, target):
    with pytest.raises(InvalidTransitionError):
        validate_baggage_transition(cur, target)


def test_missing_and_delayed_recovery():
    validate_baggage_transition(BS.SORTING, BS.MISSING)
    validate_baggage_transition(BS.MISSING, BS.DELIVERED)
    validate_baggage_transition(BS.LOADED, BS.DELAYED)
    validate_baggage_transition(BS.DELAYED, BS.LOADED)


@pytest.mark.parametrize("cat,weight,ok", [(BC.CABIN, 7, True), (BC.CABIN, 12, False), (BC.CHECKED, 32, True),
                                           (BC.CHECKED, 33, False), (BC.OVERSIZED, 60, True),
                                           (BC.SPECIAL, 90, True)])
def test_weight_limits(cat, weight, ok):
    if ok:
        validate_weight(cat, weight)
    else:
        with pytest.raises(BusinessRuleError):
            validate_weight(cat, weight)


def test_tag_format():
    tag = baggage_tag_number("AI")
    assert tag.startswith("AI") and len(tag) == 10 and tag[2:].isdigit()
