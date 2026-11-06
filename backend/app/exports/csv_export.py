import csv
import io
import json

# Cells starting with these characters are read as formulas by Excel and Sheets.
# Prefixing with an apostrophe stops a crafted agent message from running code
# on a reviewer's computer when the CSV is opened ("CSV injection").
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value)
    if text.startswith(FORMULA_START):
        return "'" + text
    return text


def to_csv(rows: list[dict], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(column)) for column in columns])
    return buffer.getvalue()