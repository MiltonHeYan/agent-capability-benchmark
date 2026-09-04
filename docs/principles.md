# Benchmark Principles

## 1. Keep the agent fixed

Each comparison uses the same model version, runner version, system prompt, task prompt, time limit, retry budget, and fixture state. The provider and adapter are the independent variables.

## 2. Measure outcomes, not claims

Every successful task ends with an independent verifier. Provider logs and agent messages are useful evidence, but neither is authoritative about the external result.

## 3. Evaluate the full action lifecycle

Tool discovery alone is not task completion. The benchmark includes discovery, inspection, connection, execution, verification, recovery, and control.

## 4. Treat safe refusal as distinct from success

When a required credential, permission, budget, or approval is absent, the correct behavior may be to stop and identify the missing prerequisite. This receives a safe-block verdict, not a successful-completion verdict.

## 5. Penalize false success heavily

Claiming success without a verified external state is a separate failure class. It must remain visible rather than being averaged into a generic error rate.

## 6. Use tracks instead of one universal feature checklist

Specialized and full-stack products should not be forced into the same eligibility boundary. A common core track supports direct comparison; capability-specific tracks preserve meaningful differences.

## 7. Publish enough to reproduce results

Public task definitions, schemas, runner versions, adapter commits, model versions, and aggregate traces must be available for each published result. Secrets and private fixture data must never appear in artifacts.

## 8. Keep a hidden evaluation set

Public tasks make the benchmark understandable and reproducible. A rotating hidden set reduces task-specific optimization. Hidden tasks must use the same published schema, capability boundaries, and scoring rules.

## 9. Report a metric vector before a composite score

Completion, safety, recovery, latency, and cost represent different tradeoffs. Early versions report them separately. A composite score may be introduced only after its weighting is justified with user evidence.

## 10. Version everything that can change

Tasks, fixtures, adapters, runners, models, provider configurations, verifiers, and scoring logic are versioned. Results from materially different versions are not silently combined.
