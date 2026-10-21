import os

from core.exceptions import ConverterError, UnsupportedConversionError
from core.formats import get_format
from converters import text_converters, image_converters, pdf_converters

# Таблица преобразований: пара форматов -> функция
# Когда добавим новые конвертеры, дописываем сюда строку
CONVERTERS = {
    ("txt", "docx"): text_converters.txt_to_docx,
    ("docx", "txt"): text_converters.docx_to_txt,
    ("png", "jpg"): image_converters.png_to_jpg,
    ("jpg", "png"): image_converters.jpg_to_png,
    ("pdf", "txt"): pdf_converters.pdf_to_txt,
    ("txt", "pdf"): pdf_converters.txt_to_pdf,
}


def convert(src, dst):
    check_source(src)

    src_format = get_format(src)
    dst_format = get_format(dst)

    if src_format == dst_format:
        raise ConverterError("Исходный и целевой форматы совпадают")

    key = (src_format, dst_format)
    if key not in CONVERTERS:
        raise UnsupportedConversionError(
            "Преобразование " + src_format.upper() + " -> "
            + dst_format.upper() + " не поддерживается"
        )

    func = CONVERTERS[key]
    func(src, dst)

    return src_format, dst_format


def check_source(src):
    if not os.path.exists(src):
        raise ConverterError("Файл не найден: " + src)

    if os.path.isdir(src):
        raise ConverterError("Это папка, а не файл: " + src)

    if not os.access(src, os.R_OK):
        raise ConverterError("Нет прав на чтение файла: " + src)


def get_supported():
    result = []
    for src_format, dst_format in sorted(CONVERTERS.keys()):
        result.append(src_format.upper() + " -> " + dst_format.upper())
    return result