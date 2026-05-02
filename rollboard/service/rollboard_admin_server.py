#!/usr/bin/env python3
"""Small localhost-only JSON API for the rollboard admin page."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse

from rollboard.tools.rollboard_build import DomjudgeClient, read_secret_file, safe_slug


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18090
DEFAULT_DATA_ROOT = "/mnt/domjudge/rollboard/www/data"
DEFAULT_BUILDER_PATH = "/mnt/domjudge/rollboard/rollboard/tools/rollboard_build.py"
DEFAULT_API_BASE_URL = "http://127.0.0.1:12345/api/v4"


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
        )


def make_rollboard_url(slug: str) -> str:
    return f"/rollboard/?component=resolver&data-source=/rollboard/data/{safe_slug(slug)}"


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
        self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def handle_action(self, action) -> None:
        try:
            self.write_json(action())
        except Exception as exc:
            self.write_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

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
