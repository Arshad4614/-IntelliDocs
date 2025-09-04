import os
import jwt
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Logger setup
logger = logging.getLogger("security_service")
logging.basicConfig(level=logging.INFO)
#---- security scheme--#
security = HTTPBearer(auto_error=True)
#--- jwt configuration scheme--#
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")  # Set in .env
JWT_ALG = os.getenv("JWT_ALG", "HS256")
#--- main fuction fo get current user--#
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Enforces JWT auth:
    - Requires Authorization: Bearer <token>
    - Validates JWT token
    - Rejects invalid/missing tokens
    """
    # token validation----#
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token required",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        #--- extract user data---#
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(401, "Invalid token payload")
        
        # Optional: logging failed token attempts
        logger.info(f"User {user_id} authenticated successfully")
# ---- return user object--#
        return {
            "_id": user_id,
            "role": payload.get("role", "user"),
            "email": payload.get("email"),
            "username": payload.get("username"),
        }
    # error--- handling ---#
    except jwt.ExpiredSignatureError:
        logger.warning(f"Token expired for user: {credentials.credentials}")
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        logger.warning(f"Invalid token attempted by user: {credentials.credentials}")
        raise HTTPException(401, "Invalid token")
