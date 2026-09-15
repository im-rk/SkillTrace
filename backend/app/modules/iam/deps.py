"""
FastAPI dependencies for IAM (auth, roles).
Provides get_current_user (stateless) and role checks.
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from app.modules.iam.schemas import TokenData
from app.modules.iam.models import UserRole
from app.modules.iam.service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Stateless JWT verification. Does not query the DB.
    """
    try:
        return decode_access_token(token)
    except (jwt.PyJWTError, ValidationError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_role(*allowed_roles: UserRole | str):
    """
    Dependency factory checking if current user has one of the allowed roles.
    Raises HTTP 403 FORBIDDEN if the user's role is insufficient.
    """
    allowed_set = {r.value if isinstance(r, UserRole) else str(r) for r in allowed_roles}

    def checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        user_role_val = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
        if user_role_val not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return checker


# Role hierarchy design:
# `require_instructor` accepts both `instructor` and `admin` (admin is a superset of instructor capabilities).
# `require_admin` strictly accepts `admin` only.
# This asymmetry allows admins to manage and inspect all instructor-level resources.
require_admin = require_role(UserRole.admin)
require_instructor = require_role(UserRole.instructor, UserRole.admin)