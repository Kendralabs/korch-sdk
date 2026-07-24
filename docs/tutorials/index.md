# Tutorials

Each tutorial is self-contained and focuses on one capability. They assume you've completed the
[Quick Start](../quickstart.md).

- **[Building a swarm](swarm.md)** — an explicit multi-agent topology, per-agent models, and
  reading the full reasoning trace.
- **[Writing a custom agent](custom-agent.md)** — subclass `Agent` and supply your own reasoning,
  no DSPy required.
- **[Writing a custom tool](custom-tool.md)** — give agents a real capability to call, from a bare
  function to a full `Connector`.
- **[Connecting an MCP server](mcp.md)** — mount a Model Context Protocol server's tools onto an
  agent.
- **[Writing a custom router](custom-router.md)** — control which model each agent uses.
- **[Human-in-the-loop](hitl.md)** — pause a run for review and resume it, with or without edits.
- **[Streaming a run's events](streaming.md)** — consume a run's progress as it happens.
