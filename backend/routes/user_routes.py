from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
import uuid, datetime as dt
import bcrypt
import logging

from backend.models.user_model import UserData
from backend.database.mongodb import db, collection
from backend.utils.jwt_handler import create_access_token, require_user

router = APIRouter()

# ---------- Sessions collection ----------
sessions = db["sessions"]
collection.create_index("email", unique=True)

# Logger setup
logger = logging.getLogger("user_routes")
logging.basicConfig(level=logging.INFO)

# ---------- Helpers ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str
#----authentication  db search by email if yes then enter pass etc --#
def authenticate(email: str, password: str) -> dict:
    user = collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user
#-- it make session on every login and every session has new session _id or uniques_id--#
def make_session(user: dict, user_agent: str | None, ip: str | None):
    sid = uuid.uuid4().hex
    doc = {
        "sid": sid,
        "user_id": str(user["_id"]),
        "username": user.get("username") or user.get("name") or user["email"],
        "user_agent": user_agent or "",
        "ip": ip or "",
        "created_at": dt.datetime.utcnow(),
        "last_seen": dt.datetime.utcnow(),
        "revoked": False,
    }
    sessions.insert_one(doc)
    return sid, doc

# ================== AUTH ==================
#---- use email id and password generate new user and store it into mongo db --#
@router.post("/signup")
def signup(user: UserData):
    if collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    # Hash password
    hashed = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    data = user.dict()
    data["password"] = hashed

    res = collection.insert_one(data)
    return {"message": "User created successfully", "inserted_id": str(res.inserted_id)}
#---- user login authentication of user , new session is created on successful login---#
@router.post("/login")
def login(body: LoginIn, request: Request):
    user = authenticate(body.email, body.password)
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
#-----------new session creation and jwt user name ,sub,sid--#
    sid, sess = make_session(user, ua, ip)
    token = create_access_token({
        "sub": str(user["_id"]),
        "username": user.get("username") or user.get("name") or user["email"],
        "sid": sid
    })
    
    logger.info(f"User {user['email']} logged in, SID: {sid}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "session": {"sid": sid, "created_at": sess["created_at"]}
    }
#----- it logout user fron system  it revoke current session which is running on current token --#
@router.post("/logout", tags=["Users"])
def logout(user=Depends(require_user)):
    res = db["sessions"].update_one(
        {"sid": user["sid"], "user_id": user["user_id"]},
        {"$set": {"revoked": True}}
    )
    logger.info(f"User {user['user_id']} logged out, SID: {user['sid']}")
    return {"revoked": int(res.modified_count == 1)}
#-- get user info fro jwt after decode --#
@router.get("/me", tags=["Users"])
def me(user=Depends(require_user)):
    return {"username": user["username"], "user_id": user["user_id"], "sid": user["sid"]}

# ================== USER CRUD ==================

@router.post("/user")
def create_user(user: UserData):
    if collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    hashed = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    data = user.dict()
    data["password"] = hashed

    res = collection.insert_one(data)
    return {"inserted_id": str(res.inserted_id)}

@router.get("/user")
def get_users():
    users = []
    for u in collection.find({}, {"password": 0}):  # exclude password
        u["_id"] = str(u["_id"])
        users.append(u)
    return {"users": users}

@router.delete("/user/{name}")
def delete_user(name: str):
    result = collection.delete_one({"name": name})
    return {"deleted_count": result.deleted_count}

@router.put("/user/{name}")
def update_user(name: str, user: UserData):
    update_data = user.dict()
    if "password" in update_data:
        update_data["password"] = bcrypt.hashpw(
            update_data["password"].encode("utf-8"),
            bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

    result = collection.update_one({"name": name}, {"$set": update_data})
    return {"modified_count": result.modified_count}
