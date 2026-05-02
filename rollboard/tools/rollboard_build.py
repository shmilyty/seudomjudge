#!/usr/bin/env python3
"""Build XCPCIO board data from the DOMjudge CLICS API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib import error, request


DEFAULT_API_BASE_URL = "http://127.0.0.1:12345/api/v4"
DEFAULT_DATA_ROOT = "/mnt/domjudge/rollboard/www/data"
SKIPPED_JUDGEMENT_TYPES = {"CE", "COMPILATION_ERROR", "COMPILE_ERROR"}
ACCEPTED_JUDGEMENT_TYPES = {"AC", "OK", "CORRECT", "ACCEPTED"}
PENDING_JUDGEMENT_TYPES = {"PD", "PENDING", "WAITING", "JUDGING", "RUNNING"}
UNOFFICIAL_GROUP_WORDS = ("observer", "unofficial", "guest", "practice")


def parse_domjudge_duration(value: Any) -> int:
    """Parse DOMjudge CLICS duration strings into whole seconds."""
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if not text:
        return 0

    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")

    if text.startswith("P"):
        raise ValueError(f"ISO-8601 durations are not supported: {value!r}")

    parts = text.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return sign * (int(hours) * 3600 + int(minutes) * 60 + int(float(seconds)))
    if len(parts) == 2:
        minutes, seconds = parts
        return sign * (int(minutes) * 60 + int(float(seconds)))
    if len(parts) == 1:
        return sign * int(float(parts[0]))

    raise ValueError(f"Unsupported DOMjudge duration: {value!r}")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    slug = slug.strip(".-")
    if not slug:
        raise ValueError("output slug is empty after sanitization")
    return slug


def convert_domjudge_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    contest = dict(payload["contest"])
    problems = sorted(payload.get("problems", []), key=lambda p: (p.get("ordinal", 0), str(p.get("label", ""))))
    groups = {str(g.get("id")): g for g in payload.get("groups", [])}
    organizations = payload.get("organizations", [])
    teams = payload.get("teams", [])
    submissions = payload.get("submissions", [])
    judgements = payload.get("judgements", [])

    problem_aliases = build_problem_aliases(problems)
    visible_problem_ids = {problem_public_id(problem) for problem in problems if problem_public_id(problem)}
    visible_team_ids = {
        str(team.get("id"))
        for team in teams
        if str(team.get("id", "")) and not team.get("hidden", False)
    }

    board_data = {
        "contest": build_contest(contest, problems, organizations),
        "teams": build_teams(teams, groups),
        "submissions": build_submissions(submissions, judgements, visible_team_ids, visible_problem_ids, contest, problem_aliases),
    }
    return board_data


def build_contest(contest: Mapping[str, Any], problems: Iterable[Mapping[str, Any]], organizations: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "contest_name": contest.get("formal_name") or contest.get("name") or contest.get("shortname") or contest.get("id", "Contest"),
        "start_time": contest.get("start_time"),
        "end_time": contest.get("end_time"),
        "penalty": int(contest.get("penalty_time") or 20) * 60,
        "problems": [convert_problem(problem) for problem in problems],
        "status_time_display": {
            "correct": True,
            "incorrect": True,
            "pending": True,
        },
        "options": {
            "enable_organization": True,
            "calculation_of_penalty": "in_minutes",
            "submission_timestamp_unit": "second",
        },
        "group": {
            "official": "Official",
            "unofficial": "Unofficial",
        },
        "organizations": [convert_organization(org) for org in organizations],
    }

    frozen_time = parse_domjudge_duration(contest.get("scoreboard_freeze_duration"))
    if frozen_time > 0:
        result["frozen_time"] = frozen_time

    return result


def convert_problem(problem: Mapping[str, Any]) -> Dict[str, Any]:
    result = {
        "id": problem_public_id(problem),
        "label": str(problem.get("label") or problem.get("short_name") or problem.get("id")),
    }
    if problem.get("name"):
        result["name"] = problem.get("name")
    color = problem.get("rgb")
    if color:
        result["balloon_color"] = {"background_color": color}
    return result


def problem_public_id(problem: Mapping[str, Any]) -> str:
    for key in ("id", "label", "short_name", "probid"):
        value = problem.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def build_problem_aliases(problems: Iterable[Mapping[str, Any]]) -> Dict[str, str]:
    aliases = {}
    for problem in problems:
        public_id = problem_public_id(problem)
        if not public_id:
            continue
        for key in ("id", "label", "short_name", "probid"):
            value = problem.get(key)
            if value is not None:
                aliases[str(value)] = public_id
    return aliases


def convert_organization(org: Mapping[str, Any]) -> Dict[str, Any]:
    result = {
        "id": str(org.get("id")),
        "name": org.get("formal_name") or org.get("name") or org.get("shortname") or str(org.get("id")),
    }
    if org.get("icpc_id"):
        result["icpc_id"] = org.get("icpc_id")
    return result


def build_teams(teams: Iterable[Mapping[str, Any]], groups: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for team in teams:
        if team.get("hidden", False):
            continue
        team_id = str(team.get("id", ""))
        if not team_id:
            continue
        converted = {
            "id": team_id,
            "name": team.get("display_name") or team.get("name") or team_id,
            "group": classify_team_groups(team.get("group_ids") or [], groups),
        }
        if team.get("organization_id"):
            converted["organization_id"] = str(team.get("organization_id"))
        if team.get("icpc_id"):
            converted["icpc_id"] = str(team.get("icpc_id"))
        if team.get("location"):
            converted["location"] = str(team.get("location"))
        result.append(converted)

    result.sort(key=lambda team: team["id"])
    return result


def classify_team_groups(group_ids: Iterable[Any], groups: Mapping[str, Mapping[str, Any]]) -> List[str]:
    names = []
    for group_id in group_ids:
        group = groups.get(str(group_id), {})
        names.append(str(group.get("name") or group_id).lower())

    if any(any(word in name for word in UNOFFICIAL_GROUP_WORDS) for name in names):
        return ["unofficial"]
    return ["official"]


def build_submissions(
    submissions: Iterable[Mapping[str, Any]],
    judgements: Iterable[Mapping[str, Any]],
    visible_team_ids: set[str],
    visible_problem_ids: set[str],
    contest: Mapping[str, Any],
    problem_aliases: Mapping[str, str],
) -> List[Dict[str, Any]]:
    judgement_by_submission = latest_valid_judgements(judgements)
    contest_duration = parse_domjudge_duration(contest.get("duration"))
    result = []

    for submission in submissions:
        submission_id = str(submission.get("id", ""))
        team_id = str(submission.get("team_id", ""))
        raw_problem_id = str(submission.get("problem_id", ""))
        problem_id = problem_aliases.get(raw_problem_id, raw_problem_id)
        if not submission_id or team_id not in visible_team_ids or problem_id not in visible_problem_ids:
            continue

        timestamp = parse_domjudge_duration(submission.get("contest_time"))
        if contest_duration and timestamp > contest_duration:
            continue

        judgement_type = judgement_by_submission.get(submission_id)
        status = map_judgement_type(judgement_type)
        if status is None:
            continue

        result.append({
            "id": submission_id,
            "team_id": team_id,
            "problem_id": problem_id,
            "timestamp": timestamp,
            "status": status,
        })

    result.sort(key=lambda item: (item["timestamp"], item["id"]))
    return result


def latest_valid_judgements(judgements: Iterable[Mapping[str, Any]]) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}
    for judgement in judgements:
        if judgement.get("valid") is False:
            continue
        submission_id = str(judgement.get("submission_id", ""))
        if not submission_id:
            continue
        judgement_type = judgement.get("judgement_type_id")
        result[submission_id] = str(judgement_type).upper() if judgement_type is not None else None
    return result


def map_judgement_type(judgement_type: Optional[str]) -> Optional[str]:
    if judgement_type is None:
        return "pending"
    value = judgement_type.upper().replace(" ", "_").replace("-", "_")
    if value in ACCEPTED_JUDGEMENT_TYPES:
        return "correct"
    if value in PENDING_JUDGEMENT_TYPES:
        return "pending"
    if value in SKIPPED_JUDGEMENT_TYPES:
        return None
    return "incorrect"


def write_board_files(data: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "config.json", data["contest"])
    write_json(output_dir / "team.json", data["teams"])
    write_json(output_dir / "run.json", data["submissions"])


def write_json(path: Path, value: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


class DomjudgeClient:
    def __init__(self, base_url: str, username: Optional[str], password: Optional[str], token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token = token

    def fetch_json(self, endpoint: str) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req = request.Request(url)
        req.add_header("Accept", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        elif self.username is not None and self.password is not None:
            import base64
            raw = f"{self.username}:{self.password}".encode("utf-8")
            req.add_header("Authorization", "Basic " + base64.b64encode(raw).decode("ascii"))

        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DOMjudge API request failed: {endpoint} HTTP {exc.code}: {body[:200]}") from exc


def load_domjudge_payload(client: DomjudgeClient, contest_id: str) -> Dict[str, Any]:
    prefix = f"contests/{contest_id}"
    return {
        "contest": client.fetch_json(prefix),
        "problems": client.fetch_json(f"{prefix}/problems"),
        "teams": client.fetch_json(f"{prefix}/teams"),
        "groups": client.fetch_json(f"{prefix}/groups"),
        "organizations": client.fetch_json(f"{prefix}/organizations"),
        "submissions": client.fetch_json(f"{prefix}/submissions"),
        "judgements": client.fetch_json(f"{prefix}/judgements"),
    }


def read_secret_file(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8").strip()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build XCPCIO rollboard JSON files from DOMjudge.")
    parser.add_argument("--contest-id", required=True, help="DOMjudge contest external id, for example demo")
    parser.add_argument("--output", default=None, help="Output slug or absolute directory. Defaults to contest id.")
    parser.add_argument("--data-root", default=os.environ.get("ROLLBOARD_DATA_ROOT", DEFAULT_DATA_ROOT))
    parser.add_argument("--base-url", default=os.environ.get("DOMJUDGE_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--username", default=os.environ.get("DOMJUDGE_API_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("DOMJUDGE_API_PASSWORD"))
    parser.add_argument("--password-file", default=os.environ.get("DOMJUDGE_API_PASSWORD_FILE"))
    parser.add_argument("--token", default=os.environ.get("DOMJUDGE_API_TOKEN"))
    return parser


def resolve_output_dir(data_root: str, contest_id: str, output: Optional[str]) -> Path:
    if output and Path(output).is_absolute():
        return Path(output)
    slug = safe_slug(output or contest_id)
    return Path(data_root) / slug


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    password = args.password or read_secret_file(args.password_file)
    client = DomjudgeClient(args.base_url, args.username, password, args.token)
    payload = load_domjudge_payload(client, args.contest_id)
    data = convert_domjudge_payload(payload)
    output_dir = resolve_output_dir(args.data_root, args.contest_id, args.output)
    write_board_files(data, output_dir)
    print(json.dumps({
        "contest_id": args.contest_id,
        "output_dir": str(output_dir),
        "teams": len(data["teams"]),
        "problems": len(data["contest"]["problems"]),
        "submissions": len(data["submissions"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
