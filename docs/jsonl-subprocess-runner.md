# JSONL Subprocess Runner Protocol

The JSONL subprocess runner is the reference integration path for CLI-based agent engines. It
starts one clean child process per benchmark run with `shell=False`, uses the sandbox workspace as
the child working directory, and exchanges exactly one JSON object per line over stdin and stdout.

The protocol identifier is `acb-jsonl` and the current protocol version is `1`.

## Starting a run

`JsonlSubprocessRunner.setup` starts the configured argument vector directly and sends one `run`
event. The task object contains only agent-visible fields. The capability bundle contains
execution-side configuration and tool metadata supplied by the selected provider adapter.

```json
{
  "protocol": "acb-jsonl",
  "protocol_version": "1",
  "type": "run",
  "run": {
    "run_id": "run-12345678",
    "workspace": "/absolute/clean/workspace",
    "namespace": "acb-run-12345678",
    "allowed_egress": ["provider.example:443"]
  },
  "runner": {
    "model": "fixed-model",
    "system_prompt": "You are the fixed benchmark agent.",
    "inference_config": {"temperature": 0},
    "fingerprint_sha256": "..."
  },
  "task": {
    "id": "read-known-record",
    "request": "Read the requested record.",
    "policy": {"approval": "not_required", "prohibited_actions": []},
    "limits": {"timeout_seconds": 60, "max_tool_calls": 5, "max_retries": 1}
  },
  "capability_bundle": {
    "transport": "mcp",
    "version": "1",
    "configuration": {"connection": "opaque-execution-handle"},
    "tool_manifest": []
  }
}
```

The executable must not expect verifier fields, expected outcomes, fixture-control endpoints, or
verification and cleanup credentials. They are removed before the runner receives the task.

## Child events

The child writes these event types to stdout:

| Type | Required fields | Meaning |
|---|---|---|
| `message` | `role`, `content` | One normalized agent message |
| `tool_event` | `name`, `status` | A tool call, result, or transport event |
| `usage` | `metrics` | Numeric counters such as tokens, calls, or provider-observed cost |
| `operational_error` | `code`, `phase`, `message` | A structured engine or transport failure |
| `input_request` | `request_id`, `when`, `event_type` | Request the matching scripted user event |
| `final` | `completed_normally` | End the run and optionally add a message, metrics, error, or metadata |

Example successful output:

```jsonl
{"type":"message","role":"assistant","content":"I found the record."}
{"type":"tool_event","name":"records.read","status":"succeeded","call_id":"call-1"}
{"type":"usage","metrics":{"input_tokens":120,"output_tokens":24,"tool_calls":1}}
{"type":"final","completed_normally":true,"metadata":{"engine_session":"session-1"}}
```

An `input_request` pauses event consumption until the runner sends a matching `user_event` on
stdin. Each scripted event can be used once. If no event matches, the response has
`"available": false` and `"event": null`; the driver never invents an approval or clarification.

```jsonl
{"type":"input_request","request_id":"approval-1","when":"on-valid-approval-request","event_type":"approval"}
{"protocol":"acb-jsonl","protocol_version":"1","type":"user_event","request_id":"approval-1","available":true,"event":{"when":"on-valid-approval-request","type":"approval","value":"approve"}}
```

## Failure and shutdown behavior

Malformed JSON, unknown events, premature exit, non-zero exit after a final event, timeout, and
protocol I/O failures become structured entries in `AgentRunResult.metadata.operational_errors`.
They do not prevent the trusted harness from capturing and verifying final external state.

After `final`, stdin is closed and the child must exit. On timeout, cancellation, or a child that
does not exit during the grace period, the runner sends terminate, then kill if necessary, and
always reaps the process.

## Security boundaries

- The runner inherits only `PATH`, locale, and timezone variables by default. Engine credentials
  must be passed explicitly through `environment`.
- Execution handles and explicit environment values are redacted from normalized messages, tool
  events, errors, stderr, and metadata.
- Never place credentials in command-line arguments. Arguments may be visible in the host process
  table and are included by digest in the runner fingerprint.
- The command vector, environment variable names, protocol version, and supported transports are
  hashed into `driver_config_sha256`. Environment values are not included in that identity.
- Provider-specific planning, retries, task hints, and verifier logic belong neither in this
  driver nor in a conforming child executable.

## Python integration

```python
from agent_capability_benchmark.runners import JsonlSubprocessRunner

runner = JsonlSubprocessRunner(
    ("/opt/agent/bin/agent-driver", "--jsonl"),
    engine="example-engine",
    engine_version="1.2.3",
    runtime_image_sha256="<64 lowercase hex characters>",
    model="fixed-model",
    system_prompt="You are the fixed benchmark agent.",
    supported_transports=("mcp",),
    inference_config={"temperature": 0},
    environment={"ENGINE_API_TOKEN": "<run-scoped secret>"},
)
```
