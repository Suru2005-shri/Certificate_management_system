"""Business logic (kept out of route handlers)."""
import json
from datetime import date, datetime, timezone

from fastapi import HTTPException

from . import forensics, storage, verify
from .db import fetch_all, fetch_one, pool
from .scoring import points, rank
from .schemas import validate_fields

DETAIL_KEYS = {"prize": "prize", "level": "sport_level", "otherType": "other_type"}


def audit(actor_id, action: str, entity_type: str, entity_id=None, metadata: dict | None = None) -> None:
    with pool.connection() as c:
        c.execute("insert into audit_logs (actor_id, action, entity_type, entity_id, metadata) values (%s,%s,%s,%s,%s)",
                  (actor_id, action, entity_type, entity_id, json.dumps(metadata or {})))


def notify(user_id, type_: str, title: str, message: str = "") -> None:
    # Never include certificate contents in notifications
    with pool.connection() as c:
        c.execute("insert into notifications (user_id, type, title, message) values (%s,%s,%s,%s)",
                  (user_id, type_, title, message))


def class_teacher_ids(class_id) -> list:
    rows = fetch_all("select teacher_id from teacher_assignments ta join profiles p on p.id = ta.teacher_id "
                     "where ta.class_id = %s and ta.active and p.active", (class_id,))
    return [r["teacher_id"] for r in rows]


def _store_files(student_id, submission_id, files: list[tuple[str, str, str | None, bytes]]) -> tuple[bytes | None, str | None]:
    """files: (kind, filename, content_type, data). Returns the certificate bytes/mime for the automated check."""
    cert_bytes, cert_mime = None, None
    for kind, name, ctype, data in files:
        ext, mime = storage.validate_upload(name, ctype, data, photo=(kind == "event_photo"))
        key = storage.put(student_id, submission_id, ext, mime, data)
        with pool.connection() as c:
            c.execute("insert into certificate_files (submission_id, storage_path, file_name, mime_type, size, file_kind) "
                      "values (%s,%s,%s,%s,%s,%s)", (submission_id, key, name[:200], mime, len(data), kind))
        if kind == "certificate":
            cert_bytes, cert_mime = data, mime
    return cert_bytes, cert_mime


PHASH_NEAR = 6          # max differing bits (of 64) to call two certificate images "the same picture"


def _reuse_signals(student: dict, sub_id, flags: dict) -> list[dict]:
    """Compare this certificate with everything already in the database (reuse / copy detection)."""
    out: list[dict] = []
    me = student["id"]
    if flags.get("sha256"):
        for r in fetch_all(
                """select s.student_id from certificate_files cf join certificate_submissions s on s.id = cf.submission_id
                   where cf.sha256=%s and cf.file_kind='certificate' and s.id <> %s""", (flags["sha256"], sub_id)):
            out.append({"level": "warn" if r["student_id"] == me else "alert", "code": "dup_file",
                        "text": "You already submitted this exact file before" if r["student_id"] == me
                        else "This exact file was already submitted by another student"})
            break
    if flags.get("cert_numbers"):
        for r in fetch_all(
                """select s.student_id from certificate_submissions s where s.cert_numbers && %s::text[] and s.id <> %s""",
                (flags["cert_numbers"], sub_id)):
            out.append({"level": "warn" if r["student_id"] == me else "alert", "code": "dup_cert_no",
                        "text": "This certificate number was already used in your earlier submission" if r["student_id"] == me
                        else "This certificate number was already used by another student"})
            break
    if flags.get("phash"):
        for r in fetch_all("select phash, s.student_id from certificate_files cf join certificate_submissions s on s.id=cf.submission_id "
                           "where cf.phash is not null and cf.file_kind='certificate' and s.id <> %s limit 20000", (sub_id,)):
            if forensics.hamming(r["phash"], flags["phash"]) <= PHASH_NEAR and r["student_id"] != me:
                out.append({"level": "alert", "code": "dup_image",
                            "text": "This certificate looks like the same picture as one submitted by another student "
                                    "(possible name change on someone else's certificate)"})
                break
    return out


