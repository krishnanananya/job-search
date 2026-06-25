import re

from config.profile import PROFILE

_SF = PROFILE["target_locations"]["sf_bay_area"]
_NYC = PROFILE["target_locations"]["nyc"]
_MIN_SALARY = PROFILE["min_salary"]

_REMOTE_RE = re.compile(r"\b(remote|work from home|wfh)\b", re.IGNORECASE)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
_STRIP_TAGS = re.compile(r"<[^>]+>")

# Titles that signal intern / new-grad roles — excluded regardless of other signals
_EXCL_TITLE_RE = re.compile(
    r"\b("
    r"intern(ship)?|co[-\s]?op|"
    r"new[\s-]grad(uate)?|"
    r"entry[\s-]level|"
    r"early[\s-]career|"
    r"summer[\s-](analyst|associate|intern|program)|"
    r"graduate[\s-](analyst|associate|program|trainee|rotational)|"
    r"rotational[\s-](program|analyst|associate)|"
    r"junior|apprentice|trainee|"
    r"freshman|sophomore"
    r")\b",
    re.IGNORECASE,
)

# Description-level junior signals (belt-and-suspenders alongside title filter)
_EXCL_DESC_RE = re.compile(
    r"\b(entry[\s-]level|new[\s-]grad(uate)?|recent\s+graduates?|"
    r"no\s+experience\s+required|"
    r"0\s*[-–]\s*[12]\s*years?\s*(?:of\s*)?(?:experience|exp))\b",
    re.IGNORECASE,
)

# Senior experience requirements — only explicit "N+" patterns or require-language to avoid
# matching company tenure ("founded 8 years ago").  N must be 6-99.
_SENIOR_EXP_RE = re.compile(
    r"\b([6-9]|\d{2})\s*\+\s*years?\s*(?:of\s*)?(?:experience|exp)\b"
    r"|"
    r"(?:requires?\s+|must\s+have\s+|minimum\s+(?:of\s+)?|at\s+least\s+)"
    r"([6-9]|\d{2})\s*\+?\s*years?\s*(?:of\s*)?(?:experience|exp)\b"
    r"|"
    r"\b([6-9]|\d{2})\s*[-–]\s*\d{1,2}\s*years?\s*(?:of\s*)?(?:experience|exp)\b",
    re.IGNORECASE,
)

# Matches "$150k", "$150,000", "$150 000", "150K", "$150K - $200K", "USD 150000"
_SALARY_RE = re.compile(
    r"(?:USD\s*|CAD\s*|GBP\s*)?\$?\s*"
    r"(\d{2,3}(?:[,\s]\d{3})*|\d+(?:\.\d+)?)\s*([kK])?"
    r"(?:\s*[-–to]+\s*"
    r"\$?\s*(\d{2,3}(?:[,\s]\d{3})*|\d+(?:\.\d+)?)\s*([kK])?)?",
)


def _parse_num(digits: str, k_suffix: str) -> int | None:
    if not digits:
        return None
    try:
        val = float(digits.replace(",", "").replace(" ", ""))
        if k_suffix:
            val *= 1000
        return int(val)
    except ValueError:
        return None


def extract_salary(job: dict) -> tuple[int | None, int | None]:
    """Return (min, max) parsed from salary_raw + description. None if absent."""
    text = f"{job.get('salary_raw', '')} {job.get('description', '')}"
    best_min: int | None = None
    best_max: int | None = None

    for m in _SALARY_RE.finditer(text):
        lo = _parse_num(m.group(1), m.group(2))
        hi = _parse_num(m.group(3), m.group(4)) if m.group(3) else None

        # Skip implausibly small numbers (e.g. "15 years experience")
        if lo and lo < 20_000:
            continue

        if lo and (best_min is None or lo > best_min):
            best_min = lo
        if hi and (best_max is None or hi > best_max):
            best_max = hi

    return best_min, best_max


def _location_label(loc: str) -> str | None:
    loc_lower = loc.lower()
    for kw in _SF:
        if kw in loc_lower:
            return "SF Bay Area"
    for kw in _NYC:
        if kw in loc_lower:
            return "New York City"
    return None


def _passes_location(job: dict) -> tuple[bool, str | None]:
    loc = job.get("location", "")
    label = _location_label(loc)

    if label:
        return True, label

    # For hybrid postings, city must still match one of our targets
    if _HYBRID_RE.search(loc):
        return False, None

    # Pure remote with no city match → exclude
    if _REMOTE_RE.search(loc):
        return False, None

    return False, None


def _passes_salary(job: dict) -> bool:
    lo, hi = extract_salary(job)
    if lo is None and hi is None:
        return True  # no salary info — keep
    cap = hi if hi is not None else lo
    return cap >= _MIN_SALARY


def _passes_seniority_desc(job: dict) -> bool:
    desc = job.get("description", "") or ""
    if not desc:
        return True
    clean = _STRIP_TAGS.sub(" ", desc)
    if _EXCL_DESC_RE.search(clean):
        return False
    if _SENIOR_EXP_RE.search(clean):
        return False
    return True


def filter_jobs(jobs: list[dict], companies: list | None = None) -> list[dict]:
    out = []
    excluded_seniority = 0
    for job in jobs:
        # Drop intern / new-grad / junior titles
        if _EXCL_TITLE_RE.search(job.get("title", "")):
            excluded_seniority += 1
            continue

        # Drop based on description-level experience signals
        if not _passes_seniority_desc(job):
            excluded_seniority += 1
            continue

        ok_loc, label = _passes_location(job)
        if not ok_loc:
            continue
        if not _passes_salary(job):
            continue

        lo, hi = extract_salary(job)
        job = {
            **job,
            "location_label": label,
            "salary_min": lo,
            "salary_max": hi,
        }
        out.append(job)

    if excluded_seniority:
        print(f"  Excluded {excluded_seniority} intern/new-grad/junior postings.")
    return out
