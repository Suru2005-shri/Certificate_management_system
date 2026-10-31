import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from . import services, storage
from .auth import can_access_submission, require
from .config import MAX_PHOTOS, MAX_UPLOAD_BYTES
from .db import fetch_all, fetch_one
from .ratelimit import limit
from .schemas import Category

router = APIRouter(prefix="/api")
student_only = require("student")


async def _read(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    return data


async def _collect(certificate: UploadFile | None, photos: list[UploadFile] | None) -> list:
    files = []
    if certificate:
        files.append(("certificate", certificate.filename or "", certificate.content_type, await _read(certificate)))
    for ph in (photos or [])[:MAX_PHOTOS]:
        files.append(("event_photo", ph.filename or "", ph.content_type, await _read(ph)))
    return files


def _fields(raw: str) -> dict:
    try:
        v = json.loads(raw)
        if not isinstance(v, dict):
            raise ValueError
        return v
    except ValueError:
        raise HTTPException(422, "Invalid form data")


@router.get("/student/dashboard")
def dashboard(p: dict = Depends(student_only)):
    counts = fetch_one(
        """select count(*) as total, count(*) filter (where status='approved') as verified,
                  count(*) filter (where status='pending') as pending from certificate_submissions where student_id=%s""", (p["id"],))
    skills = fetch_one("select count(distinct skill_name) as n from student_skills where student_id=%s", (p["id"],))
    rk = fetch_one("select coalesce(adjusted_rank, rank) as r from leaderboard_monthly "
                   "where student_id=%s and month=date_trunc('month', now())::date", (p["id"],))
    return {**counts, "skills": skills["n"], "monthly_rank": rk["r"] if rk else None}


@router.post("/certificates", status_code=201, dependencies=[Depends(limit("upload", 20, 3600))])
async def submit(category: Category = Form(...), fields: str = Form(...),
                 certificate: UploadFile = File(...), photos: list[UploadFile] | None = File(None),
                 p: dict = Depends(student_only)):
    # status, student_id, score are never accepted from the client
    return services.create_submission(p, category, _fields(fields), await _collect(certificate, photos))


@router.get("/certificates/my")
def mine(p: dict = Depends(student_only)):
    return fetch_all("select id, category, title, status, teacher_remark, created_at from certificate_submissions "
                     "where student_id=%s order by created_at desc", (p["id"],))


@router.get("/certificates/{sid}")
def detail(sid: str, p: dict = Depends(student_only)):
    s, ctx = services.get_submission(sid)
    if not can_access_submission(p, s, ctx["class_id"], ctx["department_id"]):
        raise HTTPException(404, "Not found")
    files = fetch_all("select id, file_name, file_kind from certificate_files where submission_id=%s", (sid,))
    for k in ("verification_score", "verification_flags"):
        s.pop(k, None)           # students are never told a certificate is "valid" by the automated checker
    return {**s, "files": files}


@router.post("/certificates/{sid}/resubmit", dependencies=[Depends(limit("upload", 20, 3600))])
async def resubmit(sid: str, fields: str = Form(...), certificate: UploadFile | None = File(None),
                   photos: list[UploadFile] | None = File(None), p: dict = Depends(student_only)):
    return services.resubmit(p, sid, _fields(fields), await _collect(certificate, photos))


@router.get("/certificates/{sid}/files/{fid}/url")
def file_url(sid: str, fid: str, p: dict = Depends(student_only)):
    s, ctx = services.get_submission(sid)
    if not can_access_submission(p, s, ctx["class_id"], ctx["department_id"]):
        raise HTTPException(404, "Not found")
    f = fetch_one("select storage_path from certificate_files where id=%s and submission_id=%s", (fid, sid))
    if not f:
        raise HTTPException(404, "Not found")
    return {"url": storage.signed_url(f["storage_path"])}
