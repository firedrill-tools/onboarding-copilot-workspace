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
