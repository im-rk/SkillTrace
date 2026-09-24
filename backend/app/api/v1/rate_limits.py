"""
FastAPI dependencies that apply app.core.rate_limit to requests.

Behind a reverse proxy, `request.client.host` is the proxy unless uvicorn runs
with --proxy-headers (see the deployment config) -- without that every caller
shares one IP bucket.
"""
import jwt
from fastapi import Depends, Request
from pydantic import ValidationError

from app.core.config import settings
from app.core.rate_limit import enforce
from app.core.redis_client import get_redis
from app.modules.iam.deps import get_current_user
from app.modules.iam.schemas import TokenData
from app.modules.iam.service import decode_access_token


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _principal(request: Request) -> str:
    """The authenticated user if the request carries a valid token, else the caller's IP."""
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if token:
        try:
            return f"user:{decode_access_token(token).user_id}"
        except (jwt.PyJWTError, ValidationError, ValueError):
            pass
    return f"ip:{_client_ip(request)}"


async def global_rate_limit(request: Request) -> None:
    if settings.RATE_LIMIT_ENABLED:
        await enforce(get_redis(), f"global:{_principal(request)}", settings.RATE_LIMIT_GLOBAL_PER_MINUTE)


async def auth_rate_limit(request: Request) -> None:
    if settings.RATE_LIMIT_ENABLED:
        await enforce(get_redis(), f"auth:ip:{_client_ip(request)}", settings.AUTH_RATE_LIMIT_PER_IP_PER_MINUTE)


async def redeem_rate_limit(request: Request, current_user: TokenData = Depends(get_current_user)) -> None:
    """Access-code redemption is the brute-force surface. Per user, so one account can't
    enumerate codes, plus per IP, so a rotating set of accounts can't either -- with the IP
    bound generous enough for a classroom sharing one NAT."""
    if settings.RATE_LIMIT_ENABLED:
        redis_client = get_redis()
        await enforce(redis_client, f"redeem:user:{current_user.user_id}", settings.REDEEM_RATE_LIMIT_PER_USER_PER_MINUTE)
        await enforce(redis_client, f"redeem:ip:{_client_ip(request)}", settings.REDEEM_RATE_LIMIT_PER_IP_PER_MINUTE)
