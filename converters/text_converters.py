# Преобразования текстовых форматов
# Эти функции больше ничего не знают о программе, принимают два пути и работают с файлами

from docx import Document

from core.exceptions import ConversionFailedError


def txt_to_docx(src, dst):
    # Каждая строка txt-файла становится отдельным абзацем
    try:
        doc = Document()

        f = open(src, "r", encoding="utf-8")
        for line in f:
            doc.add_paragraph(line.rstrip("\n"))
        f.close()

        doc.save(dst)
    except UnicodeDecodeError:
        raise ConversionFailedError(
            "Файл не в кодировке UTF-8, прочитать не удалось"
        )


def docx_to_txt(src, dst):
    # Из документа берём только текст абзацев, оформление теряется
    try:
        doc = Document(src)
    except Exception as e:
        raise ConversionFailedError("Не удалось открыть документ: " + str(e))

    lines = []
    for p in doc.paragraphs:
        lines.append(p.text)

    f = open(dst, "w", encoding="utf-8")
    f.write("\n".join(lines))
    f.close()