from __future__ import annotations

import json
import os
import signal
import sys
import time


def emit(event: dict) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


def receive() -> dict:
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError("expected a JSONL event on stdin")
    return json.loads(line)


def main() -> int:
    mode = sys.argv[1]
    run = receive()
    metadata = {
        "cwd": os.getcwd(),
        "pid": os.getpid(),
        "received": run,
    }

    if mode == "success":
        emit({"type": "message", "role": "assistant", "content": "done"})
        emit(
            {
                "type": "tool_event",
                "name": "records.read",
                "status": "succeeded",
                "call_id": "call-1",
            }
        )
        emit({"type": "usage", "metrics": {"input_tokens": 10, "tool_calls": 1}})
        emit(
            {
                "type": "final",
                "completed_normally": True,
                "metrics": {"output_tokens": 4},
                "metadata": metadata,
            }
        )
        return 0

    if mode == "multi-turn":
        requests = (
            ("approval-1", "on-valid-approval-request", "approval"),
            ("clarification-1", "on-clarification-request", "clarification"),
        )
        for request_id, when, event_type in requests:
            emit(
                {
                    "type": "input_request",
                    "request_id": request_id,
                    "when": when,
                    "event_type": event_type,
                }
            )
            response = receive()
            emit(
                {
                    "type": "tool_event",
                    "name": f"user.{event_type}",
                    "status": "received",
                    "response": response,
                }
            )
        emit({"type": "final", "completed_normally": True, "metadata": metadata})
        return 0

    if mode == "malformed":
        print("{not-json", flush=True)
        return 0

    if mode == "early-exit":
        print("engine failed before final", file=sys.stderr, flush=True)
        return 7

    if mode == "hang":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        emit({"type": "message", "role": "assistant", "content": "still running"})
        time.sleep(60)
        return 0

    if mode == "leak":
        secret = run["capability_bundle"]["configuration"]["connection"]
        env_secret = os.environ["ENGINE_API_TOKEN"]
        print(f"stderr contains {secret} and {env_secret}", file=sys.stderr, flush=True)
        emit(
            {
                "type": "message",
                "role": "assistant",
                "content": f"message contains {secret}",
            }
        )
        emit(
            {
                "type": "tool_event",
                "name": "records.read",
                "status": "failed",
                "detail": f"event contains {env_secret}",
            }
        )
        emit(
            {
                "type": "operational_error",
                "code": "engine-error",
                "phase": "run",
                "message": f"error contains {secret} and {env_secret}",
            }
        )
        emit(
            {
                "type": "final",
                "completed_normally": False,
                "error": f"final contains {secret}",
                "metadata": metadata,
            }
        )
        return 0

    raise ValueError(f"unknown fake mode {mode!r}")


if __name__ == "__main__":
    raise SystemExit(main())
