"""Kernel layer (L1), framework-free.

Allowed imports (beyond stdlib + pydantic): interfaces, models, exceptions, types, constants.
Runs the Pregel BSP kernel: graph, supersteps, reducers, activation and halting. No frameworks.
"""

from korchestrator.core.reducers import (
    Append,
    Delta,
    LastValue,
    MergeDict,
    Reducer,
    UniqueAppend,
)

__all__ = [
    "Append",
    "Delta",
    "LastValue",
    "MergeDict",
    "Reducer",
    "UniqueAppend",
]
