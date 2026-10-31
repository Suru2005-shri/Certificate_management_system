import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException

from . import services
from .auth import require
from .db import execute, fetch_all, fetch_one, pool
from .schemas import AssignIn, RuleIn, TeacherIn, TeacherPatch, validate_identity

router = APIRouter(prefix="/api/hod")
hod_only = require("hod")
CODE_HOURS = 72


def _own_class(p: dict, class_name: str) -> dict:
    """A class of the HOD's own department (an HOD can never touch another department's classes)."""
    cls = fetch_one("select id from classes where class_name=%s and department_id=%s", (class_name, p["department_id"]))
    if not cls:
        raise HTTPException(404, "Class not found")
    return cls


@router.get("/summary")
def summary(p: dict = Depends(hod_only)):
    return fetch_one(
        """select (select count(*) from profiles where role='student' and active and department_id=%(d)s) as students,
                  count(*) as certificates,
                  count(*) filter (where s.status='pending') as pending,
                  count(*) filter (where s.status='approved') as approved
           from certificate_submissions s join profiles pr on pr.id=s.student_id where pr.department_id=%(d)s""",
        {"d": p["department_id"]})


@router.get("/students")
def students(class_name: str | None = None, p: dict = Depends(hod_only)):
    return fetch_all(
        """select pr.id, pr.full_name, pr.roll_no, c.class_name,
                  count(s.id) filter (where s.status='approved') as approved_certificates
           from profiles pr join classes c on c.id=pr.class_id left join certificate_submissions s on s.student_id=pr.id
           where pr.role='student' and pr.department_id=%(d)s and (%(c)s::text is null or c.class_name=%(c)s)
           group by pr.id, c.class_name order by c.class_name, pr.roll_no""", {"c": class_name, "d": p["department_id"]})


@router.get("/certificates")
def certificates(class_name: str | None = None, status: str | None = None, category: str | None = None,
                 month: str | None = None, student: str | None = None, limit: int = 50, offset: int = 0,
                 p: dict = Depends(hod_only)):
    limit = max(1, min(limit, 200))
    m = services.month_start(month) if month else None
    return fetch_all(
        """select s.id, s.student_id, pr.full_name as student_name, pr.roll_no, c.class_name, s.category, s.title, s.status, s.created_at
           from certificate_submissions s join profiles pr on pr.id=s.student_id join classes c on c.id=pr.class_id
           where pr.department_id=%(d)s and (%(c)s::text is null or c.class_name=%(c)s) and (%(st)s::text is null or s.status::text=%(st)s)
             and (%(cat)s::text is null or s.category::text=%(cat)s)
             and (%(m)s::date is null or date_trunc('month', s.created_at)=%(m)s::date)
             and (%(q)s::text is null or pr.full_name ilike '%%'||%(q)s||'%%')
           order by s.created_at desc limit %(l)s offset %(o)s""",
        {"d": p["department_id"], "c": class_name, "st": status, "cat": category, "m": m, "q": student, "l": limit, "o": max(0, offset)})


@router.get("/teachers")
def teachers(p: dict = Depends(hod_only)):
    return fetch_all(
        """select t.id, t.full_name, t.email, t.phone, t.active, t.auth_user_id is not null as activated,
                  c.class_name, a.can_adjust_ranking
           from profiles t left join teacher_assignments a on a.teacher_id=t.id and a.active
           left join classes c on c.id=a.class_id where t.role='teacher' and t.department_id=%s order by t.full_name""",
        (p["department_id"],))


