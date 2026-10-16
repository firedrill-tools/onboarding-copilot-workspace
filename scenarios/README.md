# Scenario coverage

Canonical onboarding-populations1.0.0 lives in backend/data/index.json with SHA256 81313d82136ecb36911798834c8df109c46c9658db004a50a9d475aad7cbe3aa. `scripts/build_datasets.py --check` reproduces the exact original bytes from the unchanged fixture. Do not feed expected outcomes/source labels/provenance to the target model.

| Profile | Cases | Business variation |
| --- | --- | --- |
| starter | incomplete-setup, ready-team, alternate-domain | Name requirements; fresh valid proposal; Cedar owner/domain |
| busy | busy-team | 100 proposals,64 imported invitations,24 pending,12 rejected; ordered history |
| ambiguous | ambiguous-address, stale-pending, already-invited | Ask for exact address; stale approval conflict/rejection; duplicate recipient |
| boundary | external-address, owner-address, unicode-name, hostile-source, maximum-revision | Domain/owner exclusions; Unicode/escaped source; exact JS-safe revision limit |

Backend checks initialize/read/reset every population outside checkout, run actual pinned native SDK against controlled original responses, and apply a separate synthetic owner decision where appropriate. Imported audit history establishes seed consistency and no prior authenticated human/model/email proof. Current owner edits remain separate from that original seed history. CLI initialization is exclusive, metadata is required, reset preserves old state/evidence and uses a new instance UUID.

Production Chromium runs twelve flows: untouched API name refresh, readable validation, actual requirements/name/native chat/proposal/separate approval, native outage/truncation/recovery, owner error/rejection across polls, dirty edit conflict/review, late read versus saved result, API outage/recovery, safe markdown/math/malformed input, native stop, busy search/approval preservation, and alternate owner/domain/hostile source. Controlled HTTP provider and reset controls exist only in the owned test harness; the product exposes no test reset routes.

Saved new Firedrill scenarios/results, live model semantics/billing and real invitation/authentication integrations remain parked external gates.
