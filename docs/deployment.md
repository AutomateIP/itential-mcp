# Platform Connectivity and Deployment Model

Guidance for connecting the Itential MCP server to a highly-available Itential
Platform deployment, and what that means for scaling the MCP server itself.

## Overview

Itential MCP maintains a **single connection to a single Itential Platform
host for the lifetime of the server process.** This is a deliberate,
one-to-one design: an MCP server instance is meant to represent one focused
capability surface, not a router or gateway between multiple backends. There
is no configuration option, and no plan to add one, for pointing a single
itential-mcp instance at more than one Itential Platform host.

## Recommended pattern: point at the platform's own load-balanced endpoint

If your Itential Platform deployment is already highly available — running
behind a load balancer, or as a multi-node cluster presenting a single
virtual hostname — configure itential-mcp's `platform.host` (or
`ITENTIAL_MCP_PLATFORM_HOST`) to point directly at that load-balanced
endpoint, exactly as you would for any other HTTP client of the platform.

```bash
ITENTIAL_MCP_PLATFORM_HOST="platform-lb.example.com"
```

Do not attempt to build multi-endpoint failover or load balancing into
itential-mcp itself, and do not run itential-mcp against individual backend
nodes with your own client-side failover logic. Platform-side high
availability is the platform's responsibility, and it works transparently
from itential-mcp's perspective — itential-mcp only ever sees "a platform
host," and whether that hostname resolves to a single node or a load-balanced
fleet is invisible at the HTTP client level.

### Why this works without sticky sessions

Itential Platform holds its own authenticated session/token state on the
backend, independent of which load-balanced node services a given request.
itential-mcp presents the same credential on every call; the platform's own
infrastructure is responsible for validating that credential consistently
regardless of which backend node answers. No client-side sticky-session
behavior is required for this to work correctly, and itential-mcp does not
implement any.

"One connection for the life of the process" does not mean the underlying
token is static for that entire duration. itential-mcp automatically
reauthenticates when the configured authentication TTL elapses
(`platform.ttl` / `ITENTIAL_MCP_PLATFORM_TTL`, disabled by default), so a
long-running server process does not need to be restarted to pick up a fresh
token. This reauthentication is transparent to callers and does not change
anything about the connectivity model above — it is a detail of how the one
long-lived connection maintains itself, not a departure from it.

This has been validated against a real load-balanced, highly-available
Itential Platform deployment with no errors or authentication issues
attributable to backend rotation.

## Connection and state model

Understanding what state itential-mcp holds — and where — is useful context
for both the platform-connectivity guidance above and for planning any
horizontal scaling of the MCP server itself:

- **One platform connection per process.** The platform client is created
  once when the server starts and reused for every request handled by that
  process. It is not re-created per request.
- **Configuration is loaded once and is immutable for the life of the
  process.** Config values cannot change without restarting the server.
- **No per-client or per-request state accumulates.** Any request can be
  served identically regardless of what earlier requests that process
  handled — there is no session cache, request history, or per-caller state
  kept between calls.

In short: itential-mcp is stateless *between requests*, but each running
process is a stateful, long-lived connection to its configured platform host
for as long as that process runs.

## Scaling itential-mcp itself

If you need to scale the MCP server for throughput or availability reasons —
separate from platform-side HA — you can run multiple itential-mcp instances
behind their own load balancer. Because request handling is stateless (see
above), any instance can correctly handle any request. Each instance
independently authenticates and holds its own connection to the same
configured platform host.

Two things are worth planning around when doing this:

- **Each instance is its own platform session.** Running N itential-mcp
  replicas means N independent authenticated connections to the platform,
  not one shared connection — plan platform-side session/connection limits
  accordingly.
- **A given client's transport connection is sticky to whichever instance
  accepted it.** A single stdio process, or a single long-lived HTTP/SSE
  connection, is served by one instance for its duration — same as any other
  stateless-per-request service with a persistent client connection. This
  does not require special handling; it's just not something a load balancer
  in front of multiple itential-mcp instances needs to account for beyond
  normal connection routing.

## What this guidance does not cover

Running one itential-mcp instance per *distinct* Itential Platform
environment (for example, separate production and staging platforms, or
multiple regional deployments) is a supported pattern — each instance is
simply configured with its own `platform.host` and credentials — but is
outside the scope of this document, which focuses on connecting to a single,
highly-available platform deployment.
