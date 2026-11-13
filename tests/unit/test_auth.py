import pytest

from app.core.exceptions import AuthenticationError
from app.core.jwt import ACCESS, REFRESH, create_access_token, create_refresh_token, decode_token
from app.core.security import hash_password, hash_token, is_strong_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("S3cure!pass")
    assert h != "S3cure!pass"
    assert verify_password("S3cure!pass", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", None)


@pytest.mark.parametrize("pw,ok", [("Passw0rd!", True), ("password", False), ("Short1!", False),
                                   ("NoDigits!!", False), ("nouppercase1!", False), ("NoSpecial12", False)])
def test_password_policy(pw, ok):
    assert is_strong_password(pw) is ok


def test_access_and_refresh_tokens():
    access = create_access_token(42, "SUPER_ADMIN", token_version=3)
    payload = decode_token(access, ACCESS)
    assert payload["sub"] == "42" and payload["role"] == "SUPER_ADMIN" and payload["ver"] == 3
    refresh = create_refresh_token(42)
    assert decode_token(refresh, REFRESH)["type"] == "refresh"
    with pytest.raises(AuthenticationError):
        decode_token(refresh, ACCESS)  # wrong token type
    with pytest.raises(AuthenticationError):
        decode_token("not-a-jwt", ACCESS)


def test_token_hash_is_deterministic():
    assert hash_token("abc") == hash_token("abc") != hash_token("abd")
