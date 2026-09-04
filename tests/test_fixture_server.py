from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import pytest

from agent_capability_benchmark.fixture_server import (
    FixtureSessionStore,
    start_fixture_server,
)


def _request(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=2) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_session_store_preserves_baseline_snapshot() -> None:
    store = FixtureSessionStore()
    evidence = store.create(
        task_id="sample-task",
        observations={"fixture": {"mutation-count": 0}},
        references={},
    )

    assert store.replace_observations(
        evidence["run_id"],
        {"fixture": {"mutation-count": 1}},
    )
    updated = store.get(evidence["run_id"])

    assert updated is not None
    assert updated["baseline"]["fixture"]["mutation-count"] == 0
    assert updated["observations"]["fixture"]["mutation-count"] == 1


def test_fixture_server_http_lifecycle() -> None:
    with start_fixture_server(port=0) as server:
        status, health = _request(f"{server.base_url}/health")
        assert status == 200
        assert health == {"status": "ok"}

        status, created = _request(
            f"{server.base_url}/v1/sessions",
            method="POST",
            payload={
                "task_id": "sample-task",
                "observations": {"fixture": {"mutation-count": 0}},
                "references": {},
            },
        )
        assert status == 201
        run_id = created["run_id"]

        status, _ = _request(
            f"{server.base_url}/v1/sessions/{run_id}/observations",
            method="PUT",
            payload={"fixture": {"mutation-count": 1}},
        )
        assert status == 200

        status, evidence = _request(f"{server.base_url}/v1/sessions/{run_id}/evidence")
        assert status == 200
        assert evidence["baseline"]["fixture"]["mutation-count"] == 0
        assert evidence["observations"]["fixture"]["mutation-count"] == 1

        status, _ = _request(
            f"{server.base_url}/v1/sessions/{run_id}",
            method="DELETE",
        )
        assert status == 200


def test_fixture_server_rejects_non_loopback_bind() -> None:
    with pytest.raises(ValueError, match="loopback"):
        start_fixture_server("0.0.0.0", 0)
