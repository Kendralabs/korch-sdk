# Backend image for the Korchestrator dashboard.
#
# Build context MUST be the repository root, not dashboard/backend/, so this stage can install
# the `korchestrator` SDK from source (it is not yet published to PyPI — see the root README's
# Installation section). Build via dashboard/docker-compose.yml, or directly:
#   docker build -f dashboard/backend/Dockerfile -t korchestrator-dashboard-backend .
FROM python:3.11-slim AS base

WORKDIR /app

# Install the SDK non-editable, from source, with every extra so the dashboard can exercise all
# four spec scenarios (dspy for the Architect, temporal for Scenario 4, mcp/routing/otel for
# completeness). This is a deliberately large layer; it changes only when src/ or pyproject.toml
# changes, so it caches well across dashboard-only rebuilds.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir '.[all]'

# The dashboard backend's own dependencies (FastAPI, LiteLLM, boto3, ...).
COPY dashboard/backend/requirements.txt ./dashboard-requirements.txt
RUN pip install --no-cache-dir -r ./dashboard-requirements.txt

# Only the two backend source files — never the whole dashboard/backend/ directory, so a local
# .env or __pycache__ can never end up in the image even if .dockerignore is ever bypassed.
COPY dashboard/backend/main.py dashboard/backend/gateway.py ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# No secrets are baked into the image. Provide AWS_BEARER_TOKEN_BEDROCK / OPENAI_API_KEY /
# ANTHROPIC_API_KEY / BEDROCK_MODEL_ID via the container's environment at run time (docker-compose
# env_file, an ECS task definition's secrets block, etc.) — see dashboard/backend/.env.example
# and dashboard/aws/README.md.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
