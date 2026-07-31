"""Signup, login, tokens and profile."""

from app.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

import pytest


def test_password_hashing_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second, "identical passwords must not produce identical hashes"
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)


def test_verify_password_rejects_a_malformed_hash():
    """A corrupt row must fail the login, not raise a 500."""
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_password_longer_than_bcrypts_72_byte_limit_is_accepted():
    long_password = "a" * 200
    assert verify_password(long_password, hash_password(long_password))


def test_access_token_cannot_be_used_as_a_refresh_token():
    access = create_access_token(1)
    refresh = create_refresh_token(1)

    assert decode_token(access, "access") == 1
    assert decode_token(refresh, "refresh") == 1

    with pytest.raises(TokenError):
        decode_token(access, "refresh")
    with pytest.raises(TokenError):
        decode_token(refresh, "access")


def test_garbage_token_is_rejected():
    with pytest.raises(TokenError):
        decode_token("not.a.token", "access")


def test_signup_creates_a_profile_with_zeroed_counters(client, auth):
    _, user = auth("fresh@example.com")
    profile = user["profile"]

    assert profile["xp"] == 0
    assert profile["level"] == 1
    assert profile["streak_days"] == 0
    assert profile["current_track_id"] is None


def test_signup_normalises_the_email(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "MixedCase@Example.COM", "password": "hunter2hunter2"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mixedcase@example.com"

    # ...and the normalised address is what blocks a duplicate.
    duplicate = client.post(
        "/api/v1/auth/signup",
        json={"email": "mixedcase@example.com", "password": "hunter2hunter2"},
    )
    assert duplicate.status_code == 409


def test_short_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/signup", json={"email": "short@example.com", "password": "abc"}
    )
    assert response.status_code == 422


def test_login_does_not_reveal_whether_an_email_exists(client, auth):
    auth("known@example.com")

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "known@example.com", "password": "wrongwrongwrong"},
    )
    no_such_user = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrongwrongwrong"},
    )

    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json() == no_such_user.json()


def test_me_requires_authentication(client, auth):
    assert client.get("/api/v1/auth/me").status_code == 401

    headers, _ = auth()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_refresh_issues_a_working_access_token(client):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"email": "refresh@example.com", "password": "hunter2hunter2"},
    ).json()

    refreshed = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": signup["refresh_token"]}
    )
    assert refreshed.status_code == 200

    headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_profile_update(client, auth):
    headers, _ = auth()
    response = client.patch(
        "/api/v1/auth/me",
        json={"daily_hours": 5, "display_name": "Ada Lovelace"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Ada Lovelace"
    assert response.json()["profile"]["daily_hours"] == 5
