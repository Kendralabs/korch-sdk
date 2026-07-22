"""Context layer (L3).

Allowed imports (beyond stdlib + pydantic): interfaces, models, config, exceptions. Compiles
execution context and extracts the Minimum Viable Context; prunes off the hot loop.
"""

from korchestrator.context.compiler import CompiledContext, ContextCompiler, Summarizer

__all__ = ["CompiledContext", "ContextCompiler", "Summarizer"]
