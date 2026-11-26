# 🕷️ AutoScraper – Automated Web Scraper

**Owner / Made by: Hisham-Zakaria**

Browser dashboard se kisi bhi static website ka data scrape karein, schedule karein aur download karein.

## Features
- Web dashboard (job banayein, edit, delete)
- CSS selectors, "Test selectors" live preview
- Multi-page scraping (Next button follow)
- Auto scheduler (har X minute)
- Duplicate data save nahi hota
- Search, run history, error messages
- Export: CSV, JSON, Excel
- CLI mode
- Safety: robots.txt, rate limit, retries, private network block, formula-safe export

## Kaise chalayein
Python **3.9 ya usse naya** chahiye. Pehli baar internet chahiye (packages install honge).

**Windows:** ZIP extract karein, phir `run.bat` double-click karein.

**Linux / Mac:** `bash run.sh`

**Manual:**
```bash
pip install -r requirements.txt
python app.py
```
Browser me kholein: **http://127.0.0.1:5000**

Port badalna ho to `PORT` environment variable set karein.

## Pehla job (2 minute)
1. **Load example** dabayein
2. **Test selectors** se preview dekhein
3. **Save job**, phir **Run now**
4. CSV / JSON / Excel download karein

## Selector guide
| Chahiye | Likhein |
|---|---|
| Text | `h2.title` |
| Link | `a@href` |
| Image | `img@src` |
| Item ka apna attribute | `@data-id` |

Selector nikalne ke liye: page par right-click → **Inspect** → element ki class dekhein.

## CLI
```bash
python cli.py examples/quotes.json -o quotes.xlsx
```

## Tests
```bash
python -m pytest -q
```

## Folder structure
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

## Zaroori baatein
- Scheduler tabhi chalta hai jab app **chalu** ho.
- JavaScript se load hone wala data (React jaisi sites) aur login wali sites support nahi hain.
- Data `data/scraper.db` me save hota hai.
- Ek app copy ek time par chalayein.
- Ye sirf apne computer ke liye hai; ise internet par host na karein (login system nahi hai).
- Local/LAN site test karni ho to `SCRAPER_ALLOW_PRIVATE=1` set karein.
- Scraping se pehle website ki Terms of Service padhein. Personal data bina permission collect na karein.

---
© 2026 **Hisham-Zakaria**
