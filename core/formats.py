import os

from core.exceptions import UnknownFormatError

# Расширение -> название формата
# Потом сюда допишем pdf, csv, xlsx, png и остальные как дальше делать будем
EXTENSIONS = {
    ".txt": "txt",
    ".docx": "docx",
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
}


def get_format(filename):
    # Определяет формат файла по расширению имени
    ext = os.path.splitext(filename)[1].lower()

    if ext == "":
        raise UnknownFormatError("У файла нет расширения: " + filename)

    if ext not in EXTENSIONS:
        raise UnknownFormatError("Формат '" + ext + "' не поддерживается")

    return EXTENSIONS[ext]


def get_extensions():
    # Все поддерживаемые расширения
    return sorted(EXTENSIONS.keys())