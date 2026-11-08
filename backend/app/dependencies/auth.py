from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
login_bearer = HTTPBearer(
    scheme_name="LoginJWT", auto_error=False,
    description="先调用 /api/auth/login，再粘贴 data.token；此处无需填写 Bearer 前缀。",
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """JWT token 鉴权验证合法性"""
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录"
        )
    # 获取到用户ID
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的登录凭证"
        )
    # 从数据库根据用户ID查询用户信息
    user = db.query(User).filter(User.id == user_id, User.status == 1).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效或用户已被禁用",
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """判断JWT token内角色是否为admin"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限访问")
    return current_user


def get_current_authorization(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(login_bearer),
    db: Session = Depends(get_db),
) -> str:
    """Validate login locally and preserve its header for request-scoped MCP calls."""
    if credentials is None:
        raise HTTPException(401, "请先登录并提供 Bearer token")
    get_current_user(token=credentials.credentials, db=db)
    return request.headers["Authorization"]
