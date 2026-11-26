#!/usr/bin/env bash
# AutoScraper - made by Hisham-Zakaria
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python app.py
