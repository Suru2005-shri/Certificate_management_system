"""Automated certificate check (assistance only). OpenCV preprocesses, Tesseract reads text, we compare with what the
student entered, then look for reuse / tampering hints (see forensics.py). The teacher ALWAYS makes the final decision."""
import io
import re

from . import forensics

STOP = {"the", "and", "of", "for", "in", "at", "on", "to", "a", "an", "workshop", "certificate", "event"}


def label(score: float | None, alerts: int = 0) -> str:
    if alerts:
        return "Suspicious – check carefully"
    if score is None:
        return "Unable to read"
    return "Likely valid" if score >= 80 else "Needs review" if score >= 60 else "Low confidence"


def _ocr_image(img_bytes: bytes) -> str:
    import cv2
    import numpy as np
    import pytesseract
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ""
    if img.shape[1] < 1200:
        scale = 1200 / img.shape[1]
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return pytesseract.image_to_string(img)


def extract_text(data: bytes, mime: str, page_png: bytes | None = None) -> str:
    if mime == "application/pdf":
        from pypdf import PdfReader
        text = " ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages[:3])
        if len(text.strip()) >= 30 or not page_png:
            return text
        return _ocr_image(page_png)           # scanned PDF: no text layer, read the rendered page
    return _ocr_image(data)


def _tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2 and t not in STOP]


def compare(text: str, student_name: str, title: str, dates: list[str], cert_no: str | None = None) -> tuple[float | None, list[str]]:
    hay = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    if len(hay) < 15:
        return None, ["Could not read enough text from the file"]
    notes: list[str] = []
    parts: list[tuple[float, float]] = []   # (weight, fraction matched)

    nt = _tokens(student_name)
    if nt:
        f = sum(t in hay for t in nt) / len(nt)
        parts.append((40, f))
        if f < 1:
            notes.append("Student name not fully found on the certificate")
    tt = _tokens(title)
    if tt:
        f = sum(t in hay for t in tt) / len(tt)
        parts.append((40, f))
        if f < 0.6:
            notes.append("Event/company name not clearly found on the certificate")
    years = {d[:4] for d in dates if d}
    if years:
        f = sum(y in hay for y in years) / len(years)
        parts.append((20, f))
        if f < 1:
            notes.append("Year of the dates entered was not found on the certificate")
    n = forensics.normalize_no(cert_no or "")
    if n:
        found = n in forensics.normalize_no(text)
        parts.append((30, 1.0 if found else 0.0))
        if not found:
            notes.append("The certificate number you typed was not found on the certificate")
    if not parts:
        return None, ["Nothing to compare"]
    total = sum(w for w, _ in parts)
    return round(sum(w * f for w, f in parts) / total * 100, 1), notes


def _signal(level: str, code: str, text: str) -> dict:
    return {"level": level, "code": code, "text": text}      # level: ok | info | warn | alert


def run(data: bytes, mime: str, student_name: str, title: str, dates: list[str], cert_no: str | None = None) -> tuple[float | None, dict]:
    """Returns (score, flags). flags = label, notes, signals, cert_numbers, sha256, phash, qr.
    Duplicate lookups against the database are added afterwards by services.py (they need other students' records)."""
    signals: list[dict] = []
    notes: list[str] = []
    flags: dict = {"cert_numbers": [], "sha256": forensics.sha256_hex(data), "phash": None, "qr": None}
    score = None
    try:
        page_png = forensics.render_pdf_page(data) if mime == "application/pdf" else None
        image = page_png if mime == "application/pdf" else data
        text = extract_text(data, mime, page_png)
        score, notes = compare(text, student_name, title, dates, cert_no)

        found = forensics.extract_cert_numbers(text)
        typed = forensics.normalize_no(cert_no or "")
        flags["cert_numbers"] = list(dict.fromkeys(([typed] if typed else []) + found))
        if typed and typed in forensics.normalize_no(text):
            signals.append(_signal("ok", "cert_no_match", "Certificate number matches the one you typed"))
        elif found and not typed:
            signals.append(_signal("info", "cert_no_found", f"Certificate number read from the file: {found[0]}"))

        printed = forensics.awardee_name(text)
        if printed:
            if forensics.name_matches(printed, student_name):
                signals.append(_signal("ok", "awardee_match", "Name printed after “awarded to / certify that” matches the student"))
            else:
                signals.append(_signal("alert", "awardee_mismatch",
                                       f"The certificate says it was awarded to “{printed}”, which does not match the student"))

        for t in (forensics.pdf_traces(data) if mime == "application/pdf" else forensics.image_traces(data)):
            signals.append(_signal("warn", "edit_trace", t))

        if image:
            flags["phash"] = forensics.phash_hex(image)
            qr = forensics.read_qr(image)
            if qr:
                flags["qr"] = qr
                signals.append(_signal("info", "qr", "A QR code was found. Open it yourself on a safe device to check the issuer: " + qr))
            if mime != "application/pdf" and forensics.name_patch_suspect(image, student_name):
                signals.append(_signal("warn", "name_patch", "The area around the name has a different texture from the rest of the page (possible edit)"))
    except Exception:   # OCR tools missing, corrupt file, etc. — never block the submission
        score = None
        notes = ["Automated check unavailable"]
    return score, finish(score, notes, signals, flags)


def finish(score: float | None, notes: list[str], signals: list[dict], flags: dict) -> dict:
    """Apply score caps from the signals and build the flags object stored with the submission."""
    alerts = sum(s["level"] == "alert" for s in signals)
    warns = sum(s["level"] == "warn" for s in signals)
    return {**flags, "label": label(score, alerts), "notes": notes, "signals": signals,
            "alerts": alerts, "warnings": warns}


def refinish(score: float | None, flags: dict) -> tuple[float | None, dict]:
    """Recount signals (after the database reuse checks added more) and apply the score cap."""
    sig = flags.get("signals", [])
    alerts = sum(s["level"] == "alert" for s in sig)
    warns = sum(s["level"] == "warn" for s in sig)
    flags = {**flags, "alerts": alerts, "warnings": warns}
    score = cap_score(score, flags)
    flags["label"] = label(score, alerts)
    return score, flags


def cap_score(score: float | None, flags: dict) -> float | None:
    """A red-flag signal limits how high the score can go, so a tampered file is never shown as 'Likely valid'."""
    if score is None:
        return None
    if flags.get("alerts"):
        return min(score, 40.0)
    if flags.get("warnings"):
        return min(score, 70.0)
    return score