@router.post("/teachers", status_code=201)
def add_teacher(body: TeacherIn, p: dict = Depends(hod_only)):
    validate_identity(body.email, body.phone)
    if fetch_one("select 1 from profiles where lower(email)=lower(%s)", (body.email,)):
        raise HTTPException(409, "A user with this email already exists")
    cls = _own_class(p, body.class_name)
    code = secrets.token_urlsafe(9)         # shown once; only its hash is stored; single-use, expires
    with pool.connection() as c:
        t = c.execute(
            """insert into profiles (full_name, email, phone, department_id, role, access_code_hash, access_code_expires)
               values (%s,%s,%s,%s,'teacher',%s, now() + make_interval(hours => %s)) returning id""",
            (body.full_name.strip(), body.email, body.phone, p["department_id"], hashlib.sha256(code.encode()).hexdigest(), CODE_HOURS)).fetchone()
        c.execute("insert into teacher_assignments (teacher_id, class_id, assigned_by, can_adjust_ranking) values (%s,%s,%s,%s)",
                  (t["id"], cls["id"], p["id"], body.can_adjust_ranking))
    services.audit(p["id"], "teacher_added", "profile", t["id"], {"class": body.class_name})
    return {"id": t["id"], "access_code": code, "expires_in_hours": CODE_HOURS}


@router.patch("/teachers/{tid}")
def patch_teacher(tid: str, body: TeacherPatch, p: dict = Depends(hod_only)):
    t = fetch_one("select * from profiles where id=%s and role='teacher' and department_id=%s", (tid, p["department_id"]))
    if not t:
        raise HTTPException(404, "Not found")
    if body.phone:
        validate_identity(t["email"], body.phone)
    execute("update profiles set full_name=coalesce(%s, full_name), phone=coalesce(%s, phone), active=coalesce(%s, active), updated_at=now() where id=%s",
            (body.full_name, body.phone, body.active, tid))
    if body.active is False:
        execute("update teacher_assignments set active=false, updated_at=now() where teacher_id=%s", (tid,))
    services.audit(p["id"], "teacher_updated", "profile", tid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.post("/teacher-assignments", status_code=201)
def assign(body: AssignIn, p: dict = Depends(hod_only)):
    if not fetch_one("select 1 from profiles where id=%s and role='teacher' and active and department_id=%s",
                     (body.teacher_id, p["department_id"])):
        raise HTTPException(404, "Teacher not found")
    cls = _own_class(p, body.class_name)
    with pool.connection() as c:
        c.execute("update teacher_assignments set active=false, updated_at=now() where teacher_id=%s and active", (body.teacher_id,))
        c.execute("insert into teacher_assignments (teacher_id, class_id, assigned_by, can_adjust_ranking) values (%s,%s,%s,%s)",
                  (body.teacher_id, cls["id"], p["id"], body.can_adjust_ranking))
        c.execute("update classes set advisor_id=%s, updated_at=now() where id=%s", (body.teacher_id, cls["id"]))
    services.audit(p["id"], "teacher_assigned", "teacher_assignment", body.teacher_id, {"class": body.class_name})
    return {"ok": True}


@router.get("/scoring-rules")
def rules(p: dict = Depends(hod_only)):
    return fetch_all("select id, category, base_points, active from scoring_rules where department_id=%s order by category",
                     (p["department_id"],))


@router.patch("/scoring-rules/{rid}")
def patch_rule(rid: str, body: RuleIn, p: dict = Depends(hod_only)):
    if not fetch_one("select 1 from scoring_rules where id=%s and department_id=%s", (rid, p["department_id"])):
        raise HTTPException(404, "Not found")
    execute("update scoring_rules set base_points=coalesce(%s, base_points), active=coalesce(%s, active), updated_by=%s, updated_at=now() where id=%s",
            (body.base_points, body.active, p["id"], rid))
    services.audit(p["id"], "scoring_rule_changed", "scoring_rule", rid, body.model_dump(exclude_none=True))
    return {"ok": True}


@router.get("/audit-logs")
def audit_logs(limit: int = 100, offset: int = 0, p: dict = Depends(hod_only)):
    return fetch_all(
        """select a.id, a.created_at, pr.full_name as actor, a.action, a.entity_type, a.entity_id, a.metadata
           from audit_logs a left join profiles pr on pr.id=a.actor_id
           where pr.department_id=%s order by a.created_at desc limit %s offset %s""",
        (p["department_id"], max(1, min(limit, 500)), max(0, offset)))
