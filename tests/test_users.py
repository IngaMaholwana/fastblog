from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image

from config import settings
from tests.conftest import auth_header, create_test_user, login_user


def make_jpeg_bytes() -> bytes:
    """Create a small, valid JPEG without depending on a checked-in image file."""
    buffer = BytesIO()
    Image.new("RGB", (64, 64), color=(30, 90, 140)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.anyio
async def test_create_user_rejects_duplicate_username_case_insensitively(
    client: AsyncClient,
):
    await create_test_user(client)

    response = await client.post(
        "/api/users",
        json={
            "username": "TESTUSER",
            "email": "another@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already exists"


@pytest.mark.anyio
async def test_create_user_rejects_duplicate_email_case_insensitively(
    client: AsyncClient,
):
    await create_test_user(client)

    response = await client.post(
        "/api/users",
        json={
            "username": "anotheruser",
            "email": "TEST@EXAMPLE.COM",
            "password": "password123",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.anyio
async def test_get_user_success_does_not_expose_password(client: AsyncClient):
    user = await create_test_user(client)

    response = await client.get(f"/api/users/{user['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user["id"]
    assert data["username"] == "testuser"
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.anyio
async def test_get_user_not_found(client: AsyncClient):
    response = await client.get("/api/users/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.anyio
async def test_get_user_posts_supports_pagination(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    for index in range(3):
        create_response = await client.post(
            "/api/posts",
            json={"title": f"Post {index}", "content": f"Content {index}"},
            headers=auth_header(token),
        )
        assert create_response.status_code == 201

    response = await client.get(
        f"/api/users/{user['id']}/posts?skip=1&limit=1",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["skip"] == 1
    assert data["limit"] == 1
    assert len(data["posts"]) == 1
    assert data["has_more"] is True


@pytest.mark.anyio
async def test_get_user_posts_returns_404_for_unknown_user(client: AsyncClient):
    response = await client.get("/api/users/999999/posts")

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.anyio
async def test_update_user_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}",
        json={"username": "updateduser", "email": "UPDATED@example.com"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updateduser"
    assert data["email"] == "updated@example.com"


@pytest.mark.anyio
async def test_update_user_rejects_existing_username(client: AsyncClient):
    await create_test_user(client, username="user_one", email="one@example.com")
    user_two = await create_test_user(
        client,
        username="user_two",
        email="two@example.com",
    )
    token_two = await login_user(client, email="two@example.com")

    response = await client.patch(
        f"/api/users/{user_two['id']}",
        json={"username": "USER_ONE"},
        headers=auth_header(token_two),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already exists"


@pytest.mark.anyio
async def test_update_user_rejects_existing_email(client: AsyncClient):
    await create_test_user(client, username="user_one", email="one@example.com")
    user_two = await create_test_user(
        client,
        username="user_two",
        email="two@example.com",
    )
    token_two = await login_user(client, email="two@example.com")

    response = await client.patch(
        f"/api/users/{user_two['id']}",
        json={"email": "ONE@EXAMPLE.COM"},
        headers=auth_header(token_two),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.anyio
async def test_update_user_forbids_updating_another_user(client: AsyncClient):
    user_one = await create_test_user(client, username="user_one", email="one@example.com")
    await create_test_user(client, username="user_two", email="two@example.com")
    token_two = await login_user(client, email="two@example.com")

    response = await client.patch(
        f"/api/users/{user_one['id']}",
        json={"username": "changed_by_someone_else"},
        headers=auth_header(token_two),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this user"


@pytest.mark.anyio
async def test_delete_user_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(
        f"/api/users/{user['id']}",
        headers=auth_header(token),
    )

    assert response.status_code == 204
    get_response = await client.get(f"/api/users/{user['id']}")
    assert get_response.status_code == 404


@pytest.mark.anyio
async def test_delete_user_forbids_deleting_another_user(client: AsyncClient):
    user_one = await create_test_user(client, username="user_one", email="one@example.com")
    await create_test_user(client, username="user_two", email="two@example.com")
    token_two = await login_user(client, email="two@example.com")

    response = await client.delete(
        f"/api/users/{user_one['id']}",
        headers=auth_header(token_two),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this user"


@pytest.mark.anyio
async def test_upload_profile_picture_rejects_invalid_image(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("not-an-image.jpg", b"this is not an image", "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid image file")


@pytest.mark.anyio
async def test_upload_profile_picture_rejects_oversized_file(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)
    oversized_content = b"x" * (settings.max_upload_size_bytes + 1)

    response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("large.jpg", oversized_content, "image/jpeg")},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]


@pytest.mark.anyio
async def test_upload_profile_picture_forbids_another_user(client: AsyncClient):
    user_one = await create_test_user(client, username="user_one", email="one@example.com")
    await create_test_user(client, username="user_two", email="two@example.com")
    token_two = await login_user(client, email="two@example.com")

    response = await client.patch(
        f"/api/users/{user_one['id']}/picture",
        files={"file": ("profile.jpg", make_jpeg_bytes(), "image/jpeg")},
        headers=auth_header(token_two),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this user's picture"


@pytest.mark.anyio
async def test_upload_profile_picture_replaces_old_s3_object(client, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    first_response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("first.jpg", make_jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    assert first_response.status_code == 200
    first_filename = first_response.json()["image_file"]

    second_response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("second.jpg", make_jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )

    assert second_response.status_code == 200
    second_filename = second_response.json()["image_file"]
    assert second_filename is not None
    assert second_filename != first_filename

    objects = mocked_aws.list_objects_v2(Bucket="test-bucket").get("Contents", [])
    assert len(objects) == 1
    assert objects[0]["Key"].endswith(second_filename)


@pytest.mark.anyio
async def test_delete_profile_picture_rejects_user_without_picture(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(
        f"/api/users/{user['id']}/picture",
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No profile picture to delete"


@pytest.mark.anyio
async def test_delete_profile_picture_success(client: AsyncClient, mocked_aws):
    user = await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)

    upload_response = await client.patch(
        f"/api/users/{user['id']}/picture",
        files={"file": ("profile.jpg", make_jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    assert upload_response.status_code == 200
    assert mocked_aws.list_objects_v2(Bucket="test-bucket").get("Contents")

    delete_response = await client.delete(
        f"/api/users/{user['id']}/picture",
        headers=headers,
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["image_file"] is None
    assert mocked_aws.list_objects_v2(Bucket="test-bucket").get("Contents", []) == []