# Remote client (Tier 4)

Drives a **hosted** Korchestrator engine over HTTP. Optional — nothing in Tiers 1-3 depends on it.
Requires the `[remote]` extra.

```bash
pip install "korchestrator[remote]"
```

::: korchestrator.remote.KorchestratorClient

## Wire-facing models

Distinct from the local kernel's own models — `RemoteRunResult` has no nested `AgentState`, for
example, since that's an internal, non-serialised kernel detail the remote contract never exposes.

::: korchestrator.models.remote.RemoteRunResult

::: korchestrator.models.remote.RunSummary

::: korchestrator.models.remote.RunEvent

::: korchestrator.models.remote.CallerIdentity

::: korchestrator.models.remote.Quota

::: korchestrator.models.remote.ApiKey

::: korchestrator.models.remote.ApiKeySummary

::: korchestrator.models.remote.ToolDescriptor

::: korchestrator.models.remote.SwarmTemplate

::: korchestrator.exceptions.ApiError
