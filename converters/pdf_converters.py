# Преобразования между PDF и TXT
# Эти функции больше ничего не знают о программе, принимают два пути и работают с файлами

import os
from xml.sax.saxutils import escape

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from core.exceptions import ConversionFailedError

# Шрифт с кириллицей, лежит рядом с этим файлом.
# Стандартные шрифты PDF русские буквы не умеют
FONT_NAME = "DejaVuSans"
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")

FONT_SIZE = 12
LINE_HEIGHT = 16
PAGE_MARGIN = 20 * mm


def pdf_to_txt(src, dst):
    # Из PDF берём только текст, оформление и картинки теряются
    try:
        reader = PdfReader(src)

        if reader.is_encrypted:
            raise ConversionFailedError("PDF защищён паролем, прочитать не удалось")

        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
    except ConversionFailedError:
        raise
    except (PyPdfError, OSError) as e:
        raise ConversionFailedError("Файл не является PDF или повреждён: " + str(e))

    text = "\n".join(pages)

    if not text.strip():
        raise ConversionFailedError(
            "В PDF не найдено текста (возможно, это скан или картинки)"
        )

    f = open(dst, "w", encoding="utf-8")
    f.write(text)
    f.close()


def txt_to_pdf(src, dst):
    # Каждая строка txt-файла становится отдельным абзацем
    try:
        f = open(src, "r", encoding="utf-8")
        lines = f.read().splitlines()
        f.close()
    except UnicodeDecodeError:
        raise ConversionFailedError(
            "Файл не в кодировке UTF-8, прочитать не удалось"
        )

    if not "".join(lines).strip():
        raise ConversionFailedError("Файл пустой, делать PDF не из чего")

    if not os.path.exists(FONT_PATH):
        raise ConversionFailedError("Не найден шрифт для PDF: " + FONT_PATH)

    try:
        if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

        style = ParagraphStyle(
            "Body", fontName=FONT_NAME, fontSize=FONT_SIZE, leading=LINE_HEIGHT
        )

        story = []
        for line in lines:
            if line.strip():
                # escape нужен, чтобы символы < > & не воспринимались как разметка
                story.append(Paragraph(escape(line), style))
            else:
                story.append(Spacer(1, LINE_HEIGHT))

        doc = SimpleDocTemplate(
            dst,
            pagesize=A4,
            leftMargin=PAGE_MARGIN,
            rightMargin=PAGE_MARGIN,
            topMargin=PAGE_MARGIN,
            bottomMargin=PAGE_MARGIN,
        )
        doc.build(story)
    except OSError as e:
        raise ConversionFailedError("Ошибка при создании PDF: " + str(e))
