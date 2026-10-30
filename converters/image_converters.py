from PIL import Image, ImageOps, UnidentifiedImageError

from core.exceptions import ConversionFailedError

JPEG_QUALITY = 95
WEBP_QUALITY = 95
BACKGROUND_COLOR = (255, 255, 255)


def _has_alpha(img):
    return img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info


def _flatten(img):
    rgba = img.convert("RGBA")
    background = Image.new("RGB", rgba.size, BACKGROUND_COLOR)
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _prepare(img, keep_alpha):
    img = ImageOps.exif_transpose(img)
    if _has_alpha(img):
        return img.convert("RGBA") if keep_alpha else _flatten(img)
    if img.mode in ("1", "L", "RGB") and keep_alpha:
        return img
    return img.convert("RGB")


def _convert(src, dst, fmt, keep_alpha, **options):
    try:
        with Image.open(src) as img:
            _prepare(img, keep_alpha).save(dst, fmt, **options)
    except UnidentifiedImageError:
        raise ConversionFailedError(
            "Файл не является изображением или повреждён: " + src
        )
    except (OSError, ValueError) as e:
        raise ConversionFailedError("Ошибка при обработке изображения: " + str(e))


def to_jpg(src, dst):
    _convert(src, dst, "JPEG", False, quality=JPEG_QUALITY)


def to_png(src, dst):
    _convert(src, dst, "PNG", True)


def to_webp(src, dst):
    _convert(src, dst, "WEBP", True, quality=WEBP_QUALITY)


def to_bmp(src, dst):
    _convert(src, dst, "BMP", False)


def to_gif(src, dst):
    _convert(src, dst, "GIF", False)


def to_pdf(src, dst):
    _convert(src, dst, "PDF", False)
