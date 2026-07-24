# Serialization

Deterministic, version-tagged JSON for the checkpoint-safe models (`AgentState`, `ExecutionPlan`,
`ModelCard`, `RunResult`). `AgentGraph` is deliberately not supported — its nodes carry live,
non-serialisable compute callables.

::: korchestrator.to_json

::: korchestrator.from_json
