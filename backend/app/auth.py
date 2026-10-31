"""Authentication = Keycloak (JWT). Authorization = this module + route-level scoping.
Roles and class assignment are ALWAYS read from the database, never trusted from the browser."""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import KEYCLOAK_ISSUER, KEYCLOAK_JWKS_URL, REQUIRE_PHONE_VERIFIED
from .db import fetch_one

bearer = HTTPBearer(auto_error=False)
_jwks: jwt.PyJWKClient | None = None


def claims(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    global _jwks
    if not cred:
        raise HTTPException(401, "Not authenticated")
    if not KEYCLOAK_JWKS_URL or not KEYCLOAK_ISSUER:
        raise HTTPException(503, "Authentication is not configured")
    if _jwks is None:
        _jwks = jwt.PyJWKClient(KEYCLOAK_JWKS_URL)
    try:
        key = _jwks.get_signing_key_from_jwt(cred.credentials).key
        return jwt.decode(cred.credentials, key, algorithms=["RS256"],
                          issuer=KEYCLOAK_ISSUER, options={"verify_aud": False})
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired session")


def verified_claims(c: dict = Depends(claims)) -> dict:
    """Token for a user whose email (and phone, if enforced) is verified. Used before a profile exists."""
    if not c.get("email_verified"):
        raise HTTPException(403, "Please verify your email address first")
    if REQUIRE_PHONE_VERIFIED and not c.get("phone_number_verified"):
        raise HTTPException(403, "Please verify your phone number first")
    return c


def current_profile(c: dict = Depends(verified_claims)) -> dict:
    p = fetch_one("select * from profiles where auth_user_id = %s", (c["sub"],))
    if not p and c.get("email"):
        # HOD accounts are pre-provisioned by an administrator (scripts/create_hod.py); link on first verified login.
        p = fetch_one(
            """update profiles set auth_user_id = %s, updated_at = now()
               where lower(email) = lower(%s) and role = 'hod' and auth_user_id is null and active
               returning *""", (c["sub"], c["email"]))
    if not p:
        raise HTTPException(403, "Profile not registered")
    if not p["active"]:
        raise HTTPException(403, "Account deactivated")
    return p


def require(*roles: str):
    def dep(p: dict = Depends(current_profile)) -> dict:
        if p["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        if p["role"] == "teacher":
            a = fetch_one(
                "select class_id, can_adjust_ranking from teacher_assignments "
                "where teacher_id = %s and active order by created_at desc limit 1", (p["id"],))
            if not a:
                raise HTTPException(403, "No class assigned")
            p = {**p, "assigned_class_id": a["class_id"], "can_adjust_ranking": a["can_adjust_ranking"]}
        return p
    return dep


def can_access_submission(profile: dict, submission: dict, student_class_id, student_department_id=None) -> bool:
    """Object-level authorization (prevents IDOR). An HOD only sees their OWN department."""
    role = profile["role"]
    if role == "hod":
        return student_department_id is not None and student_department_id == profile.get("department_id")
    if role == "student":
        return submission["student_id"] == profile["id"]
    if role == "teacher":
        return student_class_id is not None and student_class_id == profile.get("assigned_class_id")
    return False
