"""Tests for the researcher router: no network, no OPENAI_API_KEY (T1/T4).

Uses httpx.ASGITransport (this router has no HITL gate or multi-agent fan-in, the two things
that made that transport unreliable for the other two routers this session — a single agent, no
concurrent to_thread nesting beyond one level, behaves fine here).
"""

import json
import os

import httpx

from main import app  # noqa: E402 — main.py's load_dotenv() runs on this import

# main.py's load_dotenv() (triggered by the import above) reloads these from .env if set there —
# popping *before* the import stops working the moment real keys are added to .env, since the
# reload happens after (see test_support_escalation_router.py for the first time this bit us).
# Pop here, after import, so this suite reliably stays offline (T1/T4) regardless of .env.
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("LANGSMITH_API_KEY", None)
os.environ.pop("LANGCHAIN_API_KEY", None)
os.environ.pop("KCG_API_KEY", None)


async def _ask(question: str | None = None, model: str | None = None) -> list[dict]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body: dict = {}
        if question is not None:
            body["question"] = question
        if model is not None:
            body["model"] = model
        response = await client.post("/api/swarm/researcher/run", json=body)
        assert response.status_code == 200
        run_id = response.json()["run_id"]

        events: list[dict] = []
        async with client.stream(
            "GET", f"/api/swarm/researcher/stream/{run_id}", timeout=20
        ) as stream:
            assert stream.status_code == 200
            async for line in stream.aiter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:") :])
                events.append(event)
                if event["name"] == "run_completed":
                    break
        return events


def test_researcher_answers_offline() -> None:
    import asyncio

    events = asyncio.run(asyncio.wait_for(_ask(), timeout=25))
    terminal = events[-1]
    assert terminal["name"] == "run_completed"
    assert terminal["payload"]["status"] == "completed"
    assert terminal["payload"]["answer"]


def test_researcher_custom_question_and_model_accepted() -> None:
    import asyncio

    events = asyncio.run(
        asyncio.wait_for(_ask("What is 2 + 2?", "gpt-4o-custom"), timeout=25)
    )
    terminal = events[-1]
    assert terminal["payload"]["status"] == "completed"


def test_unknown_run_id_stream_returns_404() -> None:
    import asyncio

    async def _check() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/swarm/researcher/stream/does-not-exist")
            return response.status_code

    status_code = asyncio.run(asyncio.wait_for(_check(), timeout=10))
    assert status_code == 404
