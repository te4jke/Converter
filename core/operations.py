# Операции над документами, которые не сводятся к "формат A -> формат B"

import os
import tempfile
import zipfile

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PyPdfError

from core import manager
from core.exceptions import ConversionFailedError

COMPRESSIBLE = ("jpg", "png", "webp")


def merge_to_pdf(items, dst):
    # items: список (путь, формат). PDF добавляется как есть,
    # остальное сначала конвертируется в PDF обычной цепочкой
    if len(items) < 2:
        raise ConversionFailedError("Для склейки нужно минимум два файла")

    writer = PdfWriter()
    with tempfile.TemporaryDirectory() as folder:
        for i, (path, fmt) in enumerate(items):
            pdf_path = path
            if fmt != "pdf":
                pdf_path = os.path.join(folder, "part%d.pdf" % i)
                manager.convert(path, pdf_path)
            try:
                reader = PdfReader(pdf_path)
                if reader.is_encrypted:
                    raise ConversionFailedError("PDF защищён паролем")
                for page in reader.pages:
                    writer.add_page(page)
            except PyPdfError as error:
                raise ConversionFailedError("Файл не является PDF или повреждён: " + str(error))
        with open(dst, "wb") as file:
            writer.write(file)
    return len(writer.pages)


def split_pdf(src, dst_zip):
    try:
        reader = PdfReader(src)
        if reader.is_encrypted:
            raise ConversionFailedError("PDF защищён паролем")
        total = len(reader.pages)
        if total < 2:
            raise ConversionFailedError("В PDF всего одна страница, делить нечего")
        width = max(3, len(str(total)))
        with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as archive, \
                tempfile.TemporaryDirectory() as folder:
            for i, page in enumerate(reader.pages, 1):
                part = PdfWriter()
                part.add_page(page)
                part_path = os.path.join(folder, "p%d.pdf" % i)
                with open(part_path, "wb") as file:
                    part.write(file)
                archive.write(part_path, "page-%s.pdf" % str(i).zfill(width))
    except PyPdfError as error:
        raise ConversionFailedError("Файл не является PDF или повреждён: " + str(error))
    return total


def compress_image(src, dst, fmt, quality, max_side=0):
    # Сжатие в том же формате: меньше качество и/или размер по длинной стороне
    if fmt not in COMPRESSIBLE:
        raise ConversionFailedError("Сжимать можно только JPG, PNG и WEBP")
    quality = max(1, min(100, int(quality)))

    try:
        with Image.open(src) as image:
            image = ImageOps.exif_transpose(image)
            if max_side and max(image.size) > max_side:
                image.thumbnail((max_side, max_side), Image.LANCZOS)

            if fmt == "jpg":
                image.convert("RGB").save(dst, "JPEG", quality=quality,
                                        optimize=True, progressive=True)
            elif fmt == "webp":
                image.save(dst, "WEBP", quality=quality, method=6)
            else:
                # PNG без потерь не ужать, поэтому при низком качестве режем палитру
                if quality < 90:
                    colors = max(16, int(256 * quality / 100))
                    has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
                    rgba = image.convert("RGBA")
                    image = rgba.quantize(colors=colors, method=Image.FASTOCTREE) if has_alpha \
                        else image.convert("RGB").quantize(colors=colors)
                image.save(dst, "PNG", optimize=True)
    except UnidentifiedImageError:
        raise ConversionFailedError("Файл не является изображением или повреждён")
    except (OSError, ValueError) as error:
        raise ConversionFailedError("Ошибка при сжатии: " + str(error))
