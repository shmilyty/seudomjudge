"""Filesystem-backed queue helpers for the onsite Print Station."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


JOB_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
STATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
QUEUE_STATES = ("pending", "printing", "failed", "done")


class PrintQueueError(RuntimeError):
    pass


class InvalidJobId(PrintQueueError):
    pass


class JobNotFound(PrintQueueError):
    pass


class StationConflict(PrintQueueError):
    pass


class PrintQueueStore:
    def __init__(self, root: Path, stale_seconds: int = 300, active_station_seconds: int = 45):
        self.root = Path(root)
        self.stale_seconds = stale_seconds
        self.active_station_seconds = active_station_seconds
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for state in QUEUE_STATES:
            ensure_group_queue_dir(self.root / state)
        ensure_group_queue_dir(self.root / "control")

    def is_paused(self) -> bool:
        return self.pause_file.exists()

    def set_paused(self, paused: bool) -> None:
        if paused:
            self.pause_file.write_text(json.dumps({"paused": True, "updated_at": iso_now()}), encoding="utf-8")
        else:
            self.pause_file.unlink(missing_ok=True)

    def heartbeat(self, station_id: str) -> Dict[str, Any]:
        station_id = validate_station_id(station_id)
        active = self._read_active_station()
        now = time.time()
        if active and active.get("station_id") != station_id:
            last_seen = float(active.get("last_seen") or 0)
            if now - last_seen <= self.active_station_seconds:
                return {
                    "station_id": station_id,
                    "active_station": active.get("station_id"),
                    "allowed": False,
                    "last_seen": last_seen,
                }
        payload = {"station_id": station_id, "last_seen": now, "updated_at": iso_now()}
        self.active_station_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return {
            "station_id": station_id,
            "active_station": station_id,
            "allowed": True,
            "last_seen": now,
        }

    def status(self, station_id: Optional[str] = None) -> Dict[str, Any]:
        station = self.heartbeat(station_id) if station_id else self._active_station_status()
        listing = self.list_jobs()
        return {
            "paused": self.is_paused(),
            "station": station,
            "counts": listing["counts"],
            "stale_seconds": self.stale_seconds,
        }

    def list_jobs(self, done_limit: int = 20) -> Dict[str, Any]:
        result: Dict[str, Any] = {state: [] for state in QUEUE_STATES}
        for state in QUEUE_STATES:
            jobs = [self._job_summary(path, state) for path in self._state_dir(state).iterdir() if path.is_dir()]
            jobs.sort(key=lambda item: (item.get("mtime") or 0, item["id"]))
            if state == "done":
                jobs.sort(key=lambda item: (item.get("mtime") or 0, item["id"]), reverse=True)
                jobs = jobs[:done_limit]
            result[state] = jobs
        result["counts"] = {
            state: len([path for path in self._state_dir(state).iterdir() if path.is_dir()])
            for state in QUEUE_STATES
        }
        return result

    def claim_next(self, station_id: str) -> Optional[Dict[str, Any]]:
        if self.is_paused():
            return None
        station = self.heartbeat(station_id)
        if not station["allowed"]:
            raise StationConflict(f"active station is {station['active_station']}")

        pending = sorted(
            [path for path in self._state_dir("pending").iterdir() if path.is_dir()],
            key=lambda path: (path.stat().st_mtime, path.name),
        )
        for source in pending:
            job_id = validate_job_id(source.name)
            destination = self._state_dir("printing") / job_id
            try:
                source.rename(destination)
            except FileNotFoundError:
                continue
            except FileExistsError:
                continue
            state = self._read_state(destination)
            attempts = int(state.get("attempts") or 0) + 1
            self._write_state(
                destination,
                {
                    **state,
                    "state": "printing",
                    "station_id": station_id,
                    "claimed_at": iso_now(),
                    "updated_at": iso_now(),
                    "attempts": attempts,
                },
            )
            return self._job_summary(destination, "printing")
        return None

    def mark_done(self, job_id: str, station_id: str) -> Dict[str, Any]:
        path = self._job_path("printing", job_id)
        self._require_claiming_station(path, station_id)
        state = self._read_state(path)
        self._write_state(path, {**state, "state": "done", "updated_at": iso_now()})
        destination = self._state_dir("done") / validate_job_id(job_id)
        path.rename(destination)
        return self._job_summary(destination, "done")

    def mark_failed(self, job_id: str, station_id: str, reason: str = "") -> Dict[str, Any]:
        path = self._job_path("printing", job_id)
        self._require_claiming_station(path, station_id)
        state = self._read_state(path)
        self._write_state(
            path,
            {**state, "state": "failed", "reason": reason.strip()[:200], "updated_at": iso_now()},
        )
        destination = self._state_dir("failed") / validate_job_id(job_id)
        path.rename(destination)
        return self._job_summary(destination, "failed")

    def requeue(self, job_id: str) -> Dict[str, Any]:
        job_id = validate_job_id(job_id)
        for state in ("failed", "printing", "done"):
            path = self._state_dir(state) / job_id
            if not path.is_dir():
                continue
            state_data = self._read_state(path)
            self._write_state(
                path,
                {**state_data, "state": "pending", "requeued_at": iso_now(), "updated_at": iso_now()},
            )
            destination = self._state_dir("pending") / job_id
            path.rename(destination)
            return self._job_summary(destination, "pending")
        raise JobNotFound(job_id)

    def printable_text(self, job_id: str) -> str:
        for state in QUEUE_STATES:
            path = self._state_dir(state) / validate_job_id(job_id)
            if path.is_dir():
                printable = path / "print.txt"
                if printable.is_file():
                    return printable.read_text(encoding="utf-8", errors="replace")
                source = path / "source"
                if source.is_file():
                    return source.read_text(encoding="utf-8", errors="replace")
        raise JobNotFound(job_id)

    @property
    def pause_file(self) -> Path:
        return self.root / "control" / "paused.json"

    @property
    def active_station_file(self) -> Path:
        return self.root / "control" / "active_station.json"

    def _state_dir(self, state: str) -> Path:
        if state not in QUEUE_STATES:
            raise ValueError(f"invalid queue state: {state}")
        return self.root / state

    def _job_path(self, state: str, job_id: str) -> Path:
        path = self._state_dir(state) / validate_job_id(job_id)
        if not path.is_dir():
            raise JobNotFound(job_id)
        return path

    def _require_claiming_station(self, path: Path, station_id: str) -> None:
        station_id = validate_station_id(station_id)
        state = self._read_state(path)
        owner = state.get("station_id")
        if owner and owner != station_id and not self._is_stale(state):
            raise StationConflict(f"job belongs to {owner}")

    def _job_summary(self, path: Path, state: str) -> Dict[str, Any]:
        stat = path.stat()
        metadata = read_metadata(path / "metadata.txt")
        state_data = self._read_state(path)
        updated_at = state_data.get("updated_at") or timestamp_to_iso(stat.st_mtime)
        result = {
            "id": path.name,
            "state": state,
            "teamname": metadata.get("teamname") or metadata.get("team") or "",
            "username": metadata.get("username") or "",
            "teamid": metadata.get("teamid") or "",
            "language": metadata.get("language") or "",
            "original": metadata.get("original") or metadata.get("filename") or "",
            "location": metadata.get("location") or "",
            "created_at": metadata.get("created_at") or metadata.get("queued_at") or timestamp_to_iso(stat.st_mtime),
            "updated_at": updated_at,
            "mtime": stat.st_mtime,
            "station_id": state_data.get("station_id") or "",
            "attempts": int(state_data.get("attempts") or 0),
            "reason": state_data.get("reason") or "",
            "stale": self._is_stale(state_data) if state == "printing" else False,
        }
        return result

    def _is_stale(self, state_data: Dict[str, Any]) -> bool:
        updated_at = parse_iso_timestamp(str(state_data.get("updated_at") or ""))
        if updated_at is None:
            return False
        return time.time() - updated_at > self.stale_seconds

    def _read_state(self, path: Path) -> Dict[str, Any]:
        state_file = path / "state.json"
        if not state_file.is_file():
            return {}
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write_state(self, path: Path, value: Dict[str, Any]) -> None:
        temp = path / ".state.json.tmp"
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path / "state.json")

    def _read_active_station(self) -> Optional[Dict[str, Any]]:
        if not self.active_station_file.is_file():
            return None
        try:
            data = json.loads(self.active_station_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _active_station_status(self) -> Dict[str, Any]:
        active = self._read_active_station()
        if not active:
            return {"active_station": "", "allowed": True}
        last_seen = float(active.get("last_seen") or 0)
        return {
            "active_station": active.get("station_id") or "",
            "allowed": time.time() - last_seen > self.active_station_seconds,
            "last_seen": last_seen,
        }


def validate_job_id(job_id: str) -> str:
    value = str(job_id)
    if not JOB_ID_RE.fullmatch(value) or value in {".", ".."}:
        raise InvalidJobId(value)
    return value


def validate_station_id(station_id: str) -> str:
    value = str(station_id)
    if not STATION_ID_RE.fullmatch(value) or value in {".", ".."}:
        raise InvalidJobId(value)
    return value


def read_metadata(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    metadata: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        normalized = key.strip().lower().replace(" ", "_")
        metadata[normalized] = value.strip()
    return metadata


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def timestamp_to_iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")


def parse_iso_timestamp(value: str) -> Optional[float]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def ensure_group_queue_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(path.stat().st_mode | 0o2775)
