import os
import unittest

from core import manager
from core.exceptions import ConverterError, UnknownFormatError, UnsupportedConversionError
from tests.helpers import TempDirCase, docx_bytes, pdf_pages


class ConvertTest(TempDirCase):
    def test_direct_conversion(self):
        src = self.write("a.txt", "привет\nмир")
        self.assertEqual(manager.convert(src, self.path("a.pdf")), ("txt", "pdf"))
        self.assertEqual(pdf_pages(self.path("a.pdf")), 1)

    def test_chain_conversion_produces_final_file_only(self):
        src = self.write("a.docx", docx_bytes("текст документа"))
        manager.convert(src, self.path("a.pdf"))
        self.assertEqual(sorted(os.listdir(self.dir)), ["a.docx", "a.pdf"])
        self.assertEqual(pdf_pages(self.path("a.pdf")), 1)

    def test_txt_to_xlsx_goes_through_csv(self):
        src = self.write("t.txt", "a;b\n1;2")
        manager.convert(src, self.path("t.xlsx"))
        self.assertTrue(os.path.getsize(self.path("t.xlsx")) > 0)

    def test_missing_source(self):
        with self.assertRaises(ConverterError):
            manager.convert(self.path("nope.txt"), self.path("x.pdf"))

    def test_same_format(self):
        src = self.write("a.txt", "x")
        with self.assertRaises(ConverterError):
            manager.convert(src, self.path("b.txt"))

    def test_unknown_extension(self):
        src = self.write("a.txt", "x")
        with self.assertRaises(UnknownFormatError):
            manager.convert(src, self.path("b.xyz"))

    def test_no_route(self):
        src = self.write("a.pdf", b"%PDF-1.4")
        with self.assertRaises(UnsupportedConversionError):
            manager.convert(src, self.path("b.png"))

    def test_failed_conversion_removes_partial_result(self):
        src = self.write("bad.json", "не json")
        with self.assertRaises(ConverterError):
            manager.convert(src, self.path("bad.csv"))
        self.assertFalse(os.path.exists(self.path("bad.csv")))

    def test_failed_chain_leaves_no_files_behind(self):
        src = self.write("bad.json", "не json")
        with self.assertRaises(ConverterError):
            manager.convert(src, self.path("bad.xlsx"))
        self.assertEqual(os.listdir(self.dir), ["bad.json"])


if __name__ == "__main__":
    unittest.main()
