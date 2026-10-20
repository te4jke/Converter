import pandas as pd

from core.exceptions import ConversionFailedError


def csv_to_xlsx(src, dst):
    #читаем CSV-файл и преобразуем его в таблицу
    try:
        df = pd.read_csv(src, sep=None, engine="python", encoding="utf-8-sig")
        #сохраняем таблицу в формате XLSX без индексов строк
        df.to_excel(dst, index=False, engine="openpyxl")
    #обрабатываем ошибку кодировки файла
    except UnicodeDecodeError:
        raise ConversionFailedError(
            "Не удалось прочитать CSV-файл: ошибка кодировки"
        )
    except pd.errors.EmptyDataError: #пустой файл
        raise ConversionFailedError(
            "CSV-файл пустой или не содержит данных: " + src
        )
    except OSError as e: #ошибка доступа к файлу
        raise ConversionFailedError(
            "Ошибка при обработке таблицы: " + str(e)
        )
    except Exception as e: #остальные ошибки
        raise ConversionFailedError(
            "Ошибка при конвертации CSV в XLSX: " + str(e)
        )


def xlsx_to_csv(src, dst): #преобразуем файл XLSX в CSV
    try:
        df = pd.read_excel(src, engine="openpyxl") #читаем первый лист excel-файла
        df.to_csv(dst, index=False, encoding="utf-8-sig") #сохраняем данные в CSV

    except OSError as e: #обработка ошибок
        raise ConversionFailedError(
            "Ошибка при обработке таблицы: " + str(e)
        )
    except Exception as e:
        raise ConversionFailedError(
            "Ошибка при конвертации XLSX в CSV: " + str(e)
        )