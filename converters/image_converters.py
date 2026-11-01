from PIL import Image, ImageOps, UnidentifiedImageError

from core.exceptions import ConversionFailedError

JPEG_QUALITY = 95
WEBP_QUALITY = 95
BACKGROUND_COLOR = (255, 255, 255)


def _has_alpha(image):
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def _flatten(image):
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, BACKGROUND_COLOR)
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _prepare(image, keep_alpha):
    image = ImageOps.exif_transpose(image)
    if _has_alpha(image):
        return image.convert("RGBA") if keep_alpha else _flatten(image)
    if image.mode in ("1", "L", "RGB") and keep_alpha:
        return image
    return image.convert("RGB")


def _convert(src, dst, fmt, keep_alpha, **options):
    try:
        with Image.open(src) as image:
            _prepare(image, keep_alpha).save(dst, fmt, **options)
    except UnidentifiedImageError:
        raise ConversionFailedError(
            "Файл не является изображением или повреждён: " + src
        )
    except (OSError, ValueError) as error:
        raise ConversionFailedError("Ошибка при обработке изображения: " + str(error))


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
