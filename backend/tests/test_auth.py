from datetime import datetime, timedelta, timezone
import os

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import get_session
from app.db.models import User
from app.main import create_app
from app.security import password_hasher, token_settings
from app.testing import validate_test_database


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client


@pytest.fixture
def account():
    return {"username": "cowjellys", "email": "cowjellys@example.com",
            "password": "a long test password!"}


def register(client, account):
    response = client.post("/auth/register", json=account)
    assert response.status_code == 201, response.text
    return response.json()


def login(client, account):
    return client.post("/auth/login", json={key: account[key]
                                          for key in ("username", "password")})


def test_registration_hash_and_profile(client, session, account):
    profile = register(client, account)
    assert set(profile) == {"user_id", "username", "email", "avatar_url", "created_at"}
    user = session.get(User, profile["user_id"])
    assert user.password_hash != account["password"]
    assert user.password_hash.startswith("$argon2id$")
    assert password_hasher.verify(account["password"], user.password_hash)
    response = login(client, account)
    assert response.status_code == 200
    token = response.json()
    assert token["token_type"] == "bearer"
    assert token["expires_in"] == 1800
    claims = jwt.decode(token["access_token"], os.environ["JWT_SECRET_KEY"],
                        algorithms=["HS256"], audience="smartrecipe-api")
    assert claims["exp"] - claims["iat"] == 1800
    assert account["password"] not in str(claims)
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    assert client.get("/auth/me", headers=headers).json() == profile


@pytest.mark.parametrize("field", ["username", "email"])
def test_duplicate_case_insensitive(client, account, field):
    register(client, account)
    duplicate = {**account, "username": "another", "email": "another@example.com"}
    duplicate[field] = account[field].upper()
    response = client.post("/auth/register", json=duplicate)
    assert response.status_code == 409
    assert "password" not in response.text
    assert login(client, account).status_code == 200


def test_generic_invalid_credentials(client, account):
    register(client, account)
    bad_password = login(client, {**account, "password": "wrong password"})
    missing_user = login(client, {**account, "username": "missing"})
    assert bad_password.status_code == missing_user.status_code == 401
    assert bad_password.json() == missing_user.json() == {"detail": "Invalid username or password"}
    assert bad_password.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("change", ["expired", "signature", "algorithm", "subject", "missing",
                                   "audience", "issuer", "type", "future", "deleted", "huge"])
def test_reject_invalid_tokens(client, account, change):
    user = register(client, account)
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user["user_id"]), "iat": now, "exp": now + timedelta(minutes=5),
              "aud": "smartrecipe-api", "iss": "smartrecipe", "token_type": "access"}
    key, algorithm = os.environ["JWT_SECRET_KEY"], "HS256"
    if change == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    elif change == "signature":
        key = "another key with enough bytes for signing"
    elif change == "algorithm":
        algorithm = "HS384"
    elif change == "subject":
        claims["sub"] = "invalid"
    elif change == "huge":
        claims["sub"] = "9" * 30
    elif change == "missing":
        del claims["exp"]
    elif change == "audience":
        claims["aud"] = "other"
    elif change == "issuer":
        claims["iss"] = "other"
    elif change == "type":
        claims["token_type"] = "refresh"
    elif change == "future":
        claims["iat"] = now + timedelta(minutes=5)
    elif change == "deleted":
        claims["sub"] = "9223372036854775807"
    token = jwt.encode(claims, key, algorithm=algorithm)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer broken"])
def test_profile_requires_token(client, header):
    headers = {"Authorization": header} if header else {}
    assert client.get("/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize("patch", [{"password": "short"}, {"email": "invalid"},
                                   {"username": "bad name"}, {"password": "x" * 129},
                                   {"unexpected": "secret"}, {"password": {"secret": "raw"}}])
def test_validation_redacts_inputs(account, patch):
    with TestClient(create_app()) as client:
        response = client.post("/auth/register", json={**account, **patch})
        assert response.status_code == 422
        assert account["password"] not in response.text
        assert "input" not in response.text
        assert "secret" not in response.text


def test_malformed_json_is_redacted():
    with TestClient(create_app()) as client:
        response = client.post("/auth/login", content='{"password":"private-value",',
                               headers={"Content-Type": "application/json"})
        assert response.status_code == 422
        assert "private-value" not in response.text


@pytest.mark.parametrize("secret", ["", "short", "replace-" + "x" * 40])
def test_reject_insecure_configuration(monkeypatch, secret):
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    with pytest.raises(RuntimeError):
        create_app()


@pytest.mark.parametrize("minutes", ["0", "-1", "1441", "invalid"])
def test_reject_invalid_expiry(monkeypatch, minutes):
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", minutes)
    with pytest.raises(RuntimeError):
        token_settings()


@pytest.mark.parametrize("target,development", [
    ("postgresql://localhost/smartrecipe", "postgresql://localhost/smartrecipe"),
    ("postgresql://localhost/app_test", "postgresql://otherhost/app_test"),
    ("sqlite:///app_test", None),
])
def test_database_safety(target, development):
    with pytest.raises(ValueError):
        validate_test_database(target, development)
