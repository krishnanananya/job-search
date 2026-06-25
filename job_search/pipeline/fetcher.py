import time
from datetime import datetime, timezone

import requests

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; job-search-bot/1.0)"})


def _iso(ts_ms: int | None) -> str:
    if not ts_ms:
        return ""
    try:
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return ""


def _fetch_greenhouse(slug: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    r = SESSION.get(url, timeout=12)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append({
            "id": str(j.get("id", "")),
            "title": j.get("title", ""),
            "location": j.get("location", {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "posted_at": j.get("updated_at", ""),
            "description": j.get("content", ""),
            "salary_raw": "",
        })
    return jobs


def _fetch_lever(slug: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    r = SESSION.get(url, timeout=12)
    r.raise_for_status()
    jobs = []
    for j in r.json():
        sr = j.get("salaryRange") or {}
        salary_raw = ""
        if sr.get("min") or sr.get("max"):
            currency = sr.get("currency", "USD")
            salary_raw = f"{currency} {sr.get('min', '')} - {sr.get('max', '')}".strip(" -")
        cats = j.get("categories") or {}
        location = cats.get("location") or ""
        jobs.append({
            "id": j.get("id", ""),
            "title": j.get("text", ""),
            "location": location,
            "url": j.get("hostedUrl", ""),
            "posted_at": _iso(j.get("createdAt")),
            "description": j.get("descriptionPlain", ""),
            "salary_raw": salary_raw,
        })
    return jobs


def _fetch_ashby(slug: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    r = SESSION.get(url, timeout=12)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobPostings", []):
        comp = j.get("compensation") or {}
        salary_raw = ""
        if comp.get("minValue") or comp.get("maxValue"):
            currency = comp.get("currency", "USD")
            lo = comp.get("minValue", "")
            hi = comp.get("maxValue", "")
            salary_raw = f"{currency} {lo} - {hi}".strip(" -")
        jobs.append({
            "id": j.get("id", ""),
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "url": j.get("jobUrl", ""),
            "posted_at": j.get("publishedDate", ""),
            "description": j.get("descriptionHtml", ""),
            "salary_raw": salary_raw,
        })
    return jobs


def _fetch_workable(slug: str) -> list[dict]:
    url = f"https://apply.workable.com/api/v3/accounts/{slug}/jobs"
    body = {"query": "", "location": [], "department": [], "remote": [], "workplace": []}
    r = SESSION.post(url, json=body, timeout=12)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("results", []):
        loc = j.get("location") or {}
        city = loc.get("city", "")
        region = loc.get("region", "")
        country = loc.get("country", "")
        location = ", ".join(p for p in [city, region, country] if p)
        shortcode = j.get("shortcode", "")
        jobs.append({
            "id": shortcode,
            "title": j.get("title", ""),
            "location": location,
            "url": j.get("url") or f"https://apply.workable.com/{slug}/j/{shortcode}",
            "posted_at": j.get("created_at", ""),
            "description": "",
            "salary_raw": "",
        })
    return jobs


_FETCHERS = {
    "greenhouse": _fetch_greenhouse,
    "lever": _fetch_lever,
    "ashby": _fetch_ashby,
    "workable": _fetch_workable,
}


def fetch_all(cache: dict, companies: list) -> list[dict]:
    category_map = {c["name"]: c["category"] for c in companies}
    active = [(name, info) for name, info in cache.items() if info.get("found")]
    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    for name, info in active:
        board = info["board"]
        slug = info["slug"]
        try:
            raw = _FETCHERS[board](slug)
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            time.sleep(0.3)
            continue

        for j in raw:
            dedup_key = f"{name}|{j['title']}|{j['location']}"
            if dedup_key in seen_ids:
                continue
            seen_ids.add(dedup_key)
            j["company"] = name
            j["company_category"] = category_map.get(name, "other")
            j["board"] = board
            all_jobs.append(j)

        print(f"  ✓ {name}: {len(raw)} postings")
        time.sleep(0.3)

    return all_jobs
