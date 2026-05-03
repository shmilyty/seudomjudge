import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class PrintSpoolScriptTest(unittest.TestCase):
    def test_created_jobs_are_group_writable_for_print_station(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is required for the spool script test")
        repo = Path(__file__).parents[2]
        script = repo / "deploy" / "seu-print-spool.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.cpp"
            source.write_text("int main() { return 0; }\n", encoding="utf-8")
            env = os.environ.copy()
            env["SEU_DOMJUDGE_PRINT_SPOOL"] = str(root / "spool")

            subprocess.run(
                [bash, str(script), str(source), "main.cpp", "cpp", "dino", "Team Dino", "6", "lab"],
                check=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            [job_dir] = list((root / "spool" / "pending").iterdir())
            job_mode = job_dir.stat().st_mode
            self.assertTrue(job_mode & stat.S_ISGID)
            self.assertTrue(job_mode & stat.S_IWGRP)
            for name in ("metadata.txt", "print.txt", "source"):
                file_mode = (job_dir / name).stat().st_mode
                self.assertTrue(file_mode & stat.S_IRGRP, name)
                self.assertTrue(file_mode & stat.S_IWGRP, name)

    def test_parent_directory_chmod_failure_does_not_block_queueing(self):
        bash = shutil.which("bash")
        real_chmod = shutil.which("chmod")
        if bash is None or real_chmod is None:
            self.skipTest("bash and chmod are required for the spool script test")
        repo = Path(__file__).parents[2]
        script = repo / "deploy" / "seu-print-spool.sh"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "fakebin"
            fakebin.mkdir()
            fake_chmod = fakebin / "chmod"
            fake_chmod.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        'for arg in "$@"; do',
                        '  case "$arg" in */pending|*/.tmp) echo "chmod denied" >&2; exit 1;; esac',
                        "done",
                        f'exec "{real_chmod}" "$@"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            fake_chmod.chmod(0o755)
            source = root / "main.cpp"
            source.write_text("int main() { return 0; }\n", encoding="utf-8")
            env = os.environ.copy()
            env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
            env["SEU_DOMJUDGE_PRINT_SPOOL"] = str(root / "spool")

            subprocess.run(
                [bash, str(script), str(source), "main.cpp", "cpp", "dino", "Team Dino", "6", "lab"],
                check=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(len(list((root / "spool" / "pending").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
