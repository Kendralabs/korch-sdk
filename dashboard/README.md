# Korchestrator SDK Dashboard

A client application of the `korchestrator` SDK (see [`dashboard_spec.md`](../dashboard_spec.md) for
the full specification). It treats the SDK as an installed library — imports `korchestrator`
directly, never reimplements it — and demonstrates the four testing scenarios: Architect auto-plan,
Swarm designer, tool-augmented execution, and HITL/governance.

## Quick Start

### 1. Install the SDK (editable) and backend dependencies

```powershell
pip install -e '.[all]'
cd dashboard/backend
pip install -r requirements.txt
```

### 2. Configure credentials

```powershell
Copy-Item .env.example .env
# then edit .env with your real Bedrock/OpenAI/Anthropic credentials
```

### 3. Run the backend

```powershell
python -m uvicorn main:app --reload --port 8000
```

### 4. Run the frontend

```powershell
cd dashboard/frontend
npm install
npm run dev
```

Then open <http://localhost:5173>. The frontend also lets you paste provider keys at runtime via the
⚙ Config modal — those are held in the backend's in-memory `api_keys` dict for the process lifetime
only, never written to disk.

## Model: Bedrock Claude Sonnet 4

Default model ID: `us.anthropic.claude-sonnet-4-20250514-v1:0` (cross-region inference profile),
configurable via the `BEDROCK_MODEL_ID` env var. Requires `AWS_BEARER_TOKEN_BEDROCK` and
`AWS_DEFAULT_REGION` in `dashboard/backend/.env`.

## Docker (one-command local spin-up, and the basis for the AWS images)

Prerequisite: `dashboard/backend/.env` exists (step 2 above) — it is never baked into the image,
only injected at container start via `env_file`.

```bash
docker compose -f dashboard/docker-compose.yml up --build
```

Then open <http://localhost:8080>. This builds two images:

- `dashboard/backend/Dockerfile` — build context is the **repository root** (not
  `dashboard/backend/`), since it needs `src/` and `pyproject.toml` to install `korchestrator`
  from source (`pip install '.[all]'`) — the SDK isn't published to PyPI yet.
- `dashboard/frontend/Dockerfile` — a Vite build served by nginx, which reverse-proxies `/api/*`
  to the backend container (see `dashboard/frontend/nginx.conf`) so the browser only ever talks to
  one origin and needs no CORS configuration in production.

The backend is also published on `localhost:8000` directly for debugging (`curl
localhost:8000/api/config`).

## Known limitations

- **Temporal / durable runtime**: Scenario 4's `use_temporal` path requires a running Temporal
  server (`temporal server start-dev`) and is not exercised by default; the local HITL mock above is
  what runs when `use_temporal` is left `false`. The SDK's Temporal runtime does not yet drive hooks
  (`before_superstep`/`after_superstep`) at all — that wiring is a later SDK phase — so a real
  Temporal-backed HITL pause/resume is out of scope for this dashboard today.

### Scenario 4 (HITL) reject — how it actually halts the run

`LocalHITLMiddleware.before_superstep` raises `korchestrator.exceptions.GovernanceHaltError` when
the operator rejects. The SDK's `HookRegistry` lets specifically that exception type propagate out
of `before_superstep` (every other exception from any hook stays isolated, as before); the Pregel
kernel's `PregelRunner.run` catches it and halts the run immediately with
`RunStatus.GOVERNANCE_PAUSED` — the run does not keep computing in the background. This wiring was
added to `korchestrator.core.pregel` / `korchestrator.services.hooks` as part of this dashboard's
integration work; see `docs/adr/` for the decision record and `tests/unit/core/test_pregel.py`,
`tests/unit/services/test_hooks.py`, `tests/unit/services/test_run.py` for the tests that pin it.
