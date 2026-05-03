#!/usr/bin/env python3
"""Small localhost-only JSON API for the rollboard admin page."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs, urlparse

from rollboard.service.print_station import (
    InvalidJobId,
    JobNotFound,
    PrintQueueError,
    PrintQueueStore,
    StationConflict,
)
from rollboard.tools.rollboard_build import DomjudgeClient, read_secret_file, safe_slug


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18090
DEFAULT_DATA_ROOT = "/mnt/domjudge/rollboard/www/data"
DEFAULT_BUILDER_PATH = "/mnt/domjudge/rollboard/rollboard/tools/rollboard_build.py"
DEFAULT_API_BASE_URL = "http://127.0.0.1:12345/api/v4"
DEFAULT_PRINT_SPOOL_ROOT = "/mnt/domjudge/domjudge-live/domserver/var/print-spool"
PRINT_JOB_ROUTE_RE = re.compile(r"^/print-station/api/jobs/([^/]+)/(print|done|fail|requeue)$")


@dataclass
class Settings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    data_root: Path = Path(DEFAULT_DATA_ROOT)
    builder_path: Path = Path(DEFAULT_BUILDER_PATH)
    api_base_url: str = DEFAULT_API_BASE_URL
    api_username: str = "admin"
    api_password_file: Optional[str] = None
    api_token: Optional[str] = None
    print_spool_root: Path = Path(DEFAULT_PRINT_SPOOL_ROOT)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.environ.get("ROLLBOARD_ADMIN_HOST", DEFAULT_HOST),
            port=int(os.environ.get("ROLLBOARD_ADMIN_PORT", DEFAULT_PORT)),
            data_root=Path(os.environ.get("ROLLBOARD_DATA_ROOT", DEFAULT_DATA_ROOT)),
            builder_path=Path(os.environ.get("ROLLBOARD_BUILDER", DEFAULT_BUILDER_PATH)),
            api_base_url=os.environ.get("DOMJUDGE_API_BASE_URL", DEFAULT_API_BASE_URL),
            api_username=os.environ.get("DOMJUDGE_API_USERNAME", "admin"),
            api_password_file=os.environ.get("DOMJUDGE_API_PASSWORD_FILE"),
            api_token=os.environ.get("DOMJUDGE_API_TOKEN"),
            print_spool_root=Path(os.environ.get("PRINT_STATION_SPOOL_ROOT", DEFAULT_PRINT_SPOOL_ROOT)),
        )


def make_rollboard_url(slug: str) -> str:
    return f"/rollboard/resolver?data-source=/rollboard/data/{safe_slug(slug)}"


def resolve_output_slug(contest_id: str, output: Optional[str]) -> str:
    return safe_slug(output or contest_id)


def contest_summary(contest: Mapping[str, Any], output_dir: Path) -> Dict[str, Any]:
    slug = output_dir.name
    return {
        "id": contest.get("id"),
        "cid": contest.get("cid"),
        "shortname": contest.get("shortname"),
        "name": contest.get("formal_name") or contest.get("name") or contest.get("shortname") or contest.get("id"),
        "start_time": contest.get("start_time"),
        "end_time": contest.get("end_time"),
        "generated": all((output_dir / filename).exists() for filename in ("config.json", "team.json", "run.json")),
        "rollboard_url": make_rollboard_url(slug),
    }


def make_client(settings: Settings) -> DomjudgeClient:
    password = read_secret_file(settings.api_password_file)
    return DomjudgeClient(settings.api_base_url, settings.api_username, password, settings.api_token)


def list_contests(settings: Settings) -> List[Dict[str, Any]]:
    contests = make_client(settings).fetch_json("contests")
    summaries = []
    for contest in contests:
        contest_id = str(contest.get("id"))
        output_dir = settings.data_root / safe_slug(contest_id)
        summaries.append(contest_summary(contest, output_dir))
    summaries.sort(key=lambda item: (item.get("start_time") or "", item.get("id") or ""), reverse=True)
    return summaries


def build_contest(settings: Settings, contest_id: str, output: Optional[str]) -> Dict[str, Any]:
    slug = resolve_output_slug(contest_id, output)
    env = os.environ.copy()
    env.update({
        "ROLLBOARD_DATA_ROOT": str(settings.data_root),
        "DOMJUDGE_API_BASE_URL": settings.api_base_url,
        "DOMJUDGE_API_USERNAME": settings.api_username,
    })
    if settings.api_password_file:
        env["DOMJUDGE_API_PASSWORD_FILE"] = settings.api_password_file
    if settings.api_token:
        env["DOMJUDGE_API_TOKEN"] = settings.api_token

    proc = subprocess.run(
        [
            sys.executable,
            str(settings.builder_path),
            "--contest-id",
            contest_id,
            "--output",
            slug,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "rollboard build failed").strip())

    build_info = json.loads(proc.stdout.strip().splitlines()[-1])
    return {
        "contest_id": contest_id,
        "output": slug,
        "rollboard_url": make_rollboard_url(slug),
        "build": build_info,
    }


def print_store(settings: Settings) -> PrintQueueStore:
    return PrintQueueStore(settings.print_spool_root)


def print_status(settings: Settings, station_id: Optional[str] = None) -> Dict[str, Any]:
    return print_store(settings).status(station_id)


def print_jobs(settings: Settings) -> Dict[str, Any]:
    return print_store(settings).list_jobs()


def print_pause(settings: Settings) -> Dict[str, Any]:
    store = print_store(settings)
    store.set_paused(True)
    return store.status()


def print_resume(settings: Settings) -> Dict[str, Any]:
    store = print_store(settings)
    store.set_paused(False)
    return store.status()


def print_claim(settings: Settings, station_id: str) -> Dict[str, Any]:
    store = print_store(settings)
    station = store.heartbeat(station_id)
    if not station["allowed"]:
        return {"job": None, "blocked_by": station["active_station"], "paused": store.is_paused()}
    job = store.claim_next(station_id)
    return {"job": job, "blocked_by": "", "paused": store.is_paused()}


def print_mark_done(settings: Settings, job_id: str, station_id: str) -> Dict[str, Any]:
    return {"job": print_store(settings).mark_done(job_id, station_id)}


def print_mark_failed(settings: Settings, job_id: str, station_id: str, reason: str = "") -> Dict[str, Any]:
    return {"job": print_store(settings).mark_failed(job_id, station_id, reason)}


def print_requeue(settings: Settings, job_id: str) -> Dict[str, Any]:
    return {"job": print_store(settings).requeue(job_id)}


def print_text(settings: Settings, job_id: str) -> str:
    return print_store(settings).printable_text(job_id)


class RollboardAdminHandler(BaseHTTPRequestHandler):
    server_version = "SEURollboardAdmin/1.0"

    def do_GET(self) -> None:
        route = normalized_path(self.path)
        if route == "/api/health":
            self.write_json({"ok": True})
            return
        if route == "/api/contests":
            self.handle_action(lambda: {"contests": list_contests(self.server.settings)})
            return
        if route == "/print-station/api/status":
            query = parse_qs(urlparse(self.path).query)
            station_id = first_query_value(query, "station_id")
            self.handle_print_action(lambda: print_status(self.server.settings, station_id))
            return
        if route == "/print-station/api/jobs":
            self.handle_print_action(lambda: print_jobs(self.server.settings))
            return
        match = PRINT_JOB_ROUTE_RE.match(route)
        if match and match.group(2) == "print":
            self.handle_print_text(match.group(1))
            return
        self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        route = normalized_path(self.path)
        if route == "/api/build":
            body = self.read_json_body()
            contest_id = str(body.get("contest_id", "")).strip()
            if not contest_id:
                self.write_json({"error": "contest_id is required"}, HTTPStatus.BAD_REQUEST)
                return
            output = body.get("output")
            self.handle_action(lambda: build_contest(self.server.settings, contest_id, str(output).strip() if output else None))
            return
        if route == "/print-station/api/pause":
            self.handle_print_action(lambda: print_pause(self.server.settings))
            return
        if route == "/print-station/api/resume":
            self.handle_print_action(lambda: print_resume(self.server.settings))
            return
        if route == "/print-station/api/jobs/claim":
            body = self.read_json_body()
            station_id = str(body.get("station_id", "")).strip()
            if not station_id:
                self.write_json({"error": "station_id is required"}, HTTPStatus.BAD_REQUEST)
                return
            self.handle_print_action(lambda: print_claim(self.server.settings, station_id))
            return
        match = PRINT_JOB_ROUTE_RE.match(route)
        if match:
            job_id, action = match.groups()
            body = self.read_json_body()
            station_id = str(body.get("station_id", "")).strip()
            if action in {"done", "fail"} and not station_id:
                self.write_json({"error": "station_id is required"}, HTTPStatus.BAD_REQUEST)
                return
            if action == "done":
                self.handle_print_action(lambda: print_mark_done(self.server.settings, job_id, station_id))
                return
            if action == "fail":
                reason = str(body.get("reason", "")).strip()
                self.handle_print_action(lambda: print_mark_failed(self.server.settings, job_id, station_id, reason))
                return
            if action == "requeue":
                self.handle_print_action(lambda: print_requeue(self.server.settings, job_id))
                return
        self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def handle_action(self, action) -> None:
        try:
            self.write_json(action())
        except Exception as exc:
            self.write_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_print_action(self, action) -> None:
        try:
            self.write_json(action())
        except InvalidJobId as exc:
            self.write_json({"error": f"invalid job id: {exc}"}, HTTPStatus.BAD_REQUEST)
        except JobNotFound as exc:
            self.write_json({"error": f"job not found: {exc}"}, HTTPStatus.NOT_FOUND)
        except StationConflict as exc:
            self.write_json({"error": str(exc)}, HTTPStatus.CONFLICT)
        except PrintQueueError as exc:
            self.write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.write_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_print_text(self, job_id: str) -> None:
        try:
            text = print_text(self.server.settings, job_id)
        except InvalidJobId as exc:
            self.write_json({"error": f"invalid job id: {exc}"}, HTTPStatus.BAD_REQUEST)
            return
        except JobNotFound as exc:
            self.write_json({"error": f"job not found: {exc}"}, HTTPStatus.NOT_FOUND)
            return
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def write_json(self, value: Mapping[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def normalized_path(path: str) -> str:
    parsed = urlparse(path)
    route = parsed.path
    if route.startswith("/rollboard/api/"):
        route = route[len("/rollboard") :]
    return route.rstrip("/") or "/"


def first_query_value(query: Mapping[str, List[str]], name: str) -> Optional[str]:
    values = query.get(name)
    if not values:
        return None
    value = values[0].strip()
    return value or None


class RollboardHTTPServer(ThreadingHTTPServer):
    settings: Settings


def main() -> int:
    settings = Settings.from_env()
    server = RollboardHTTPServer((settings.host, settings.port), RollboardAdminHandler)
    server.settings = settings
    print(f"rollboard admin server listening on {settings.host}:{settings.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
