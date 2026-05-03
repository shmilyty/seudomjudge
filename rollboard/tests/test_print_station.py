import tempfile
import time
import unittest
from pathlib import Path

from rollboard.service.print_station import InvalidJobId, PrintQueueStore, StationConflict


def write_job(path: Path, label: str) -> None:
    path.mkdir(parents=True)
    (path / "metadata.txt").write_text(
        "\n".join(
            [
                f"job_id={path.name}",
                f"teamname=Team {label}",
                "username=contestant",
                "language=cpp",
                "original=main.cpp",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (path / "print.txt").write_text(f"// {label}\nint main() {{ return 0; }}\n", encoding="utf-8")
    (path / "source").write_text(f"// source {label}\n", encoding="utf-8")


class PrintQueueStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.spool = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_claim_moves_oldest_pending_job_to_printing(self):
        first = self.spool / "pending" / "job-1"
        second = self.spool / "pending" / "job-2"
        write_job(first, "older")
        time.sleep(0.01)
        write_job(second, "newer")

        store = PrintQueueStore(self.spool)
        job = store.claim_next("station-a")

        self.assertIsNotNone(job)
        self.assertEqual(job["id"], "job-1")
        self.assertFalse(first.exists())
        self.assertTrue((self.spool / "printing" / "job-1").exists())

    def test_pause_blocks_claiming_but_keeps_pending_jobs(self):
        write_job(self.spool / "pending" / "job-1", "queued")

        store = PrintQueueStore(self.spool)
        store.set_paused(True)

        self.assertIsNone(store.claim_next("station-a"))
        self.assertTrue((self.spool / "pending" / "job-1").exists())

    def test_invalid_job_id_is_rejected(self):
        store = PrintQueueStore(self.spool)

        with self.assertRaises(InvalidJobId):
            store.mark_done("../job-1", "station-a")

    def test_only_claiming_station_can_mark_done(self):
        write_job(self.spool / "pending" / "job-1", "queued")
        store = PrintQueueStore(self.spool)
        store.claim_next("station-a")

        with self.assertRaises(StationConflict):
            store.mark_done("job-1", "station-b")

        self.assertTrue((self.spool / "printing" / "job-1").exists())

    def test_requeue_moves_failed_job_back_to_pending(self):
        write_job(self.spool / "pending" / "job-1", "queued")
        store = PrintQueueStore(self.spool)
        store.claim_next("station-a")
        store.mark_failed("job-1", "station-a", "paper jam")

        job = store.requeue("job-1")

        self.assertEqual(job["state"], "pending")
        self.assertTrue((self.spool / "pending" / "job-1").exists())
        self.assertFalse((self.spool / "failed" / "job-1").exists())

    def test_listing_reports_counts_and_recent_done_jobs(self):
        write_job(self.spool / "pending" / "job-1", "queued")
        write_job(self.spool / "pending" / "job-2", "done soon")
        store = PrintQueueStore(self.spool)
        store.claim_next("station-a")
        store.mark_done("job-1", "station-a")

        listing = store.list_jobs()

        self.assertEqual(listing["counts"]["pending"], 1)
        self.assertEqual(listing["counts"]["done"], 1)
        self.assertEqual(listing["done"][0]["id"], "job-1")


if __name__ == "__main__":
    unittest.main()
