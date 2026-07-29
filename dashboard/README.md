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

## Known limitations

- **Scenario 4 (HITL) reject, local runtime**: `korchestrator.services.hooks.HookRegistry` isolates
  every exception raised from `before_superstep` (catch, log, continue — this is documented in
  `hooks.py`'s module docstring: the governance halt→pause wiring lands in a later SDK phase). The
  dashboard's `LocalHITLMiddleware` therefore cannot make the SDK itself abort a run. "Reject"
  publishes a terminal `cancelled` status to the UI and stops relaying further events, but the
  underlying `Swarm`/`Korch` computation keeps running to completion on its worker thread in the
  background (Python cannot forcibly interrupt synchronous code) — its result is just not surfaced.
  Approve works cleanly since it only needs to unblock, not cancel.
- **Temporal / durable runtime**: Scenario 4's `use_temporal` path requires a running Temporal
  server (`temporal server start-dev`) and is not exercised by default; the local HITL mock above is
  what runs when `use_temporal` is left `false`.

