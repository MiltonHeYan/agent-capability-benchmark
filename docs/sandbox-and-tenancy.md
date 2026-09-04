# Sandbox and Test-Tenant Model

The benchmark isolates both the local runner and every external side effect. A container alone is not a sufficient sandbox for account-connected capability providers because writes occur outside the container.

## Trust boundaries

```text
Untrusted execution plane                 Trusted control plane

fixed runner + provider adapter           sandbox backend
              |                                  |
              | opaque execution handles         | verifier credentials
              v                                  v
       dedicated test tenant  <---------- independent observation
              ^                                  |
              |                                  | cleanup credentials
              +---------------- namespace cleanup+
```

The provider adapter receives only execution-side connection handles. It never receives verifier or cleanup credentials, baseline snapshots, hidden expected values, or direct access to the evidence store.

## Isolation layers

1. **Process and filesystem** — run in a disposable container or VM with a fresh workspace and state directory.
2. **Network** — deny by default; permit only the provider endpoint, declared target services, and benchmark telemetry endpoint.
3. **Account** — use dedicated test organizations and users. Personal or production accounts are prohibited.
4. **Namespace** — prefix every external object with the complete `run_id`, and reject writes outside the leased namespace where the target service permits enforcement.
5. **Credential** — execution and verification use distinct principals. Tokens are short-lived and represented in benchmark objects only by opaque handles.
6. **Budget** — enforce task-level call, retry, time, and monetary ceilings outside the provider.

## Run lifecycle

1. Generate an unpredictable `run_id`.
2. Lease a clean runner and an external test-tenant namespace.
3. Mint or attach short-lived execution, verifier, and cleanup grants.
4. Capture an immutable baseline with verifier credentials.
5. Project only execution handles into `AdapterContext`.
6. Execute the provider attempt.
7. Capture final state even if the adapter times out or reports an error.
8. Build evidence in the trusted control plane and run deterministic checks.
9. Revoke credentials and remove run-scoped resources.
10. Quarantine the tenant if cleanup leaves residual resources.

## Credential roles

| Role | Holder | Minimum access | Visible to adapter |
|---|---|---|---|
| Execution | provider connection path | actions required by the task | yes, as an opaque handle |
| Verification | benchmark control plane | read-only where possible | no |
| Cleanup | benchmark control plane | delete only within leased namespace | no |

Execution and verifier grants must use distinct principals. Cleanup may require elevated access, but it remains outside the runner and is constrained to the run namespace.

## Failure semantics

A transport error is not automatically a task failure. The provider may complete an external write and lose the response. The harness therefore captures final state after normal completion, timeout, or adapter error. Deterministic external state decides task success; the transport failure is recorded separately as a reliability signal.

Cleanup failure does not rewrite the task verdict. It is reported as an infrastructure and safety failure, and the affected tenant must not be returned to the available pool until reconciled.

## Reference implementation boundary

`SandboxBackend` defines provisioning, verifier snapshots, and cleanup. `IsolatedRunHarness` enforces the lifecycle and constructs evidence. The loopback fixture server is suitable only for contract testing; official evaluations require service-specific test tenants and independent credentials.

Production backends must additionally provide:

- tenant-pool leasing with concurrency control;
- secret-manager integration and automatic revocation;
- egress-policy enforcement;
- immutable audit logs with secret redaction;
- cleanup reconciliation and quarantine;
- per-service rate and spend controls.
