# Agent notes

Preserve the strict split between ADK proposal tools and owner decisions. Never add a send or approval tool to the model. Keep `.example` addresses and fixture data synthetic. The UI must render the API's committed state; do not invent success states in the browser. Do not claim live Gemini or Firedrill execution from offline tests. Do not commit secrets, generated workspace files or frontend build output.

## Current Firedrill integration

Released CLI/SDK 2.2.2, current command invocation, remote operator MCP and recovery are documented in the root firedrill/README.md. Offline checks preserve actual ASGI/AG-UI state/native key behavior and separate owner decisions. Authenticated persisted runs and live quality/cost remain parked separately.
