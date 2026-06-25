"""Extract job details from a URL. Tries known ATS APIs first, then falls back to HTML parsing."""

import json
import re
from urllib.parse import urlparse

import requests

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
})

_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def _name(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _try_greenhouse(host: str, path: str):
    if "greenhouse.io" not in host:
        return None
    m = re.search(r"/([^/]+)/jobs/(\d+)", path)
    if not m:
        return None
    slug, job_id = m.group(1), m.group(2)
    try:
        r = _SESSION.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}?content=true",
            timeout=8,
        )
        if r.ok:
            j = r.json()
            return {
                "title": j.get("title", ""),
                "company": _name(slug),
                "location": (j.get("location") or {}).get("name", ""),
                "salary_raw": "",
                "scraped": True,
                "partial": False,
            }
    except Exception:
        pass
    return None


def _try_lever(host: str, path: str):
    if "lever.co" not in host:
        return None
    slug_m = re.match(r"/([^/]+)/", path)
    uid_m = _UUID_RE.search(path)
    if not slug_m or not uid_m:
        return None
    slug, uid = slug_m.group(1), uid_m.group(0)
    try:
        r = _SESSION.get(f"https://api.lever.co/v0/postings/{slug}/{uid}", timeout=8)
        if r.ok:
            j = r.json()
            cats = j.get("categories") or {}
            sr = j.get("salaryRange") or {}
            salary = ""
            if sr.get("min") or sr.get("max"):
                currency = sr.get("currency", "USD")
                lo, hi = sr.get("min", ""), sr.get("max", "")
                salary = f"{currency} {lo} - {hi}".strip(" -")
            return {
                "title": j.get("text", ""),
                "company": _name(slug),
                "location": cats.get("location", ""),
                "salary_raw": salary,
                "scraped": True,
                "partial": False,
            }
    except Exception:
        pass
    return None


def _try_ashby(host: str, path: str):
    if "ashbyhq.com" not in host:
        return None
    parts = [p for p in path.split("/") if p]
    uid_m = _UUID_RE.search(path)
    if len(parts) < 2 or not uid_m:
        return None
    org, uid = parts[0], uid_m.group(0)
    try:
        r = _SESSION.get(f"https://api.ashbyhq.com/posting-api/job-board/{org}", timeout=8)
        if r.ok:
            posting = next(
                (p for p in r.json().get("jobPostings", []) if p.get("id") == uid),
                None,
            )
            if posting:
                comp = posting.get("compensation") or {}
                salary = ""
                if comp.get("minValue") or comp.get("maxValue"):
                    salary = f"{comp.get('currency','USD')} {comp.get('minValue','')} - {comp.get('maxValue','')}".strip(" -")
                return {
                    "title": posting.get("title", ""),
                    "company": _name(org),
                    "location": posting.get("location", ""),
                    "salary_raw": salary,
                    "scraped": True,
                    "partial": False,
                }
    except Exception:
        pass
    return None


def _try_workable(host: str, path: str):
    if "workable.com" not in host:
        return None
    m = re.search(r"/([^/]+)/j/([^/?#]+)", path)
    if not m:
        return None
    slug, shortcode = m.group(1), m.group(2)
    try:
        r = _SESSION.get(
            f"https://apply.workable.com/api/v3/accounts/{slug}/jobs/{shortcode}",
            timeout=8,
        )
        if r.ok:
            j = r.json()
            loc = j.get("location") or {}
            location = ", ".join(p for p in [loc.get("city", ""), loc.get("region", "")] if p)
            return {
                "title": j.get("title", ""),
                "company": _name(slug),
                "location": location,
                "salary_raw": "",
                "scraped": True,
                "partial": False,
            }
    except Exception:
        pass
    return None


def _try_html(url: str) -> dict:
    base: dict = {"title": "", "company": "", "location": "", "salary_raw": "", "scraped": False, "partial": False}
    try:
        r = _SESSION.get(url, timeout=10)
        if not r.ok:
            return base
        html = r.text

        # 1. Schema.org JobPosting in JSON-LD
        for block in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        ):
            try:
                data = json.loads(block.strip())
                if isinstance(data, list):
                    data = next((d for d in data if isinstance(d, dict) and d.get("@type") == "JobPosting"), {})
                if not isinstance(data, dict) or data.get("@type") != "JobPosting":
                    continue
                org = data.get("hiringOrganization") or {}
                loc_obj = data.get("jobLocation") or {}
                addr = (loc_obj.get("address") or {}) if isinstance(loc_obj, dict) else {}
                location = ", ".join(p for p in [addr.get("addressLocality", ""), addr.get("addressRegion", "")] if p)
                base_sal = data.get("baseSalary") or {}
                sal_val = (base_sal.get("value") or {}) if isinstance(base_sal, dict) else {}
                salary = ""
                if isinstance(sal_val, dict) and (sal_val.get("minValue") or sal_val.get("maxValue")):
                    salary = f"{sal_val.get('currency','USD')} {sal_val.get('minValue','')} - {sal_val.get('maxValue','')}".strip(" -")
                company = org.get("name", "") if isinstance(org, dict) else ""
                title = data.get("title", "")
                if title:
                    return {
                        "title": title,
                        "company": company,
                        "location": location,
                        "salary_raw": salary,
                        "scraped": True,
                        "partial": not company,
                    }
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        # 2. Open Graph / page title fallback
        og_title_m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        og_site_m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        pg_title_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)

        best_title = og_title_m or pg_title_m
        if best_title:
            base["title"] = best_title.group(1).strip()
            base["scraped"] = True
            base["partial"] = True
        if og_site_m:
            base["company"] = og_site_m.group(1).strip()

    except Exception:
        pass

    return base


def scrape_url(url: str) -> dict:
    """
    Extract job details from a job posting URL.
    Returns: {title, company, location, salary_raw, scraped, partial}
    scraped=True means we got something; partial=True means fields may be missing.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path

    for fn in (_try_greenhouse, _try_lever, _try_ashby, _try_workable):
        result = fn(host, path)
        if result:
            return result

    return _try_html(url)
