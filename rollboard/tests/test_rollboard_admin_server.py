import unittest
import tempfile
from pathlib import Path

from rollboard.service import rollboard_admin_server
from rollboard.tests.test_print_station import write_job


class RollboardAdminServerTest(unittest.TestCase):
    def test_make_rollboard_url_uses_protected_data_path(self):
        self.assertEqual(
            rollboard_admin_server.make_rollboard_url("demo"),
            "/rollboard/resolver?data-source=/rollboard/data/demo",
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
            self.assertEqual(summary["rollboard_url"], "/rollboard/resolver?data-source=/rollboard/data/demo")

    def test_print_status_reports_pause_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp)
            write_job(spool / "pending" / "job-1", "queued")
            settings = rollboard_admin_server.Settings(print_spool_root=spool)

            status = rollboard_admin_server.print_status(settings, "station-a")

            self.assertFalse(status["paused"])
            self.assertTrue(status["station"]["allowed"])
            self.assertEqual(status["counts"]["pending"], 1)

    def test_print_claim_respects_station_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp)
            write_job(spool / "pending" / "job-1", "queued")
            settings = rollboard_admin_server.Settings(print_spool_root=spool)

            claimed = rollboard_admin_server.print_claim(settings, "station-a")

            self.assertEqual(claimed["job"]["id"], "job-1")
            self.assertEqual(claimed["job"]["state"], "printing")

            blocked = rollboard_admin_server.print_claim(settings, "station-b")
            self.assertIsNone(blocked["job"])
            self.assertEqual(blocked["blocked_by"], "station-a")

    def test_print_mark_done_uses_claiming_station(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp)
            write_job(spool / "pending" / "job-1", "queued")
            settings = rollboard_admin_server.Settings(print_spool_root=spool)
            rollboard_admin_server.print_claim(settings, "station-a")

            done = rollboard_admin_server.print_mark_done(settings, "job-1", "station-a")

            self.assertEqual(done["job"]["state"], "done")
            self.assertTrue((spool / "done" / "job-1").exists())


if __name__ == "__main__":
    unittest.main()
