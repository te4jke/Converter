import io
import mimetypes
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from core import manager, operations
from core.exceptions import ConverterError
from core.formats import EXTENSIONS
from core.sniff import detect_format

MAX_SIZE = 25 * 1024 * 1024
MAX_FILES = 30
MAX_TOTAL = 150 * 1024 * 1024
WORKERS = 4

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_TOTAL


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/formats")
def formats():
    routes = manager.get_routes()
    return jsonify(
        extensions=EXTENSIONS,
        targets=manager.get_targets(),
        routes=routes,
        edges=[list(pair) for pair in sorted(manager.CONVERTERS)],
        lossy={
            src: [dst for dst, route in dsts.items() if manager.is_lossy_route(route)]
            for src, dsts in routes.items()
        },
        ocr=manager.ocr_converters.is_available(),
        max_size=MAX_SIZE,
        max_files=MAX_FILES,
    )


def clean_name(filename):
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    return name or "file"


def stem_of(filename):
    return os.path.splitext(clean_name(filename))[0] or "file"


def save_upload(upload, folder, index):
    # Сохраняет файл и определяет его формат по содержимому.
    # Возвращает (путь, формат, заметка)
    name = clean_name(upload.filename)
    ext = os.path.splitext(name)[1].lower()
    tmp = os.path.join(folder, "upload%d%s" % (index, ext))
    upload.save(tmp)

    if os.path.getsize(tmp) > MAX_SIZE:
        raise ConverterError("Файл больше %d МБ" % (MAX_SIZE // 1024 // 1024))
    if os.path.getsize(tmp) == 0:
        raise ConverterError("Файл пустой")

    fmt, note = detect_format(tmp, name)
    if fmt is None:
        raise ConverterError("Не удалось определить формат файла")

    path = os.path.join(folder, "source%d.%s" % (index, fmt))
    os.replace(tmp, path)
    return path, fmt, note


def public_message(error, upload_name, *paths):
    message = str(error)
    for path in paths:
        if path:
            message = message.replace(path, upload_name)
    return message


def attach(response, filename, **headers):
    response.headers["Content-Disposition"] = (
        "attachment; filename*=UTF-8''" + quote(filename)
    )
    for key, value in headers.items():
        response.headers["X-" + key.replace("_", "-")] = str(value)
    expose = ["Content-Disposition"] + ["X-" + k.replace("_", "-") for k in headers]
    response.headers["Access-Control-Expose-Headers"] = ", ".join(expose)
    return response


def fail(message, status=400):
    return jsonify(error=message), status


def read_result(path, mime=None):
    with open(path, "rb") as f:
        data = io.BytesIO(f.read())
    return send_file(data, mimetype=mime or mimetypes.guess_type(path)[0]
                     or "application/octet-stream")


@app.route("/api/convert", methods=["POST"])
def convert():
    upload = request.files.get("file")
    target = request.form.get("target", "").lower()

    if upload is None or not upload.filename:
        return fail("Файл не выбран")
    if not target:
        return fail("Не выбран целевой формат")

    with tempfile.TemporaryDirectory() as folder:
        dst = os.path.join(folder, "result." + target)
        src = None
        try:
            src, fmt, note = save_upload(upload, folder, 0)
            manager.convert(src, dst)
        except ConverterError as e:
            return fail(public_message(e, upload.filename, src or "", dst))
        except Exception:
            app.logger.exception("conversion crashed")
            return fail("Внутренняя ошибка при конвертации", 500)

        route = manager.find_route(fmt, target)
        response = read_result(dst)

    return attach(response, stem_of(upload.filename) + "." + target,
                  Route=">".join(route), Detected=fmt, Note=quote(note))


def convert_one(job):
    # Выполняется в потоке, поэтому наружу не бросает исключений
    upload_name, src, dst_name, dst = job
    try:
        manager.convert(src, dst)
        return upload_name, dst_name, dst, None
    except ConverterError as e:
        return upload_name, dst_name, None, public_message(e, upload_name, src, dst)
    except Exception:
        app.logger.exception("batch item crashed")
        return upload_name, dst_name, None, "Внутренняя ошибка"


def unique_name(name, used):
    base, ext = os.path.splitext(name)
    candidate, n = name, 1
    while candidate.lower() in used:
        n += 1
        candidate = "%s (%d)%s" % (base, n, ext)
    used.add(candidate.lower())
    return candidate


@app.route("/api/batch", methods=["POST"])
def batch():
    uploads = [u for u in request.files.getlist("files") if u.filename]
    target = request.form.get("target", "").lower()

    if not uploads:
        return fail("Файлы не выбраны")
    if len(uploads) > MAX_FILES:
        return fail("Не больше %d файлов за раз" % MAX_FILES)
    if not target:
        return fail("Не выбран целевой формат")

    with tempfile.TemporaryDirectory() as folder:
        jobs, problems, used = [], [], set()
        for i, upload in enumerate(uploads):
            try:
                src, fmt, _ = save_upload(upload, folder, i)
            except ConverterError as e:
                problems.append((clean_name(upload.filename), str(e)))
                continue
            dst_name = unique_name(stem_of(upload.filename) + "." + target, used)
            jobs.append((clean_name(upload.filename), src,
                         dst_name, os.path.join(folder, "out%d.%s" % (i, target))))

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = list(pool.map(convert_one, jobs))

        buffer = io.BytesIO()
        done = 0
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for upload_name, dst_name, dst, error in results:
                if error:
                    problems.append((upload_name, error))
                else:
                    z.write(dst, dst_name)
                    done += 1
            if problems:
                lines = ["%s: %s" % item for item in problems]
                z.writestr("ОШИБКИ.txt", "\n".join(lines) + "\n")

    if done == 0:
        return fail("Ни один файл не удалось сконвертировать: "
                    + "; ".join("%s — %s" % p for p in problems[:3]))

    buffer.seek(0)
    response = send_file(buffer, mimetype="application/zip")
    return attach(response, "converted_%s.zip" % target,
                  Done=done, Failed=len(problems))


@app.route("/api/merge", methods=["POST"])
def merge():
    uploads = [u for u in request.files.getlist("files") if u.filename]
    if len(uploads) < 2:
        return fail("Для склейки нужно минимум два файла")
    if len(uploads) > MAX_FILES:
        return fail("Не больше %d файлов за раз" % MAX_FILES)

    with tempfile.TemporaryDirectory() as folder:
        dst = os.path.join(folder, "merged.pdf")
        items = []
        try:
            for i, upload in enumerate(uploads):
                try:
                    path, fmt, _ = save_upload(upload, folder, i)
                except ConverterError as e:
                    raise ConverterError("%s: %s" % (clean_name(upload.filename), e))
                items.append((path, fmt))
            pages = operations.merge_to_pdf(items, dst)
        except ConverterError as e:
            return fail(str(e))
        except Exception:
            app.logger.exception("merge crashed")
            return fail("Внутренняя ошибка при склейке", 500)
        response = read_result(dst, "application/pdf")

    return attach(response, "merged.pdf", Pages=pages)


@app.route("/api/split", methods=["POST"])
def split():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return fail("Файл не выбран")

    with tempfile.TemporaryDirectory() as folder:
        dst = os.path.join(folder, "pages.zip")
        try:
            src, fmt, _ = save_upload(upload, folder, 0)
            if fmt != "pdf":
                raise ConverterError("Делить можно только PDF")
            pages = operations.split_pdf(src, dst)
        except ConverterError as e:
            return fail(str(e))
        except Exception:
            app.logger.exception("split crashed")
            return fail("Внутренняя ошибка при разбиении", 500)
        response = read_result(dst, "application/zip")

    return attach(response, stem_of(upload.filename) + "_pages.zip", Pages=pages)


@app.route("/api/compress", methods=["POST"])
def compress():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return fail("Файл не выбран")
    try:
        quality = int(request.form.get("quality", 70))
        max_side = int(request.form.get("max_side", 0) or 0)
    except ValueError:
        return fail("Некорректные параметры сжатия")

    with tempfile.TemporaryDirectory() as folder:
        try:
            src, fmt, _ = save_upload(upload, folder, 0)
            dst = os.path.join(folder, "small." + fmt)
            operations.compress_image(src, dst, fmt, quality, max_side)
        except ConverterError as e:
            return fail(str(e))
        except Exception:
            app.logger.exception("compress crashed")
            return fail("Внутренняя ошибка при сжатии", 500)
        before, after = os.path.getsize(src), os.path.getsize(dst)
        response = read_result(dst)

    return attach(response, stem_of(upload.filename) + "_small." + fmt,
                  Before=before, After=after)


@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error="Слишком большой объём загрузки (до 150 МБ)"), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
