"""Fetching and parsing logic. Made by Hisham-Zakaria."""
import ipaddress
import os
import socket
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "AutoScraper/1.0 (by Hisham-Zakaria)"
MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 50
TIMEOUT = 15


class ScrapeError(Exception):
    """An error with a message that is safe to show to the user."""


def check_url(url):
    """Allow only public http/https addresses.

    Set SCRAPER_ALLOW_PRIVATE=1 to scrape localhost / LAN (for testing).
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ScrapeError("URL http:// ya https:// se start hona chahiye")
    if os.environ.get("SCRAPER_ALLOW_PRIVATE") == "1":
        return
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except (socket.gaierror, UnicodeError):
        raise ScrapeError(f"Website nahi mili: {parts.hostname}")
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise ScrapeError("Private / local network address blocked hai")


class Fetcher:
    def __init__(self, delay=1.0, respect_robots=True, retries=2):
        self.delay = delay
        self.respect_robots = respect_robots
        self.retries = retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots = {}
        self._last = 0.0

    def _request(self, url):
        """GET with rate limit and retries. Redirects are not auto-followed."""
        error = ""
        for attempt in range(self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                res = self.session.get(url, timeout=TIMEOUT, stream=True,
                                       allow_redirects=False)
                if res.status_code != 429 and res.status_code < 500:
                    return res
                error = f"HTTP {res.status_code}"
                res.close()
            except requests.RequestException as exc:
                error = type(exc).__name__
            if attempt < self.retries:
                time.sleep(2 ** attempt)
        raise ScrapeError(f"Request fail hui ({error}): {url}")

    def _read(self, res):
        body = bytearray()
        try:
            for chunk in res.iter_content(65536):
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ScrapeError("Page 5 MB se bada hai")
        except requests.RequestException as exc:
            raise ScrapeError(f"Download fail hua: {type(exc).__name__}")
        finally:
            res.close()
        return bytes(body)

    def _allowed(self, url):
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser = RobotFileParser()
            res, link = None, root + "/robots.txt"
            for _ in range(5):
                check_url(link)
                res = self._request(link)
                location = res.headers.get("Location")
                if res.is_redirect and location:
                    res.close()
                    link = urljoin(link, location)
                    continue
                break
            if res.status_code == 200:
                parser.parse(self._read(res).decode("utf-8", "replace").splitlines())
            else:
                res.close()
                if res.status_code in (401, 403):
                    parser.disallow_all = True
                else:
                    parser.allow_all = True
            self._robots[root] = parser
        return self._robots[root].can_fetch(USER_AGENT, url)

    def get(self, url):
        """Return (final_url, html_bytes)."""
        for _ in range(6):
            check_url(url)
            if self.respect_robots and not self._allowed(url):
                raise ScrapeError(f"robots.txt is page ko allow nahi karta: {url}")
            res = self._request(url)
            location = res.headers.get("Location")
            if res.is_redirect and location:
                res.close()
                url = urljoin(url, location)
                continue
            if res.status_code != 200:
                res.close()
                raise ScrapeError(f"HTTP {res.status_code}: {url}")
            return url, self._read(res)
        raise ScrapeError("Bahut zyada redirects")


def parse_field(spec):
    """'a.title@href' -> ('a.title', 'href'); 'h2' -> ('h2', None)."""
    selector, sep, attr = spec.rpartition("@")
    # An @ inside [..] or quotes belongs to the CSS selector itself.
    if sep and attr.replace("-", "").replace("_", "").isalnum():
        return selector.strip(), attr
    return spec.strip(), None


def _select(node, selector, many=False):
    try:
        return node.select(selector) if many else node.select_one(selector)
    except Exception:
        raise ScrapeError(f"Galat CSS selector: {selector}")


def extract(soup, base_url, item_selector, fields):
    rows = []
    for item in _select(soup, item_selector, many=True):
        row = {}
        for name, spec in fields.items():
            selector, attr = parse_field(spec)
            node = _select(item, selector) if selector else item
            value = ""
            if node is not None:
                if attr:
                    value = node.get(attr, "")
                    if isinstance(value, list):
                        value = " ".join(value)
                    if attr in ("href", "src") and value:
                        value = urljoin(base_url, value)
                else:
                    value = " ".join(node.get_text(" ").split())
            row[name] = value
        if any(row.values()):
            rows.append(row)
    return rows


def scrape(job, fetcher=None, max_pages=None):
    """Run a job config. Returns (rows, pages_scraped)."""
    fetcher = fetcher or Fetcher(delay=job.get("delay", 1.0),
                                 respect_robots=job.get("respect_robots", True))
    limit = min(max_pages or job.get("max_pages", 1), MAX_PAGES)
    url, seen, rows, pages = job["url"], set(), [], 0
    while url and url not in seen and pages < limit:
        seen.add(url)
        final_url, html = fetcher.get(url)
        seen.add(final_url)
        soup = BeautifulSoup(html, "html.parser")
        rows.extend(extract(soup, final_url, job["item_selector"], job["fields"]))
        pages += 1
        url = None
        if job.get("next_selector"):
            link = _select(soup, job["next_selector"])
            if link is not None and link.get("href"):
                url = urljoin(final_url, link["href"])
    return rows, pages
