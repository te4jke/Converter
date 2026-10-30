# Распознавание текста на изображениях через tesseract.
# Если tesseract не установлен, is_available() вернёт False и преобразование не регистрируется

import shutil

from PIL import Image, ImageOps, UnidentifiedImageError

from converters.common import write_text
from core.exceptions import ConversionFailedError

try:
    import pytesseract
except ImportError:
    pytesseract = None

PREFERRED_LANGS = ("rus", "eng")


def is_available():
    return pytesseract is not None and shutil.which("tesseract") is not None


def _languages():
    try:
        installed = set(pytesseract.get_languages(config=""))
    except Exception:
        installed = set()
    langs = [l for l in PREFERRED_LANGS if l in installed]
    return "+".join(langs) if langs else "eng"


def image_to_txt(src, dst):
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img).convert("L")
            text = pytesseract.image_to_string(img, lang=_languages())
    except UnidentifiedImageError:
        raise ConversionFailedError("Файл не является изображением или повреждён")
    except (OSError, pytesseract.TesseractError) as e:
        raise ConversionFailedError("Не удалось распознать текст: " + str(e))

    if not text.strip():
        raise ConversionFailedError("На изображении не найден текст")
    write_text(dst, text)
