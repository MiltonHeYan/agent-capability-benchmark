# Tasks

Tasks are vendor-neutral, versioned evaluation contracts validated against `spec/task.schema.json`.

A task defines:

- The exact user request
- Required capabilities and track eligibility
- Resettable fixture state
- Approval and prohibited-action policy
- Time, retry, call, and spending limits
- Optional failure injections
- An independent verifier and success condition

Public task files belong in a directory named for their track. Private or rotating tasks must use the same schema but must not be committed to this repository.

Task authors should describe observable goals rather than name a specific provider tool. Adapters are responsible for translating the common task into provider-specific access.
