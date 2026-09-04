# Verifiers

Verifiers inspect fixture or external-system state independently of the agent and provider execution path.

A verifier must:

- Be read-only with respect to the evaluated outcome
- Check a task's declared success condition
- Detect duplicate or prohibited side effects where applicable
- Return structured evidence and a deterministic verdict input
- Avoid relying solely on agent output or provider success messages

Verifier credentials and fixture secrets must never appear in public traces.
