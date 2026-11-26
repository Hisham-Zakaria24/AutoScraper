"""Web dashboard. Run: python app.py  |  Made by Hisham-Zakaria."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, Response, abort, jsonify, render_template, request

from scraper.db import Database
from scraper.engine import ScrapeError, scrape
from scraper.exporter import MIME, export
from scraper.service import Runner, validate_job

BASE = Path(__file__).resolve().parent


def create_app(db_path=None, start_scheduler=True):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.json.sort_keys = False  # keep the user's field order
    if db_path is None:
        (BASE / "data").mkdir(exist_ok=True)
        db_path = BASE / "data" / "scraper.db"
    db = Database(db_path)
    runner = Runner(db)
    app.runner = runner
    if start_scheduler:
        runner.start_scheduler()

    @app.before_request
    def protect():
        # Local-only tool: reject foreign Host names (DNS rebinding) and
        # non-JSON writes (cross-site form posts).
        if urlsplit("//" + request.host).hostname not in ("127.0.0.1", "localhost"):
            abort(403)
        if request.method in ("POST", "PUT", "DELETE") and not request.is_json:
            abort(415)

    def job_or_404(job_id):
        return db.get_job(job_id) or abort(404)

    def body():
        return request.get_json(silent=True)

    @app.errorhandler(ValueError)
    @app.errorhandler(ScrapeError)
    def bad_request(error):
        return jsonify(error=str(error)), 400

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/api/jobs")
    def list_jobs():
        return jsonify([{**j, "running": runner.is_running(j["id"])}
                        for j in db.list_jobs()])

    @app.post("/api/jobs")
    def create_job():
        return jsonify(id=db.add_job(validate_job(body()))), 201

    @app.put("/api/jobs/<int:job_id>")
    def update_job(job_id):
        job_or_404(job_id)
        db.update_job(job_id, validate_job(body()))
        return jsonify(ok=True)

    @app.delete("/api/jobs/<int:job_id>")
    def delete_job(job_id):
        job_or_404(job_id)
        if runner.is_running(job_id):
            return jsonify(error="Job chal rahi hai, khatam hone dein"), 409
        db.delete_job(job_id)
        return jsonify(ok=True)

    @app.post("/api/preview")
    def preview():
        job = validate_job(body())
        rows, _ = scrape(job, max_pages=1)
        return jsonify(count=len(rows), rows=rows[:10], fields=list(job["fields"]))

    @app.post("/api/jobs/<int:job_id>/run")
    def run_job(job_id):
        job_or_404(job_id)
        if not runner.run_async(job_id):
            return jsonify(error="Job pehle se chal rahi hai"), 409
        return jsonify(ok=True), 202

    @app.get("/api/jobs/<int:job_id>/items")
    def items(job_id):
        job = job_or_404(job_id)
        page = max(request.args.get("page", 1, type=int), 1)
        rows, total = db.get_items(job_id, 25, (page - 1) * 25,
                                   request.args.get("q", "").strip())
        return jsonify(rows=rows, total=total, page=page, fields=list(job["fields"]))

    @app.delete("/api/jobs/<int:job_id>/items")
    def clear_items(job_id):
        job_or_404(job_id)
        db.clear_items(job_id)
        return jsonify(ok=True)

    @app.get("/api/jobs/<int:job_id>/runs")
    def runs(job_id):
        job_or_404(job_id)
        return jsonify(db.list_runs(job_id))

    @app.get("/api/jobs/<int:job_id>/export/<fmt>")
    def download(job_id, fmt):
        job = job_or_404(job_id)
        content = export(fmt, job["fields"], db.get_items(job_id)[0])
        return Response(content, mimetype=MIME[fmt], headers={
            "Content-Disposition": f"attachment; filename=job_{job_id}.{fmt}"})

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  AutoScraper (by Hisham-Zakaria): http://127.0.0.1:{port}\n")
    create_app().run(host="127.0.0.1", port=port, threaded=True)
