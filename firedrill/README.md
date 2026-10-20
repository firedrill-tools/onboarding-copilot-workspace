# Simulate this agent with Firedrill

Firedrill is a simulation platform for AI agents. Your coding agent can prepare
and operate these simulations; the application and its model run in your own
repository or CI.

Start in the repository root, not inside `firedrill/`:

```sh
npx firedrill-run init
```

Authorize Firedrill and select a project/environment. Installation choices are
optional; skip them when using the locked `firedrill/` toolchain below. This setup
does not invoke the target agent or grant it access to real business accounts.

The optional execution toolchain pins released CLI/SDK **2.2.2**, Node 22+ (October 19, 2026). The existing Google ADK/Gemini/CopilotKit runtime remains separately locked.

## Prepare and run

From the workspace root:

```sh
(cd backend && uv sync --locked --extra test)
npm ci --prefix firedrill --ignore-scripts --no-audit --no-fund
node firedrill/node_modules/@firedrill-run/cli/bin/firedrill.mjs validate firedrill/scenario.json --json --non-interactive
```

Validation is offline. Human authorization/scope selection uses `npx firedrill-run init`; automation uses protected `FIREDRILL_TOKEN`, `FIREDRILL_PROJECT_ID`, `FIREDRILL_ENVIRONMENT_ID`. The app independently needs `GOOGLE_API_KEY` and enabled `GEMINI_MODEL` or recipe model parameter. With scope/provider budget authorized, use `node firedrill/simulate.mjs --preview` and then `node firedrill/simulate.mjs`.

The bounded sequential recipe initializes a private hash-bound onboarding workspace and invokes its actual `create_app` factory, normal `/agent` AG-UI handler and native ADK/Gemini runtime. No model, client or transport is injected. Ready-team and ambiguous-address use native chat; busy-team inspection calls the actual `/workspace` GET without creating a model runtime. This is an in-process ASGI callable seam, not a hosted/browser-flow claim. Existing owner approval, invitation decisions, source/revision validation and synthetic outbox gates remain separate. The model has proposal/read tools only; neither approval nor sending is a target action.

Before app work, `invocation.json` retains outer run/attempt/scenario IDs in private `.runs/firedrill/attempt-*`. Chat separately allocates unique application thread/run IDs and saves them before dispatch, retains original AG-UI response bytes and reads the original private native receipt by matching its exact thread/client-run identity. Success requires correlated RUN_FINISHED, no RUN_ERROR, a completed actual receipt and confirmed runtime closure; HTTP 200 alone is insufficient. Key failure is a retained failed receipt/RUN_ERROR with a nonzero target exit. Inspection is explicitly model-free. Earlier proposal effects and unknown outcomes remain inspectable; no rollback, remote cancellation/billing or delivery guarantee is inferred. New attempts never reset earlier state/journals. Paths/AG-UI files are local evidence, not uploaded platform artifacts.

Only explicit reviewed case/message and optional model are accepted. Current ID-only invocation excludes controller/assessment data; unsupported Tool bindings are rejected and operator/CI credentials are removed from child dispatch. Only business context reaches model tools. The adapter grants no operator approval or publication authority.

## MCP and recovery

Configure remote OAuth operator MCP at **https://mcp.firedrill.run/mcp** using [host setup](https://docs.firedrill.run/guides/coding-agents). MCP prepares, queues and inspects; the local SDK/CLI executes the command target. Host OAuth and execution login are separate. Use `--run BATCH_ID` to attach queued work, `--resume OPERATION_ID` after uncertainty, and `--result BATCH_ID` to read retained results. Preserve SDK journals and local evidence. These scripts retain public SDK diagnostics and whole-batch exit status; a new simulation starts new work.

CI and the fresh locked source archive run offline integration tests with actual committed workspace inspection and native missing-key boundary. They establish wiring and cleanup, not live model quality, platform persistence, or uploaded captures. The observation recipe defines no grader/gate. Authenticated persisted happy/negative runs, paid model quality/cost, and licensing remain separate gates.

References: [SDK](https://docs.firedrill.run/sdk/typescript), [command targets](https://docs.firedrill.run/guides/callbacks), [operator MCP](https://docs.firedrill.run/guides/control-mcp), [CI](https://docs.firedrill.run/guides/ci).

## Offline verification

After installing the application dependencies and locked integration toolchain,
run `npm test --prefix firedrill` to exercise the adapter checks. These checks are
optional for first use and call no paid model. The Node 22+ requirement above is
for the Firedrill clients; it does not lower any application runtime requirement
in the root README.
