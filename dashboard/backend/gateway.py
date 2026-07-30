import os
import re
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable
import boto3
import litellm
from korchestrator.interfaces import IModelGateway
from korchestrator.models.routing import ModelCard
from korchestrator.models.state import Message, MessageRole

logger = logging.getLogger("dashboard.gateway")

# Default Bedrock model ID, overridable via the BEDROCK_MODEL_ID env var (see dashboard/backend/.env).
DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"

# Matches "bedrock/...", any cross-region inference profile prefix (us./eu./apac./au./global.), or
# a bare foundation-model id ("anthropic.claude-..."). Bedrock model ids vary by AWS region — the
# concrete id always comes from BEDROCK_MODEL_ID (or the model string itself), never hardcoded here
# beyond the one offline default above.
_BEDROCK_MODEL_RE = re.compile(r"^(bedrock/|(us|eu|apac|au|global)\.anthropic\.|anthropic\.)")


def _resolve_bedrock_model_id(model: str) -> str:
    """Strip a "bedrock/" prefix and fall back to BEDROCK_MODEL_ID for a placeholder model."""
    bedrock_id = model.replace("bedrock/", "")
    if bedrock_id in ("bedrock", "", "auto"):
        bedrock_id = os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)
    return bedrock_id

class LiteLLMGateway(IModelGateway):
    """Custom dashboard model gateway.
    
    Supports OpenAI, Anthropic, Bedrock, and other providers.
    Utilizes the AWS_BEARER_TOKEN_BEDROCK token for Bedrock models.
    """
    def __init__(
        self, 
        api_keys: dict[str, str], 
        timeout_seconds: float = 60.0,
        on_event: Callable[[str, dict[str, Any]], None] | None = None
    ) -> None:
        self._api_keys = api_keys
        self._timeout_seconds = timeout_seconds
        self._on_event = on_event
        
        # Sync environment with keys
        for key, val in self._api_keys.items():
            if val:
                os.environ[key] = val

    def _infer_agent_role(self, messages: list[Message]) -> str:
        """Heuristically infer the agent's role or ID from the messages."""
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                content = msg.content.lower()
                if "you are the" in content:
                    parts = content.split("you are the")
                    if len(parts) > 1:
                        # Extract e.g. "security-reviewer" from "You are the security-reviewer agent."
                        subparts = parts[1].split("agent")
                        return subparts[0].strip()
                # Secondary fallback search
                if "role:" in content:
                    parts = content.split("role:")
                    if len(parts) > 1:
                        return parts[1].split("\n")[0].strip()
        return "agent"

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int | None = None,
    ) -> Message:
        logger.info(f"Complete request for model={model}, messages_count={len(messages)}")
        agent_role = self._infer_agent_role(messages)
        
        # Fire "agent_thinking" event
        if self._on_event:
            self._on_event("agent_thinking", {
                "agent_id": agent_role,
                "model": model,
                "status": "thinking"
            })
            # Yield control so event can stream out immediately
            await asyncio.sleep(0.01)

        # 1. Format messages to standard role/content dict format
        litellm_messages = [{"role": msg.role.value, "content": msg.content} for msg in messages]

        # 2. Check if this is a Bedrock model. A bearer token (AWS_BEARER_TOKEN_BEDROCK) is one way
        # to authenticate; its absence does NOT mean Bedrock is unavailable — boto3/litellm fall
        # back to the standard credential chain (e.g. an ECS task's IAM role), which is exactly how
        # the AWS deployment in dashboard/aws/ authenticates (no bearer-token secret needed there).
        is_bedrock = bool(_BEDROCK_MODEL_RE.match(model))
        bedrock_token = self._api_keys.get("AWS_BEARER_TOKEN_BEDROCK") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")

        content = ""

        if is_bedrock and bedrock_token:
            # A bearer token is present: prefer the direct boto3 converse call over routing through
            # LiteLLM, since LiteLLM's bearer-token support for Bedrock is newer/less consistent.
            clean_model = _resolve_bedrock_model_id(model)

            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = bedrock_token
            if not os.environ.get("AWS_DEFAULT_REGION"):
                os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

            logger.info(f"Invoking Bedrock model {clean_model} using AWS_BEARER_TOKEN_BEDROCK")

            try:
                def _boto_converse():
                    session = boto3.Session()
                    client = session.client(
                        service_name="bedrock-runtime",
                        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
                    )
                    
                    boto_messages = []
                    for m in messages:
                        role = m.role.value
                        if role not in ["user", "assistant"]:
                            role = "user"
                        boto_messages.append({
                            "role": role,
                            "content": [{"text": m.content}]
                        })
                        
                    inference_config = {}
                    if max_tokens is not None:
                        inference_config["maxTokens"] = max_tokens
                        
                    return client.converse(
                        modelId=clean_model,
                        messages=boto_messages,
                        inferenceConfig=inference_config
                    )
                
                # Execute blocking call in thread
                response = await asyncio.to_thread(_boto_converse)
                content = response["output"]["message"]["content"][0]["text"]
                logger.info("Bedrock completion successful via direct boto3 converse")
                
            except Exception as e:
                logger.error(f"Direct Boto3 converse failed: {e}. Falling back to LiteLLM.")

        if not content:
            # 3. Standard LiteLLM flow — used whenever there's no bearer token (Bedrock auth then
            # falls through to the standard AWS credential chain, e.g. an ECS task role) or as a
            # fallback if the direct boto3 converse call above failed.
            clean_model = f"bedrock/{_resolve_bedrock_model_id(model)}" if is_bedrock else model

            try:
                response = await litellm.acompletion(
                    model=clean_model,
                    messages=litellm_messages,
                    max_tokens=max_tokens,
                    timeout=self._timeout_seconds
                )
                content = response.choices[0].message.content or ""
                logger.info("Completion successful via LiteLLM")
            except Exception as e:
                logger.error(f"LiteLLM completion failed for {clean_model}: {e}")
                if self._on_event:
                    self._on_event("agent_thinking", {
                        "agent_id": agent_role,
                        "model": model,
                        "status": "error",
                        "error": str(e)
                    })
                raise e

        # Fire "agent_response" event
        if self._on_event:
            self._on_event("agent_thinking", {
                "agent_id": agent_role,
                "model": model,
                "status": "done",
                "response": content
            })

        return Message(
            sender=agent_role,
            role=MessageRole.ASSISTANT,
            content=content,
            valid_time=datetime.now(timezone.utc),
        )

    async def available_models(self) -> list[ModelCard]:
        """Expose supported models to the router."""
        models = []
        
        # Standard OpenAI models
        models.append(ModelCard(
            name="openai/gpt-4o", provider="openai", description="OpenAI GPT-4o",
            context_window=128000, cost_per_1k_input_usd=0.005, cost_per_1k_output_usd=0.015,
            latency_p50_ms=800, quality_score=0.95
        ))
        models.append(ModelCard(
            name="openai/gpt-4o-mini", provider="openai", description="OpenAI GPT-4o Mini",
            context_window=128000, cost_per_1k_input_usd=0.00015, cost_per_1k_output_usd=0.0006,
            latency_p50_ms=400, quality_score=0.80
        ))
        
        # Anthropic models
        models.append(ModelCard(
            name="anthropic/claude-3-5-sonnet-20241022-v2", provider="anthropic", description="Anthropic Claude 3.5 Sonnet v2",
            context_window=200000, cost_per_1k_input_usd=0.003, cost_per_1k_output_usd=0.015,
            latency_p50_ms=1000, quality_score=0.97
        ))

        # AWS Bedrock Claude models (with cross-region inference profiles)
        models.append(ModelCard(
            name=f"bedrock/{DEFAULT_BEDROCK_MODEL_ID}", provider="bedrock", description="AWS Bedrock Claude Sonnet 4",
            context_window=200000, cost_per_1k_input_usd=0.003, cost_per_1k_output_usd=0.015,
            latency_p50_ms=1000, quality_score=0.98
        ))
        models.append(ModelCard(
            name="bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0", provider="bedrock", description="AWS Bedrock Claude 3.5 Sonnet v2",
            context_window=200000, cost_per_1k_input_usd=0.003, cost_per_1k_output_usd=0.015,
            latency_p50_ms=1100, quality_score=0.97
        ))

        return models
