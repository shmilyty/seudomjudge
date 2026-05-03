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

    def test_print_station_uses_separate_basic_auth_file(self):
        config = Path(__file__).parents[1] / "nginx" / "rollboard.locations.conf"
        text = config.read_text(encoding="utf-8")

        self.assertIn("auth_basic_user_file /mnt/domjudge/rollboard/secrets/print-station.htpasswd;", text)

    def test_rollboard_admin_service_can_write_www_data_jobs(self):
        service = Path(__file__).parents[1] / "systemd" / "rollboard-admin.service"
        text = service.read_text(encoding="utf-8")

        self.assertIn("SupplementaryGroups=www-data", text)


if __name__ == "__main__":
    unittest.main()
