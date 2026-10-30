import csv
import io
import json

from converters.common import read_text, write_text
from core.exceptions import ConversionFailedError


def csv_to_json(src, dst):
    text = read_text(src)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    try:
        rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    except csv.Error as e:
        raise ConversionFailedError("Некорректный CSV: " + str(e))

    for row in rows:
        row.pop(None, None)

    write_text(dst, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


def json_to_csv(src, dst):
    try:
        data = json.loads(read_text(src))
    except json.JSONDecodeError as e:
        raise ConversionFailedError("Некорректный JSON: " + str(e))

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ConversionFailedError(
            "Для CSV нужен JSON-объект или список объектов"
        )

    fields = []
    for row in data:
        for key in row:
            if key not in fields:
                fields.append(key)

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(fields)
    for row in data:
        writer.writerow([_cell(row.get(k)) for k in fields])

    write_text(dst, out.getvalue())


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value
