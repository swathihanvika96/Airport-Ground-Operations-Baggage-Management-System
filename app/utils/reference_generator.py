"""Human-friendly unique references (boarding passes, baggage tags, PNRs, incidents)."""
import re
import secrets
import string
from datetime import datetime

_ALPHANUM = string.ascii_uppercase + string.digits
_SAFE = "".join(c for c in _ALPHANUM if c not in "O0I1")  # avoid ambiguous chars


def _rand(n: int, alphabet: str = _SAFE) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def booking_reference() -> str:
    """6-char PNR style reference."""
    return _rand(6)


def boarding_pass_reference(flight_number: str, departure: datetime) -> str:
    fn = re.sub(r"[^A-Z0-9]", "", flight_number.upper())
    return f"BP-{fn}-{departure:%Y%m%d}-{_rand(6)}"


def baggage_tag_number(airline_code: str | None) -> str:
    """IATA-like license plate: 2-letter airline code + 8 digits."""
    prefix = (airline_code or "XX").upper()[:3]
    return f"{prefix}{_rand(8, string.digits)}"


def incident_reference(now: datetime) -> str:
    return f"INC-{now:%Y%m%d}-{_rand(5)}"
