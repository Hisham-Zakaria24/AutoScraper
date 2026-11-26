"""Job validation, running and scheduling. Made by Hisham-Zakaria."""
import logging
import threading
import time

from .engine import MAX_PAGES, ScrapeError, scrape

log = logging.getLogger("autoscraper")


def _number(data, key, default, low, high, kind=int):
    value = data.get(key)
    if value in (None, ""):
        return default
    try:
        value = kind(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{key} number hona chahiye")
    if not low <= value <= high:
        raise ValueError(f"{key} {low} se {high} ke beech hona chahiye")
    return value


def validate_job(data):
    if not isinstance(data, dict):
        raise ValueError("Invalid data")
    job = {}
    for key, required in (("name", True), ("url", True),
                          ("item_selector", True), ("next_selector", False)):
        value = str(data.get(key) or "").strip()
        if required and not value:
            raise ValueError(f"{key} zaroori hai")
        job[key] = value
    if not job["url"].lower().startswith(("http://", "https://")):
        raise ValueError("URL http:// ya https:// se start hona chahiye")
    fields = data.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("Kam se kam ek field add karein")
    job["fields"] = {}
    for name, spec in fields.items():
        name, spec = str(name).strip(), str(spec).strip()
        if not name or not spec or name.startswith("_"):
            raise ValueError("Field ka naam aur selector dono chahiye (naam _ se start na ho)")
        job["fields"][name] = spec
    job["max_pages"] = _number(data, "max_pages", 1, 1, MAX_PAGES)
    job["delay"] = _number(data, "delay", 1.0, 0.5, 60, float)
    job["interval_minutes"] = _number(data, "interval_minutes", 0, 0, 10080)
    job["respect_robots"] = bool(data.get("respect_robots", True))
    return job


class Runner:
    """Runs jobs in background threads and starts the scheduled ones."""

    def __init__(self, db, tick=5.0, max_parallel=3):
        self.db = db
        self.tick = tick
        self._active = set()
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(max_parallel)
        self._stop = threading.Event()

    def is_running(self, job_id):
        with self._lock:
            return job_id in self._active

    def _claim(self, job_id):
        with self._lock:
            if job_id in self._active:
                return False
            self._active.add(job_id)
            return True

    def _release(self, job_id):
        with self._lock:
            self._active.discard(job_id)

    def _execute(self, job_id):
        job = self.db.get_job(job_id)
        if not job:
            return None
        run_id = self.db.start_run(job_id)
        result = {"status": "failed", "pages": 0, "found": 0, "added": 0, "error": ""}
        try:
            rows, pages = scrape(job)
            result.update(pages=pages, found=len(rows),
                          added=self.db.save_items(job_id, rows),
                          status="success" if rows else "empty")
            if not rows:
                result["error"] = "Koi data nahi mila. Selectors check karein."
        except ScrapeError as exc:
            result["error"] = str(exc)
        except Exception as exc:  # keep the scheduler alive
            log.exception("Job %s crashed", job_id)
            result["error"] = f"Unexpected error: {type(exc).__name__}"
        self.db.finish_run(run_id, **result)
        return result

    def run_now(self, job_id):
        """Blocking run (used by CLI)."""
        if not self._claim(job_id):
            return None
        try:
            return self._execute(job_id)
        finally:
            self._release(job_id)

    def run_async(self, job_id):
        if not self._claim(job_id):
            return False

        def work():
            try:
                with self._slots:
                    self._execute(job_id)
            except Exception:
                log.exception("Job %s could not run", job_id)
            finally:
                self._release(job_id)

        threading.Thread(target=work, daemon=True).start()
        return True

    def run_due(self):
        now = time.time()
        for job_id in self.db.due_jobs(now):
            job = self.db.get_job(job_id)
            if job and self.run_async(job_id):
                self.db.set_next_run(job_id, now + job["interval_minutes"] * 60)

    def start_scheduler(self):
        self.db.close_stale_runs()

        def loop():
            while not self._stop.is_set():
                try:
                    self.run_due()
                except Exception:
                    log.exception("Scheduler error")
                self._stop.wait(self.tick)

        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self._stop.set()
