"""Tamper / reuse hints for an uploaded certificate. Pure functions, no database.
These are HINTS for the teacher, never proof: a clean result does not guarantee a genuine certificate, and a
warning does not prove forgery. Real issuer verification needs the issuer's own system (QR / verify link)."""
import hashlib
import io
import re
import subprocess
import tempfile
from pathlib import Path

EDITOR_WORDS = ("photoshop", "gimp", "canva", "illustrator", "pixlr", "paint", "picsart", "snapseed", "lightroom",
                "ilovepdf", "smallpdf", "sejda", "pdfescape", "foxit", "pdf24", "nitro", "acrobat pro", "wps", "libreoffice",
                "microsoft word", "word", "powerpoint", "inkscape", "affinity")

_NO_LABEL = re.compile(
    r"(?:certificate|cert\.?|credential|registration|reg\.?|serial|verification|ref(?:erence)?|licen[sc]e|id)"
    r"\s*(?:no\.?|number|num|#|id|code)?\s*[:#\-–]?\s*([A-Z0-9][A-Z0-9/\-_.]{3,28}[A-Z0-9])", re.I)
_AWARDEE = re.compile(
    r"(?:certify\s+that|awarded\s+to|presented\s+to|conferred\s+(?:up)?on|proudly\s+presented\s+to|issued\s+to|granted\s+to)"
    r"\s*[:\-]?\s*((?:mr\.?|ms\.?|mrs\.?|miss|dr\.?|shri|smt\.?)?\s*[A-Za-z][A-Za-z.'\- ]{2,60})", re.I)
_END_WORDS = re.compile(r"\b(?:has|have|for|of|in|on|from|who|to|successfully|participated|completed|secured|is|was)\b", re.I)


def normalize_no(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def extract_cert_numbers(text: str) -> list[str]:
    """Certificate/registration numbers printed near a label. Must contain a digit and be 5-30 chars."""
    out: list[str] = []
    for m in _NO_LABEL.finditer(text or ""):
        n = normalize_no(m.group(1))
        if 5 <= len(n) <= 30 and any(ch.isdigit() for ch in n) and n not in out:
            out.append(n)
    return out[:5]


def awardee_name(text: str) -> str | None:
    """The name printed right after 'awarded to / certify that ...' (cut at the first verb/preposition)."""
    flat = re.sub(r"\s+", " ", text or "")
    m = _AWARDEE.search(flat)
    if not m:
        return None
    name = _END_WORDS.split(m.group(1))[0]
    name = re.sub(r"^(?:mr|ms|mrs|miss|dr|shri|smt)\.?\s+", "", name.strip(), flags=re.I).strip(" .-")
    return name if len(name) >= 3 else None


def name_matches(printed: str, student: str) -> bool:
    """Every word of the student's name must appear in the printed name (order-free, case-free)."""
    a = {t for t in re.findall(r"[a-z]+", printed.lower()) if len(t) > 1}
    b = [t for t in re.findall(r"[a-z]+", student.lower()) if len(t) > 1]
    return bool(b) and all(t in a for t in b)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_pdf_page(data: bytes) -> bytes | None:
    """First PDF page as PNG using poppler's pdftoppm (needed for scanned PDFs and for the image fingerprint)."""
    try:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, "in.pdf")
            src.write_bytes(data)
            subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", "1", "-l", "1", str(src), str(Path(d, "p"))],
                           check=True, timeout=30, capture_output=True)
            png = next(Path(d).glob("p*.png"), None)
            return png.read_bytes() if png else None
    except Exception:
        return None


def _gray(data: bytes):
    import cv2
    import numpy as np
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)


def phash_hex(image_bytes: bytes) -> str | None:
    """64-bit perceptual hash (DCT). Survives re-saving, resizing and recompression."""
    import cv2
    import numpy as np
    g = _gray(image_bytes)
    if g is None:
        return None
    small = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low = cv2.dct(small)[:8, :8]
    bits = (low > np.median(low[1:].ravel())).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def pdf_traces(data: bytes) -> list[str]:
    """Signs that a PDF was edited after it was created."""
    notes: list[str] = []
    try:
        from pypdf import PdfReader
        meta = PdfReader(io.BytesIO(data)).metadata or {}
        tool = f"{meta.get('/Producer', '')} {meta.get('/Creator', '')}".lower()
        hit = next((w for w in EDITOR_WORDS if w in tool), None)
        if hit:
            notes.append(f"PDF was produced by an editing tool ({hit.title()}) — normal for some issuers, but check it")
        c, m = str(meta.get("/CreationDate", "")), str(meta.get("/ModDate", ""))
        if c and m and c[:16] != m[:16]:
            notes.append("PDF was modified after it was created")
    except Exception:
        pass
    if data.count(b"%%EOF") > 1:
        notes.append("PDF contains later edits appended to the original (incremental update)")
    return notes


def image_traces(data: bytes) -> list[str]:
    """EXIF 'Software' tag naming an editor."""
    try:
        from PIL import Image
        sw = str(Image.open(io.BytesIO(data)).getexif().get(305, "")).lower()
        hit = next((w for w in EDITOR_WORDS if w in sw), None)
        if hit:
            return [f"Image was saved by an editing program ({hit.title()})"]
    except Exception:
        pass
    return []


def read_qr(image_bytes: bytes) -> str | None:
    """QR payload as text. Shown to the teacher only — the server NEVER opens it (SSRF/phishing risk)."""
    try:
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        val, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return val[:300] if val else None
    except Exception:
        return None


def name_patch_suspect(image_bytes: bytes, student_name: str) -> bool:
    """Weak hint for scans/photos: a pasted-in name usually has a different noise texture than the paper around it.
    Compares high-frequency noise in the name's box with the page's median."""
    try:
        import cv2
        import numpy as np
        import pytesseract
        g = _gray(image_bytes)
        if g is None or g.shape[1] < 600:
            return False
        if g.shape[1] > 1600:
            g = cv2.resize(g, None, fx=1600 / g.shape[1], fy=1600 / g.shape[1], interpolation=cv2.INTER_AREA)
        hp = np.abs(cv2.Laplacian(cv2.GaussianBlur(g, (3, 3), 0), cv2.CV_32F))
        page_noise = float(np.median([hp[y:y + 40, x:x + 40].mean()
                                      for y in range(0, g.shape[0] - 40, 40) for x in range(0, g.shape[1] - 40, 40)]))
        if page_noise < 0.8:
            return False        # clean digital export: no texture to compare with
        d = pytesseract.image_to_data(g, output_type=pytesseract.Output.DICT)
        want = {t for t in re.findall(r"[a-z]+", student_name.lower()) if len(t) > 2}
        boxes = [(d["left"][i], d["top"][i], d["width"][i], d["height"][i]) for i, w in enumerate(d["text"])
                 if re.sub(r"[^a-z]", "", w.lower()) in want]
        if not boxes:
            return False
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
        pad = 6
        around = hp[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
        mask = (g[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] > 200)   # paper pixels near the text
        if mask.sum() < 200:
            return False
        return float(around[mask].mean()) < 0.35 * page_noise
    except Exception:
        return False
