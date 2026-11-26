"""Tests (no internet needed). Made by Hisham-Zakaria."""
import io
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cli
from app import create_app
from scraper.engine import Fetcher, ScrapeError, check_url, parse_field, scrape
from scraper.exporter import export

PAGES = {
    "/robots.txt": "User-agent: *\nDisallow: /secret",
    "/p1": '<div class="q"><b>Alpha</b><a href="/a">x</a></div>'
           '<div class="q"><b>=1+1</b><a href="/b">x</a></div><a class="next" href="/p2">n</a>',
    "/p2": '<div class="q"><b>नमस्ते</b><a href="/c">x</a></div><a class="next" href="/p1">loop</a>',
    "/secret": "<p>no</p>",
}


class Site(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/p1")
            self.end_headers()
            return
        self.send_response(200 if self.path in PAGES else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGES.get(self.path, "").encode())

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def allow_local(monkeypatch):
    monkeypatch.setenv("SCRAPER_ALLOW_PRIVATE", "1")


def config(site, **extra):
    return {"name": "T", "url": site + "/p1", "item_selector": "div.q",
            "fields": {"title": "b", "link": "a@href"}, "next_selector": "a.next",
            "max_pages": 10, "delay": 0.5, **extra}


def wait_done(client, job_id):
    for _ in range(100):
        runs = client.get(f"/api/jobs/{job_id}/runs").get_json()
        job = next(j for j in client.get("/api/jobs").get_json() if j["id"] == job_id)
        if runs and runs[0]["status"] != "running" and not job["running"]:
            return runs[0]
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_pagination_stops_on_loop(site):
    rows, pages = scrape(config(site), Fetcher(delay=0))
    assert pages == 2
    assert [r["title"] for r in rows] == ["Alpha", "=1+1", "नमस्ते"]
    assert rows[0]["link"] == site + "/a"


def test_redirect_and_robots(site):
    assert Fetcher(delay=0).get(site + "/redirect")[0] == site + "/p1"
    with pytest.raises(ScrapeError, match="robots"):
        Fetcher(delay=0).get(site + "/secret")


def test_errors(site):
    with pytest.raises(ScrapeError, match="404"):
        Fetcher(delay=0).get(site + "/missing")
    with pytest.raises(ScrapeError, match="selector"):
        scrape(config(site, item_selector="div[["), Fetcher(delay=0))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/",
                                 "http://10.0.0.1/", "http://[::1]/"])
def test_unsafe_urls_blocked(url, monkeypatch):
    monkeypatch.delenv("SCRAPER_ALLOW_PRIVATE")
    with pytest.raises(ScrapeError):
        check_url(url)


def test_parse_field():
    assert parse_field("a.x@href") == ("a.x", "href")
    assert parse_field("@data-id") == ("", "data-id")
    assert parse_field('a[href*="@"]') == ('a[href*="@"]', None)


def test_exports_block_formulas():
    items = [{"t": "=1+1", "_first_seen": 0}]
    assert "'=1+1" in export("csv", ["t"], items).decode("utf-8-sig")
    cell = load_workbook(io.BytesIO(export("xlsx", ["t"], items))).active["A2"]
    assert cell.value == "=1+1" and cell.data_type == "s"
    assert json.loads(export("json", ["t"], items))[0]["t"] == "=1+1"


def test_full_api_flow(site, tmp_path):
    app = create_app(tmp_path / "t.db", start_scheduler=False)
    client = app.test_client()
    assert client.get("/").status_code == 200
    preview = client.post("/api/preview", json=config(site)).get_json()
    assert preview["count"] == 2
    job_id = client.post("/api/jobs", json=config(site)).get_json()["id"]
    for expected_new in (3, 0):  # second run must not duplicate
        assert client.post(f"/api/jobs/{job_id}/run", json={}).status_code == 202
        run = wait_done(client, job_id)
        assert (run["status"], run["found"], run["added"]) == ("success", 3, expected_new)
    assert client.get(f"/api/jobs/{job_id}/items?q=alpha").get_json()["total"] == 1
    for fmt in ("csv", "json", "xlsx"):
        assert client.get(f"/api/jobs/{job_id}/export/{fmt}").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/export/exe").status_code == 400
    assert client.put(f"/api/jobs/{job_id}", json=config(site, name="N")).status_code == 200
    assert client.delete(f"/api/jobs/{job_id}/items", json={}).status_code == 200
    assert client.delete(f"/api/jobs/{job_id}", json={}).status_code == 200
    assert client.get(f"/api/jobs/{job_id}/items").status_code == 404


def test_validation_and_protection(site, tmp_path):
    client = create_app(tmp_path / "t.db", start_scheduler=False).test_client()
    for bad in (config(site, max_pages=999), config(site, delay="abc"),
                config(site, fields={}), config(site, name=""), []):
        assert client.post("/api/jobs", json=bad).status_code == 400
    assert client.post("/api/jobs", data="x").status_code == 415
    assert client.get("/api/jobs", headers={"Host": "evil.example"}).status_code == 403


def test_scheduler_runs_due_job(site, tmp_path):
    app = create_app(tmp_path / "t.db", start_scheduler=False)
    client = app.test_client()
    job_id = client.post("/api/jobs", json=config(site, interval_minutes=5)).get_json()["id"]
    app.runner.run_due()
    assert wait_done(client, job_id)["added"] == 3
    assert app.runner.db.get_job(job_id)["next_run"] > time.time() + 200


def test_cli(site, tmp_path):
    cfg, out = tmp_path / "c.json", tmp_path / "o.xlsx"
    cfg.write_text(json.dumps(config(site)), encoding="utf-8")
    assert cli.main([str(cfg), "-o", str(out)]) == 0
    assert load_workbook(out).active.max_row == 4
