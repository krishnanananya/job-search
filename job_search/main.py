#!/usr/bin/env python3
"""
Job Search Tool — Ananya Krishnan
Usage:
  python main.py           # fetch in background + open dashboard (default)
  python main.py run       # same as above
  python main.py fetch     # just fetch and cache results (no dashboard)
  python main.py discover  # re-run company board discovery
  python main.py view      # open dashboard from cached results only (no fetch)
"""
import argparse
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Ensure project root is on the path regardless of where script is called from
sys.path.insert(0, str(Path(__file__).parent))

_PROFILE_PATH = Path(__file__).parent / "config" / "profile.py"
if not _PROFILE_PATH.exists():
    print("Error: config/profile.py not found.\n")
    print("Create it from the template:")
    print("  cp config/profile.example.py config/profile.py")
    print("\nThen edit it with your skills, target locations, and minimum salary.")
    sys.exit(1)

from config.companies import COMPANIES
from pipeline.discovery import run_discovery, load_cache
from pipeline.fetcher import fetch_all
from pipeline.filter import filter_jobs
from pipeline.matcher import classify_and_rank

DATA_DIR = Path(__file__).parent / "data"
SLUG_CACHE = DATA_DIR / "slug_cache.json"
LAST_RUN = DATA_DIR / "last_run.json"

fetch_state: dict = {
    "fetching": False,
    "stage": "idle",
    "last_updated": None,
    "job_count": 0,
    "error": None,
}


def _save_last_run(jobs: list) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(LAST_RUN, "w") as f:
        json.dump({"jobs": jobs, "fetched_at": time.time()}, f)


def run_pipeline(force_discover: bool = False) -> None:
    global fetch_state
    fetch_state.update({"fetching": True, "error": None, "stage": "discovering"})

    try:
        cache = load_cache()
        found_count = sum(1 for v in cache.values() if v.get("found"))
        needs_discovery = force_discover or found_count < 5

        if needs_discovery:
            print("\nRunning company discovery (first time — may take ~2 minutes)...")
            cache = run_discovery(COMPANIES, force=force_discover)
            found_count = sum(1 for v in cache.values() if v.get("found"))
            print(f"\n  {found_count} company boards discovered.")
        else:
            # Still re-check stale entries in the background
            stale = [
                c for c in COMPANIES
                if c["name"] in cache and _is_stale(cache[c["name"]])
            ]
            if stale:
                print(f"  Re-checking {len(stale)} stale cache entries…")
                cache = run_discovery(stale)

        fetch_state["stage"] = "fetching"
        print("\nFetching job postings…")
        raw_jobs = fetch_all(cache, COMPANIES)
        print(f"\n  {len(raw_jobs)} raw postings fetched.")

        fetch_state["stage"] = "filtering"
        filtered = filter_jobs(raw_jobs, COMPANIES)
        print(f"  {len(filtered)} postings pass location + salary filters.")

        fetch_state["stage"] = "ranking"
        ranked = classify_and_rank(filtered)
        core = sum(1 for j in ranked if j["match_category"] == "core")
        stretch = len(ranked) - core
        print(f"  {core} core matches, {stretch} stretch matches.")

        _save_last_run(ranked)
        fetch_state.update({
            "fetching": False,
            "stage": "done",
            "last_updated": time.time(),
            "job_count": len(ranked),
        })
        print(f"\nDone — {len(ranked)} jobs saved.\n")

    except Exception as e:
        fetch_state.update({"fetching": False, "stage": "error", "error": str(e)})
        print(f"\nPipeline error: {e}", file=sys.stderr)


def _is_stale(entry: dict) -> bool:
    age_days = (time.time() - entry.get("verified_at", 0)) / 86400
    if entry.get("found") and age_days > 7:
        return True
    if not entry.get("found") and age_days > 30:
        return True
    return False


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_discover(_args) -> None:
    print("Running full company discovery…")
    cache = run_discovery(COMPANIES, force=True)
    found = [k for k, v in cache.items() if v.get("found")]
    not_found = [k for k, v in cache.items() if not v.get("found")]
    print(f"\n✓ {len(found)} boards found")
    if not_found:
        print(f"✗ {len(not_found)} companies with no public board (add manually to slug_cache.json):")
        for name in sorted(not_found):
            print(f"    {name}")


def cmd_fetch(_args) -> None:
    run_pipeline()


def cmd_view(_args) -> None:
    from dashboard.server import create_app
    app = create_app(fetch_state, LAST_RUN)
    threading.Timer(0.8, lambda: webbrowser.open("http://localhost:5001")).start()
    print("Dashboard → http://localhost:5001  (Ctrl+C to quit)")
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)


def cmd_run(_args) -> None:
    from dashboard.server import create_app
    app = create_app(fetch_state, LAST_RUN)

    t = threading.Thread(target=run_pipeline, daemon=True)
    t.start()

    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:5001")).start()
    print("Dashboard → http://localhost:5001  (fetching in background…)  Ctrl+C to quit")
    app.run(host="127.0.0.1", port=5001, debug=False, use_reloader=False)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Personal job search dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run",      help="Fetch + open dashboard (default)")
    sub.add_parser("fetch",    help="Fetch and cache results, no dashboard")
    sub.add_parser("discover", help="Re-run company board discovery")
    sub.add_parser("view",     help="Open dashboard from cache, no fetch")

    args = parser.parse_args()
    dispatch = {
        "run": cmd_run,
        "fetch": cmd_fetch,
        "discover": cmd_discover,
        "view": cmd_view,
        None: cmd_run,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
