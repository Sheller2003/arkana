from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer

from src.arkana_auth.amezitUserObject import AmezitUserPolicyError
from src.arkana_auth.user_manager import UserManager
from src.arkana_auth.user_object import ArkanaUser
from src.arkana_mdd_db.config import ArkanaMainDBConfig, get_main_db_config
from src.arkana_mdd_db.main_db import ArkanaMainDB

security = HTTPBasic(auto_error=False)
bearer_security = HTTPBearer(auto_error=False)


def get_main_db() -> ArkanaMainDB:
    config: ArkanaMainDBConfig = get_main_db_config()
    return ArkanaMainDB(config)


def get_user_manager(main_db: ArkanaMainDB = Depends(get_main_db)) -> UserManager:
    return UserManager(main_db)


def get_current_user(
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    credentials: HTTPBasicCredentials | None = Depends(security),
    user_manager: UserManager = Depends(get_user_manager),
) -> ArkanaUser:
    if bearer_credentials is not None:
        try:
            user = user_manager.authenticate_access_token(bearer_credentials.credentials)
        except AmezitUserPolicyError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        if user is not None:
            return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token or basic auth credentials",
            headers={"WWW-Authenticate": "Bearer, Basic"},
        )
    try:
        user = user_manager.authenticate(credentials.username, credentials.password)
    except AmezitUserPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token or basic auth credentials",
            headers={"WWW-Authenticate": "Bearer, Basic"},
        )
    return user


def require_admin(user: ArkanaUser = Depends(get_current_user)) -> ArkanaUser:
    if not user.is_admin():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
