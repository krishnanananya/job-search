# Job Search Dashboard

A local job search tool that finds openings from 167 quant/finance companies, scores them against your profile, and displays them in an interactive dashboard.

Jobs are fetched from public career boards (Greenhouse, Lever, Ashby, Workable), filtered by location and salary, scored by role relevance and skill match, then shown in a sortable, filterable table.

## Quick start

```bash
cd job_search
pip install -r requirements.txt
cp config/profile.example.py config/profile.py   # then edit with your details
python main.py
```

The dashboard opens at **http://localhost:5001**. On first run, company board discovery takes ~2 minutes; subsequent runs use the cache.

## Setup

### Profile

Copy the template and fill in your details:

```bash
cp config/profile.example.py config/profile.py
```

Edit `config/profile.py` with:
- **skills** — keywords matched against job descriptions to boost relevance scores
- **target_locations** — city keyword lists for location filtering (defaults to SF Bay Area and NYC)
- **min_salary** — jobs with a listed max salary below this are filtered out (jobs with no salary listed are kept)

### Companies

The company list lives in `config/companies.py` — 167 firms across categories: `quant_fund`, `trading_shop`, `crypto_trading`, `bank`, `asset_manager`, `vc`, `fintech`, `tech`, `crypto`. Add or remove companies by editing this file.

## Usage

```
python main.py              # fetch jobs in background + open dashboard (default)
python main.py fetch        # fetch and cache results, no dashboard
python main.py discover     # re-run company board discovery
python main.py view         # open dashboard from cache only, no fetch
```

## How it works

### Pipeline

1. **Discovery** — finds each company's ATS board slug by trying known slugs, then brute-forcing name variations across Greenhouse/Lever/Ashby/Workable. Results cached in `data/slug_cache.json`.
2. **Fetch** — pulls live postings from each discovered board and normalizes them into a common format.
3. **Filter** — removes intern/new-grad roles, applies location filtering (SF Bay Area + NYC by default), and drops jobs below the minimum salary.
4. **Score & classify** — scores each job 0–100 based on title match, company category, and skill overlap. Jobs are classified as **core** (strong title match) or **stretch** (weaker match but still relevant).

### Dashboard

Dark-themed, table-based UI with:

- **Roles tab** — all jobs with filters for match type, location, recency, company type, and a per-company cap (default: top 3 per company)
- **Saved tab** — bookmarked jobs with status tracking (saved → applied → interviewing → offer/rejected)
- **Composite score** — combines role match (60%), recency (30%), and salary signal (10%) for default sorting
- **Manual entry** — paste any job URL via "+ Add Job" to track roles not in the pipeline

The dashboard auto-refreshes when a background fetch completes.

## File structure

```
job_search/
├── main.py                     # CLI entry point
├── config/
│   ├── profile.example.py      # Profile template (copy to profile.py)
│   ├── profile.py              # Your profile (gitignored)
│   └── companies.py            # 167 seed companies
├── pipeline/
│   ├── discovery.py            # ATS board slug discovery
│   ├── fetcher.py              # Job posting retrieval
│   ├── filter.py               # Location + salary + seniority filters
│   ├── matcher.py              # Scoring and classification
│   └── scraper.py              # URL scraper for manual job entry
├── dashboard/
│   ├── server.py               # Flask API + server
│   └── templates/index.html    # Dashboard UI
├── data/                       # Runtime data (gitignored)
│   ├── slug_cache.json         # Discovered board slugs
│   ├── last_run.json           # Latest fetch results
│   └── saved_jobs.json         # Bookmarked jobs + statuses
└── requirements.txt
```

## Adding companies with non-standard boards

If a company uses a private or non-standard ATS, add it directly to `data/slug_cache.json`:

```json
{
  "Company Name": {
    "board": "greenhouse",
    "slug": "their-slug",
    "found": true,
    "verified_at": 0
  }
}
```

Setting `verified_at: 0` forces a re-check on the next discovery run.
