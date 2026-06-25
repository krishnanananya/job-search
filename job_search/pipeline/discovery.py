import json
import re
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
SLUG_CACHE_PATH = DATA_DIR / "slug_cache.json"

BOARDS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "workable": "https://apply.workable.com/api/v3/accounts/{slug}/jobs",
}

# Known-good slugs for companies with non-obvious ATS names
KNOWN_SLUGS: dict[str, dict] = {
    "Citadel": {"board": "greenhouse", "slug": "citadel"},
    "Citadel Securities": {"board": "greenhouse", "slug": "citadel-securities"},
    "Jane Street": {"board": "greenhouse", "slug": "jane-street"},
    "Jump Trading": {"board": "greenhouse", "slug": "jump-trading"},
    "Hudson River Trading": {"board": "greenhouse", "slug": "hudson-river-trading"},
    "Optiver": {"board": "greenhouse", "slug": "optiver"},
    "AQR Capital Management": {"board": "greenhouse", "slug": "aqr"},
    "Bridgewater Associates": {"board": "greenhouse", "slug": "bridgewater-associates"},
    "Point72": {"board": "greenhouse", "slug": "point72"},
    "Goldman Sachs": {"board": "greenhouse", "slug": "goldman-sachs"},
    "JPMorgan": {"board": "greenhouse", "slug": "jpmorgan-chase"},
    "Morgan Stanley": {"board": "greenhouse", "slug": "morgan-stanley"},
    "BlackRock": {"board": "greenhouse", "slug": "blackrock"},
    "Citadel Wellington": {"board": "greenhouse", "slug": "citadel"},
    "Virtu Financial": {"board": "greenhouse", "slug": "virtu-financial"},
    "Andreessen Horowitz": {"board": "greenhouse", "slug": "a16z"},
    "Coinbase": {"board": "greenhouse", "slug": "coinbase"},
    "Palantir": {"board": "lever", "slug": "palantir"},
    "Robinhood": {"board": "greenhouse", "slug": "robinhood"},
    "Stripe": {"board": "greenhouse", "slug": "stripe"},
    "Databricks": {"board": "greenhouse", "slug": "databricks"},
    "Scale AI": {"board": "greenhouse", "slug": "scale-ai"},
    "Schonfeld Strategic Advisors": {"board": "greenhouse", "slug": "schonfeld"},
    "Balyasny Asset Management": {"board": "greenhouse", "slug": "balyasny"},
    "Neuberger Berman": {"board": "greenhouse", "slug": "neuberger-berman"},
    "KKR": {"board": "greenhouse", "slug": "kkr"},
    "Apollo Global Management": {"board": "greenhouse", "slug": "apollo-global-management"},
    "Blackstone": {"board": "greenhouse", "slug": "blackstone"},
    "Kraken": {"board": "lever", "slug": "kraken"},
    "Gemini": {"board": "greenhouse", "slug": "gemini"},
    "Chainalysis": {"board": "greenhouse", "slug": "chainalysis"},
    "Fireblocks": {"board": "greenhouse", "slug": "fireblocks"},
    "Plaid": {"board": "greenhouse", "slug": "plaid"},
    "Affirm": {"board": "greenhouse", "slug": "affirm"},
    "Brex": {"board": "lever", "slug": "brex"},
    "Ramp": {"board": "greenhouse", "slug": "ramp"},
    "OpenAI": {"board": "greenhouse", "slug": "openai"},
    "Anthropic": {"board": "ashby", "slug": "anthropic"},
    "Waymo": {"board": "greenhouse", "slug": "waymo"},
    "Insight Partners": {"board": "greenhouse", "slug": "insight-partners"},
    "General Catalyst": {"board": "greenhouse", "slug": "general-catalyst"},
    "Sequoia Capital": {"board": "greenhouse", "slug": "sequoia-capital"},
    "Accel": {"board": "greenhouse", "slug": "accel"},
    "Bessemer Venture Partners": {"board": "greenhouse", "slug": "bvp"},
    "Galaxy Digital": {"board": "greenhouse", "slug": "galaxy-digital"},
    "Anchorage Digital": {"board": "greenhouse", "slug": "anchorage-digital"},
    "BitGo": {"board": "greenhouse", "slug": "bitgo"},
    "Wintermute Trading": {"board": "greenhouse", "slug": "wintermute-trading"},
    "SoFi": {"board": "greenhouse", "slug": "sofi"},
    "Marqeta": {"board": "greenhouse", "slug": "marqeta"},
    "FactSet": {"board": "greenhouse", "slug": "factset"},
    "S&P Global": {"board": "greenhouse", "slug": "sp-global"},
    "MSCI": {"board": "greenhouse", "slug": "msci"},
    "DRW": {"board": "greenhouse", "slug": "drw"},
    "Akuna Capital": {"board": "greenhouse", "slug": "akuna-capital"},
    "Chicago Trading Company": {"board": "greenhouse", "slug": "chicago-trading-company"},
    "Old Mission Capital": {"board": "greenhouse", "slug": "old-mission"},
    "Wolverine Trading": {"board": "greenhouse", "slug": "wolverine-trading"},
    "Five Rings Capital": {"board": "greenhouse", "slug": "five-rings"},
    "Belvedere Trading": {"board": "greenhouse", "slug": "belvedere-trading"},
    "Ares Management": {"board": "greenhouse", "slug": "ares-management"},
    "Bain Capital": {"board": "greenhouse", "slug": "bain-capital"},
    "TPG": {"board": "greenhouse", "slug": "tpg"},
    "Carlyle Group": {"board": "greenhouse", "slug": "the-carlyle-group"},
    "Evercore": {"board": "greenhouse", "slug": "evercore"},
    "Lazard": {"board": "greenhouse", "slug": "lazard"},
    "Jefferies": {"board": "greenhouse", "slug": "jefferies"},
    "Warburg Pincus": {"board": "greenhouse", "slug": "warburg-pincus"},
    "T. Rowe Price": {"board": "greenhouse", "slug": "t-rowe-price"},
    "Franklin Templeton": {"board": "greenhouse", "slug": "franklin-templeton"},
    "Invesco": {"board": "greenhouse", "slug": "invesco"},
    "AllianceBernstein": {"board": "greenhouse", "slug": "alliancebernstein"},
    "Wellington Management": {"board": "greenhouse", "slug": "wellington-management"},
    "PIMCO": {"board": "greenhouse", "slug": "pimco"},
    "Northern Trust": {"board": "greenhouse", "slug": "northern-trust"},
    "Fidelity Investments": {"board": "greenhouse", "slug": "fidelity-investments"},
    "State Street Global Advisors": {"board": "greenhouse", "slug": "state-street"},
    "Nuveen": {"board": "greenhouse", "slug": "nuveen"},
    "Kensho": {"board": "greenhouse", "slug": "kensho"},
    "xAI": {"board": "greenhouse", "slug": "xai"},
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)"})


