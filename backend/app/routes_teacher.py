from fastapi import APIRouter, Depends, HTTPException

from . import services, storage
from .auth import can_access_submission, require
from .db import execute, fetch_all, fetch_one
from .schemas import AdjustIn, ReviewIn

router = APIRouter(prefix="/api/teacher")
teacher_only = require("teacher")


@router.get("/dashboard")
def dashboard(p: dict = Depends(teacher_only)):
    return fetch_one(
        """select count(*) filter (where s.status in ('pending','under_review')) as pending,
                  count(*) filter (where s.status='approved' and date_trunc('month', s.verified_at)=date_trunc('month', now())) as approved_this_month,
                  count(*) filter (where s.status in ('rejected','resubmission_required')) as rejected_or_resubmission,
                  count(distinct s.student_id) as participating_students
           from certificate_submissions s join profiles pr on pr.id=s.student_id where pr.class_id=%s""",
        (p["assigned_class_id"],))


@router.get("/pending")
def pending(p: dict = Depends(teacher_only)):
    return fetch_all(
        """select s.id, s.student_id, s.status, pr.full_name as student_name, pr.roll_no, s.category, s.title, s.created_at,
                  s.verification_score, s.verification_flags->>'label' as verification_label
           from certificate_submissions s join profiles pr on pr.id=s.student_id
           where pr.class_id=%s and s.status in ('pending','under_review') order by s.created_at""", (p["assigned_class_id"],))


@router.get("/approved")
def approved(p: dict = Depends(teacher_only)):
    return fetch_all(
        """select s.id, s.student_id, s.status, pr.full_name as student_name, pr.roll_no, s.category, s.title, s.created_at, s.verified_at
           from certificate_submissions s join profiles pr on pr.id=s.student_id
           where pr.class_id=%s and s.status='approved' order by s.verified_at desc""", (p["assigned_class_id"],))


@router.get("/submissions/{sid}")
def submission(sid: str, p: dict = Depends(teacher_only)):
    s, ctx = services.get_submission(sid)
    if not can_access_submission(p, s, ctx["class_id"], ctx["department_id"]):
        raise HTTPException(404, "Not found")
    if s["status"] == "pending":
        execute("update certificate_submissions set status='under_review', updated_at=now() where id=%s", (sid,))
        s["status"] = "under_review"
    files = fetch_all("select id, file_name, file_kind from certificate_files where submission_id=%s", (sid,))
    return {**s, "files": files}


@router.get("/submissions/{sid}/files/{fid}/url")
def file_url(sid: str, fid: str, p: dict = Depends(teacher_only)):
    s, ctx = services.get_submission(sid)
    if not can_access_submission(p, s, ctx["class_id"], ctx["department_id"]):
        raise HTTPException(404, "Not found")
    f = fetch_one("select storage_path from certificate_files where id=%s and submission_id=%s", (fid, sid))
    if not f:
        raise HTTPException(404, "Not found")
    services.audit(p["id"], "file_accessed", "certificate_file", fid, {"submission": sid})
    return {"url": storage.signed_url(f["storage_path"])}


@router.post("/submissions/{sid}/approve")
def approve(sid: str, body: ReviewIn, p: dict = Depends(teacher_only)):
    return services.review(p, sid, "approved", body.remark)


@router.post("/submissions/{sid}/reject")
def reject(sid: str, body: ReviewIn, p: dict = Depends(teacher_only)):
    return services.review(p, sid, "rejected", body.remark)


@router.post("/submissions/{sid}/request-resubmission")
def request_resubmission(sid: str, body: ReviewIn, p: dict = Depends(teacher_only)):
    return services.review(p, sid, "resubmission_required", body.remark)


@router.get("/students")
def students(p: dict = Depends(teacher_only)):
    return fetch_all(
        """select pr.id, pr.full_name, pr.roll_no,
                  count(s.id) filter (where s.status='approved') as verified_certificates,
                  coalesce((select array_agg(distinct skill_name) from student_skills k where k.student_id=pr.id), '{}') as skills
           from profiles pr left join certificate_submissions s on s.student_id=pr.id
           where pr.class_id=%s and pr.role='student' and pr.active group by pr.id order by pr.roll_no""", (p["assigned_class_id"],))


@router.post("/leaderboard/{lid}/adjust")
def adjust(lid: str, body: AdjustIn, p: dict = Depends(teacher_only)):
    if not p["can_adjust_ranking"]:
        raise HTTPException(403, "You do not have permission to change rankings")
    row = fetch_one("select * from leaderboard_monthly where id=%s and class_id=%s", (lid, p["assigned_class_id"]))
    if not row:
        raise HTTPException(404, "Not found")
    previous = row["adjusted_rank"] or row["rank"]
    execute("update leaderboard_monthly set adjusted_rank=%s, adjusted_by=%s, adjustment_reason=%s, updated_at=now() where id=%s",
            (body.new_rank, p["id"], body.reason, lid))
    services.audit(p["id"], "leaderboard_adjusted", "leaderboard_monthly", lid,
                   {"previous_rank": previous, "new_rank": body.new_rank, "reason": body.reason})
    return {"id": lid, "rank": body.new_rank}
