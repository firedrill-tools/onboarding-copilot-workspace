# Onboarding copilot development plan

## Goal
Complete the synthetic workspace setup UI and ADK/Gemini invitation proposal agent with separate owner decisions and API-backed committed browser state. Live Gemini semantics/billing, qualified new Firedrill and publication/license remain external gates. No real invitation service is connected.

## Reproduced baseline

At2db3bb7b544cc29fbdfd0f55b9fe0216a8f05cb0 the original7 backend checks passed, yet HTTP accepted revision=true plus an undeclared field, and altering saved proposal email/role committed another recipient with unsupported owner role. Actual ADK/Gemini accepted a MAX_TOKENS tool call and saved a proposal. Two ADKAgent adapters ignored the second supplied session service through a global singleton. Production Chromium found untouched name state stuck after an API revision and unreadable validation output. Private reproductions are recorded in COMPATIBILITY.md and the portfolio execution log.

## Tasks and evidence

1. **Complete: source/API decisions.** Strict source/setup/contact/domain/role/proposal/decision/invitation/audit contracts, exact non-boolean revisions and raw HTTP JSON, immutable proposal/source hash, captured separate owner decision and fresh final checks. Persistent cooperating-process mutex, atomic source/instance fencing and no silent repair. Source15 checkpoint74842ec passed CI38909252459.
2. **Complete: owned native bridge.** Actual ADK/Gemini/HTTP and official public AG-UI translator, original STOP/argument/usage authority before tools, current read-before-write, bounded calls/output/zero retry/cancellation/deadline, private partial/failure evidence, genuine scoped history and awaited session/runner/SDK/HTTP shutdown. Final state is read after cleanup. Native45 checkpoint6e1623e passed CI38911070314. No model approval/send tool or vendor singleton/cache patch.
3. **Complete: production UI behavior.** Dirty/untouched revision handling, readable persistent errors, unavailable reads block actions, actual CopilotKit chat/proposal and separate owner decisions, explicit accessible Send/Stop, public sanitizer/math path and patched KaTeX. Twelve production Chromium flows pass including busy/alternate data, rejection/errors, stale/late reads, stop/recovery and unsafe markup. Screenshots were visually inspected.
4. **Complete: rich data/private CLI.** Twelve hash-bound starter/busy/ambiguous/boundary populations. Busy has100proposals/64importedinvitations/24pending/12rejected with coherent ordered source audit. Exclusive private initialization/readback/reset preserves old source/evidence and fences new UUID; no model keys needed. Task/source labels are excluded from context. Current source edits remain separate from imported seed provenance.
5. **Local distribution complete; exact Linux proof next.** 82 backend checks and12 production Chromium flows pass from fresh locked wheel/sdist/complete source installs outside checkout. Locked backend wheel/sdist and complete source packaging exercise all twelve populations and installed native SDK over owned loopback HTTP, actual AG-UI/API and separate owner decision. Complete source repeats82 backend/12 production browser flows, npm-ci/typecheck/build, checks unchanged delivered files and repeated deterministic archive bytes. Exact completed commit/Linux run/artifact/catalog proof follows this fresh distribution gate.

## Completion rule

Mark independent project work complete only after the exact pushed source passes full fresh Linux distribution/native/browser CI and its retained source artifact matches local bytes. Record exact commit/run/artifact/hash in the catalog and master plan. Then continue #20/#23/#24/#25/#28/#29/#30/#33/#34/#35/#37/#38/#39. Overall portfolio goal remains active. External credentials/model semantics/billing, qualified Firedrill interface/saved runs, real connectors and publication/license remain parked.
