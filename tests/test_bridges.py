import json
import unittest

from converters import bridge_converters as b
from core.exceptions import ConversionFailedError
from tests.helpers import TempDirCase, docx_bytes


class TxtJsonTest(TempDirCase):
    def test_txt_to_json_is_array_of_lines(self):
        b.txt_to_json(self.write("a.txt", "привет\n\nмир"), self.path("a.json"))
        self.assertEqual(json.loads(self.read("a.json")), ["привет", "", "мир"])

    def test_roundtrip_restores_lines(self):
        b.txt_to_json(self.write("a.txt", "один\nдва"), self.path("a.json"))
        b.json_to_txt(self.path("a.json"), self.path("b.txt"))
        self.assertEqual(self.read("b.txt").splitlines(), ["один", "два"])

    def test_json_object_becomes_pretty_text(self):
        b.json_to_txt(self.write("a.json", '{"к": 1}'), self.path("a.txt"))
        self.assertEqual(json.loads(self.read("a.txt")), {"к": 1})

    def test_empty_txt_is_rejected(self):
        with self.assertRaises(ConversionFailedError):
            b.txt_to_json(self.write("a.txt", "  \n"), self.path("a.json"))

    def test_bad_json_is_rejected(self):
        with self.assertRaises(ConversionFailedError):
            b.json_to_txt(self.write("a.json", "{"), self.path("a.txt"))


class TxtCsvTest(TempDirCase):
    def test_delimiter_is_detected(self):
        b.txt_to_csv(self.write("a.txt", "a;b;c\n1;2;3"), self.path("a.csv"))
        self.assertEqual(self.read("a.csv"), "a,b,c\n1,2,3\n")

    def test_lines_without_delimiter_become_one_column(self):
        b.txt_to_csv(self.write("a.txt", "один\nдва"), self.path("a.csv"))
        self.assertEqual(self.read("a.csv").splitlines(), ["один", "два"])

    def test_csv_to_txt_uses_tabs(self):
        b.csv_to_txt(self.write("a.csv", "a,b\n1,2"), self.path("a.txt"))
        self.assertEqual(self.read("a.txt"), "a\tb\n1\t2\n")


class HtmlTableTest(TempDirCase):
    def test_csv_to_html_builds_header_and_rows(self):
        b.csv_to_html(self.write("a.csv", "x,y\n1,2"), self.path("a.html"))
        html = self.read("a.html")
        self.assertIn("<th>x</th>", html)
        self.assertIn("<td>2</td>", html)

    def test_html_is_escaped(self):
        b.csv_to_html(self.write("a.csv", "x\n<b>&</b>"), self.path("a.html"))
        self.assertIn("&lt;b&gt;&amp;&lt;/b&gt;", self.read("a.html"))

    def test_json_to_html_unions_keys(self):
        src = self.write("a.json", '[{"a": 1}, {"b": 2}]')
        b.json_to_html(src, self.path("a.html"))
        html = self.read("a.html")
        self.assertIn("<th>a</th><th>b</th>", html)

    def test_json_to_html_rejects_scalars(self):
        with self.assertRaises(ConversionFailedError):
            b.json_to_html(self.write("a.json", "[1, 2]"), self.path("a.html"))

    def test_html_to_csv_takes_first_table_only(self):
        page = ("<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>"
                "<table><tr><td>other</td></tr></table>")
        b.html_to_csv(self.write("a.html", page), self.path("a.csv"))
        self.assertEqual(self.read("a.csv"), "a,b\n1,2\n")

    def test_html_to_csv_ignores_nested_tables(self):
        page = "<table><tr><td>x<table><tr><td>inner</td></tr></table></td><td>y</td></tr></table>"
        b.html_to_csv(self.write("a.html", page), self.path("a.csv"))
        self.assertNotIn("inner", self.read("a.csv"))

    def test_html_without_tables(self):
        with self.assertRaises(ConversionFailedError):
            b.html_to_csv(self.write("a.html", "<p>нет</p>"), self.path("a.csv"))


class DocxCsvTest(TempDirCase):
    def test_first_table_is_extracted(self):
        src = self.write("a.docx", docx_bytes("текст", table=[["a", "b"], ["1", "2"]]))
        b.docx_to_csv(src, self.path("a.csv"))
        self.assertEqual(self.read("a.csv"), "a,b\n1,2\n")

    def test_document_without_tables(self):
        with self.assertRaises(ConversionFailedError):
            b.docx_to_csv(self.write("a.docx", docx_bytes("только текст")), self.path("a.csv"))

    def test_garbage_is_reported(self):
        with self.assertRaises(ConversionFailedError):
            b.docx_to_csv(self.write("a.docx", b"not a zip"), self.path("a.csv"))


if __name__ == "__main__":
    unittest.main()
