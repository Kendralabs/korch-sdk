# Installation

Korchestrator requires **Python 3.10 or newer**.

!!! note "Private distribution, not PyPI (ADR 0020)"
    `Kendralabs/korch-sdk` is a private repository and Korchestrator is not published to PyPI —
    see [ADR 0020](adr/0020-private-distribution-defers-pypi-publishing.md). Every `pip install
    korchestrator` below needs one substitution: replace `korchestrator` with a git reference
    pinned to a released tag, `korchestrator @ git+https://github.com/Kendralabs/korch-sdk.git@vX.Y.Z`.
    You need GitHub credentials with read access to the repo — see below.

## Base install

```bash
pip install "korchestrator @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
```

Installing this way needs a GitHub credential with read access to `Kendralabs/korch-sdk`:

- **SSH** (recommended for a personal machine): if you already have an SSH key registered with
  GitHub, use an SSH remote instead —
  `korchestrator @ git+ssh://git@github.com/Kendralabs/korch-sdk.git@v0.1.0`.
- **HTTPS with a token** (recommended for CI): a fine-grained personal access token with
  `contents:read` on this repo, supplied via a credential helper or embedded in the URL —
  `git+https://<token>@github.com/Kendralabs/korch-sdk.git@v0.1.0`. Don't hardcode a token in a
  committed file; inject it from a secret store or CI secret.

Alternatively, download the wheel from the tag's [GitHub
Release](https://github.com/Kendralabs/korch-sdk/releases) (requires being logged in with repo
access) and `pip install` the local file directly.

The base install depends on **`pydantic` alone** — no LLM SDK, no workflow engine, nothing heavy.
It imports cleanly and lets you construct configuration and typed models, but it cannot yet *run*
a swarm: reasoning is built on [DSPy](https://dspy.ai) and needs the `[dspy]` extra (see below).

## Install what you need

Everything beyond `pydantic` is an **optional extra** — install only what your use case needs.

| Extra | Adds | Needed for |
|---|---|---|
| `[dspy]` | `dspy` | Actually running a swarm — every reasoning agent is built on it. **Almost everyone needs this one.** |
| `[temporal]` | `temporalio` | The durable, replayable runtime (survives process crashes, supports pause/resume) |
| `[routing]` | `sentence-transformers`, `numpy` | Semantic model routing (routing by embedding similarity) |
| `[mcp]` | `mcp` | Connecting to Model Context Protocol tool servers |
| `[remote]` | `httpx` | `KorchestratorClient` — driving a remote, hosted Korchestrator engine |
| `[otel]` | `opentelemetry-api`, `opentelemetry-sdk` | Optional tracing/metrics export |
| `[all]` | every extra above | Development, or when you're not sure yet what you'll need |

Extras compose — request as many as you need in one install. With `pip`, extras go after the
package name inside the same quoted string as the git reference:

```bash
# The common case: run swarms locally, durably, with real tools.
pip install "korchestrator[dspy,temporal,mcp] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"

# Everything.
pip install "korchestrator[all] @ git+https://github.com/Kendralabs/korch-sdk.git@v0.1.0"
```

Or, working from a local clone:

```bash
git clone git@github.com:Kendralabs/korch-sdk.git && cd korch-sdk
pip install -e ".[dspy]"
```

## Verify the install

```bash
python -c "import korchestrator; print(korchestrator.__version__)"
```

This works on the base install — no extras, no network, no API key required.

## Next

Continue to the [Quick Start](quickstart.md) to run your first swarm.
