"use client";
import {
  CopilotChat,
  CopilotChatAssistantMessage,
  CopilotChatInput,
  useAgent,
} from "@copilotkit/react-core/v2";
import { useEffect, useState, type ComponentProps } from "react";
import { defaultRehypePlugins } from "streamdown";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import rehypeKatex from "rehype-katex";
const plugins: ComponentProps<
  typeof CopilotChatAssistantMessage.MarkdownRenderer
>["rehypePlugins"] = [
  defaultRehypePlugins.raw,
  [
    rehypeSanitize,
    {
      ...defaultSchema,
      attributes: {
        ...defaultSchema.attributes,
        code: [["className", /^language-./, "math-inline", "math-display"]],
      },
    },
  ],
  [rehypeKatex, { trust: false, errorColor: "var(--color-muted-foreground)" }],
  defaultRehypePlugins.harden,
];
function AccessibleInput(props: ComponentProps<typeof CopilotChatInput>) {
  return (
    <CopilotChatInput
      {...props}
      sendButton={{
        "aria-label": props.isRunning ? "Stop response" : "Send message",
        title: props.isRunning ? "Stop response" : "Send message",
      }}
    />
  );
}

const AccessibleInputSlot = Object.assign(AccessibleInput, CopilotChatInput);

export function OnboardingChat() {
  const { agent, isReady } = useAgent({ agentId: "onboarding_agent" });
  const [error, setError] = useState("");
  useEffect(() => {
    const subscription = agent.subscribe({
      onRunInitialized: () => setError(""),
    });
    return () => subscription.unsubscribe();
  }, [agent]);
  return (
    <>
      {!isReady && <p role="status">Connecting to the onboarding copilot…</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {isReady && (
        <CopilotChat
          agentId="onboarding_agent"
          className="chat"
          input={AccessibleInputSlot}
          messageView={{
            assistantMessage: { markdownRenderer: { rehypePlugins: plugins } },
          }}
          onError={() =>
            setError(
              "The onboarding copilot could not complete this request. Check the current invitation queue and try again.",
            )
          }
        />
      )}
    </>
  );
}
