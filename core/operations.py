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
            except PyPdfError as e:
                raise ConversionFailedError("Файл не является PDF или повреждён: " + str(e))
        with open(dst, "wb") as f:
            writer.write(f)
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
        with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as z, \
                tempfile.TemporaryDirectory() as folder:
            for i, page in enumerate(reader.pages, 1):
                part = PdfWriter()
                part.add_page(page)
                part_path = os.path.join(folder, "p%d.pdf" % i)
                with open(part_path, "wb") as f:
                    part.write(f)
                z.write(part_path, "page-%s.pdf" % str(i).zfill(width))
    except PyPdfError as e:
        raise ConversionFailedError("Файл не является PDF или повреждён: " + str(e))
    return total


def compress_image(src, dst, fmt, quality, max_side=0):
    # Сжатие в том же формате: меньше качество и/или размер по длинной стороне
    if fmt not in COMPRESSIBLE:
        raise ConversionFailedError("Сжимать можно только JPG, PNG и WEBP")
    quality = max(1, min(100, int(quality)))

    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            if max_side and max(img.size) > max_side:
                img.thumbnail((max_side, max_side), Image.LANCZOS)

            if fmt == "jpg":
                img.convert("RGB").save(dst, "JPEG", quality=quality,
                                        optimize=True, progressive=True)
            elif fmt == "webp":
                img.save(dst, "WEBP", quality=quality, method=6)
            else:
                # PNG без потерь не ужать, поэтому при низком качестве режем палитру
                if quality < 90:
                    colors = max(16, int(256 * quality / 100))
                    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
                    rgba = img.convert("RGBA")
                    img = rgba.quantize(colors=colors, method=Image.FASTOCTREE) if has_alpha \
                        else img.convert("RGB").quantize(colors=colors)
                img.save(dst, "PNG", optimize=True)
    except UnidentifiedImageError:
        raise ConversionFailedError("Файл не является изображением или повреждён")
    except (OSError, ValueError) as e:
        raise ConversionFailedError("Ошибка при сжатии: " + str(e))
