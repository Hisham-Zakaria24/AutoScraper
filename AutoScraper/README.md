# 🕷️ AutoScraper – Automated Web Scraper

**Owner / Made by: Hisham-Zakaria**

Scrape data from any static website using a browser dashboard, schedule scraping jobs, and download the results.

## Features
- Web dashboard (create, edit, and delete jobs)
- CSS selectors with a live "Test selectors" preview
- Multi-page scraping (follows the Next button)
- Auto scheduler (runs every X minutes)
- Duplicate data is not saved
- Search, run history, and error messages
- Export to CSV, JSON, and Excel
- CLI mode
- Safety: robots.txt support, rate limiting, retries, private network blocking, and formula-safe export

## How to Run
Requires Python **3.9 or newer**. An internet connection is needed on the first run to install the packages.

**Windows:** Extract the ZIP file, then double-click `run.bat`.

**Linux / Mac:** `bash run.sh`

**Manual:**
```bash
pip install -r requirements.txt
python app.py
```
Open in your browser: **http://127.0.0.1:5000**

To use a different port, set the `PORT` environment variable.

## Your First Job (2 minutes)
1. Click **Load example**
2. Click **Test selectors** to see a preview
3. Click **Save job**, then **Run now**
4. Download the data as CSV, JSON, or Excel

## Selector Guide
| What you need | What to write |
|---|---|
| Text | `h2.title` |
| Link | `a@href` |
| Image | `img@src` |
| The item's own attribute | `@data-id` |

To find a selector: right-click on the page → **Inspect** → check the element's class.

## CLI
```bash
python cli.py examples/quotes.json -o quotes.xlsx
```

## Tests
```bash
python -m pytest -q
```

## Folder Structure
```
AutoScraper/
├── app.py            # Web server + API
├── cli.py            # Command line
├── scraper/
│   ├── engine.py     # Fetch + parse
│   ├── db.py         # SQLite
│   ├── service.py    # Runner + scheduler
│   └── exporter.py   # CSV/JSON/Excel
├── templates/  static/   # Dashboard UI
├── tests/  examples/
└── run.bat  run.sh
```

## Important Notes
- The scheduler works only while the app is **running**.
- Data loaded by JavaScript (such as on many React sites) and sites that require login are not supported.
- Data is saved in `data/scraper.db`.
- Run only one copy of the app at a time.
- This app is meant for use on your own computer only. Do not host it on the internet, as it has no login system.
- To test a local or LAN site, set `SCRAPER_ALLOW_PRIVATE=1`.
- Read a website's Terms of Service before scraping it. Do not collect personal data without permission.

---
© 2026 **Hisham-Zakaria**
