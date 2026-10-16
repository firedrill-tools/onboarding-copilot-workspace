# Customer onboarding copilot workspace

A CopilotKit interface shows a synthetic team setup, committed member list, and invitation review queue. A Google ADK agent can inspect requirements and create an invitation proposal through an AG-UI bridge. The agent has no approval or invitation-send tool. Only a separate owner decision in the workspace records an invitation.

## Run locally

Requires Python 3.12+, `uv`, Node 22+, and npm.

```sh
cp fixtures/starter.json workspace.json
cd backend
uv sync --extra test
uv run pytest
ONBOARDING_OFFLINE=1 uv run python -m onboarding_workspace.api
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. Offline mode serves the real workspace API and approval UI without a model; chat requests require the live backend. For live chat, set `GOOGLE_API_KEY` and an enabled `GEMINI_MODEL`, then start the backend without `ONBOARDING_OFFLINE=1`. `ag-ui-adk` exposes the Google ADK agent to CopilotKit through `/agent`; the Next.js runtime proxies it at `/api/copilotkit`. A missing key is an error, not a simulated model.

## Control boundary

The seed starts with a missing workspace name. The owner first saves a name, then the copilot may propose an exact `@acme.example` teammate with role `member` or `admin`. Proposals appear in the review queue and **do not** add members. The owner can approve or reject; approval adds a single invitation to the local JSON workspace. The backend rechecks owner identity, proposal and setup revisions, allowed domain, and duplicates at decision time. The `actor` field is a synthetic demo identity, not production authentication. No email or third-party invitation service is called.

The UI polls the same state the API writes, so visible members and review decisions reflect committed data. Offline tests cover incomplete setup, malformed addresses, duplicate proposals, unauthorized decision, changed setup, rejection, and approval. Frontend typecheck/build and a local browser flow cover UI rendering and approval. These checks do not prove live Gemini behavior. A live model proof and the new Firedrill integration remain pending.

This private example intentionally has no license pending publication decisions. Versions are pinned in `backend/uv.lock` and `frontend/package-lock.json`.

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release; this repository records its current integration limits above.

## Source and API checkpoint

15 local backend checks now qualify strict bounded source/setup/contact/domain/role/proposal/decision/invitation/audit contracts, exact non-boolean API revisions and rejection of unknown fields. A proposed recipient/role and complete setup snapshot are bound by a stored content hash; the separate synthetic owner decision captures the reviewed hash and current owner setup. Saved proposal tampering, same-revision setup changes and unsupported roles cannot create invitations. Rejection can stop stale proposals. A persistent SQLite mutex serializes cooperating local processes, and actual independent-process approval produces one invitation. Uncooperative filesystem writers and arbitrary hostile processes are outside an OS boundary; legacy state without instance identity has no cross-reset guarantee. Previously saved proposals without immutable source/decision bindings are rejected without repair.

This is an intermediate source checkpoint. The baseline native ADK/Gemini path accepted a MAX_TOKENS function call and saved a proposal over controlled HTTP; original transport completion/lifecycle/measurements, normal AG-UI/browser chat, UI refresh/error behavior, rich datasets/private CLI and fresh distributions remain active in PLAN.md. Current source checks do not establish native completion safety or live Gemini semantics/billing. No paid provider or real invitation action was used.

## Owned native runtime checkpoint

45 backend checks now exercise actual pinned ADK2.12.0/GoogleGenAI2.31.0/HTTPX0.28.1/Pydantic2.14.1 through owned native Gemini JSON and the publicly exported ag-ui-adk0.4.2 EventTranslator/EventEncoder. The original MAX_TOKENS proposal dispatch is rejected before SDK/tool release. Unknown/refused/unfinished/parallel/mixed/forged-result/replayed content cannot save a proposal; one allowed function per turn, strict arguments and a genuine current read precede a write. A current setup change after that read returns a conflict without creating a proposal.

Each application runtime owns bounded thread history from genuine completed server-observed turns. Caller-supplied assistant/state claims and tools cannot create context or permissions. Every run owns/deletes an actual ADK session and closes its runner, explicit Gemini SDK and HTTP clients before terminal answer/RunFinished. This avoids the pinned ADKAgent wrapper's process-global session manager, which ignored a second explicitly supplied service. No vendor cache/singleton is patched/reset. Four simultaneous runs,32 threads/eight retained completed turns,512 attempted run IDs,8 prepared HTTP calls,4096 requested output tokens per call, zero SDK retries,30-second HTTP and120-second default operation budget are explicit bounds. Duplicate run IDs/active-thread overlap are rejected; failed operations require a fresh explicit run ID and reread actual state. Scope is a local synthetic owner session, not real authentication or hostile-process isolation.

Private UUID receipts record initial/final source bytes/hash, raw provider JSON/unknown fields, IDs/model/arguments/usage, SDK events, actual read/proposal effects, prepared protocol events and cleanup. Original observed/unknown/invalid/zero counters are separate from SDK defaults; cost is unknown. Missing original function IDs remain unknown even when ADK generates its own IDs. Errors after a proposal preserve its actual pending state; persistent evidence/close failures cannot report success. Client delivery of prepared events is not acknowledged. Decoded caps are after buffering, not hard wire/heap limits; synchronous source/filesystem work can delay budgets.

Normal in-process HTTP AG-UI protocol passes; production CopilotKit/browser chat, UI refresh/errors, richer populations/private CLI, fresh distributions and exact Linux proof remain active. Controlled provider responses do not establish live semantic quality, billing or real invitation delivery.
