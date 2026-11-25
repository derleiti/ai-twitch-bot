"""Regression tests for HS256 JWT verification after removal of python-jose."""
import importlib
import secrets
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from jwt import InvalidTokenError


@pytest.fixture
def service(monkeypatch, tmp_path):
    import auth.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("JWT_SECRET", secrets.token_hex(32))
    monkeypatch.setenv("JWT_ISS", "https://auth.example.test")
    monkeypatch.setenv("JWT_AUD", "zephyr-test")
    import auth_service

    return importlib.reload(auth_service)


def claims(service):
    now = int(time.time())
    return {
        "iss": service.JWT_ISS,
        "aud": service.JWT_AUD,
        "iat": now - 1,
        "exp": now + 300,
        "sub": "test-user",
        "email": "user@example.test",
        "roles": ["member"],
    }


def test_round_trip(service):
    token = service.issue_jwt("test-user", "user@example.test", ["member"])
    verified = service.verify_jwt(token)
    assert verified["sub"] == "test-user"
    assert verified["iss"] == service.JWT_ISS
    assert verified["roles"] == ["member"]


@pytest.mark.parametrize("algorithm", ["none", "HS384", "HS512"])
def test_reject_other_algorithms(service, algorithm):
    key = "" if algorithm == "none" else service.JWT_SECRET
    token = jwt.encode(claims(service), key, algorithm=algorithm)
    with pytest.raises(InvalidTokenError):
        service.verify_jwt(token)


@pytest.mark.parametrize("claim,value", [
    ("iss", "https://other.example.test"),
    ("aud", "wrong-audience"),
    ("exp", 1),
    ("iat", int(time.time()) + 3600),
])
def test_reject_invalid_claim(service, claim, value):
    payload = claims(service)
    payload[claim] = value
    token = jwt.encode(payload, service.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        service.verify_jwt(token)


@pytest.mark.parametrize("claim", ["iss", "aud", "iat", "exp", "sub"])
def test_reject_missing_claim(service, claim):
    payload = claims(service)
    del payload[claim]
    token = jwt.encode(payload, service.JWT_SECRET, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        service.verify_jwt(token)


def test_reject_wrong_signature(service):
    token = jwt.encode(claims(service), secrets.token_hex(32), algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        service.verify_jwt(token)


@pytest.mark.parametrize("secret", ["", "insecure", "CHANGE_ME_TO_32+_RANDOM_CHARS", "short"])
def test_reject_weak_configuration(service, monkeypatch, secret):
    monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        service._load_jwt_secret()


def test_auth_endpoint(service):
    from auth.db import upsert_user

    user, roles = upsert_user("google", "test-id", "user@example.test")
    token = service.issue_jwt(user, "user@example.test", roles)
    client = TestClient(service.app)
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer malformed"}).status_code == 401
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"email": "user@example.test", "roles": roles}
    assert client.get("/auth/me", headers={"Cookie": f"session={token}"}).status_code == 200


def test_der_public_key_is_not_hmac_secret():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import get_default_algorithms
    from jwt.exceptions import InvalidKeyError

    public_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    der = public_key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(InvalidKeyError):
        get_default_algorithms()["HS256"].prepare_key(der)
