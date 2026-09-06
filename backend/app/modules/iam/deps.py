"""
FastAPI dependencies for IAM (auth, roles).
Provides get_current_user (stateless) and role checks.
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from app.core.config import settings
from app.modules.iam.schemas import TokenData
from app.modules.iam.models import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Stateless JWT verification. Does not query the DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, role=UserRole(role))
    except (jwt.PyJWTError, ValidationError, ValueError):
        raise credentials_exception
    
    return token_data

def require_instructor(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role not in [UserRole.instructor, UserRole.admin]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user