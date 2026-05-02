import unittest
import tempfile
from pathlib import Path

from rollboard.service import rollboard_admin_server


class RollboardAdminServerTest(unittest.TestCase):
    def test_make_rollboard_url_uses_protected_data_path(self):
        self.assertEqual(
            rollboard_admin_server.make_rollboard_url("demo"),
            "/rollboard/?component=resolver&data-source=/rollboard/data/demo",
        )

    def test_resolve_output_slug_defaults_to_contest_id(self):
        self.assertEqual(rollboard_admin_server.resolve_output_slug("demo", None), "demo")
        self.assertEqual(rollboard_admin_server.resolve_output_slug("demo", "current"), "current")

    def test_contest_summary_marks_generated_data(self):
        with self.subTest("generated"):
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "demo"
                output_dir.mkdir()
                for name in ("config.json", "team.json", "run.json"):
                    (output_dir / name).write_text("{}")

                summary = rollboard_admin_server.contest_summary(
                    {
                        "id": "demo",
                        "cid": 2,
                        "shortname": "demo",
                        "formal_name": "Demo Contest",
                        "start_time": "2026-05-02T12:00:00+08:00",
                        "end_time": "2026-05-02T17:00:00+08:00",
                    },
                    output_dir,
                )
            self.assertTrue(summary["generated"])
            self.assertEqual(summary["rollboard_url"], "/rollboard/?component=resolver&data-source=/rollboard/data/demo")


if __name__ == "__main__":
    unittest.main()
