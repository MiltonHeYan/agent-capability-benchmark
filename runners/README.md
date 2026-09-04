# Runners

Runners hold the agent side of the experiment constant. A runner binds a pinned model and system prompt to exactly one provider adapter for a run.

A conforming runner must:

- Start from a clean task context
- Enforce time, retry, call, and spending limits
- Capture messages, tool calls, approvals, and timestamps
- Avoid provider-specific prompt changes
- Emit a normalized evidence bundle
- Separate harness failures from provider task failures

Initial development should implement one reference runner before adding cross-runtime comparisons.
