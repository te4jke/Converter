import os

from core.exceptions import UnknownFormatError

EXTENSIONS = {
    ".txt": "txt",
    ".docx": "docx",
    ".html": "html",
    ".htm": "html",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".json": "json",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".webp": "webp",
    ".bmp": "bmp",
    ".gif": "gif",
    ".pdf": "pdf",
}


def get_format(filename):
    ext = os.path.splitext(filename)[1].lower()

    if ext == "":
        raise UnknownFormatError("У файла нет расширения: " + filename)

    if ext not in EXTENSIONS:
        raise UnknownFormatError("Формат '" + ext + "' не поддерживается")

    return EXTENSIONS[ext]


def get_extensions():
    return sorted(EXTENSIONS.keys())
