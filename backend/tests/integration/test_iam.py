import uuid
from datetime import timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iam.deps import get_current_user
from app.modules.iam.models import UserRole
from app.modules.iam.service import create_access_token


@pytest.mark.asyncio
async def test_case_1_register_valid_user(client: AsyncClient):
    """Case 1: Register with valid data -> 201, user created, password never returned in response."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123",
            "display_name": "Jane Student",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["display_name"] == "Jane Student"
    assert data["role"] == "student"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_case_2_register_duplicate_email(client: AsyncClient):
    """Case 2: Register with duplicate email -> 409 Conflict."""
    email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "SecurePassword123",
        "display_name": "Original User",
    }
    res1 = await client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/auth/register", json=payload)
    assert res2.status_code == 409
    assert res2.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_case_3_login_valid_credentials(client: AsyncClient):
    """Case 3: Login with correct credentials -> 200, valid JWT returned with expires_in."""
    email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123",
            "display_name": "Login User",
        },
    )

    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert isinstance(data["expires_in"], int)
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_case_4_login_wrong_password(client: AsyncClient):
    """Case 4: Login with wrong password -> 401 with 'Invalid credentials'."""
    email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "CorrectPassword123",
            "display_name": "Wrong PW User",
        },
    )

    response = await client.post(
        "/auth/login",
        json={"email": email, "password": "IncorrectPassword999"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_case_5_protected_route_valid_token(client: AsyncClient):
    """Case 5: Access a protected route with a valid, unexpired token -> 200."""
    email = f"protected_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123",
            "display_name": "Protected User",
        },
    )
    login_res = await client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePassword123"},
    )
    token = login_res.json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "student"
    assert "user_id" in data


@pytest.mark.asyncio
async def test_case_6_protected_route_expired_token(client: AsyncClient):
    """Case 6: Access a protected route with an expired token -> 401."""
    expired_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "role": "student"},
        expires_delta=timedelta(seconds=-60),
    )
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_case_7_protected_route_malformed_token(client: AsyncClient):
    """Case 7: Access a protected route with a malformed token -> 401."""
    response = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_case_8_student_on_admin_route_403(client: AsyncClient):
    """Case 8: Student token on an admin-only route -> 403 Forbidden."""
    student_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "role": "student"}
    )
    response = await client.get("/auth/admin-only", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role"


@pytest.mark.asyncio
async def test_case_9_instructor_on_admin_route_403(client: AsyncClient):
    """Case 9: Instructor token on an admin-only route -> 403 Forbidden."""
    instructor_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "role": "instructor"}
    )
    response = await client.get("/auth/admin-only", headers={"Authorization": f"Bearer {instructor_token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role"


@pytest.mark.asyncio
async def test_case_10_admin_on_instructor_route_200(client: AsyncClient):
    """Case 10: Admin token on an instructor-or-admin route -> 200 (proving role hierarchy)."""
    admin_token = create_access_token(
        data={"sub": str(uuid.uuid4()), "role": "admin"}
    )
    response = await client.get("/auth/instructor-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_case_11_statelessness_proof(mocker):
    """
    Case 11: The statelessness proof.
    Verifies that get_current_user decodes and validates JWT purely in-memory
    with zero database queries.
    """
    token = create_access_token(data={"sub": str(uuid.uuid4()), "role": "student"})
    db_spy = mocker.spy(AsyncSession, "execute")

    user_data = get_current_user(token)

    assert user_data.role == UserRole.student
    assert user_data.user_id is not None
    assert db_spy.call_count == 0, "get_current_user must not touch the database"


@pytest.mark.asyncio
async def test_public_registration_role_escalation_prevented(client: AsyncClient):
    """Security Guard: Attempting to register as 'admin' via public registration defaults to 'student'."""
    email = f"hacker_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123",
            "display_name": "Sneaky User",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "student"


@pytest.mark.asyncio
async def test_register_short_password_rejected(client: AsyncClient):
    """Validation Guard: Passwords shorter than 8 characters are rejected with 422."""
    response = await client.post(
        "/auth/register",
        json={
            "email": f"short_{uuid.uuid4().hex[:8]}@example.com",
            "password": "short",
            "display_name": "Short Password User",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_sets_httponly_auth_cookie(client: AsyncClient):
    """The frontend authenticates via this cookie, not by reading the JWT in
    the response body into JS -- httponly means client-side script can't."""
    email = f"cookie_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register", json={"email": email, "password": "SecurePassword123", "display_name": "Cookie User"}
    )
    response = await client.post("/auth/login", json={"email": email, "password": "SecurePassword123"})
    assert response.status_code == 200
    cookie = response.cookies.get("access_token")
    assert cookie is not None
    assert cookie == response.json()["access_token"]


@pytest.mark.asyncio
async def test_protected_route_accessible_via_cookie_alone(client: AsyncClient):
    """No Authorization header at all -- relies entirely on the cookie the
    AsyncClient's cookie jar picked up from the prior login response."""
    email = f"cookieauth_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register", json={"email": email, "password": "SecurePassword123", "display_name": "Cookie Auth User"}
    )
    await client.post("/auth/login", json={"email": email, "password": "SecurePassword123"})

    response = await client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["role"] == "student"


@pytest.mark.asyncio
async def test_bearer_header_takes_priority_over_cookie(client: AsyncClient):
    """A cookie left over from a different session must not silently
    override an explicit Authorization header for a different user."""
    email_cookie_user = f"cookieuser_{uuid.uuid4().hex[:8]}@example.com"
    email_header_user = f"headeruser_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register",
        json={"email": email_cookie_user, "password": "SecurePassword123", "display_name": "Cookie Holder"},
    )
    header_reg = await client.post(
        "/auth/register",
        json={"email": email_header_user, "password": "SecurePassword123", "display_name": "Header User"},
    )
    header_user_id = header_reg.json()["id"]

    # Cookie jar holds the cookie-user's session; the header names a
    # different user entirely, minted directly (not via /auth/login, so it
    # never touches the cookie jar).
    await client.post("/auth/login", json={"email": email_cookie_user, "password": "SecurePassword123"})
    header_token = create_access_token(data={"sub": header_user_id, "role": "student"})

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {header_token}"})
    assert response.status_code == 200
    assert response.json()["user_id"] == header_user_id


@pytest.mark.asyncio
async def test_logout_clears_auth_cookie(client: AsyncClient):
    email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/auth/register", json={"email": email, "password": "SecurePassword123", "display_name": "Logout User"}
    )
    await client.post("/auth/login", json={"email": email, "password": "SecurePassword123"})

    logout_res = await client.post("/auth/logout")
    assert logout_res.status_code == 204

    me_res = await client.get("/auth/me")
    assert me_res.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_at_all_is_401(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401