def _verify_and_save(student: dict, sub_id, cert_bytes: bytes, cert_mime: str, f: dict) -> None:
    score, flags = verify.run(cert_bytes, cert_mime, student["full_name"], f["title"],
                              [f.get("start", ""), f.get("end", "")], f.get("certificateNo"))
    flags["signals"] = flags.get("signals", []) + _reuse_signals(student, sub_id, flags)
    score, flags = verify.refinish(score, flags)
    with pool.connection() as c:
        c.execute("update certificate_submissions set verification_score=%s, verification_flags=%s, certificate_no=%s, "
                  "cert_numbers=%s where id=%s",
                  (score, json.dumps(flags), f.get("certificateNo"), flags.get("cert_numbers") or [], sub_id))
        c.execute("update certificate_files set sha256=%s, phash=%s where submission_id=%s and file_kind='certificate' and sha256 is null",
                  (flags.get("sha256"), flags.get("phash"), sub_id))


def create_submission(student: dict, category: str, raw_fields: dict, files: list) -> dict:
    f = validate_fields(category, raw_fields)
    if not any(k == "certificate" for k, *_ in files):
        raise HTTPException(422, "Please attach your certificate")
    # validate everything BEFORE writing anything
    for kind, name, ctype, data in files:
        storage.validate_upload(name, ctype, data, photo=(kind == "event_photo"))

    start = date.fromisoformat(f["start"]) if f.get("start") else None
    end = date.fromisoformat(f["end"]) if f.get("end") else None
    with pool.connection() as c:
        sub = c.execute(
            """insert into certificate_submissions
               (student_id, category, title, start_date, end_date, duration, mode, place, learning, status)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending') returning id""",
            (student["id"], category, f["title"], start, end, f.get("duration"), f.get("mode"),
             f.get("place"), f.get("learning") or f.get("skills"))).fetchone()
        skills = [s.strip() for s in f.get("skills", "").split(",") if s.strip()][:20]
        c.execute("insert into certificate_details (submission_id, company_name, prize, sport_level, skills, event_name, other_type) "
                  "values (%s,%s,%s,%s,%s,%s,%s)",
                  (sub["id"], f["title"] if category == "internship" else None, f.get("prize"), f.get("level"),
                   skills or None, f["title"] if category in ("participation", "hackathon") else None, f.get("otherType")))
    cert_bytes, cert_mime = _store_files(student["id"], sub["id"], files)

    if cert_bytes:
        _verify_and_save(student, sub["id"], cert_bytes, cert_mime, f)

    audit(student["id"], "certificate_submitted", "certificate_submission", sub["id"], {"category": category})
    notify(student["id"], "submission_received", "Certificate submitted", f.get("title", ""))
    for tid in class_teacher_ids(student["class_id"]):
        notify(tid, "new_submission", "New certificate to review", student["full_name"])
    return {"id": sub["id"], "status": "pending"}


def resubmit(student: dict, submission_id, raw_fields: dict, files: list) -> dict:
    s = fetch_one("select * from certificate_submissions where id=%s", (submission_id,))
    if not s or s["student_id"] != student["id"]:
        raise HTTPException(404, "Not found")
    if s["status"] != "resubmission_required":
        raise HTTPException(409, "This certificate is not awaiting resubmission")
    f = validate_fields(s["category"], raw_fields)
    for kind, name, ctype, data in files:
        storage.validate_upload(name, ctype, data, photo=(kind == "event_photo"))
    with pool.connection() as c:
        c.execute("""update certificate_submissions set title=%s, start_date=%s, end_date=%s, duration=%s, mode=%s, place=%s,
                     learning=%s, status='pending', teacher_remark=null, updated_at=now() where id=%s""",
                  (f["title"], f.get("start") or None, f.get("end") or None, f.get("duration"), f.get("mode"),
                   f.get("place"), f.get("learning") or f.get("skills"), submission_id))
    if files:
        cert_bytes, cert_mime = _store_files(student["id"], submission_id, files)
        if cert_bytes:
            _verify_and_save(student, submission_id, cert_bytes, cert_mime, f)
    audit(student["id"], "certificate_resubmitted", "certificate_submission", submission_id)
    for tid in class_teacher_ids(student["class_id"]):
        notify(tid, "new_submission", "Certificate resubmitted", student["full_name"])
    return {"id": submission_id, "status": "pending"}


