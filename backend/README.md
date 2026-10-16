# Onboarding workspace backend

Python 3.12+; pinned ADK/Gemini and official AG-UI EventTranslator. This backend package supports private model-free workspaces and the same synthetic API as the full example. It has no email/invitation vendor connection. An actor email is a fixture identity, without real authentication.

```sh
uv sync --locked --extra test
uv run onboarding-workspace datasets
uv run onboarding-workspace init --workspace run-output/workspace.json --case incomplete-setup
uv run onboarding-workspace workspace --workspace run-output/workspace.json
uv run onboarding-workspace reset --workspace run-output/workspace.json --destination run-output/fresh.json
uv run onboarding-workspace serve --workspace run-output/workspace.json --offline
```

Installed wheel/sdist work outside checkout. `python -m onboarding_workspace` and `python -m onboarding_workspace.api` expose the same CLI. Default command is `serve`, port8125; explicit `--workspace` or ONBOARDING_WORKSPACE_FILE chooses the source. Removing --offline registers real chat. Set GOOGLE_API_KEY and an enabled GEMINI_MODEL; ONBOARDING_GEMINI_BASE_URL is an explicit HTTPS or owned loopback endpoint. No model/key fallback is supplied. Missing keys produce private failed run receipts. The frontend in the complete workspace archive uses real CopilotKit HttpAgent/AG-UI; this backend distribution alone does not include that frontend.

Each run owns an ADK session/runner, Gemini SDK and HTTP clients; original STOP JSON/arguments precede tools. Model tools read/propose only; separate owner API decisions commit local invitation records. Budgets:8 prepared calls/4096 requested output/zero retries/30-second HTTP/120-second operation. Original counters and SDK values stay separate; cost is unknown. RunFinished follows terminal translation, evidence and cleanup; failures retain partial effects. Caps are not hard heap/wire/OS containment. Legacy sources without instance IDs lack a cross-reset guarantee. New dataset state has immutable authority metadata and UUID instance fencing; missing/corrupt source is rejected without repair.

The package includes twelve coherent hash-bound populations and the unchanged original fixture. Busy has100 proposals/64 imported invitations/24pending/12rejected, with ordered audit history and explicit lack of prior model/human-auth/email evidence. Source/task/fixture labels are excluded from target context. Full root README/PLAN/COMPATIBILITY, original generation scripts, frontend and production Chromium qualification are in the complete source archive. No paid model, real invitation delivery or qualified new Firedrill run is claimed; external gates remain parked. No license pending portfolio publication decision.
