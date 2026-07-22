"""Cognitive layer (L2).

Allowed imports (beyond stdlib + pydantic): core, interfaces, models, exceptions, logging, and
dspy (lazy, [dspy] extra). The DSPy reasoning layer: agent base, worker, architect, compiled
signatures.
"""

from korchestrator.agents.base import Agent
from korchestrator.agents.signatures import (
    ArchitectSignature,
    InputField,
    OutputField,
    Signature,
    WorkerSignature,
)
from korchestrator.agents.worker import WorkerAgent

__all__ = [
    "Agent",
    "ArchitectSignature",
    "InputField",
    "OutputField",
    "Signature",
    "WorkerAgent",
    "WorkerSignature",
]
