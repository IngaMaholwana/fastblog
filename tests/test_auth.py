from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

import models
from auth import hash_reset_token
from tests.conftest import auth_header, create_test_user, login_user


@pytest.mark.anyio
async def test_login_accepts_email_case_insensitively(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token",
        data={"username": "TEST@EXAMPLE.COM", "password": "testpassword123"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "email,password",
    [
        ("test@example.com", "wrong-password"),
        ("missing@example.com", "testpassword123"),
    ],
)
async def test_login_rejects_invalid_credentials(
    client: AsyncClient,
    email: str,
    password: str,
):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token",
        data={"username": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.anyio
async def test_get_current_user_requires_authentication(client: AsyncClient):
    response = await client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_get_current_user_returns_authenticated_user(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.get(
        "/api/users/me",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["username"] == user["username"]
    assert data["email"] == user["email"]
    assert "password_hash" not in data


@pytest.mark.anyio
async def test_forgot_password_unknown_email_does_not_send_email(
    client: AsyncClient,
):
    with patch(
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "unknown@example.com"},
        )

    assert response.status_code == 202
    assert "If an account exists" in response.json()["message"]
    mock_send.assert_not_awaited()


@pytest.mark.anyio
async def test_forgot_password_looks_up_email_case_insensitively(
    client: AsyncClient,
):
    await create_test_user(client)

    with (
        patch(
            "routers.users.generate_reset_token",
            return_value="known-reset-token",
        ),
        patch(
            "routers.users.send_password_reset_email",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        response = await client.post(
            "/api/users/forgot-password",
            json={"email": "TEST@EXAMPLE.COM"},
        )

    assert response.status_code == 202
    mock_send.assert_awaited_once()
    assert mock_send.call_args.kwargs["to_email"] == "test@example.com"


@pytest.mark.anyio
async def test_reset_password_rejects_unknown_token(client: AsyncClient):
    response = await client.post(
        "/api/users/reset-password",
        json={"token": "not-a-real-token", "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


@pytest.mark.anyio
async def test_reset_password_changes_password_and_token_is_one_time(
    client: AsyncClient,
):
    await create_test_user(client)
    reset_token = "one-time-reset-token"

    with (
        patch("routers.users.generate_reset_token", return_value=reset_token),
        patch(
            "routers.users.send_password_reset_email",
            new_callable=AsyncMock,
        ),
    ):
        forgot_response = await client.post(
            "/api/users/forgot-password",
            json={"email": "test@example.com"},
        )

    assert forgot_response.status_code == 202

    reset_response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "brandnewpassword123"},
    )

    assert reset_response.status_code == 200
    assert "successfully" in reset_response.json()["message"]

    old_password_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "testpassword123"},
    )
    new_password_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "brandnewpassword123"},
    )
    reused_token_response = await client.post(
        "/api/users/reset-password",
        json={"token": reset_token, "new_password": "anotherpassword123"},
    )

    assert old_password_login.status_code == 401
    assert new_password_login.status_code == 200
    assert reused_token_response.status_code == 400


@pytest.mark.anyio
async def test_reset_password_rejects_expired_token(client: AsyncClient, db_session):
    user = await create_test_user(client)
    raw_token = "expired-reset-token"
    db_session.add(
        models.PasswordResetToken(
            user_id=user["id"],
            token_hash=hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ),
    )
    await db_session.commit()

    response = await client.post(
        "/api/users/reset-password",
        json={"token": raw_token, "new_password": "newpassword123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


@pytest.mark.anyio
async def test_change_password_rejects_incorrect_current_password(
    client: AsyncClient,
):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={
            "current_password": "incorrect-password",
            "new_password": "newpassword123",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


@pytest.mark.anyio
async def test_change_password_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        "/api/users/me/password",
        json={
            "current_password": "testpassword123",
            "new_password": "newpassword123",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"

    old_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "testpassword123"},
    )
    new_login = await client.post(
        "/api/users/token",
        data={"username": "test@example.com", "password": "newpassword123"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200


@pytest.mark.anyio
async def test_change_password_requires_authentication(client: AsyncClient):
    response = await client.patch(
        "/api/users/me/password",
        json={
            "current_password": "testpassword123",
            "new_password": "newpassword123",
        },
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_change_password_invalidates_existing_reset_tokens(
    client: AsyncClient,
    db_session,
):
    user = await create_test_user(client)
    raw_token = "reset-token-before-password-change"
    db_session.add(
        models.PasswordResetToken(
            user_id=user["id"],
            token_hash=hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        ),
    )
    await db_session.commit()

    access_token = await login_user(client)
    change_response = await client.patch(
        "/api/users/me/password",
        json={
            "current_password": "testpassword123",
            "new_password": "newpassword123",
        },
        headers=auth_header(access_token),
    )
    reset_response = await client.post(
        "/api/users/reset-password",
        json={"token": raw_token, "new_password": "thirdpassword123"},
    )

    assert change_response.status_code == 200
    assert reset_response.status_code == 400