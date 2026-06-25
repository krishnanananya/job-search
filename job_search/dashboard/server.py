import json
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request


def create_app(fetch_state: dict, last_run_path: Path) -> Flask:
    template_dir = Path(__file__).parent / "templates"
    data_dir = last_run_path.parent
    saved_path = data_dir / "saved_jobs.json"

    app = Flask(__name__, template_folder=str(template_dir))
    app.config["JSON_SORT_KEYS"] = False

    def _load_saved() -> dict:
        if saved_path.exists():
            with open(saved_path) as f:
                return json.load(f)
        return {}

    def _write_saved(data: dict) -> None:
        data_dir.mkdir(exist_ok=True)
        with open(saved_path, "w") as f:
            json.dump(data, f, indent=2)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/jobs")
    def api_jobs():
        if last_run_path.exists():
            with open(last_run_path) as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify({"jobs": [], "fetched_at": None})

    @app.route("/api/status")
    def api_status():
        return jsonify({
            "fetching": fetch_state.get("fetching", False),
            "stage": fetch_state.get("stage", "idle"),
            "last_updated": fetch_state.get("last_updated"),
            "job_count": fetch_state.get("job_count", 0),
            "error": fetch_state.get("error"),
        })

    # ── Saved jobs ──────────────────────────────────────────────────────────

    @app.route("/api/saved", methods=["GET"])
    def api_get_saved():
        return jsonify(_load_saved())

    @app.route("/api/scrape", methods=["POST"])
    def api_scrape():
        data = request.get_json() or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"ok": False, "error": "No URL provided", "scraped": False}), 400
        try:
            from pipeline.scraper import scrape_url
            result = scrape_url(url)
            result["ok"] = True
            return jsonify(result)
        except Exception as e:
            return jsonify({
                "ok": False, "error": str(e), "scraped": False, "partial": True,
                "title": "", "company": "", "location": "", "salary_raw": "",
            })

    @app.route("/api/saved", methods=["POST"])
    def api_save_job():
        data = request.get_json()
        saved = _load_saved()
        key = data["key"]
        job = data["job"]
        if job.get("manual") and job.get("salary_raw"):
            try:
                from pipeline.filter import extract_salary
                lo, hi = extract_salary(job)
                job = {**job, "salary_min": lo, "salary_max": hi}
            except Exception:
                pass
        saved[key] = {
            "job": job,
            "status": data.get("status", "saved"),
            "saved_at": time.time(),
            "notes": data.get("notes", ""),
        }
        _write_saved(saved)
        return jsonify({"ok": True})

    @app.route("/api/saved/<path:key>", methods=["PATCH"])
    def api_update_saved(key):
        data = request.get_json()
        saved = _load_saved()
        if key not in saved:
            return jsonify({"ok": False}), 404
        for field in ("status", "notes"):
            if field in data:
                saved[key][field] = data[field]
        _write_saved(saved)
        return jsonify({"ok": True})

    @app.route("/api/saved/<path:key>", methods=["DELETE"])
    def api_delete_saved(key):
        saved = _load_saved()
        saved.pop(key, None)
        _write_saved(saved)
        return jsonify({"ok": True})

    return app
