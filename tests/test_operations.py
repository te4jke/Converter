import unittest
import zipfile

from PIL import Image

from core import operations
from core.exceptions import ConversionFailedError
from tests.helpers import TempDirCase, pdf_pages, png_bytes


class MergeTest(TempDirCase):
    def test_merges_mixed_files_in_order(self):
        img = self.write("a.png", png_bytes())
        txt = self.write("b.txt", "строка")
        pages = operations.merge_to_pdf([(img, "png"), (txt, "txt")], self.path("m.pdf"))
        self.assertEqual(pages, 2)
        self.assertEqual(pdf_pages(self.path("m.pdf")), 2)

    def test_pdf_parts_are_kept_as_is(self):
        from converters import pdf_converters
        pdf_converters.txt_to_pdf(self.write("a.txt", "x"), self.path("a.pdf"))
        pdf_converters.txt_to_pdf(self.write("b.txt", "y"), self.path("b.pdf"))
        pages = operations.merge_to_pdf(
            [(self.path("a.pdf"), "pdf"), (self.path("b.pdf"), "pdf")], self.path("m.pdf"))
        self.assertEqual(pages, 2)

    def test_needs_two_files(self):
        with self.assertRaises(ConversionFailedError):
            operations.merge_to_pdf([(self.write("a.txt", "x"), "txt")], self.path("m.pdf"))


class SplitTest(TempDirCase):
    def make_pdf(self, pages):
        from converters import pdf_converters
        self.write("src.txt", "\n".join(["строка"] * pages))
        pdf_converters.txt_to_pdf(self.path("src.txt"), self.path("src.pdf"))
        return self.path("src.pdf")

    def test_one_file_per_page(self):
        merged = self.path("m.pdf")
        operations.merge_to_pdf(
            [(self.write("a.txt", "a"), "txt"), (self.write("b.txt", "b"), "txt"),
             (self.write("c.txt", "c"), "txt")], merged)
        total = operations.split_pdf(merged, self.path("p.zip"))
        self.assertEqual(total, 3)
        with zipfile.ZipFile(self.path("p.zip")) as z:
            self.assertEqual(z.namelist(), ["page-001.pdf", "page-002.pdf", "page-003.pdf"])

    def test_single_page_is_rejected(self):
        with self.assertRaises(ConversionFailedError):
            operations.split_pdf(self.make_pdf(1), self.path("p.zip"))

    def test_garbage_is_rejected(self):
        with self.assertRaises(ConversionFailedError):
            operations.split_pdf(self.write("x.pdf", b"nope"), self.path("p.zip"))


class CompressTest(TempDirCase):
    def noisy_jpg(self):
        Image.effect_noise((800, 600), 80).convert("RGB").save(self.path("n.jpg"), quality=95)
        return self.path("n.jpg")

    def test_lower_quality_shrinks_file(self):
        import os
        src = self.noisy_jpg()
        operations.compress_image(src, self.path("s.jpg"), "jpg", 30)
        self.assertLess(os.path.getsize(self.path("s.jpg")), os.path.getsize(src))

    def test_max_side_resizes(self):
        operations.compress_image(self.noisy_jpg(), self.path("s.jpg"), "jpg", 80, max_side=200)
        with Image.open(self.path("s.jpg")) as img:
            self.assertEqual(max(img.size), 200)

    def test_smaller_image_is_not_upscaled(self):
        operations.compress_image(self.noisy_jpg(), self.path("s.jpg"), "jpg", 80, max_side=5000)
        with Image.open(self.path("s.jpg")) as img:
            self.assertEqual(img.size, (800, 600))

    def test_png_and_webp_are_supported(self):
        src = self.write("a.png", png_bytes(size=(100, 100)))
        for fmt in ("png", "webp"):
            operations.compress_image(src, self.path("s." + fmt), fmt, 50)
            with Image.open(self.path("s." + fmt)) as img:
                self.assertEqual(img.format, fmt.upper())

    def test_quality_is_clamped(self):
        src = self.write("a.png", png_bytes())
        operations.compress_image(src, self.path("s.png"), "png", 9999)
        operations.compress_image(src, self.path("t.png"), "png", -5)

    def test_unsupported_format(self):
        with self.assertRaises(ConversionFailedError):
            operations.compress_image(self.write("a.bmp", b"BM"), self.path("s.bmp"), "bmp", 50)

    def test_not_an_image(self):
        with self.assertRaises(ConversionFailedError):
            operations.compress_image(self.write("a.jpg", b"text"), self.path("s.jpg"), "jpg", 50)


if __name__ == "__main__":
    unittest.main()
