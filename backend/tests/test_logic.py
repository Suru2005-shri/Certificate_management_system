import pytest
from fastapi import HTTPException

from app import ratelimit, scoring, storage, verify
from app.auth import can_access_submission
from app.schemas import validate_fields, validate_identity

PDF = b"%PDF-1.4\n" + b"x" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100


# ---- input validation ----
def test_end_before_start_rejected():
    with pytest.raises(HTTPException) as e:
        validate_fields("workshop", {"title": "W", "duration": "1d", "start": "2026-10-05", "end": "2026-10-01",
                                     "mode": "Online", "learning": "x"})
    assert e.value.status_code == 422


def test_offline_requires_place():
    with pytest.raises(HTTPException):
        validate_fields("hackathon", {"title": "H", "mode": "Offline"})
    assert validate_fields("hackathon", {"title": "H", "mode": "Offline", "place": "Mumbai"})["place"] == "Mumbai"


def test_sports_level_must_be_valid():
    with pytest.raises(HTTPException):
        validate_fields("sports", {"title": "Football", "place": "Thane", "level": "Galactic"})


def test_unknown_fields_are_dropped():
    f = validate_fields("hackathon", {"title": "H", "mode": "Online", "status": "approved", "verification_score": "99"})
    assert "status" not in f and "verification_score" not in f


def test_identity_checks():
    with pytest.raises(HTTPException):
        validate_identity("a@b.com", "123")
    with pytest.raises(HTTPException):
        validate_identity("a@b.com", "9876543210", "!!")
    validate_identity("a@b.com", "9876543210", "SE-IT-01")


# ---- uploads ----
def test_valid_upload_accepted():
    assert storage.validate_upload("c.pdf", "application/pdf", PDF) == (".pdf", "application/pdf")


@pytest.mark.parametrize("name,ctype,data", [
    ("run.exe", "application/octet-stream", b"MZ" + b"0" * 50),
    ("c.pdf", "application/pdf", b"not a pdf"),               # wrong signature
    ("c.pdf", "image/png", PDF),                              # mime mismatch
    ("c.png", "image/png", b""),                              # empty
    ("c.pdf", "application/pdf", PDF + b"0" * (5 * 1024 * 1024)),   # too large
])
def test_bad_uploads_rejected(name, ctype, data):
    with pytest.raises(HTTPException):
        storage.validate_upload(name, ctype, data)


def test_photo_must_be_image():
    with pytest.raises(HTTPException):
        storage.validate_upload("c.pdf", "application/pdf", PDF, photo=True)
    storage.validate_upload("p.png", "image/png", PNG, photo=True)


# ---- scoring / leaderboard ----
def test_points_with_bonuses():
    assert scoring.points("workshop", 5, None, None) == 5
    assert scoring.points("sports", 8, "National", None) == 16
    assert scoring.points("hackathon", 10, None, "1st") == 15
    assert scoring.points("hackathon", 10, None, "  ") == 10


def test_ranking_with_ties():
    out = scoring.rank([("a", 10), ("b", 15), ("c", 10), ("d", 5)])
    assert out == [("b", 15, 1), ("a", 10, 2), ("c", 10, 2), ("d", 5, 4)]


# ---- access control (IDOR) ----
def test_object_level_access():
    sub = {"student_id": "s1"}
    assert can_access_submission({"role": "student", "id": "s1"}, sub, "c1")
    assert not can_access_submission({"role": "student", "id": "s2"}, sub, "c1")
    assert can_access_submission({"role": "teacher", "assigned_class_id": "c1"}, sub, "c1")
    assert not can_access_submission({"role": "teacher", "assigned_class_id": "c2"}, sub, "c1")
    assert can_access_submission({"role": "hod", "department_id": "d1"}, sub, "c1", "d1")
    assert not can_access_submission({"role": "hod", "department_id": "d2"}, sub, "c1", "d1")   # other department's HOD
    assert not can_access_submission({"role": "hod", "department_id": "d1"}, sub, "c1")
    assert not can_access_submission({"role": "teacher"}, sub, None)


