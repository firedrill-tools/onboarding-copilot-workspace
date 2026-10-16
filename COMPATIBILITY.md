# Qualification and compatibility

## Locked native stack

Python3.12; google-adk2.12.0, google-genai2.31.0, HTTPX0.28.1, Pydantic2.14.1, ag-ui-adk0.4.2, AG-UI protocol0.1.22, FastAPI0.141.1 and Uvicorn0.54.0. Frontend: Next16.4.1/React19.2.2, CopilotKit1.79.0, AG-UI client1.0.2, Playwright1.64.1, Streamdown1.6.11/rehype-katex7.0.1/rehype-sanitize6.0.0 and patched KaTeX0.18.2. Node22 CI and Node24 local qualification. Lockfiles are authoritative; no inferred compatibility with future versions.

KaTeX is pinned directly and overridden transitively after npm audit found inherited low-severity parser recursion advisories. Primary references: [KaTeX advisory](https://github.com/advisories/GHSA-238p-pmpm-9mq7) and [v0.18.2 release](https://github.com/KaTeX/KaTeX/releases/tag/v0.18.2). Current npm audit reports zero findings. Math uses the pinned Streamdown default double-dollar notation; sanitizer and trust=false remain enabled.

## Reproduced baseline and scope

Baseline2db3bb7b544cc29fbdfd0f55b9fe0216a8f05cb0 passed7 backend tests yet accepted HTTP revision=true/unknown fields and altered saved proposal recipient/unsupported owner role. Actual native SDK accepted a MAX_TOKENS function call and saved a proposal. Two actual ADKAgent adapters shared the first session service despite independent constructor arguments. The production UI retained an untouched old name after an API revision and rendered validation as [object Object]. These have explicit local reproductions and regression qualification.

Source/API checkpoint74842ec6c73e9936428e5751d17cb3629e0d4cea passed15 checks and CI38909252459. Native checkpoint6e1623e9119235eb31e15d87954eb132e5596e5c passed45 and CI38911070314. The current completed independent implementation adds strict raw HTTP JSON,12 hash-bound populations/private CLI, production UI/native chat and distribution qualification:82 backend plus12 production Chromium flows. Exact completed source commit/Linux run/artifact are recorded in the portfolio catalog after CI; do not infer completion from an earlier checkpoint.

The actual public ADK Runner/Gemini/EventTranslator and CopilotKit HttpAgent paths are used with owned transport, session and shutdown. Controlled responses qualify original completion/argument authority and lifecycle/protocol, not live Gemini semantic quality, pricing/billing, remote availability, human authentication or invitation delivery. SDK normalized counters/IDs remain separate from original evidence; cost is unknown. No package cache or global singleton is modified. Backend wheel/sdist include pinned data/original fixture and work outside checkout; complete source contains both backend and production frontend/browser checks.

82 backend checks include exact contracts/source/owner decisions, real independent process serialization, native completion refusals/ambiguity/replay, current read-before-write, original measurements, cancellation/deadline/recording/cleanup, final state after cleanup, all12 population/private CLI operations and imported history authority. Twelve browser flows include API requirements/name/proposal/approval, rejection/owner failure, stale dirty/untouched state, late polls, outages, native stop/recovery, math/markup and busy/alternate sources. Fresh distribution qualification repeats full checks under locked installs and verifies manifest files/modes/hashes, original delivered files after build/test and repeated source bytes.

## External gates

Actual enabled Gemini credentials/model/budget plus live semantic and billing review; qualified new Firedrill interface with saved scenarios/results; real connector/authentication accounts and publication/license. No live or Firedrill claim is inferred from controlled native tests. Model approval/send tools remain absent. All records and decisions are synthetic local JSON.