def get_submission(submission_id) -> tuple[dict, dict]:
    row = fetch_one(
        """select s.*, p.full_name as student_name, p.roll_no, p.class_id as student_class_id, p.department_id as student_department_id,
                  d.company_name, d.prize, d.sport_level, d.skills, d.event_name, d.other_type
           from certificate_submissions s join profiles p on p.id = s.student_id
           left join certificate_details d on d.submission_id = s.id where s.id = %s""", (submission_id,))
    if not row:
        raise HTTPException(404, "Not found")
    return row, {"class_id": row["student_class_id"], "department_id": row["student_department_id"]}


def month_start(month: str) -> date:
    try:
        y, m = month.split("-")
        return date(int(y), int(m), 1)
    except Exception:
        raise HTTPException(422, "Month must look like 2026-10")


def recompute_leaderboard(class_id, when: datetime) -> None:
    m = date(when.year, when.month, 1)
    rules = {r["category"]: r["base_points"] for r in fetch_all(
        "select r.category, r.base_points from scoring_rules r join classes c on c.department_id = r.department_id "
        "where r.active and c.id = %s", (class_id,))}
    rows = fetch_all(
        """select s.student_id, s.category, d.sport_level, d.prize from certificate_submissions s
           join profiles p on p.id = s.student_id left join certificate_details d on d.submission_id = s.id
           where p.class_id = %s and s.status = 'approved' and date_trunc('month', s.verified_at) = %s""", (class_id, m))
    totals: dict[str, int] = {}
    for r in rows:
        totals[str(r["student_id"])] = totals.get(str(r["student_id"]), 0) + points(
            r["category"], rules.get(r["category"], 0), r["sport_level"], r["prize"])
    with pool.connection() as c:
        c.execute("delete from leaderboard_monthly where class_id=%s and month=%s and student_id <> all(%s::uuid[]) "
                  "and adjusted_rank is null", (class_id, m, list(totals.keys())))
        for sid, score, rk in rank(list(totals.items())):
            c.execute("""insert into leaderboard_monthly (class_id, month, student_id, score, rank) values (%s,%s,%s,%s,%s)
                         on conflict (class_id, month, student_id) do update set score=excluded.score, rank=excluded.rank, updated_at=now()""",
                      (class_id, m, sid, score, rk))


def review(teacher: dict, submission_id, decision: str, remark: str | None) -> dict:
    sub, ctx = get_submission(submission_id)
    if ctx["class_id"] != teacher["assigned_class_id"]:
        raise HTTPException(404, "Not found")          # do not reveal other classes' records
    if sub["status"] not in ("pending", "under_review"):
        raise HTTPException(409, "This certificate has already been decided")
    if decision != "approved" and not (remark or "").strip():
        raise HTTPException(422, "A remark is required")
    now = datetime.now(timezone.utc)
    with pool.connection() as c:
        c.execute("update certificate_submissions set status=%s, teacher_remark=%s, verified_by=%s, verified_at=%s, updated_at=now() where id=%s",
                  (decision, (remark or "").strip() or None, teacher["id"], now, submission_id))
        if decision == "approved":
            for sk in sub["skills"] or []:
                c.execute("insert into student_skills (student_id, skill_name, source_submission_id) values (%s,%s,%s)",
                          (sub["student_id"], sk, submission_id))
    if decision == "approved":
        recompute_leaderboard(ctx["class_id"], now)
    audit(teacher["id"], f"certificate_{decision}", "certificate_submission", submission_id)
    notify(sub["student_id"], f"certificate_{decision}", "Your certificate was " + decision.replace("_", " "))
    return {"id": submission_id, "status": decision}
