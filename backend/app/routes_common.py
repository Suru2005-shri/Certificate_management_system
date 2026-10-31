import hashlib
import hmac
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException

from . import services
from .auth import current_profile, require, verified_claims
from .config import MCAPTCHA_SECRET, MCAPTCHA_SITE_KEY, MCAPTCHA_VERIFY_URL
from .db import execute, fetch_all, fetch_one
from .ratelimit import limit
from .schemas import RegisterIn, TeacherActivateIn, validate_identity

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/departments")
def departments():
    """Public: departments and their classes (with advisor), read from the database."""
    deps = fetch_all("select id, code, name from departments where active order by position")
    cls = fetch_all(
        """select c.department_id, c.class_name, p.full_name as advisor from classes c
           left join profiles p on p.id = c.advisor_id where c.active
           order by array_position(array['SE','TE','BE'], c.class_name)""")
    return [{"code": d["code"], "name": d["name"],
             "classes": [{"class_name": c["class_name"], "advisor": c["advisor"]} for c in cls if c["department_id"] == d["id"]]}
            for d in deps]


@router.get("/classes")
def classes(department: str | None = None):
    """Public: class list with its advisor and department code."""
    return fetch_all(
        """select c.class_name, d.code as department, p.full_name as advisor from classes c
           join departments d on d.id = c.department_id
           left join profiles p on p.id = c.advisor_id
           where c.active and (%(d)s::text is null or d.code = upper(%(d)s))
           order by d.position, array_position(array['SE','TE','BE'], c.class_name)""", {"d": department})


def _captcha_ok(token: str | None) -> bool:
    if not MCAPTCHA_VERIFY_URL:
        return True      # CAPTCHA not configured for this environment
    if not token:
        return False
    try:
        r = httpx.post(MCAPTCHA_VERIFY_URL, json={"token": token, "key": MCAPTCHA_SITE_KEY, "secret": MCAPTCHA_SECRET}, timeout=5)
        return bool(r.json().get("valid"))
    except Exception:
        return False


@router.post("/profile/register", status_code=201, dependencies=[Depends(limit("register", 5, 600))])
def register_student(body: RegisterIn, c: dict = Depends(verified_claims)):
    """Creates a STUDENT profile after Keycloak sign-up. Role is fixed server-side; HOD/teacher can never be created here."""
    if not _captcha_ok(body.captcha_token):
        raise HTTPException(422, "CAPTCHA verification failed")
    email = c.get("email", "")
    validate_identity(email, body.phone, body.roll_no)
    if fetch_one("select 1 from profiles where auth_user_id=%s or lower(email)=lower(%s)", (c["sub"], email)):
        raise HTTPException(409, "Profile already exists")
    cls = fetch_one(
        """select c.id, c.department_id from classes c join departments d on d.id = c.department_id
           where c.class_name=%s and d.code=%s and c.active and d.active""", (body.class_name, body.department.upper()))
    if not cls:
        raise HTTPException(422, "Unknown department or class")
    if fetch_one("select 1 from profiles where roll_no=%s", (body.roll_no,)):
        raise HTTPException(409, "This roll number is already registered")
    row = fetch_one(
        """insert into profiles (auth_user_id, full_name, email, phone, roll_no, class_id, department_id, role)
           values (%s,%s,%s,%s,%s,%s,%s,'student') returning id""",
        (c["sub"], body.full_name.strip(), email, body.phone, body.roll_no, cls["id"], cls["department_id"]))
    services.audit(row["id"], "student_registered", "profile", row["id"])
    return {"id": row["id"], "role": "student"}


@router.post("/auth/teacher-activate", dependencies=[Depends(limit("teacher_activate", 5, 600))])
def teacher_activate(body: TeacherActivateIn, c: dict = Depends(verified_claims)):
    """Teacher links their verified login to the profile the HOD created (phone + single-use access code)."""
    row = fetch_one(
        "select * from profiles where role='teacher' and auth_user_id is null and active and lower(email)=lower(%s) and phone=%s",
        (c.get("email", ""), body.phone))
    ok = bool(row and row["access_code_hash"] and row["access_code_expires"]
              and row["access_code_expires"] > fetch_one("select now() as n")["n"]
              and hmac.compare_digest(row["access_code_hash"], hashlib.sha256(body.access_code.encode()).hexdigest()))
    if not ok:
        raise HTTPException(403, "Invalid or expired access code")     # same message for every failure reason
    execute("update profiles set auth_user_id=%s, access_code_hash=null, access_code_expires=null, updated_at=now() where id=%s",
            (c["sub"], row["id"]))
    services.audit(row["id"], "teacher_activated", "profile", row["id"])
    return {"id": row["id"], "role": "teacher"}


@router.get("/me")
def me(p: dict = Depends(current_profile)):
    cls = fetch_one("select class_name from classes where id=%s", (p["class_id"],)) if p["class_id"] else None
    dep = fetch_one("select code, name from departments where id=%s", (p["department_id"],))
    adv = fetch_one("select pr.full_name from classes c join profiles pr on pr.id=c.advisor_id where c.id=%s",
                    (p["class_id"],)) if p["class_id"] else None
    assigned = None
    if p["role"] == "teacher":
        a = fetch_one("select c.class_name from teacher_assignments t join classes c on c.id=t.class_id "
                      "where t.teacher_id=%s and t.active order by t.created_at desc limit 1", (p["id"],))
        assigned = a["class_name"] if a else None
    return {"id": p["id"], "full_name": p["full_name"], "role": p["role"], "roll_no": p["roll_no"],
            "department": dep["code"], "department_name": dep["name"],
            "class_name": cls["class_name"] if cls else assigned, "advisor": adv["full_name"] if adv else None}


@router.get("/leaderboard/{class_name}/{month}")
def get_leaderboard(class_name: str, month: str, p: dict = Depends(require("student", "teacher", "hod"))):
    # always the caller's own department; students/teachers additionally only their own class
    cls = fetch_one("select id from classes where class_name=%s and department_id=%s", (class_name.upper(), p["department_id"]))
    if not cls:
        raise HTTPException(404, "Not found")
    own = p["class_id"] if p["role"] == "student" else p.get("assigned_class_id")
    if p["role"] != "hod" and cls["id"] != own:
        raise HTTPException(403, "You can only view your own class leaderboard")
    m = services.month_start(month)
    rows = fetch_all(
        """select l.id, pr.full_name, pr.roll_no, l.score, l.rank, l.adjusted_rank,
                  coalesce(l.adjusted_rank, l.rank) as final_rank
           from leaderboard_monthly l join profiles pr on pr.id = l.student_id
           where l.class_id=%s and l.month=%s order by final_rank, l.score desc""", (cls["id"], m))
    return {"class": class_name.upper(), "month": month, "student_of_the_month": rows[0]["full_name"] if rows else None,
            "rows": rows}


@router.get("/notifications")
def notifications(p: dict = Depends(current_profile)):
    return fetch_all("select id, type, title, message, read_at, created_at from notifications "
                     "where user_id=%s order by created_at desc limit 50", (p["id"],))


@router.post("/notifications/read")
def mark_read(p: dict = Depends(current_profile)):
    execute("update notifications set read_at=now() where user_id=%s and read_at is null", (p["id"],))
    return {"ok": True}
