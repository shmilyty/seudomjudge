import json
import tempfile
import unittest
from pathlib import Path

from rollboard.tools import rollboard_build


class RollboardBuildTest(unittest.TestCase):
    def test_parse_domjudge_duration(self):
        self.assertEqual(rollboard_build.parse_domjudge_duration("1:02:03.456"), 3723)
        self.assertEqual(rollboard_build.parse_domjudge_duration("2902:27:12.215"), 10448832)
        self.assertEqual(rollboard_build.parse_domjudge_duration(None), 0)

    def test_convert_domjudge_api_to_xcpcio_data(self):
        payload = sample_domjudge_payload()

        data = rollboard_build.convert_domjudge_payload(payload)

        self.assertEqual(data["contest"]["contest_name"], "SEU Test Contest")
        self.assertEqual(data["contest"]["penalty"], 1200)
        self.assertEqual(data["contest"]["frozen_time"], 3600)
        self.assertEqual(
            data["contest"]["problems"],
            [
                {
                    "id": "A",
                    "label": "A",
                    "name": "Apple",
                    "balloon_color": {"background_color": "#ff0000"},
                },
                {
                    "id": "B",
                    "label": "B",
                    "name": "Banana",
                    "balloon_color": {"background_color": "#ffff00"},
                },
            ],
        )
        self.assertTrue(data["contest"]["options"]["enable_organization"])
        self.assertEqual(data["teams"], [
            {
                "id": "t1",
                "name": "Alpha",
                "organization_id": "seu",
                "group": ["official"],
                "icpc_id": "alpha-icpc",
            },
            {
                "id": "t2",
                "name": "Beta",
                "organization_id": "seu",
                "group": ["unofficial"],
            },
        ])
        self.assertEqual(data["submissions"], [
            {"id": "s1", "team_id": "t1", "problem_id": "A", "timestamp": 600, "status": "correct"},
            {"id": "s2", "team_id": "t1", "problem_id": "B", "timestamp": 16200, "status": "incorrect"},
            {"id": "s3", "team_id": "t2", "problem_id": "A", "timestamp": 16800, "status": "correct"},
            {"id": "s4", "team_id": "t2", "problem_id": "B", "timestamp": 17000, "status": "pending"},
        ])

    def test_write_board_files(self):
        payload = sample_domjudge_payload()
        data = rollboard_build.convert_domjudge_payload(payload)

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "contest"
            rollboard_build.write_board_files(data, output_dir)

            self.assertEqual(
                sorted(p.name for p in output_dir.iterdir()),
                ["config.json", "run.json", "team.json"],
            )
            self.assertEqual(json.loads((output_dir / "config.json").read_text())["contest_name"], "SEU Test Contest")
            self.assertEqual(json.loads((output_dir / "team.json").read_text())[0]["id"], "t1")
            self.assertEqual(json.loads((output_dir / "run.json").read_text())[0]["status"], "correct")

    def test_problem_with_empty_domjudge_id_uses_label(self):
        payload = sample_domjudge_payload()
        payload["problems"].append({
            "id": "",
            "label": "hello",
            "short_name": "hello",
            "name": "Hello World",
            "ordinal": 2,
            "rgb": "#ff00ff",
        })
        payload["submissions"].append({
            "id": "s7",
            "team_id": "t1",
            "problem_id": "",
            "contest_time": "4:50:00.000",
        })
        payload["judgements"].append({
            "id": "j7",
            "submission_id": "s7",
            "judgement_type_id": "AC",
            "valid": True,
        })

        data = rollboard_build.convert_domjudge_payload(payload)

        self.assertIn({"id": "hello", "label": "hello", "name": "Hello World", "balloon_color": {"background_color": "#ff00ff"}}, data["contest"]["problems"])
        self.assertIn({"id": "s7", "team_id": "t1", "problem_id": "hello", "timestamp": 17400, "status": "correct"}, data["submissions"])


def sample_domjudge_payload():
    return {
        "contest": {
            "id": "demo",
            "formal_name": "SEU Test Contest",
            "name": "SEU Test",
            "start_time": "2026-05-02T12:00:00+08:00",
            "end_time": "2026-05-02T17:00:00+08:00",
            "duration": "5:00:00.000",
            "scoreboard_freeze_duration": "1:00:00.000",
            "penalty_time": 20,
        },
        "problems": [
            {"id": "A", "label": "A", "name": "Apple", "ordinal": 0, "rgb": "#ff0000"},
            {"id": "B", "label": "B", "name": "Banana", "ordinal": 1, "rgb": "#ffff00"},
        ],
        "teams": [
            {
                "id": "t1",
                "name": "Alpha",
                "display_name": "Alpha",
                "organization_id": "seu",
                "group_ids": ["official"],
                "hidden": False,
                "icpc_id": "alpha-icpc",
            },
            {
                "id": "t2",
                "name": "Beta",
                "display_name": "Beta",
                "organization_id": "seu",
                "group_ids": ["observers"],
                "hidden": False,
            },
            {
                "id": "hidden",
                "name": "Hidden",
                "organization_id": "seu",
                "group_ids": ["official"],
                "hidden": True,
            },
        ],
        "groups": [
            {"id": "official", "name": "Participants", "hidden": False},
            {"id": "observers", "name": "Observers", "hidden": False},
        ],
        "organizations": [
            {"id": "seu", "name": "SEU", "formal_name": "Southeast University"},
        ],
        "submissions": [
            {"id": "s1", "team_id": "t1", "problem_id": "A", "contest_time": "0:10:00.000"},
            {"id": "s2", "team_id": "t1", "problem_id": "B", "contest_time": "4:30:00.000"},
            {"id": "s3", "team_id": "t2", "problem_id": "A", "contest_time": "4:40:00.000"},
            {"id": "s4", "team_id": "t2", "problem_id": "B", "contest_time": "4:43:20.000"},
            {"id": "s5", "team_id": "hidden", "problem_id": "A", "contest_time": "0:11:00.000"},
            {"id": "s6", "team_id": "t1", "problem_id": "A", "contest_time": "0:12:00.000"},
        ],
        "judgements": [
            {"id": "j1", "submission_id": "s1", "judgement_type_id": "AC", "valid": True},
            {"id": "j2", "submission_id": "s2", "judgement_type_id": "WA", "valid": True},
            {"id": "j3", "submission_id": "s3", "judgement_type_id": "AC", "valid": True},
            {"id": "j4", "submission_id": "s5", "judgement_type_id": "AC", "valid": True},
            {"id": "j5", "submission_id": "s6", "judgement_type_id": "CE", "valid": True},
        ],
    }


if __name__ == "__main__":
    unittest.main()
