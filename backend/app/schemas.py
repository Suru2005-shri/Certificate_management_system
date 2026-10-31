import re
from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .config import ALLOWED_EMAIL_DOMAINS, PHONE_PATTERN, ROLL_NO_PATTERN

Category = Literal["workshop", "internship", "hackathon", "participation", "sports", "other"]
ClassName = Literal["SE", "TE", "BE"]

LEVELS = ["College", "Taluka", "District", "Zonal", "State", "National"]
# category -> (required keys, allowed modes or None)
SPEC: dict[str, tuple[list[str], list[str] | None]] = {
    "workshop": (["title", "duration", "start", "end", "mode", "learning"], ["Online", "Offline"]),
    "internship": (["title", "duration", "start", "end", "mode", "skills"], ["Remote", "Hybrid", "Offline"]),
    "hackathon": (["title", "mode"], ["Online", "Offline"]),
    "participation": (["title", "duration", "learning", "place", "mode"], ["Online", "Offline"]),
    "sports": (["title", "place", "level"], None),
    "other": (["otherType", "title"], None),
}
OPTIONAL = {"duration", "start", "end", "mode", "place", "learning", "skills", "prize", "level", "otherType", "title", "certificateNo"}
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean(v: object) -> str:
    return _CTRL.sub("", str(v or "")).strip()[:2000]


def validate_fields(category: str, raw: dict) -> dict[str, str]:
    if category not in SPEC:
        raise HTTPException(422, "Unknown certificate type")
    required, modes = SPEC[category]
    f = {k: clean(v) for k, v in raw.items() if k in OPTIONAL and clean(v)}
    errors: list[str] = []
    for k in required:
        if not f.get(k):
            errors.append(f"{k} is required")
    if modes and f.get("mode") and f["mode"] not in modes:
        errors.append("mode is not valid for this certificate type")
    if f.get("mode") == "Offline" and category in ("workshop", "hackathon", "participation") and not f.get("place"):
        errors.append("place is required for offline events")
    if category == "sports" and f.get("level") not in LEVELS:
        errors.append("level is not valid")
    for k in ("start", "end"):
        if f.get(k):
            try:
                date.fromisoformat(f[k])
            except ValueError:
                errors.append(f"{k} is not a valid date")
    if not errors and f.get("start") and f.get("end") and f["end"] < f["start"]:
        errors.append("end date cannot be before start date")
    if errors:
        raise HTTPException(422, "; ".join(errors))
    return f


def validate_identity(email: str, phone: str, roll_no: str | None = None) -> None:
    if ALLOWED_EMAIL_DOMAINS and email.split("@")[-1].lower() not in ALLOWED_EMAIL_DOMAINS:
        raise HTTPException(422, "This email domain is not allowed")
    if not re.match(PHONE_PATTERN, phone):
        raise HTTPException(422, "Enter a valid phone number")
    if roll_no is not None and not re.match(ROLL_NO_PATTERN, roll_no):
        raise HTTPException(422, "Roll number format is not valid")


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    roll_no: str
    department: str = Field(pattern=r"^(CS|AIML|IT|CIVIL)$")
    class_name: ClassName
    phone: str
    captcha_token: str | None = None


class TeacherActivateIn(BaseModel):
    phone: str
    access_code: str = Field(min_length=6, max_length=64)


class ReviewIn(BaseModel):
    remark: str | None = Field(default=None, max_length=1000)


class AdjustIn(BaseModel):
    new_rank: int = Field(ge=1, le=500)
    reason: str = Field(min_length=3, max_length=500)


class TeacherIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str
    phone: str
    class_name: ClassName
    can_adjust_ranking: bool = False


class TeacherPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = None
    active: bool | None = None


class AssignIn(BaseModel):
    teacher_id: str
    class_name: ClassName
    can_adjust_ranking: bool = False


class RuleIn(BaseModel):
    base_points: int | None = Field(default=None, ge=0, le=100)
    active: bool | None = None
