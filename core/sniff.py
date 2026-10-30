# Определение формата по содержимому файла, а не по расширению

import json
import os
import zipfile

from core.formats import EXTENSIONS

TEXT_FORMATS = ("txt", "csv", "json", "html")
HEAD_SIZE = 4096
JSON_LIMIT = 5 * 1024 * 1024


def _binary_format(path, head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"BM") and len(head) > 14:
        return "bmp"
    if head.lstrip().startswith(b"%PDF") or b"%PDF-" in head[:1024]:
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return "docx"
        if "xl/workbook.xml" in names:
            return "xlsx"
    return None


def _text_format(path, head):
    try:
        text = head.decode("utf-8-sig")
    except UnicodeDecodeError:
        # обрезка могла попасть на середину символа
        try:
            text = head[:-3].decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    if "\x00" in text:
        return None

    stripped = text.lstrip()
    low = stripped[:200].lower()
    if low.startswith(("<!doctype html", "<html")):
        return "html"
    if stripped[:1] in "{[" and os.path.getsize(path) <= JSON_LIMIT:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                json.load(f)
            return "json"
        except (ValueError, OSError):
            pass
    return "txt"


def sniff(path):
    with open(path, "rb") as f:
        head = f.read(HEAD_SIZE)
    if not head:
        return None
    return _binary_format(path, head) or _text_format(path, head)


def detect_format(path, filename):
    # Возвращает (формат, заметка). Заметка непустая, если расширение врёт.
    # Для текстовых форматов расширению верим: csv от txt по содержимому не отличить
    ext = os.path.splitext(filename)[1].lower()
    by_ext = EXTENSIONS.get(ext)
    by_content = sniff(path)

    if by_content is None:
        return by_ext, ""
    if by_ext in TEXT_FORMATS and by_content in TEXT_FORMATS:
        if by_ext == "txt" and by_content in ("json", "html"):
            return by_content, ""
        return by_ext, ""
    if by_ext == by_content:
        return by_ext, ""
    if by_ext is None:
        return by_content, ""
    return by_content, (
        "расширение %s, а внутри %s" % (ext, by_content.upper())
    )
