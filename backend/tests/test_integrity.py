import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from onboarding_workspace.api import create_app
from onboarding_workspace.store import Workspace, Conflict

FIXTURE = Path(__file__).parents[2] / "fixtures/starter.json"


def setup(tmp_path):
    file = tmp_path / "state.json"
    file.write_bytes(FIXTURE.read_bytes())
    w = Workspace(file)
    w.set_name("Acme North", 1, "owner@acme.example")
    return w, file


@pytest.mark.parametrize("field", ["email", "role", "source", "hash"])
def test_altered_reviewed_proposal_cannot_create_an_invitation_or_repair_source(
    tmp_path, field
):
    w, file = setup(tmp_path)
    p = w.propose_invite("mira@acme.example", "member")
    state = w.read()
    target = state["invite_proposals"][0]
    if field == "email":
        target["email"] = "other@acme.example"
    if field == "role":
        target["role"] = "owner"
    if field == "source":
        target["source_setup"]["name"] = "Changed"
    if field == "hash":
        target["content_sha256"] = "0" * 64
    file.write_text(json.dumps(state))
    before = file.read_bytes()
    with pytest.raises(ValueError):
        w.decide(p["id"], 1, "approve", "owner@acme.example")
    assert file.read_bytes() == before


def test_api_boolean_revisions_and_unknown_fields_cannot_change_state(tmp_path):
    w, file = setup(tmp_path)
    client = TestClient(create_app(file, include_agent=False))
    before = file.read_bytes()
    for body in (
        {"name": "Other", "revision": True, "actor": "owner@acme.example"},
        {
            "name": "Other",
            "revision": 2,
            "actor": "owner@acme.example",
            "undeclared": True,
        },
    ):
        assert client.patch("/workspace/name", json=body).status_code == 422
    assert file.read_bytes() == before
    p = w.propose_invite("mira@acme.example", "member")
    assert (
        client.post(
            f"/proposals/{p['id']}/decision",
            json={
                "revision": True,
                "actor": "owner@acme.example",
                "decision": "approve",
            },
        ).status_code
        == 422
    )
    assert not w.read()["invitations"]


def test_same_revision_setup_change_blocks_approval_but_rejection_still_stops_proposal(
    tmp_path,
):
    w, file = setup(tmp_path)
    p = w.propose_invite("mira@acme.example", "admin")
    state = w.read()
    state["setup"]["name"] = "Changed by owner"
    file.write_text(json.dumps(state))
    with pytest.raises(Conflict, match="setup_changed"):
        w.decide(p["id"], 1, "approve", "owner@acme.example")
    assert (
        w.decide(p["id"], 1, "reject", "owner@acme.example")["proposal"]["status"]
        == "rejected"
        and not w.read()["invitations"]
    )


def test_source_invalid_contact_domain_role_reference_and_duplicate_json_are_refused(
    tmp_path,
):
    w, file = setup(tmp_path)
    original = w.read()
    for kind in ("domain", "owner", "revision", "unknown", "orphan"):
        s = json.loads(json.dumps(original))
        if kind == "domain":
            s["setup"]["allowed_domain"] = "gmail.com"
        if kind == "owner":
            s["setup"]["owner_email"] = "owner@other.example"
        if kind == "revision":
            s["setup"]["revision"] = True
        if kind == "unknown":
            s["undeclared"] = True
        if kind == "orphan":
            s["invitations"] = [
                {
                    "id": "INV-1",
                    "proposal_id": "missing",
                    "email": "mira@acme.example",
                    "role": "admin",
                }
            ]
        file.write_text(json.dumps(s))
        with pytest.raises(ValueError):
            Workspace(file)
    file.write_text('{"synthetic":true,"synthetic":false}')
    with pytest.raises(ValueError, match="duplicate JSON"):
        Workspace(file)


def _approve(file, proposal):
    try:
        return Workspace(file).decide(proposal, 1, "approve", "owner@acme.example")
    except Conflict as error:
        return {"error": str(error)}


def test_independent_processes_approve_only_one_exact_invitation(tmp_path):
    w, file = setup(tmp_path)
    p = w.propose_invite("mira@acme.example", "member")
    with ProcessPoolExecutor(
        max_workers=2, mp_context=multiprocessing.get_context("spawn")
    ) as executor:
        results = [
            f.result(timeout=15)
            for f in [executor.submit(_approve, str(file), p["id"]) for _ in range(2)]
        ]
    assert (
        sum("proposal" in r for r in results) == 1 and len(w.read()["invitations"]) == 1
    )
    assert w.read()["invitations"][0]["role"] == "member"