def _slugify(name: str) -> list[str]:
    base = name.lower()
    base = re.sub(r"[&]", "and", base)
    base = re.sub(r"[^a-z0-9\s-]", "", base)
    base = base.strip()
    hyphen = re.sub(r"[\s]+", "-", base)
    nospace = re.sub(r"[\s-]+", "", base)
    underscore = re.sub(r"[\s]+", "_", base)
    seen, out = set(), []
    for v in [hyphen, nospace, underscore]:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _check_greenhouse(slug: str) -> bool:
    try:
        r = SESSION.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            timeout=6,
        )
        if r.status_code == 200:
            return "jobs" in r.json()
    except Exception:
        pass
    return False


def _check_lever(slug: str) -> bool:
    try:
        r = SESSION.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            timeout=6,
        )
        if r.status_code == 200:
            return isinstance(r.json(), list)
    except Exception:
        pass
    return False


def _check_ashby(slug: str) -> bool:
    try:
        r = SESSION.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            timeout=6,
        )
        if r.status_code == 200:
            return "jobPostings" in r.json()
    except Exception:
        pass
    return False


def _check_workable(slug: str) -> bool:
    try:
        r = SESSION.post(
            f"https://apply.workable.com/api/v3/accounts/{slug}/jobs",
            json={"query": "", "location": [], "department": [], "remote": [], "workplace": []},
            timeout=6,
        )
        if r.status_code == 200:
            return "results" in r.json()
    except Exception:
        pass
    return False


CHECKERS = {
    "greenhouse": _check_greenhouse,
    "lever": _check_lever,
    "ashby": _check_ashby,
    "workable": _check_workable,
}


def _discover_one(company: dict) -> dict | None:
    """Try known slug first, then brute-force slug variations."""
    name = company["name"]
    hint = KNOWN_SLUGS.get(name) or {}

    if hint:
        board, slug = hint["board"], hint["slug"]
        if CHECKERS[board](slug):
            return {"board": board, "slug": slug}
        # hint was wrong or slug changed — fall through to brute force

    slugs = _slugify(name)
    for board in ["greenhouse", "lever", "ashby", "workable"]:
        for slug in slugs:
            if CHECKERS[board](slug):
                return {"board": board, "slug": slug}
            time.sleep(0.15)

    return None


def load_cache() -> dict:
    if SLUG_CACHE_PATH.exists():
        with open(SLUG_CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(SLUG_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def run_discovery(companies: list, force: bool = False) -> dict:
    cache = load_cache()
    now = time.time()
    to_check = []

    for company in companies:
        name = company["name"]
        entry = cache.get(name, {})

        if not entry:
            to_check.append(company)
            continue

        if force:
            to_check.append(company)
            continue

        age_days = (now - entry.get("verified_at", 0)) / 86400
        if entry.get("found") and age_days > 7:
            to_check.append(company)
        elif not entry.get("found") and age_days > 30:
            to_check.append(company)

    total = len(to_check)
    if total == 0:
        print("  Discovery cache is fresh — no checks needed.")
        return cache

    print(f"  Checking {total} companies for public job boards...")
    for i, company in enumerate(to_check, 1):
        name = company["name"]
        print(f"  [{i}/{total}] {name}...", end=" ", flush=True)
        result = _discover_one(company)
        if result:
            cache[name] = {**result, "found": True, "verified_at": now}
            print(f"✓ {result['board']}/{result['slug']}")
        else:
            cache[name] = {"found": False, "verified_at": now}
            print("✗ no public board")

    save_cache(cache)
    return cache
