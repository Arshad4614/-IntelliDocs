from fastapi import APIRouter, Depends, HTTPException, Query
from backend.utils.jwt_handler import require_user
from backend.database.mongodb import db
from datetime import datetime
import logging

# Logger setup
logger = logging.getLogger("session_routes")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/sessions", tags=["Sessions"])
sessions = db["sessions"]

# Ensure indexes for performance + optional TTL expiry
sessions.create_index("created_at")
sessions.create_index("last_seen")
# Uncomment if you want sessions to expire automatically (30 days):
# sessions.create_index("created_at", expireAfterSeconds=2592000)

#----it get the session of user latest session on the top- these are the active session of user ---#
@router.get("/my")
def list_my_sessions(user=Depends(require_user), limit: int = Query(10, ge=1), skip: int = Query(0, ge=0)):
    """List all active sessions for the current user."""
    cur = sessions.find(
        {"user_id": user["user_id"], "revoked": False},
        {"_id": 0, "sid": 1, "user_agent": 1, "ip": 1, "created_at": 1, "last_seen": 1}
    ).sort("created_at", -1).skip(skip).limit(limit)
    return {"ok": True, "sessions": list(cur)}
#--- it show the current _session of user revoke its mea user can logout or revoke his current session --###
@router.post("/revoke/current")
def revoke_current(user=Depends(require_user)):
    """Revoke the current session (logout)."""
    res = sessions.update_one(
        {"sid": user["sid"], "user_id": user["user_id"]},
        {"$set": {"revoked": True, "last_seen": datetime.utcnow()}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Session not found")
    logger.info(f"Session revoked for user {user['user_id']} (SID: {user['sid']})")
    return {"ok": True, "revoked": 1, "sid": user["sid"]}
#---- revoke the session of same user---#
@router.post("/revoke/{sid}")
def revoke_by_sid(sid: str, user=Depends(require_user)):
    """Revoke a specific session by ID."""
    res = sessions.update_one(
        {"sid": sid, "user_id": user["user_id"]},
        {"$set": {"revoked": True, "last_seen": datetime.utcnow()}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Session not found")
    logger.info(f"Session revoked for user {user['user_id']} (SID: {sid})")
    return {"ok": True, "revoked": 1, "sid": sid}

#--- leave current sessiion and revoke other-- means user can revoke all its sessio in one click --# 
@router.post("/revoke/others")
def revoke_other_sessions(user=Depends(require_user)):
    """Revoke all other sessions except the current one."""
    res = sessions.update_many(
        {"user_id": user["user_id"], "sid": {"$ne": user["sid"]}},
        {"$set": {"revoked": True, "last_seen": datetime.utcnow()}}
    )
    logger.info(f"Revoked other sessions for user {user['user_id']}")
    return {"ok": True, "revoked": res.modified_count}
