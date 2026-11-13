from tests.conftest import API, PASSWORD, login


def test_register_login_me_refresh(client):
    r = client.post(f"{API}/auth/register", json={"email": "agent@airportops.com", "full_name": "Agent One",
                                                  "password": PASSWORD, "role": "CHECKIN_AGENT"})
    assert r.status_code == 201, r.text
    assert "hashed_password" not in r.json()
    r = client.post(f"{API}/auth/login", json={"username": "agent@airportops.com", "password": PASSWORD})
    assert r.status_code == 200
    tokens = r.json()
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["role"] == "CHECKIN_AGENT"
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200 and r.json()["access_token"]
    # refresh token cannot be used as an access token
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}).status_code == 401


def test_register_rejects_weak_password_duplicate_and_privileged_role(client):
    body = {"email": "x@airportops.com", "full_name": "X User", "password": PASSWORD, "role": "GATE_AGENT"}
    assert client.post(f"{API}/auth/register", json={**body, "password": "weak"}).status_code == 422
    assert client.post(f"{API}/auth/register", json=body).status_code == 201
    assert client.post(f"{API}/auth/register", json=body).status_code == 409
    r = client.post(f"{API}/auth/register", json={**body, "email": "y@airportops.com", "role": "SUPER_ADMIN"})
    assert r.status_code == 403


def test_bad_credentials_and_protected_endpoint(client):
    assert client.post(f"{API}/auth/token", data={"username": "nobody", "password": "x"}).status_code == 401
    r = client.get(f"{API}/flights")
    assert r.status_code == 401 and r.json()["success"] is False


def test_deactivation_blocks_login_and_existing_tokens(client, admin, factory):
    headers = factory.user("GATE_AGENT")
    uid = client.get(f"{API}/auth/me", headers=headers).json()["id"]
    assert client.post(f"{API}/users/{uid}/deactivate", headers=admin).json()["is_active"] is False
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401
    email = client.get(f"{API}/users/{uid}", headers=admin).json()["email"]
    assert client.post(f"{API}/auth/token", data={"username": email, "password": PASSWORD}).status_code == 401
    client.post(f"{API}/users/{uid}/activate", headers=admin)
    login(client, email, PASSWORD)


def test_password_reset_flow(client):
    client.post(f"{API}/auth/register", json={"email": "reset@airportops.com", "full_name": "Reset Me",
                                              "password": PASSWORD, "role": "GATE_AGENT"})
    r = client.post(f"{API}/auth/forgot-password", json={"email": "reset@airportops.com"})
    token = r.json()["data"]["reset_token"]
    new_pw = "N3wPassw0rd!"
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": new_pw}).status_code == 200
    # token is single-use
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": new_pw}).status_code == 400
    login(client, "reset@airportops.com", new_pw)
    # unknown email does not leak existence
    r = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@airportops.com"})
    assert r.status_code == 200 and r.json()["data"] is None


def test_change_password_revokes_tokens(client, factory):
    headers = factory.user("GATE_AGENT")
    r = client.post(f"{API}/auth/change-password", headers=headers,
                    json={"current_password": PASSWORD, "new_password": "An0therPass!"})
    assert r.status_code == 200
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_oauth_registration_creates_and_links_account(client):
    from app.db.session import SessionLocal
    from app.services.auth_service import AuthService
    from app.utils.enums import AuthProvider
    db = SessionLocal()
    try:
        svc = AuthService(db)
        profile = {"sub": "google-123", "email": "oauth.user@gmail.com", "name": "OAuth User", "email_verified": True}
        tokens = svc.oauth_login_or_register(AuthProvider.GOOGLE, profile)
        assert tokens["access_token"]
        user = svc.users.get_by_email("oauth.user@gmail.com")
        assert user.auth_provider == AuthProvider.GOOGLE and user.hashed_password is None
        again = svc.oauth_login_or_register(AuthProvider.GOOGLE, profile)  # second login reuses account
        assert again["access_token"]
        assert svc.users.count() == 2  # admin + oauth user
    finally:
        db.close()


def test_google_login_not_configured(client):
    r = client.get(f"{API}/auth/oauth/google/login")
    assert r.status_code == 400 and r.json()["error"]["code"] == "OAUTH_NOT_CONFIGURED"


def test_role_permissions_enforced(client, factory):
    agent = factory.user("CHECKIN_AGENT")
    r = client.post(f"{API}/airports", headers=agent, json={"code": "XYZ", "name": "No Way", "city": "c",
                                                             "country": "IN"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED"
    assert client.get(f"{API}/users", headers=agent).status_code == 403
    assert client.get(f"{API}/audit-logs", headers=agent).status_code == 403
    assert client.get(f"{API}/airports", headers=agent).status_code == 200
