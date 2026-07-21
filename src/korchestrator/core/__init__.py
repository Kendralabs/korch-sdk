"""Kernel layer (L1), framework-free.

Allowed imports (beyond stdlib + pydantic): interfaces, models, exceptions, types, constants.
Runs the Pregel BSP kernel: graph, supersteps, reducers, activation and halting. No frameworks.
"""

from korchestrator.core.channels import ChannelSchema
from korchestrator.core.graph import AgentCallable, AgentGraph, Edge, Node
from korchestrator.core.pregel import Clock, PregelRunner
from korchestrator.core.reducers import (
    Append,
    Delta,
    LastValue,
    MergeDict,
    Reducer,
    UniqueAppend,
)

__all__ = [
    "AgentCallable",
    "AgentGraph",
    "Append",
    "ChannelSchema",
    "Clock",
    "Delta",
    "Edge",
    "LastValue",
    "MergeDict",
    "Node",
    "PregelRunner",
    "Reducer",
    "UniqueAppend",
]
