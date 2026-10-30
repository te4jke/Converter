import unittest

from core import manager


class FindRouteTest(unittest.TestCase):
    def test_direct_edge_is_a_single_hop(self):
        self.assertEqual(manager.find_route("txt", "pdf"), ["txt", "pdf"])

    def test_chain_through_intermediate_format(self):
        self.assertEqual(manager.find_route("docx", "pdf"), ["docx", "txt", "pdf"])

    def test_bridge_connects_documents_and_tables(self):
        self.assertEqual(manager.find_route("txt", "json"), ["txt", "json"])
        self.assertEqual(manager.find_route("txt", "xlsx"), ["txt", "csv", "xlsx"])
        self.assertEqual(manager.find_route("docx", "json"), ["docx", "csv", "json"])

    def test_same_format_has_no_route(self):
        self.assertIsNone(manager.find_route("pdf", "pdf"))

    def test_unknown_format_has_no_route(self):
        self.assertIsNone(manager.find_route("txt", "mp3"))

    def test_direct_edge_wins_over_cheaper_looking_chain(self):
        for src, dst in manager.CONVERTERS:
            self.assertEqual(manager.find_route(src, dst), [src, dst])

    def test_image_pdf_is_never_an_intermediate_step(self):
        # PNG -> PDF -> TXT дал бы пустой результат: в таком PDF нет текста
        for src in manager.IMAGE_SOURCES:
            for dst, route in manager.get_routes().get(src, {}).items():
                self.assertNotIn("pdf", route[1:-1], (src, dst, route))

    def test_every_route_uses_only_registered_converters(self):
        for src, dsts in manager.get_routes().items():
            for dst, route in dsts.items():
                self.assertEqual((route[0], route[-1]), (src, dst))
                for pair in zip(route, route[1:]):
                    self.assertIn(pair, manager.CONVERTERS)


class LossyRouteTest(unittest.TestCase):
    def test_direct_route_is_not_lossy(self):
        self.assertFalse(manager.is_lossy_route(["txt", "pdf"]))

    def test_chain_through_txt_is_lossy(self):
        self.assertTrue(manager.is_lossy_route(["docx", "txt", "pdf"]))

    def test_chain_through_lossless_format_is_not_lossy(self):
        self.assertFalse(manager.is_lossy_route(["a", "html", "b"]))


class TargetsTest(unittest.TestCase):
    def test_targets_are_sorted_and_exclude_source(self):
        for src, dsts in manager.get_targets().items():
            self.assertEqual(dsts, sorted(dsts))
            self.assertNotIn(src, dsts)

    def test_text_formats_reach_six_targets(self):
        targets = manager.get_targets()
        for fmt in ("txt", "docx", "html", "pdf", "csv", "json", "xlsx"):
            self.assertGreaterEqual(len(targets[fmt]), 6, fmt)

    def test_supported_list_mentions_transfers(self):
        lines = manager.get_supported()
        self.assertIn("DOCX -> PDF  (через TXT)", lines)


if __name__ == "__main__":
    unittest.main()
