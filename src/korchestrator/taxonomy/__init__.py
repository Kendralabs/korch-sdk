"""Cognitive layer (L2).

Allowed imports (beyond stdlib + pydantic): models, interfaces, exceptions. Classifies intent
and difficulty and holds agent descriptors for planning and routing.
"""

from korchestrator.taxonomy.classifier import TaxonomyClassifier
from korchestrator.taxonomy.descriptors import default_descriptors, descriptors_for_intent

__all__ = ["TaxonomyClassifier", "default_descriptors", "descriptors_for_intent"]
