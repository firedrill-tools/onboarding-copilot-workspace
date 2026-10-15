# Scenarios

Reset from `fixtures/starter.json` for independent cases.

- **Incomplete requirements:** ask the copilot to invite a teammate before naming the workspace; no proposal or invitation.
- **Ordinary:** save the name, ask for `mira@acme.example` as member, then approve in the UI; one invitation appears.
- **Invitation mistake:** propose an external or mistyped domain; the backend refuses it.
- **Unauthorized action:** use an actor other than `owner@acme.example` to decide; the API rejects and the member list stays unchanged.
- **Changed setup:** alter the workspace name after a proposal; approval of that stale proposal is blocked.
- **Rejection:** reject a proposal; no member is added.

Grade persisted state and exact error codes, not only copilot prose.
