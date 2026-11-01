from core.exceptions import ConversionFailedError


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            return file.read()
    except UnicodeDecodeError:
        raise ConversionFailedError(
            "Файл не в кодировке UTF-8, прочитать не удалось"
        )
    except OSError as error:
        raise ConversionFailedError("Не удалось прочитать файл: " + str(error))


def write_text(path, text):
    try:
        with open(path, "w", encoding="utf-8", newline="") as file:
            file.write(text)
    except OSError as error:
        raise ConversionFailedError("Не удалось записать файл: " + str(error))
