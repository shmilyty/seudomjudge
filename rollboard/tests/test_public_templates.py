import unittest
from pathlib import Path


class PublicTemplateTest(unittest.TestCase):
    def test_jury_dashboard_links_print_station(self):
        template = Path(__file__).parents[2] / "webapp" / "templates" / "jury" / "index.html.twig"
        html = template.read_text(encoding="utf-8")

        self.assertIn('/print-station/', html)
        self.assertIn('Print Station', html)

    def test_jury_navbar_links_print_station(self):
        template = Path(__file__).parents[2] / "webapp" / "templates" / "jury" / "menu.html.twig"
        html = template.read_text(encoding="utf-8")

        self.assertIn('/print-station/', html)
        self.assertIn('print station', html)


if __name__ == "__main__":
    unittest.main()
