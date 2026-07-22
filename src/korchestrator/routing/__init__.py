"""Cognitive layer (L2).

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions, logging;
[routing] extra (lazy) for semantic strategies. Selects a model per agent through strategies
behind one BaseRouter.

Public surface (spec 11 §154): ``BaseRouter`` (the supporting protocol, defined in ``interfaces``
and re-exported here as the documented import path — spec 07 §5), ``get_router``, and the routing
models (in ``korchestrator.models``). The concrete strategies are exported for composition.
"""

from korchestrator.interfaces import BaseRouter
from korchestrator.routing.algorithmic import AlgorithmicRouter
from korchestrator.routing.composite import CompositeRouter
from korchestrator.routing.explicit import ExplicitRouter, FallbackRouter
from korchestrator.routing.factory import get_router
from korchestrator.routing.model_cards import builtin_model_cards, load_model_cards
from korchestrator.routing.semantic import Embedder, SemanticRouter

__all__ = [
    "AlgorithmicRouter",
    "BaseRouter",
    "CompositeRouter",
    "Embedder",
    "ExplicitRouter",
    "FallbackRouter",
    "SemanticRouter",
    "builtin_model_cards",
    "get_router",
    "load_model_cards",
]
