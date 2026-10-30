import io
import unittest
import zipfile
from urllib.parse import unquote

from app import app
from tests.helpers import docx_bytes, png_bytes


def upload(data, name):
    return (io.BytesIO(data if isinstance(data, bytes) else data.encode()), name)


class ApiTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def post(self, url, **data):
        return self.client.post(url, data=data, content_type="multipart/form-data")

    def test_formats_describes_graph(self):
        data = self.client.get("/api/formats").get_json()
        self.assertIn("pdf", data["targets"]["docx"])
        self.assertEqual(data["routes"]["docx"]["pdf"], ["docx", "txt", "pdf"])
        self.assertIn(["txt", "json"], data["edges"])
        self.assertIn("pdf", data["lossy"]["docx"])
        self.assertIsInstance(data["ocr"], bool)

    def test_convert_reports_route(self):
        r = self.post("/api/convert", file=upload(docx_bytes("текст"), "a.docx"), target="pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Route"], "docx>txt>pdf")
        self.assertTrue(r.data.startswith(b"%PDF"))

    def test_convert_names_download_by_original_stem(self):
        r = self.post("/api/convert", file=upload("x", "отчёт.txt"), target="pdf")
        self.assertIn(unquote(r.headers["Content-Disposition"]), "attachment; filename*=UTF-8''отчёт.pdf")

    def test_convert_detects_lying_extension(self):
        r = self.post("/api/convert", file=upload(png_bytes(), "photo.jpg"), target="webp")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Detected"], "png")
        self.assertIn("PNG", unquote(r.headers["X-Note"]))

    def test_convert_validation_errors(self):
        self.assertEqual(self.post("/api/convert", target="pdf").status_code, 400)
        self.assertEqual(self.post("/api/convert", file=upload("x", "a.txt")).status_code, 400)
        r = self.post("/api/convert", file=upload("", "a.txt"), target="pdf")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "Файл пустой")

    def test_convert_error_does_not_leak_temp_paths(self):
        r = self.post("/api/convert", file=upload("не json", "bad.json"), target="csv")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("/tmp", r.get_json()["error"])

    def test_batch_zips_results_and_reports_failures(self):
        r = self.post("/api/batch", target="pdf", files=[
            upload(png_bytes(), "a.png"), upload("x", "t.txt"), upload("x", "t.txt"),
            upload("не json", "bad.json")])
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.headers["X-Done"], r.headers["X-Failed"]), ("3", "1"))
        names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
        self.assertEqual(sorted(names), sorted(["ОШИБКИ.txt", "a.pdf", "t (2).pdf", "t.pdf"]))

    def test_batch_all_failed_is_an_error(self):
        r = self.post("/api/batch", target="csv", files=[upload("не json", "a.json")])
        self.assertEqual(r.status_code, 400)

    def test_batch_limits(self):
        files = [upload("x", "f%d.txt" % i) for i in range(31)]
        self.assertEqual(self.post("/api/batch", target="pdf", files=files).status_code, 400)
        self.assertEqual(self.post("/api/batch", target="pdf").status_code, 400)

    def test_merge_and_split_roundtrip(self):
        r = self.post("/api/merge", files=[
            upload(png_bytes(), "a.png"), upload("строка", "b.txt"), upload("ещё", "c.txt")])
        self.assertEqual((r.status_code, r.headers["X-Pages"]), (200, "3"))
        r = self.post("/api/split", file=upload(r.data, "book.pdf"))
        self.assertEqual((r.status_code, r.headers["X-Pages"]), (200, "3"))
        self.assertEqual(len(zipfile.ZipFile(io.BytesIO(r.data)).namelist()), 3)

    def test_merge_needs_two_files(self):
        self.assertEqual(self.post("/api/merge", files=[upload("x", "a.txt")]).status_code, 400)

    def test_split_rejects_non_pdf(self):
        r = self.post("/api/split", file=upload("x", "a.txt"))
        self.assertEqual(r.status_code, 400)

    def test_compress_reports_sizes(self):
        r = self.post("/api/compress", file=upload(png_bytes(size=(300, 300)), "a.png"),
                      quality="40", max_side="100")
        self.assertEqual(r.status_code, 200)
        self.assertLess(int(r.headers["X-After"]), int(r.headers["X-Before"]))

    def test_compress_bad_params(self):
        r = self.post("/api/compress", file=upload(png_bytes(), "a.png"), quality="abc")
        self.assertEqual(r.status_code, 400)

    def test_compress_rejects_documents(self):
        r = self.post("/api/compress", file=upload("x", "a.txt"))
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
