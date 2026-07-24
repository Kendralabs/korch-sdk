# API Reference

Auto-generated from the source docstrings — always in sync with the installed version, never
hand-copied out of date.

This reference covers the **curated public surface**: `korchestrator.__all__`, the ARI ports and
their supporting protocols, the models in the compatibility surface, and the remote (Tier 4)
contract. Anything not listed here — anything not in `__all__`, not a documented port, not a
listed model, and not part of the remote contract — is internal and may change in any release,
regardless of whether it happens to be importable.

- **[Services](services.md)** — `Korch`, `Swarm`, `Agent`
- **[Models](models.md)** — the typed data every entry point accepts and returns
- **[Interfaces](interfaces.md)** — the ARI ports and supporting protocols
- **[Exceptions](exceptions.md)** — the `KorchError` tree
- **[Configuration](config.md)** — `Settings`, `configure`, logging
- **[Serialization](serialization.md)** — `to_json`/`from_json`
- **[Remote client](remote.md)** — `KorchestratorClient` (Tier 4, `[remote]` extra)
