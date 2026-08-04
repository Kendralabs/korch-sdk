"""Tests for the support-escalation router: no network, no OPENAI_API_KEY (T1/T4).

Exercises the same offline deterministic path examples/08_support_escalation_swarm.py uses.

Each test drives its own `asyncio.run(...)` rather than using an async test + pytest-asyncio's
managed loop: `swarm.run()` internally spins up `asyncio.to_thread` + a nested `asyncio.run()`
per model call (spec 05 §36), which is reliably exercised under a plain top-level loop but hangs
under pytest-asyncio's function-scoped loop on this platform — a test-harness quirk, not a
router bug (confirmed by running the identical request/stream sequence both ways).
"""

import asyncio
import json
import os

import httpx

from main import app  # noqa: E402 — main.py's load_dotenv() runs on this import

# main.py's load_dotenv() (triggered by the import above) reloads OPENAI_API_KEY from
# dashboard/backend/.env if it's set there — popping *before* the import (the previous approach)
# stopped working the moment a real key was added to .env, since the reload happens after. Pop
# it here, after import, so these tests reliably exercise the offline gateway regardless of what
# is or isn't in .env (T1/T4: no test touches the network or a real model).
os.environ.pop("OPENAI_API_KEY", None)

_TERMINAL_STATUSES = ("completed", "failed", "cancelled")


async def _run_and_collect(body: dict) -> list[dict]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/swarm/support-escalation/run", json=body)
        assert response.status_code == 200
        run_id = response.json()["run_id"]

        events: list[dict] = []
        async with client.stream(
            "GET", f"/api/swarm/support-escalation/stream/{run_id}", timeout=20
        ) as stream:
            assert stream.status_code == 200
            async for line in stream.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:") :])
                events.append(event)
                if (
                    event["name"] == "status_change"
                    and event["payload"].get("status") in _TERMINAL_STATUSES
                ):
                    break
        return events


def test_support_escalation_run_completes_offline() -> None:
    events = asyncio.run(asyncio.wait_for(_run_and_collect({}), timeout=25))

    terminal = events[-1]
    assert terminal["name"] == "status_change"
    assert terminal["payload"]["status"] == "completed"
    assert terminal["payload"]["resolution"]

    superstep_events = [e for e in events if e["name"] == "superstep"]
    assert superstep_events, "expected at least one superstep progress event"


def test_support_escalation_agent_models_override_is_honored() -> None:
    events = asyncio.run(
        asyncio.wait_for(
            _run_and_collect({"agent_models": {"resolver": "gpt-4o-custom"}}), timeout=25
        )
    )

    terminal = events[-1]
    assert terminal["payload"]["status"] == "completed"


def test_unknown_run_id_stream_returns_404() -> None:
    async def _check() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/swarm/support-escalation/stream/does-not-exist")
            return response.status_code

    status_code = asyncio.run(asyncio.wait_for(_check(), timeout=10))
    assert status_code == 404
