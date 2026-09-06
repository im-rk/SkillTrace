import pytest
from httpx import AsyncClient
from app.modules.iam.deps import get_current_user

@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # 1. Register a new user
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "secretpassword",
        "display_name": "Test User",
        "role": "student"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    
    # 2. Login
    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "secretpassword"
    })
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    
    # 3. Access protected route
    token = token_data["access_token"]
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    me_data = response.json()
    assert me_data["role"] == "student"

@pytest.mark.asyncio
async def test_stateless_verification(client: AsyncClient):
    # Get a token
    await client.post("/auth/register", json={
        "email": "stateless@example.com",
        "password": "pass",
        "display_name": "Stateless",
        "role": "admin"
    })
    response = await client.post("/auth/login", json={
        "email": "stateless@example.com",
        "password": "pass"
    })
    token = response.json()["access_token"]
    
    # Call get_current_user directly, which shouldn't need a DB session.
    # Since get_current_user only requires the token string, we can test it directly
    # and prove it does not touch the database (it doesn't even take a session param!)
    user_data = get_current_user(token)
    assert user_data.role == "admin"
    assert user_data.user_id is not None
