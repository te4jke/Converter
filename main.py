import argparse
import sys

from core import manager
from core.exceptions import ConverterError


def print_supported():
    print("Поддерживаемые преобразования:")
    for item in manager.get_supported():
        print("  " + item)


def main():
    parser = argparse.ArgumentParser(description="Конвертер форматов файлов")
    parser.add_argument("source", nargs="?", help="исходный файл")
    parser.add_argument("target", nargs="?", help="результирующий файл")
    parser.add_argument("-l", "--list", action="store_true",
                        help="показать поддерживаемые преобразования")

    args = parser.parse_args()

    if args.list:
        print_supported()
        return 0

    if args.source is None or args.target is None:
        parser.print_help()
        return 1

    try:
        src_format, dst_format = manager.convert(args.source, args.target)
    except ConverterError as e:
        print("Ошибка: " + str(e))
        return 1
    except Exception as e:
        print("Непредвиденная ошибка: " + str(e))
        return 1

    route = manager.find_route(src_format, dst_format)
    print("Выполнено: " + " -> ".join(f.upper() for f in route))
    print("Результат сохранён в " + args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())