# Свои исключения. Нужны, чтобы в main.py отличать
# предусмотренные ошибки от настоящих багов.


class ConverterError(Exception):
    """Базовая ошибка конвертера."""
    pass


class UnknownFormatError(ConverterError):
    """Расширение файла не распознано."""
    pass


class UnsupportedConversionError(ConverterError):
    """Такая пара форматов не поддерживается."""
    pass


class ConversionFailedError(ConverterError):
    """Ошибка во время самого преобразования."""
    pass