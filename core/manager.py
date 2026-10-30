import heapq
import os
import tempfile

from core.exceptions import ConverterError, UnsupportedConversionError
from core.formats import get_format
from converters import (
    text_converters, image_converters, json_converters,
    pdf_converters, table_converters, ocr_converters, bridge_converters,
)

CONVERTERS = {
    ("txt", "docx"): text_converters.txt_to_docx,
    ("docx", "txt"): text_converters.docx_to_txt,
    ("txt", "html"): text_converters.txt_to_html,
    ("html", "txt"): text_converters.html_to_txt,
    ("pdf", "txt"): pdf_converters.pdf_to_txt,
    ("txt", "pdf"): pdf_converters.txt_to_pdf,
    ("csv", "xlsx"): table_converters.csv_to_xlsx,
    ("xlsx", "csv"): table_converters.xlsx_to_csv,
    ("csv", "json"): json_converters.csv_to_json,
    ("json", "csv"): json_converters.json_to_csv,
    # мосты между документами и таблицами
    ("txt", "json"): bridge_converters.txt_to_json,
    ("json", "txt"): bridge_converters.json_to_txt,
    ("txt", "csv"): bridge_converters.txt_to_csv,
    ("csv", "txt"): bridge_converters.csv_to_txt,
    ("xlsx", "txt"): bridge_converters.xlsx_to_txt,
    ("csv", "html"): bridge_converters.csv_to_html,
    ("json", "html"): bridge_converters.json_to_html,
    ("xlsx", "html"): bridge_converters.xlsx_to_html,
    ("docx", "csv"): bridge_converters.docx_to_csv,
    ("html", "csv"): bridge_converters.html_to_csv,
}

IMAGE_TARGETS = {
    "jpg": image_converters.to_jpg,
    "png": image_converters.to_png,
    "webp": image_converters.to_webp,
    "bmp": image_converters.to_bmp,
    "gif": image_converters.to_gif,
    "pdf": image_converters.to_pdf,
}

IMAGE_SOURCES = ("png", "jpg", "webp", "bmp", "gif")

for _src in IMAGE_SOURCES:
    for _dst, _func in IMAGE_TARGETS.items():
        if _src != _dst:
            CONVERTERS[(_src, _dst)] = _func


# Распознавание текста на картинках появляется, только если установлен tesseract
if ocr_converters.is_available():
    for _src in IMAGE_SOURCES:
        CONVERTERS[(_src, "txt")] = ocr_converters.image_to_txt

# "Цена" шага при поиске цепочки. Прямое преобразование всегда выбирается первым,
# а в цепочках избегаем шагов, где теряется структура документа
LOSSY_COST = {"txt": 3, "csv": 2, "json": 2}

# Картинка в PDF остаётся картинкой, текста там нет, поэтому дальше по цепочке
# такой PDF не идёт (иначе получилось бы PNG -> PDF -> TXT с пустым результатом)
FINAL_ONLY = {(src, "pdf") for src in IMAGE_SOURCES}


def _step_cost(dst_format):
    return LOSSY_COST.get(dst_format, 1)


def find_route(src_format, dst_format):
    # Возвращает список форматов от исходного до целевого или None.
    # Пример: docx -> pdf даст ["docx", "txt", "pdf"]
    if src_format == dst_format:
        return None
    if (src_format, dst_format) in CONVERTERS:
        return [src_format, dst_format]

    best = {src_format: 0}
    came = {}
    queue = [(0, src_format)]
    while queue:
        cost, node = heapq.heappop(queue)
        if node == dst_format:
            break
        if cost > best.get(node, cost):
            continue
        for (a, b) in CONVERTERS:
            if a != node:
                continue
            if (a, b) in FINAL_ONLY and b != dst_format:
                continue
            new_cost = cost + _step_cost(b)
            if new_cost < best.get(b, float("inf")):
                best[b] = new_cost
                came[b] = node
                heapq.heappush(queue, (new_cost, b))

    if dst_format not in came:
        return None
    route = [dst_format]
    while route[-1] != src_format:
        route.append(came[route[-1]])
    return route[::-1]


def is_lossy_route(route):
    # Цепочка из нескольких шагов, где хотя бы раз текст вытаскивается без оформления
    return len(route) > 2 and any(f in LOSSY_COST for f in route[1:-1])


def _run_route(route, src, dst):
    with tempfile.TemporaryDirectory() as folder:
        current = src
        for i, (a, b) in enumerate(zip(route, route[1:])):
            last = i == len(route) - 2
            target = dst if last else os.path.join(folder, "step%d.%s" % (i, b))
            CONVERTERS[(a, b)](current, target)
            current = target


def convert(src, dst):
    check_source(src)

    src_format = get_format(src)
    dst_format = get_format(dst)

    if src_format == dst_format:
        raise ConverterError("Исходный и целевой форматы совпадают")

    route = find_route(src_format, dst_format)
    if route is None:
        raise UnsupportedConversionError(
            "Преобразование " + src_format.upper() + " -> "
            + dst_format.upper() + " не поддерживается"
        )

    if os.path.exists(src) and os.path.exists(dst) and os.path.samefile(src, dst):
        raise ConverterError("Исходный и результирующий файл совпадают")

    check_target(dst)

    existed = os.path.exists(dst)
    try:
        _run_route(route, src, dst)
    except Exception:
        if not existed and os.path.isfile(dst):
            os.remove(dst)
        raise

    return src_format, dst_format


def check_source(src):
    if not os.path.exists(src):
        raise ConverterError("Файл не найден: " + src)

    if os.path.isdir(src):
        raise ConverterError("Это папка, а не файл: " + src)

    if not os.access(src, os.R_OK):
        raise ConverterError("Нет прав на чтение файла: " + src)


def check_target(dst):
    if os.path.isdir(dst):
        raise ConverterError("Результат указывает на папку: " + dst)

    folder = os.path.dirname(os.path.abspath(dst))
    if not os.path.isdir(folder):
        raise ConverterError("Папки не существует: " + folder)

    if not os.access(folder, os.W_OK):
        raise ConverterError("Нет прав на запись в папку: " + folder)


def get_routes():
    # {исходный формат: {целевой формат: [цепочка форматов]}}
    formats = {f for pair in CONVERTERS for f in pair}
    result = {}
    for src_format in sorted(formats):
        for dst_format in sorted(formats):
            route = find_route(src_format, dst_format)
            if route:
                result.setdefault(src_format, {})[dst_format] = route
    return result


def get_targets():
    return {src: sorted(dsts) for src, dsts in get_routes().items()}


def get_supported():
    result = []
    for src_format, dsts in sorted(get_routes().items()):
        for dst_format, route in sorted(dsts.items()):
            line = src_format.upper() + " -> " + dst_format.upper()
            if len(route) > 2:
                line += "  (через " + ", ".join(f.upper() for f in route[1:-1]) + ")"
            result.append(line)
    return result
