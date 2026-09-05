from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from typing import Any

from agent_capability_benchmark.adapters.base import CapabilityBundle
from agent_capability_benchmark.runners.base import (
    AgentRunContext,
    AgentRunner,
    AgentRunResult,
    RunnerFingerprint,
)

PROTOCOL = "acb-jsonl"
PROTOCOL_VERSION = "1"
RUNNER_VERSION = "0.1.0"
_SAFE_INHERITED_ENV = ("PATH", "LANG", "LC_ALL", "TZ")
_MAX_STDERR_CHARS = 8192
_MAX_EVENT_BYTES = 1024 * 1024


class JsonlProtocolError(ValueError):
    """Raised internally when a child emits an invalid protocol event."""


class JsonlSubprocessRunner(AgentRunner):
    """Run one agent engine process over a line-delimited JSON protocol."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        engine: str,
        engine_version: str,
        runtime_image_sha256: str,
        model: str,
        system_prompt: str,
        supported_transports: Sequence[str],
        inference_config: Mapping[str, Any] | None = None,
        environment: Mapping[str, str] | None = None,
        termination_grace_seconds: float = 1.0,
    ) -> None:
        if isinstance(command, (str, bytes)) or not command:
            raise ValueError("command must be a non-empty sequence of arguments")
        if not all(isinstance(argument, str) and argument for argument in command):
            raise ValueError("every command argument must be a non-empty string")
        if not supported_transports or not all(
            isinstance(transport, str) and transport for transport in supported_transports
        ):
            raise ValueError("supported_transports must not be empty")
        if termination_grace_seconds <= 0:
            raise ValueError("termination_grace_seconds must be positive")
        if environment is not None and not all(
            isinstance(name, str) and name and isinstance(value, str) and "=" not in name
            for name, value in environment.items()
        ):
            raise ValueError("environment names and values must be valid strings")

        self.command = tuple(command)
        self.supported_transports = frozenset(supported_transports)
        self._system_prompt = system_prompt
        self._inference_config = dict(inference_config or {})
        self._environment = dict(environment or {})
        self._termination_grace_seconds = termination_grace_seconds
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[str] | None = None
        self._secret_values: tuple[str, ...] = ()
        self._started_at: float | None = None

        driver_config = {
            "command": list(self.command),
            "environment_keys": sorted(self._environment),
            "protocol": PROTOCOL,
            "protocol_version": PROTOCOL_VERSION,
            "supported_transports": sorted(self.supported_transports),
        }
        driver_config_sha256 = _stable_digest(driver_config)
        self.fingerprint = RunnerFingerprint.from_system_prompt(
            runner="jsonl-subprocess",
            runner_version=RUNNER_VERSION,
            engine=engine,
            engine_version=engine_version,
            runtime_image_sha256=runtime_image_sha256,
            model=model,
            system_prompt=system_prompt,
            inference_config=self._inference_config,
            driver_config_sha256=driver_config_sha256,
        )

    @property
    def process_returncode(self) -> int | None:
        return self._process.returncode if self._process is not None else None

    async def setup(self, context: AgentRunContext, bundle: CapabilityBundle) -> None:
        if self._process is not None and self._process.returncode is None:
            raise RuntimeError("runner already has an active child process")
        if not context.workspace.is_absolute() or not context.workspace.is_dir():
            raise ValueError("runner workspace must be an existing absolute directory")

        self._secret_values = tuple(
            sorted(
                {
                    *_collect_string_values(bundle.configuration),
                    *(value for value in self._environment.values() if len(value) >= 4),
                },
                key=len,
                reverse=True,
            )
        )
        process_environment = {
            name: os.environ[name] for name in _SAFE_INHERITED_ENV if name in os.environ
        }
        process_environment.update(self._environment)

        self._started_at = time.monotonic()
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=context.workspace,
            env=process_environment,
            limit=_MAX_EVENT_BYTES,
        )
        self._stderr_task = asyncio.create_task(self._read_stderr())
        try:
            await self._send(
                {
                    "protocol": PROTOCOL,
                    "protocol_version": PROTOCOL_VERSION,
                    "type": "run",
                    "run": {
                        "run_id": context.run_id,
                        "workspace": str(context.workspace),
                        "namespace": context.namespace,
                        "allowed_egress": list(context.allowed_egress),
                    },
                    "runner": {
                        "model": self.fingerprint.model,
                        "system_prompt": self._system_prompt,
                        "inference_config": self._inference_config,
                        "fingerprint_sha256": self.fingerprint.digest,
                    },
                    "task": context.task,
                    "capability_bundle": {
                        "transport": bundle.transport,
                        "version": bundle.version,
                        "configuration": bundle.configuration,
                        "tool_manifest": list(bundle.tool_manifest),
                    },
                }
            )
        except BaseException:
            await self._stop_process()
            raise

    async def run(self, context: AgentRunContext) -> AgentRunResult:
        process = self._require_process()
        if process.stdout is None:
            raise RuntimeError("child stdout is unavailable")

        messages: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        metrics: dict[str, int | float] = {}
        operational_errors: list[dict[str, str]] = []
        child_metadata: dict[str, Any] = {}
        final_received = False
        child_completed_normally = False
        child_error: str | None = None
        scripted_events = list(context.task.get("scripted_user_events", []))
        used_scripted_events: set[int] = set()
        started = time.monotonic()

        async def consume() -> None:
            nonlocal final_received, child_completed_normally, child_error, child_metadata
            while True:
                try:
                    line = await process.stdout.readline()
                except ValueError as error:
                    operational_errors.append(
                        {
                            "code": "malformed-jsonl-event",
                            "phase": "run",
                            "message": str(self._redact(str(error))),
                        }
                    )
                    return
                if not line:
                    return
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise JsonlProtocolError("event must be a JSON object")
                    event_type = event.get("type")
                    if not isinstance(event_type, str):
                        raise JsonlProtocolError("event.type must be a string")
                    if event_type == "message":
                        messages.append(self._normalize_message(event))
                    elif event_type == "tool_event":
                        events.append(self._normalize_tool_event(event))
                    elif event_type == "usage":
                        _merge_metrics(metrics, event.get("metrics"))
                    elif event_type == "operational_error":
                        operational_errors.append(self._normalize_operational_error(event))
                    elif event_type == "input_request":
                        response, normalized = _match_scripted_event(
                            event,
                            scripted_events,
                            used_scripted_events,
                        )
                        await self._send(response)
                        events.append(self._redact(normalized))
                    elif event_type == "final":
                        completed_normally = event.get("completed_normally")
                        if not isinstance(completed_normally, bool):
                            raise JsonlProtocolError("final.completed_normally must be a boolean")
                        final_received = True
                        child_completed_normally = completed_normally
                        if event.get("error") is not None:
                            child_error = str(self._redact(event["error"]))
                        if "message" in event:
                            message = event["message"]
                            if not isinstance(message, dict):
                                raise JsonlProtocolError("final.message must be an object")
                            messages.append(self._normalize_message({"type": "message", **message}))
                        if "metrics" in event:
                            _merge_metrics(metrics, event["metrics"])
                        metadata = event.get("metadata", {})
                        if not isinstance(metadata, dict):
                            raise JsonlProtocolError("final.metadata must be an object")
                        child_metadata = self._redact(metadata)
                        return
                    else:
                        raise JsonlProtocolError(f"unknown event type {event_type!r}")
                except (JsonlProtocolError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    operational_errors.append(
                        {
                            "code": "malformed-jsonl-event",
                            "phase": "run",
                            "message": str(self._redact(str(error))),
                        }
                    )
                    return
                except (BrokenPipeError, ConnectionResetError) as error:
                    operational_errors.append(
                        {
                            "code": "protocol-io-error",
                            "phase": "run",
                            "message": str(self._redact(str(error))),
                        }
                    )
                    return

        timeout_seconds = float(context.task.get("limits", {}).get("timeout_seconds", 60))
        try:
            await asyncio.wait_for(consume(), timeout=timeout_seconds)
        except TimeoutError:
            operational_errors.append(
                {
                    "code": "timeout",
                    "phase": "run",
                    "message": f"child exceeded the {timeout_seconds:g}s task timeout",
                }
            )
        except asyncio.CancelledError:
            await self._stop_process()
            raise

        if final_received:
            await self._close_stdin()
            try:
                await asyncio.wait_for(process.wait(), timeout=self._termination_grace_seconds)
            except TimeoutError:
                operational_errors.append(
                    {
                        "code": "exit-timeout",
                        "phase": "teardown",
                        "message": "child did not exit after its final event",
                    }
                )
        elif not operational_errors:
            await process.wait()
            operational_errors.append(
                {
                    "code": "early-exit",
                    "phase": "run",
                    "message": f"child exited with code {process.returncode} before a final event",
                }
            )

        if final_received and process.returncode not in (None, 0):
            operational_errors.append(
                {
                    "code": "nonzero-exit",
                    "phase": "run",
                    "message": f"child exited with code {process.returncode} after its final event",
                }
            )

        if process.returncode is None:
            await self._stop_process()
        stderr = await self._finish_stderr()
        elapsed_from = self._started_at if self._started_at is not None else started
        elapsed_ms = round((time.monotonic() - elapsed_from) * 1000, 3)
        metrics["runner_elapsed_ms"] = elapsed_ms

        errors = [error["message"] for error in operational_errors]
        if child_error:
            errors.insert(0, child_error)
        completed_normally = final_received and child_completed_normally and not operational_errors
        metadata = {
            **child_metadata,
            "protocol": f"{PROTOCOL}/{PROTOCOL_VERSION}",
            "process_returncode": process.returncode,
            "operational_errors": operational_errors,
        }
        if stderr:
            metadata["stderr"] = stderr
        return AgentRunResult(
            completed_normally=completed_normally,
            error="; ".join(errors) or None,
            messages=tuple(messages),
            events=tuple(events),
            metrics=metrics,
            metadata=metadata,
        )

    async def teardown(self, context: AgentRunContext) -> None:
        await self._stop_process()

    def _normalize_message(self, event: dict[str, Any]) -> dict[str, Any]:
        role = event.get("role")
        content = event.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise JsonlProtocolError("message role and content must be strings")
        return self._redact({key: value for key, value in event.items() if key != "type"})

    def _normalize_tool_event(self, event: dict[str, Any]) -> dict[str, Any]:
        name = event.get("name")
        status = event.get("status")
        if not isinstance(name, str) or not isinstance(status, str):
            raise JsonlProtocolError("tool_event name and status must be strings")
        return self._redact({key: value for key, value in event.items() if key != "type"})

    def _normalize_operational_error(self, event: dict[str, Any]) -> dict[str, str]:
        code = event.get("code")
        message = event.get("message")
        phase = event.get("phase", "run")
        if not all(isinstance(value, str) and value for value in (code, message, phase)):
            raise JsonlProtocolError("operational_error code, phase, and message must be strings")
        return self._redact({"code": code, "phase": phase, "message": message})

    def _redact(self, value: Any) -> Any:
        return _redact(value, self._secret_values)

    async def _send(self, event: dict[str, Any]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise RuntimeError("child stdin is unavailable")
        serialized = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        process.stdin.write(serialized.encode("utf-8") + b"\n")
        await process.stdin.drain()

    async def _read_stderr(self) -> str:
        process = self._require_process()
        if process.stderr is None:
            return ""
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = await process.stderr.read(1024)
            if not chunk:
                break
            if size < _MAX_STDERR_CHARS:
                retained = chunk[: _MAX_STDERR_CHARS - size]
                chunks.append(retained)
                size += len(retained)
        return str(self._redact(b"".join(chunks).decode("utf-8", errors="replace")))

    async def _finish_stderr(self) -> str:
        if self._stderr_task is None:
            return ""
        try:
            return await self._stderr_task
        finally:
            self._stderr_task = None

    async def _close_stdin(self) -> None:
        process = self._require_process()
        if process.stdin is not None and not process.stdin.is_closing():
            process.stdin.close()
            with suppress(BrokenPipeError, ConnectionResetError):
                await process.stdin.wait_closed()

    async def _stop_process(self) -> None:
        process = self._process
        if process is None:
            return
        await self._close_stdin()
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=self._termination_grace_seconds)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                await process.wait()
        await self._finish_stderr()

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise RuntimeError("runner setup has not started a child process")
        return self._process


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _collect_string_values(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str) and len(value) >= 4:
        found.add(value)
    elif isinstance(value, Mapping):
        for child in value.values():
            found.update(_collect_string_values(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_collect_string_values(child))
    return found


def _redact(value: Any, secrets: Sequence[str]) -> Any:
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {_redact(key, secrets): _redact(child, secrets) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact(child, secrets) for child in value]
    if isinstance(value, tuple):
        return tuple(_redact(child, secrets) for child in value)
    return value


def _merge_metrics(target: dict[str, int | float], raw_metrics: Any) -> None:
    if not isinstance(raw_metrics, dict):
        raise JsonlProtocolError("usage.metrics must be an object")
    for name, value in raw_metrics.items():
        if (
            not isinstance(name, str)
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise JsonlProtocolError("usage metrics must have string names and numeric values")
        target[name] = target.get(name, 0) + value


def _match_scripted_event(
    request: dict[str, Any],
    scripted_events: list[dict[str, Any]],
    used: set[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_id = request.get("request_id")
    when = request.get("when")
    event_type = request.get("event_type")
    if not all(isinstance(value, str) and value for value in (request_id, when, event_type)):
        raise JsonlProtocolError(
            "input_request request_id, when, and event_type must be non-empty strings"
        )

    selected_index = next(
        (
            index
            for index, event in enumerate(scripted_events)
            if index not in used and event.get("when") == when and event.get("type") == event_type
        ),
        None,
    )
    selected = scripted_events[selected_index] if selected_index is not None else None
    if selected_index is not None:
        used.add(selected_index)
    response = {
        "protocol": PROTOCOL,
        "protocol_version": PROTOCOL_VERSION,
        "type": "user_event",
        "request_id": request_id,
        "available": selected is not None,
        "event": selected,
    }
    normalized = {
        "type": "scripted_user_event",
        "request_id": request_id,
        "when": when,
        "event_type": event_type,
        "available": selected is not None,
    }
    return response, normalized
