import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_user


@pytest.mark.anyio
async def test_get_post_success(client: AsyncClient):
    user = await create_test_user(client)
    token = await login_user(client)
    create_response = await client.post(
        "/api/posts",
        json={"title": "A post", "content": "Post body"},
        headers=auth_header(token),
    )
    post_id = create_response.json()["id"]

    response = await client.get(f"/api/posts/{post_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == post_id
    assert data["title"] == "A post"
    assert data["content"] == "Post body"
    assert data["user_id"] == user["id"]
    assert data["author"]["username"] == user["username"]


@pytest.mark.anyio
async def test_update_post_full_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    headers = auth_header(token)
    create_response = await client.post(
        "/api/posts",
        json={"title": "Before", "content": "Old body"},
        headers=headers,
    )
    post_id = create_response.json()["id"]

    response = await client.put(
        f"/api/posts/{post_id}",
        json={"title": "After", "content": "Completely replaced body"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "After"
    assert response.json()["content"] == "Completely replaced body"


@pytest.mark.anyio
async def test_update_post_full_forbids_wrong_user(client: AsyncClient):
    await create_test_user(client, username="owner", email="owner@example.com")
    owner_token = await login_user(client, email="owner@example.com")
    create_response = await client.post(
        "/api/posts",
        json={"title": "Owner post", "content": "Owner content"},
        headers=auth_header(owner_token),
    )
    post_id = create_response.json()["id"]

    await create_test_user(client, username="other", email="other@example.com")
    other_token = await login_user(client, email="other@example.com")
    response = await client.put(
        f"/api/posts/{post_id}",
        json={"title": "Changed", "content": "Changed by another user"},
        headers=auth_header(other_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to update this post"


@pytest.mark.anyio
async def test_update_post_returns_404_for_missing_post(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.put(
        "/api/posts/999999",
        json={"title": "Missing", "content": "Does not exist"},
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


@pytest.mark.anyio
async def test_delete_post_success(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)
    create_response = await client.post(
        "/api/posts",
        json={"title": "Delete me", "content": "Temporary content"},
        headers=auth_header(token),
    )
    post_id = create_response.json()["id"]

    delete_response = await client.delete(
        f"/api/posts/{post_id}",
        headers=auth_header(token),
    )
    get_response = await client.get(f"/api/posts/{post_id}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


@pytest.mark.anyio
async def test_delete_post_forbids_wrong_user(client: AsyncClient):
    await create_test_user(client, username="owner", email="owner@example.com")
    owner_token = await login_user(client, email="owner@example.com")
    create_response = await client.post(
        "/api/posts",
        json={"title": "Owner post", "content": "Owner content"},
        headers=auth_header(owner_token),
    )
    post_id = create_response.json()["id"]

    await create_test_user(client, username="other", email="other@example.com")
    other_token = await login_user(client, email="other@example.com")
    response = await client.delete(
        f"/api/posts/{post_id}",
        headers=auth_header(other_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to delete this post"


@pytest.mark.anyio
async def test_delete_post_returns_404_for_missing_post(client: AsyncClient):
    await create_test_user(client)
    token = await login_user(client)

    response = await client.delete(
        "/api/posts/999999",
        headers=auth_header(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Post not found"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query_string",
    ["?skip=-1", "?limit=0", "?limit=101"],
)
async def test_get_posts_rejects_invalid_pagination(
    client: AsyncClient,
    query_string: str,
):
    response = await client.get(f"/api/posts{query_string}")

    assert response.status_code == 422