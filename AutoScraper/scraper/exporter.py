"""CSV / JSON / Excel export. Made by Hisham-Zakaria."""
import csv
import io
import json
from datetime import datetime

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill

MIME = {
    "csv": "text/csv",
    "json": "application/json",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _table(fields, items):
    header = list(fields) + ["first_seen"]
    rows = [[str(i.get(f, "")) for f in fields] +
            [datetime.fromtimestamp(i["_first_seen"]).strftime("%Y-%m-%d %H:%M:%S")]
            for i in items]
    return header, rows


def _safe(value):
    """Stop scraped text from running as a spreadsheet formula."""
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def export(fmt, fields, items):
    """Return file content as bytes."""
    if fmt not in MIME:
        raise ValueError("Format csv, json ya xlsx hona chahiye")
    header, rows = _table(fields, items)
    if fmt == "json":
        return json.dumps([dict(zip(header, r)) for r in rows],
                          ensure_ascii=False, indent=2).encode("utf-8")
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([_safe(h) for h in header])
        writer.writerows([[_safe(v) for v in r] for r in rows])
        return out.getvalue().encode("utf-8-sig")  # BOM so Excel reads Unicode
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    for r, values in enumerate([header] + rows, start=1):
        for c, value in enumerate(values, start=1):
            cell = sheet.cell(r, c, ILLEGAL_CHARACTERS_RE.sub("", value)[:32767])
            cell.data_type = "s"  # always text, never a formula
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0F766E")
        sheet.column_dimensions[cell.column_letter].width = 30
    sheet.freeze_panes = "A2"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
