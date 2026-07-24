# Models

The typed data every public entry point accepts and returns — all frozen (`model_config =
ConfigDict(frozen=True)`), all in the compatibility surface (spec 05 §4): fields are never removed
or narrowed within a major version.

## Execution state

::: korchestrator.AgentState

::: korchestrator.StateUpdate

::: korchestrator.Message

::: korchestrator.RunStatus

## Results

::: korchestrator.RunResult

::: korchestrator.models.tool.ToolResult

## Agent configuration

::: korchestrator.models.agent.AgentConfig

::: korchestrator.models.agent.AgentPersona

## Planning

::: korchestrator.models.plan.ExecutionPlan

::: korchestrator.models.plan.TaskDecomposition

## Routing

::: korchestrator.models.routing.ModelCard

::: korchestrator.models.routing.TaskSemantics

::: korchestrator.models.routing.RoutingContext

::: korchestrator.models.routing.RoutingResult
