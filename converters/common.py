from core.exceptions import ConversionFailedError


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return f.read()
    except UnicodeDecodeError:
        raise ConversionFailedError(
            "Файл не в кодировке UTF-8, прочитать не удалось"
        )
    except OSError as e:
        raise ConversionFailedError("Не удалось прочитать файл: " + str(e))


def write_text(path, text):
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    except OSError as e:
        raise ConversionFailedError("Не удалось записать файл: " + str(e))
