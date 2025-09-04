import os
import logging
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from backend.database.mongodb import db
from bson import ObjectId

# Logger setup
logger = logging.getLogger("jwt_handler")
logging.basicConfig(level=logging.INFO)

# ---------- Config ----------
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-env")
ALGORITHM = os.getenv("JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")
sessions = db["sessions"]

# ---------- Token ization helpers ----------
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
# --- verification of tokens----#
def verify_token(token: str) -> Dict[str, str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        user_id  = payload.get("sub")
        sid      = payload.get("sid")

        if not (username and user_id and sid):
            raise HTTPException(status_code=401, detail="Invalid token payload")

        sess = sessions.find_one({"sid": sid})
        if not sess or sess.get("revoked"):
            raise HTTPException(status_code=401, detail="Session expired or revoked")

        sessions.update_one({"sid": sid}, {"$set": {"last_seen": datetime.utcnow()}})

        # 🟢 Always normalize user_id to string
        try:
            uid = str(ObjectId(user_id))  # if it’s a valid ObjectId
        except Exception:
            uid = str(user_id)  # already string

        # 🟢 Standardized return dict
        return {
            "_id": uid,
            "user_id": uid,
            "username": str(username),
            "sid": str(sid),
        }

    except JWTError as e:
        logger.error(f"JWT error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Dependency for protected routes---#
def require_user(token: str = Depends(oauth2_scheme)) -> Dict[str, str]:
    return verify_token(token)
