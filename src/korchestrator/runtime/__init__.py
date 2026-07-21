"""Adapter layer.

Allowed imports (beyond stdlib + pydantic): core, interfaces, models, config, exceptions,
logging; temporalio lazy in temporal_runtime.py only ([temporal] extra). Implements
IDurableRuntime twice: in-process local_runtime and durable temporal_runtime.
"""

__all__: list[str] = []
