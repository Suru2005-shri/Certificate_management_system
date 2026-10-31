SPORT_BONUS = {"College": 0, "Taluka": 1, "District": 2, "Zonal": 3, "State": 5, "National": 8}
PRIZE_BONUS = 5


def points(category: str, base: int, sport_level: str | None, prize: str | None) -> int:
    p = base
    if category == "sports":
        p += SPORT_BONUS.get(sport_level or "", 0)
    if category == "hackathon" and (prize or "").strip():
        p += PRIZE_BONUS
    return p


def rank(rows: list[tuple[str, int]]) -> list[tuple[str, int, int]]:
    """rows: (student_id, score) -> (student_id, score, rank). Ties share a rank."""
    ordered = sorted(rows, key=lambda r: -r[1])
    out, last_score, last_rank = [], None, 0
    for i, (sid, sc) in enumerate(ordered, start=1):
        last_rank = last_rank if sc == last_score else i
        last_score = sc
        out.append((sid, sc, last_rank))
    return out
