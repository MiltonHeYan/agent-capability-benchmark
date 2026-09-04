from __future__ import annotations

import json
import threading
from copy import deepcopy
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

_MAX_REQUEST_BYTES = 1_048_576


class FixtureSessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}

    def create(
        self,
        *,
        task_id: str,
        observations: dict[str, Any],
        references: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = str(uuid4())
        evidence = {
            "task_id": task_id,
            "run_id": run_id,
            "observations": deepcopy(observations),
            "baseline": deepcopy(observations),
            "references": deepcopy(references),
            "events": [],
            "metadata": {"fixture_runtime": "reference"},
        }
        with self._lock:
            self._sessions[run_id] = evidence
        return deepcopy(evidence)

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            evidence = self._sessions.get(run_id)
            return deepcopy(evidence) if evidence is not None else None

    def replace_observations(self, run_id: str, observations: dict[str, Any]) -> bool:
        with self._lock:
            if run_id not in self._sessions:
                return False
            self._sessions[run_id]["observations"] = deepcopy(observations)
            return True

    def append_event(self, run_id: str, event: dict[str, Any]) -> bool:
        with self._lock:
            if run_id not in self._sessions:
                return False
            self._sessions[run_id]["events"].append(deepcopy(event))
            return True

    def delete(self, run_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(run_id, None) is not None


@dataclass
class FixtureServerHandle:
    server: ThreadingHTTPServer
    thread: threading.Thread

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def __enter__(self) -> FixtureServerHandle:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def start_fixture_server(host: str = "127.0.0.1", port: int = 0) -> FixtureServerHandle:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the reference fixture server may bind only to loopback")

    store = FixtureSessionStore()

    class Handler(_FixtureRequestHandler):
        session_store = store

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return FixtureServerHandle(server=server, thread=thread)


class _FixtureRequestHandler(BaseHTTPRequestHandler):
    session_store: FixtureSessionStore

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        run_id, suffix = self._session_path(path)
        if run_id and suffix == "evidence":
            evidence = self.session_store.get(run_id)
            if evidence is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
            else:
                self._send_json(HTTPStatus.OK, evidence)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_json()
        if body is None:
            return
        if path == "/v1/sessions":
            task_id = body.get("task_id")
            observations = body.get("observations")
            references = body.get("references")
            if (
                not isinstance(task_id, str)
                or not isinstance(observations, dict)
                or not isinstance(references, dict)
            ):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid session payload"})
                return
            evidence = self.session_store.create(
                task_id=task_id,
                observations=observations,
                references=references,
            )
            self._send_json(HTTPStatus.CREATED, evidence)
            return
        run_id, suffix = self._session_path(path)
        if run_id and suffix == "events":
            if not self.session_store.append_event(run_id, body):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
            else:
                self._send_json(HTTPStatus.CREATED, {"status": "recorded"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        body = self._read_json()
        if body is None:
            return
        run_id, suffix = self._session_path(path)
        if run_id and suffix == "observations":
            if not self.session_store.replace_observations(run_id, body):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
            else:
                self._send_json(HTTPStatus.OK, {"status": "updated"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        run_id, suffix = self._session_path(path)
        if run_id and not suffix:
            if not self.session_store.delete(run_id):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "session not found"})
            else:
                self._send_json(HTTPStatus.OK, {"status": "deleted"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return None

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > _MAX_REQUEST_BYTES:
                self._send_json(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    {"error": "request body exceeds limit"},
                )
                return None
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            return None
        if not isinstance(body, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "JSON object required"})
            return None
        return body

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _session_path(path: str) -> tuple[str | None, str]:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 3 or parts[:2] != ["v1", "sessions"]:
            return None, ""
        run_id = parts[2]
        suffix = "/".join(parts[3:])
        return run_id, suffix
