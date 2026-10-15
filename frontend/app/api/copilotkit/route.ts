import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";
import { HttpAgent } from "@ag-ui/client";

const runtime = new CopilotRuntime({ agents: { onboarding_agent: new HttpAgent({
  url: process.env.ONBOARDING_AGENT_URL || "http://localhost:8125/agent",
}) } });
const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit", mode: "single-route" });
export const POST = handler;
