from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

MCP_AUDIENCE = "campus-mcp"


def create_tool_token(user_id: int) -> str:
    """Mint a short-lived credential with an audience distinct from browser login."""
    return jwt.encode(
        {"user_id": user_id, "aud": MCP_AUDIENCE,
         "exp": datetime.now(timezone.utc) + timedelta(seconds=settings.AGENT_TIMEOUT_SECONDS + 60)},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )


def decode_tool_token(token: str) -> dict:
    return jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
        audience=MCP_AUDIENCE, options={"require": ["exp", "aud", "user_id"]},
    )


def user_id_from_authorization(authorization: str) -> int:
    """Accept login JWTs and scoped Agent JWTs, never arbitrary audiences."""
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("需要 Bearer 登录凭证")
    try:
        payload = jwt.decode(
            parts[1], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "user_id"]},
        )
        if "aud" in payload:
            payload = decode_tool_token(parts[1])
    except jwt.InvalidAudienceError:
        payload = decode_tool_token(parts[1])
    user_id = payload["user_id"]
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("无效的用户标识")
    return user_id
