"""Command line use. Made by Hisham-Zakaria.

  python cli.py examples/quotes.json -o quotes.csv
"""
import argparse
import json
import sys
import time
from pathlib import Path

from scraper.engine import ScrapeError, scrape
from scraper.exporter import MIME, export
from scraper.service import validate_job


def main(argv=None):
    parser = argparse.ArgumentParser(description="AutoScraper CLI - by Hisham-Zakaria")
    parser.add_argument("config", help="job JSON file")
    parser.add_argument("-o", "--output", default="output.csv",
                        help="output file (.csv, .json, .xlsx)")
    args = parser.parse_args(argv)
    fmt = Path(args.output).suffix.lstrip(".").lower()
    if fmt not in MIME:
        parser.error("output .csv, .json ya .xlsx hona chahiye")
    try:
        job = validate_job(json.loads(Path(args.config).read_text(encoding="utf-8")))
        rows, pages = scrape(job)
        now = time.time()
        Path(args.output).write_bytes(
            export(fmt, job["fields"], [{**r, "_first_seen": now} for r in rows]))
    except (OSError, ValueError, ScrapeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"{pages} page(s), {len(rows)} item(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
