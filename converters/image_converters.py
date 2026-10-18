
from PIL import Image, UnidentifiedImageError

from core.exceptions import ConversionFailedError

JPEG_QUALITY = 95

BACKGROUND_COLOR = (255, 255, 255)


def png_to_jpg(src, dst):
    try:
        with Image.open(src) as img:
            if img.mode in ("RGBA", "LA", "P"):
                rgba = img.convert("RGBA")
                background = Image.new("RGB", rgba.size, BACKGROUND_COLOR)
                background.paste(rgba, mask=rgba.getchannel("A"))
                result = background
            else:
                result = img.convert("RGB")

            result.save(dst, "JPEG", quality=JPEG_QUALITY)

    except UnidentifiedImageError:
        raise ConversionFailedError(
            "Файл не является изображением или повреждён: " + src
        )
    except OSError as e:
        raise ConversionFailedError("Ошибка при обработке изображения: " + str(e))


def jpg_to_png(src, dst):
    try:
        with Image.open(src) as img:
            img.save(dst, "PNG")

    except UnidentifiedImageError:
        raise ConversionFailedError(
            "Файл не является изображением или повреждён: " + src
        )
    except OSError as e:
        raise ConversionFailedError("Ошибка при обработке изображения: " + str(e))