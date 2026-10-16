# Customer onboarding copilot workspace

A Next.js/CopilotKit workspace and Google ADK agent share the same committed synthetic setup, review queue and invitation records. Chat can read requirements and propose an exact recipient/role. A separate owner action approves or rejects a proposal. No email or invitation service is connected; an actor email is a fixture identity without production authentication.

## Run locally

Python 3.12+, uv, Node 22+ and npm are required. No model key is needed for setup or owner review.

```sh
cd backend
uv sync --locked --extra test
uv run onboarding-workspace datasets
uv run onboarding-workspace init --workspace run-output/workspace.json --case incomplete-setup
uv run onboarding-workspace serve --workspace run-output/workspace.json --offline
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Save a workspace name, then review actual API proposals and invitations. For real chat, set GOOGLE_API_KEY and an enabled GEMINI_MODEL in the backend shell and omit --offline. The frontend proxies its actual HttpAgent through `/api/copilotkit` to `/agent`. Missing configuration produces a private failed receipt; there is no model fallback. `.env.example` lists explicit configuration; export backend variables yourself. No paid provider was used to qualify this example.

Model-free `workspace` reads source/seed provenance; `reset --destination NEW_PATH` creates a fresh UUID instance while preserving the old workspace, metadata, mutex and evidence. Initialization is exclusive: collisions, corrupt state or missing authority metadata are rejected without repair. Interrupted multi-file initialization may leave partial private files; choose a fresh destination. Commands also work as `python -m onboarding_workspace` and from installed backend wheel/sdist outside checkout.

## Data and control boundary

`backend/data/index.json` contains onboarding-populations1.0.0, twelve coherent starter/busy/ambiguous/boundary cases pinned by SHA256. Busy has100 proposals,64 imported invitations,24 pending and12 rejected decisions with ordered synthetic audit history. Alternate domain, stale proposal, duplicate/owner/external recipient, Unicode/hostile name and maximum safe revision cover different workflows. Imported history describes the original seed; subsequent owner edits are current state. Prior model, human authentication and email evidence remain unknown. Dataset/task/provenance labels stay outside model context.

Strict schemas reject unknown fields, ambiguous JSON, unsupported roles and boolean revisions. A proposal binds its original recipient/role and complete source setup by hash. Separate owner decisions capture the reviewed proposal hash/revision and current setup; approval rechecks original/current recipient, role, domain, owner and duplicates. Stale proposals may be rejected. A persistent SQLite mutex serializes cooperating local processes, with source hash/inode and UUID instance checks before atomic writes. Uncooperative writers are outside an OS boundary; legacy state without UUID lacks a cross-reset guarantee.

The UI follows API revisions, preserves dirty edits against concurrent changes, surfaces readable validation/owner/chat errors and blocks writes while reads are unavailable. Queue search and bounded lists support busy history. CopilotKit's public slots expose accessible Send/Stop controls. Markdown passes through public sanitizer/math plugins with KaTeX0.18.2, trust disabled; malformed math stays readable. No vendor code/cache is patched.

## Owned ADK/Gemini runtime

The application owns an actual ADK session/runner for each operation and uses the official ag-ui-adk EventTranslator/EventEncoder. It avoids that pinned adapter's process-global SessionManager, which ignored a second supplied session service. Explicit Developer API Gemini SDK and async HTTP clients use no environment proxies, redirects or retries. Original STOP JSON, strict arguments and one allowed function per turn are checked before eager SDK tools execute. An actual current workspace read is required before a proposal; no model approval/send tool exists. Caller assistant/state/tool claims cannot create server history or permissions.

Limits: four active runs,32 threads/eight completed turns,512 attempted run IDs,8 prepared HTTP calls,4096 requested output tokens per call,30-second HTTP and120-second operation budget. Duplicate runs/active-thread overlaps are rejected. Cancellation/shutdown drains owned tasks and attempts session/runner/SDK/HTTP cleanup once. Terminal answer and RunFinished follow verified translation, final source reread, evidence and cleanup; partial proposals stay pending after later failure.

Private0700 UUID run directories and0600 receipts retain original source bytes/hash, requests/responses/unknown fields, original provider identities and observed/unknown/invalid/zero usage, SDK events, actual tools, protocol preparation and cleanup. Cost is unknown. SDK-generated IDs are distinguished from absent original IDs. Prepared delivery is not client acknowledgement. Decoded caps apply after buffering, and synchronous source/filesystem work can delay deadlines; these are not hard wire/heap/OS limits.

## Verify and distribute

```sh
cd backend
uv run --locked pytest -q
uv build
cd ..
backend/.venv/bin/python scripts/build_datasets.py --check
cd frontend
npm ci
npm run typecheck
NEXT_PUBLIC_ONBOARDING_API_URL=http://127.0.0.1:38125 npm run build
npx playwright install chromium
npm run test:browser
cd ..
backend/.venv/bin/python scripts/package_source.py
backend/.venv/bin/python scripts/check_distribution.py
```

82 backend checks and12 production Chromium flows cover actual pinned Gemini SDK over owned loopback HTTP, AG-UI, CopilotKit chat, separate approval/rejection, busy/alternate populations, stale UI/API state, errors, stop/recovery, malformed math and unsafe markup. Test provider responses are controlled, not semantic model evidence. `check_distribution.py` installs locked wheel/sdist and the complete source outside checkout, exercises installed native/API/CLI paths and every case, then repeats the full backend/browser suite and verifies unchanged delivered files and byte-identical archives. CI retains backend distributions, deterministic source/manifest, qualification and browser screenshots. Backend sdist alone does not include the frontend; the complete source archive does.

See [PLAN.md](PLAN.md), [COMPATIBILITY.md](COMPATIBILITY.md) and [scenarios](scenarios/README.md). Actual enabled Gemini/model semantics/billing, qualified new Firedrill persistent scenarios and publication/license remain external gates. No license is granted pending publication decisions. [Example catalog](https://github.com/firedrill-tools/firedrill-example-catalog), [Firedrill](https://firedrill.run/) and [official documentation](https://docs.firedrill.run/) provide portfolio context; matching release qualification is required.
