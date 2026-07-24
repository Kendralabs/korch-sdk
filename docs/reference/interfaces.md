# Interfaces (ports)

The seams the SDK is built to swap. A port exists only where there's more than one real
implementation — one local, in-process default, and one Kendra-hosted or otherwise networked
alternative.

## ARI ports

Portability between the local default and a Kendra-hosted deployment.

::: korchestrator.IModelGateway

::: korchestrator.IDurableRuntime

::: korchestrator.IExecutionSandbox

::: korchestrator.IIdentityProvider

## Supporting protocols

::: korchestrator.interfaces.GraphRepository

::: korchestrator.interfaces.TenantStore

::: korchestrator.interfaces.BaseRouter

::: korchestrator.interfaces.AUBConnector

::: korchestrator.interfaces.Connector

::: korchestrator.interfaces.IToolInvoker
