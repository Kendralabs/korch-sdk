# Exceptions

Everything the SDK raises on purpose is a `KorchError` subclass with a stable `code` — no raw
`temporalio`/`httpx`/`dspy` exception ever crosses a public boundary.

::: korchestrator.KorchError

::: korchestrator.AuthError

::: korchestrator.ValidationError

::: korchestrator.NetworkError

::: korchestrator.ProviderError

::: korchestrator.exceptions.TimeoutError

::: korchestrator.RateLimitError

::: korchestrator.QuotaExceededError

::: korchestrator.RoutingError

::: korchestrator.GovernanceHaltError

::: korchestrator.RunFailedError

::: korchestrator.RunTimeoutError

::: korchestrator.ToolError

::: korchestrator.MissingExtraError

::: korchestrator.exceptions.ConfigurationError
