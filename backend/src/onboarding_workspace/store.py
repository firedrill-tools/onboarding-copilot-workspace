"""Invitation proposal and approval boundary for one synthetic workspace."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class Conflict(Exception):
    pass


class Workspace:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.read()

    def read(self) -> dict:
        state = json.loads(self.path.read_text())
        if state.get("synthetic") is not True or state.get("version") != 1:
            raise ValueError("only synthetic version 1 workspace is supported")
        return state

    def _write(self, state: dict):
        fd, temp = tempfile.mkstemp(prefix=".onboarding-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(state, stream, indent=2)
                stream.write("\n")
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def detail(self) -> dict:
        return self.read()

    def set_name(self, name: str, expected_revision: int, actor: str) -> dict:
        state = self.read()
        setup = state["setup"]
        if actor != setup["owner_email"]:
            raise Conflict("owner_required")
        if setup["revision"] != expected_revision:
            raise Conflict("stale_setup_revision")
        name = name.strip()
        if not 3 <= len(name) <= 60:
            raise ValueError("workspace name must be 3 to 60 characters")
        setup["name"] = name
        setup["revision"] += 1
        state["audit"].append({"action": "set_name", "actor": actor, "outcome": "saved"})
        self._write(state)
        return setup

    def propose_invite(self, email: str, role: str) -> dict:
        state = self.read()
        setup = state["setup"]
        email = email.strip().lower()
        if not setup["name"]:
            raise Conflict("setup_incomplete")
        if not email.endswith("@" + setup["allowed_domain"]) or email.count("@") != 1:
            raise Conflict("email_outside_allowed_domain")
        if email == setup["owner_email"]:
            raise Conflict("owner_already_present")
        if role not in {"member", "admin"}:
            raise ValueError("role must be member or admin")
        if any(item["email"] == email for item in state["invitations"]):
            raise Conflict("already_invited")
        if any(item["email"] == email and item["status"] == "pending" for item in state["invite_proposals"]):
            raise Conflict("proposal_already_pending")
        proposal = {"id": f"P-{len(state['invite_proposals']) + 1}", "email": email, "role": role,
                    "setup_revision": setup["revision"], "revision": 1, "status": "pending", "decision_actor": None}
        state["invite_proposals"].append(proposal)
        state["audit"].append({"action": "propose_invite", "target": proposal["id"], "outcome": "pending"})
        self._write(state)
        return proposal

    def decide(self, proposal_id: str, revision: int, decision: str, actor: str) -> dict:
        state = self.read()
        setup = state["setup"]
        if actor != setup["owner_email"]:
            raise Conflict("owner_required")
        proposal = next((item for item in state["invite_proposals"] if item["id"] == proposal_id), None)
        if proposal is None:
            raise KeyError("unknown proposal")
        if proposal["status"] != "pending" or proposal["revision"] != revision:
            raise Conflict("proposal_not_current")
        if proposal["setup_revision"] != setup["revision"] or not setup["name"]:
            raise Conflict("setup_changed")
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        if decision == "approve":
            if not proposal["email"].endswith("@" + setup["allowed_domain"]):
                raise Conflict("email_outside_allowed_domain")
            if any(item["email"] == proposal["email"] for item in state["invitations"]):
                raise Conflict("already_invited")
            state["invitations"].append({"id": f"INV-{len(state['invitations']) + 1}",
                                          "proposal_id": proposal_id, "email": proposal["email"], "role": proposal["role"]})
        proposal["status"] = "approved" if decision == "approve" else "rejected"
        proposal["decision_actor"] = actor
        proposal["revision"] += 1
        state["audit"].append({"action": "decide", "target": proposal_id, "outcome": proposal["status"], "actor": actor})
        self._write(state)
        return {"proposal": proposal, "invitations": state["invitations"]}
