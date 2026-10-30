import unittest
import zipfile

from core.sniff import detect_format, sniff
from tests.helpers import TempDirCase, docx_bytes, png_bytes


class SniffTest(TempDirCase):
    def test_binary_signatures(self):
        cases = {
            "png": png_bytes(),
            "jpg": b"\xff\xd8\xff\xe0" + b"\0" * 20,
            "gif": b"GIF89a" + b"\0" * 20,
            "webp": b"RIFF\0\0\0\0WEBPVP8 ",
            "bmp": b"BM" + b"\0" * 30,
            "pdf": b"%PDF-1.7\n",
        }
        for fmt, data in cases.items():
            self.assertEqual(sniff(self.write("f." + fmt, data)), fmt)

    def test_docx_and_xlsx_are_told_apart_inside_zip(self):
        self.assertEqual(sniff(self.write("d.bin", docx_bytes("x"))), "docx")
        with zipfile.ZipFile(self.path("x.bin"), "w") as z:
            z.writestr("xl/workbook.xml", "<x/>")
        self.assertEqual(sniff(self.path("x.bin")), "xlsx")

    def test_plain_zip_is_unknown(self):
        with zipfile.ZipFile(self.path("z.bin"), "w") as z:
            z.writestr("a.txt", "x")
        self.assertIsNone(sniff(self.path("z.bin")))

    def test_text_variants(self):
        self.assertEqual(sniff(self.write("a", '{"a": 1}')), "json")
        self.assertEqual(sniff(self.write("b", "<!DOCTYPE html><html></html>")), "html")
        self.assertEqual(sniff(self.write("c", "просто текст")), "txt")

    def test_broken_json_falls_back_to_txt(self):
        self.assertEqual(sniff(self.write("a", "{не json")), "txt")

    def test_empty_and_binary_garbage(self):
        self.assertIsNone(sniff(self.write("e", b"")))
        self.assertIsNone(sniff(self.write("g", b"\x00\x01\x02\xff\xfe")))


class DetectFormatTest(TempDirCase):
    def test_extension_is_enough_for_honest_files(self):
        path = self.write("a.png", png_bytes())
        self.assertEqual(detect_format(path, "a.png"), ("png", ""))

    def test_content_beats_lying_extension(self):
        path = self.write("a.jpg", png_bytes())
        fmt, note = detect_format(path, "photo.jpg")
        self.assertEqual(fmt, "png")
        self.assertIn("PNG", note)

    def test_csv_extension_is_trusted_for_text(self):
        path = self.write("a.csv", "a,b\n1,2")
        self.assertEqual(detect_format(path, "a.csv"), ("csv", ""))

    def test_txt_extension_with_json_inside_is_json(self):
        path = self.write("a.txt", '[1, 2]')
        self.assertEqual(detect_format(path, "a.txt")[0], "json")

    def test_no_extension_uses_content(self):
        path = self.write("a", "%PDF-1.4 ...".encode())
        self.assertEqual(detect_format(path, "a"), ("pdf", ""))

    def test_unknown_everything(self):
        path = self.write("a.xyz", b"\x00\x01")
        self.assertEqual(detect_format(path, "a.xyz"), (None, ""))


if __name__ == "__main__":
    unittest.main()