# ---- rate limiting ----
def test_rate_limit_blocks_then_recovers():
    key = "t:ip"
    assert [ratelimit.check(key, 3, 60, now=100.0 + i) for i in range(3)] == [0, 0, 0]
    assert ratelimit.check(key, 3, 60, now=104.0) > 0
    assert ratelimit.check(key, 3, 60, now=170.0) == 0


# ---- automated verification (assistance only) ----
def test_compare_scores_matching_certificate_high():
    text = "Certificate of participation awarded to Aarav Mehta for React Fundamentals workshop held in 2026"
    score, notes = verify.compare(text, "Aarav Mehta", "React Fundamentals", ["2026-10-01", ""])
    assert score == 100 and not notes and verify.label(score) == "Likely valid"


def test_compare_flags_wrong_name():
    text = "Certificate awarded to Someone Else for React Fundamentals workshop held in 2026"
    score, notes = verify.compare(text, "Aarav Mehta", "React Fundamentals", ["2026-10-01"])
    assert score < 80 and any("name" in n for n in notes)


def test_unreadable_text_gives_no_score():
    score, _ = verify.compare("", "Aarav Mehta", "React", [])
    assert score is None and verify.label(score) == "Unable to read"


# ---- certificate number, awardee name and reuse/tampering hints ----
from app import forensics, verify  # noqa: E402


def test_certificate_number_extracted_and_normalized():
    t = "Certificate No: ABC/2026-0042  issued on 5 May 2026"
    assert forensics.extract_cert_numbers(t) == ["ABC20260042"]
    assert forensics.normalize_no("abc-2026 0042") == "ABC20260042"


def test_no_digit_means_not_a_certificate_number():
    assert forensics.extract_cert_numbers("Certificate of Participation") == []


def test_awardee_name_detected_and_compared():
    text = "This is to certify that Rahul Kumar Sharma has successfully completed the workshop"
    assert forensics.awardee_name(text) == "Rahul Kumar Sharma"
    assert forensics.name_matches("Rahul Kumar Sharma", "Rahul Sharma")
    assert not forensics.name_matches("Rahul Kumar Sharma", "Sri Devi")


def test_typed_certificate_number_changes_score():
    text = "Certificate of completion awarded to Asha Patil for Python workshop 2026 Certificate No: PY99812"
    ok, _ = verify.compare(text, "Asha Patil", "Python workshop", ["2026-01-05"], "PY-99812")
    bad, notes = verify.compare(text, "Asha Patil", "Python workshop", ["2026-01-05"], "ZZ11111")
    assert ok == 100 and bad < ok and any("number" in n for n in notes)


def test_alert_caps_score_and_label():
    flags = {"signals": [{"level": "alert", "code": "x", "text": "t"}]}
    score, out = verify.refinish(95.0, flags)
    assert score == 40.0 and out["label"].startswith("Suspicious")
    score, out = verify.refinish(95.0, {"signals": [{"level": "warn", "code": "x", "text": "t"}]})
    assert score == 70.0 and out["label"] == "Needs review"
    assert verify.refinish(95.0, {"signals": []})[0] == 95.0


def test_phash_survives_resize_and_differs_for_other_image():
    import cv2
    import numpy as np
    rng = np.random.default_rng(1)
    a = cv2.GaussianBlur((rng.random((400, 600)) * 255).astype("uint8"), (0, 0), 6)
    a = cv2.normalize(a, None, 0, 255, cv2.NORM_MINMAX)
    b = (rng.random((400, 600)) * 255).astype("uint8")
    b = cv2.normalize(cv2.GaussianBlur(b, (0, 0), 6), None, 0, 255, cv2.NORM_MINMAX)
    enc = lambda im: cv2.imencode(".png", im)[1].tobytes()
    small = cv2.resize(a, (300, 200))
    assert forensics.hamming(forensics.phash_hex(enc(a)), forensics.phash_hex(enc(small))) <= 6
    assert forensics.hamming(forensics.phash_hex(enc(a)), forensics.phash_hex(enc(b))) > 6


def test_pdf_incremental_update_flagged():
    assert any("appended" in n for n in forensics.pdf_traces(b"%PDF-1.4 a %%EOF b %%EOF"))
