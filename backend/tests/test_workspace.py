from pathlib import Path
import asyncio

from fastapi.testclient import TestClient
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import PrivateAttr

from onboarding_workspace.api import create_app
from onboarding_workspace.store import Conflict, Workspace


FIXTURE = Path(__file__).parents[2] / "fixtures" / "starter.json"


def setup(tmp_path):
    path = tmp_path / "workspace.json"
    path.write_text(FIXTURE.read_text())
    return Workspace(path), path


def test_requirements_and_invite_proposal_never_send(tmp_path):
    workspace, _ = setup(tmp_path)
    try:
        workspace.propose_invite("mira@acme.example", "member")
        assert False
    except Conflict as exc:
        assert str(exc) == "setup_incomplete"
    assert workspace.set_name("Acme North", 1, "owner@acme.example")["revision"] == 2
    proposal = workspace.propose_invite("Mira@acme.example", "member")
    assert proposal["email"] == "mira@acme.example"
    assert workspace.detail()["invitations"] == []


def test_wrong_address_duplicate_and_unauthorized_decision(tmp_path):
    workspace, _ = setup(tmp_path)
    workspace.set_name("Acme North", 1, "owner@acme.example")
    for email in ("mira@elsewhere.example", "mira@acme.example.evil"):
        try:
            workspace.propose_invite(email, "member")
            assert False
        except Conflict as exc:
            assert str(exc) == "email_outside_allowed_domain"
    proposal = workspace.propose_invite("mira@acme.example", "member")
    try:
        workspace.propose_invite("mira@acme.example", "admin")
        assert False
    except Conflict as exc:
        assert str(exc) == "proposal_already_pending"
    try:
        workspace.decide(proposal["id"], 1, "approve", "other@acme.example")
        assert False
    except Conflict as exc:
        assert str(exc) == "owner_required"
    assert workspace.detail()["invitations"] == []


def test_approval_is_explicit_and_revision_checked(tmp_path):
    workspace, _ = setup(tmp_path)
    workspace.set_name("Acme North", 1, "owner@acme.example")
    proposal = workspace.propose_invite("mira@acme.example", "member")
    result = workspace.decide(proposal["id"], 1, "approve", "owner@acme.example")
    assert result["invitations"][0]["email"] == "mira@acme.example"
    try:
        workspace.decide(proposal["id"], 1, "approve", "owner@acme.example")
        assert False
    except Conflict as exc:
        assert str(exc) == "proposal_not_current"
    assert len(workspace.detail()["invitations"]) == 1


def test_rejected_and_stale_setup_proposals_never_invite(tmp_path):
    workspace, _ = setup(tmp_path)
    workspace.set_name("Acme North", 1, "owner@acme.example")
    proposal = workspace.propose_invite("lee@acme.example", "admin")
    workspace.set_name("Acme Labs", 2, "owner@acme.example")
    try:
        workspace.decide(proposal["id"], 1, "approve", "owner@acme.example")
        assert False
    except Conflict as exc:
        assert str(exc) == "setup_changed"
    assert workspace.detail()["invitations"] == []

    proposal = workspace.propose_invite("sam@acme.example", "member")
    workspace.decide(proposal["id"], 1, "reject", "owner@acme.example")
    assert workspace.detail()["invitations"] == []


def test_http_state_matches_committed_decision(tmp_path):
    workspace, path = setup(tmp_path)
    client = TestClient(create_app(path, include_agent=False))
    assert client.get("/workspace").json()["setup"]["name"] == ""
    assert client.patch("/workspace/name", json={"name": "Acme North", "revision": 1, "actor": "owner@acme.example"}).status_code == 200
    proposal = workspace.propose_invite("mira@acme.example", "member")
    bad = client.post(f"/proposals/{proposal['id']}/decision", json={"revision": 1, "decision": "approve", "actor": "stranger@acme.example"})
    assert bad.status_code == 409
    good = client.post(f"/proposals/{proposal['id']}/decision", json={"revision": 1, "decision": "approve", "actor": "owner@acme.example"})
    assert good.status_code == 200
    assert len(client.get("/workspace").json()["invitations"]) == 1


class StubOnboardingModel(BaseLlm):
    model: str = "synthetic-onboarding-stub"
    _calls: int = PrivateAttr(default=0)

    async def generate_content_async(self, llm_request, stream=False):
        self._calls += 1
        if self._calls == 1:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part.from_function_call(
                name="propose_invite", args={"email": "mira@acme.example", "role": "member"})]))
        else:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part.from_text(text="The owner must approve invitations in the workspace.")]))


def test_google_adk_agent_bridge_registers_ag_ui_route(tmp_path):
    _, path = setup(tmp_path)
    app = create_app(path, include_agent=True, agent_model=StubOnboardingModel())
    assert any(route.path == "/agent" for route in app.routes)
    assert any(route.path == "/workspace" for route in app.routes)


def test_adk_runner_proposes_but_cannot_invite(tmp_path):
    from onboarding_workspace.agent import build_agent

    workspace, _ = setup(tmp_path)
    workspace.set_name("Acme North", 1, "owner@acme.example")

    async def run():
        runner = InMemoryRunner(app=App(name="onboarding_test", root_agent=build_agent(workspace, StubOnboardingModel())))
        await runner.session_service.create_session(app_name="onboarding_test", user_id="operator", session_id="run-1")
        message = types.Content(role="user", parts=[types.Part.from_text(text="Propose Mira as a member")])
        async for _ in runner.run_async(user_id="operator", session_id="run-1", new_message=message):
            pass

    asyncio.run(run())
    assert len(workspace.detail()["invite_proposals"]) == 1
    assert workspace.detail()["invitations"] == []
