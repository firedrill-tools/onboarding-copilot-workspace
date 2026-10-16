"""Strict synthetic setup, reviewed invitation and decision authority."""

from __future__ import annotations
import hashlib
import json
import re
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

MAX = 2**53 - 1
Id = Annotated[str, StringConstraints(min_length=1, max_length=160)]
Revision = Annotated[int, Field(ge=1, le=MAX)]
Email = Annotated[
    str,
    StringConstraints(
        max_length=254,
        pattern=r"^[a-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.example$",
    ),
]


class Strict(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", revalidate_instances="always"
    )


class Setup(Strict):
    id: Id
    name: Annotated[str, StringConstraints(max_length=60)]
    region: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    plan: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    owner_email: Email
    allowed_domain: Annotated[
        str,
        StringConstraints(
            min_length=9,
            max_length=240,
            pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.example$",
        ),
    ]
    revision: Revision

    @model_validator(mode="after")
    def coherent(self):
        if (
            not self.id.strip()
            or not self.region.strip()
            or not self.plan.strip()
            or self.name
            and (len(self.name.strip()) < 3 or self.name != self.name.strip())
        ):
            raise ValueError("invalid setup text")
        if self.owner_email.split("@")[1] != self.allowed_domain:
            raise ValueError("owner/domain differ")
        return self


class Decision(Strict):
    kind: Literal["synthetic_owner_decision"]
    actor: Email
    action: Literal["approve", "reject"]
    proposal_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    proposal_revision: Revision
    decision_setup: Setup


class Proposal(Strict):
    id: Id
    email: Email
    role: Literal["member", "admin"]
    setup_revision: Revision
    revision: Revision
    status: Literal["pending", "approved", "rejected"]
    decision_actor: Email | None
    source_setup: Setup
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    decision: Decision | None = None


class Invitation(Strict):
    id: Id
    proposal_id: Id
    email: Email
    role: Literal["member", "admin"]


class Audit(Strict):
    action: Literal["set_name", "propose_invite", "decide"]
    actor: Email | None = None
    target: Id | None = None
    outcome: Literal["saved", "pending", "approved", "rejected"]


class State(Strict):
    synthetic: Literal[True]
    version: Literal[1]
    instance_id: (
        Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")] | None
    ) = None
    setup: Setup
    invite_proposals: Annotated[list[Proposal], Field(max_length=1000)]
    invitations: Annotated[list[Invitation], Field(max_length=256)]
    audit: Annotated[list[Audit], Field(max_length=4000)]

    @model_validator(mode="before")
    @classmethod
    def exact_header(cls, v):
        if (
            not isinstance(v, dict)
            or v.get("synthetic") is not True
            or type(v.get("version")) is not int
        ):
            raise ValueError("exact synthetic/version header required")
        return v


def canonical(v):
    return json.dumps(
        v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(v):
    return hashlib.sha256(canonical(v).encode()).hexdigest()


def proposal_digest(p):
    return digest(
        {k: p[k] for k in ("id", "email", "role", "setup_revision", "source_setup")}
    )


def validate_state(value):
    state = State.model_validate(value).model_dump()
    setup = state["setup"]
    proposals = {p["id"]: p for p in state["invite_proposals"]}
    if (
        len(proposals) != len(state["invite_proposals"])
        or len({i["id"] for i in state["invitations"]}) != len(state["invitations"])
        or len({i["email"] for i in state["invitations"]}) != len(state["invitations"])
    ):
        raise ValueError("duplicate proposal/invitation identity")
    pending = set()
    approved = set()
    for p in state["invite_proposals"]:
        source = p["source_setup"]
        if (
            not source["name"]
            or source["revision"] != p["setup_revision"]
            or p["email"].split("@")[1] != source["allowed_domain"]
            or p["email"] == source["owner_email"]
            or p["content_sha256"] != proposal_digest(p)
        ):
            raise ValueError("proposal differs from reviewed source")
        if p["status"] == "pending":
            if (
                p["decision_actor"] is not None
                or p["decision"] is not None
                or p["revision"] != 1
                or p["email"] in pending
            ):
                raise ValueError("invalid/duplicate pending proposal")
            pending.add(p["email"])
        else:
            d = p["decision"]
            action = "approve" if p["status"] == "approved" else "reject"
            if (
                not d
                or d["action"] != action
                or d["actor"] != p["decision_actor"]
                or d["proposal_sha256"] != p["content_sha256"]
                or d["proposal_revision"] + 1 != p["revision"]
            ):
                raise ValueError("decision differs from reviewed proposal")
            if d["actor"] != d["decision_setup"]["owner_email"]:
                raise ValueError("decision actor differs from captured owner")
            if p["status"] == "approved":
                if canonical(d["decision_setup"]) != canonical(source):
                    raise ValueError("approved setup differs from reviewed source")
                approved.add(p["id"])
    linked = set()
    for invitation in state["invitations"]:
        p = proposals.get(invitation["proposal_id"])
        if (
            not p
            or p["status"] != "approved"
            or p["email"] != invitation["email"]
            or p["role"] != invitation["role"]
            or p["id"] in linked
            or invitation["email"] == setup["owner_email"]
        ):
            raise ValueError("invitation differs from approved proposal")
        linked.add(p["id"])
    if linked != approved:
        raise ValueError("approved invitation history incomplete")
    for a in state["audit"]:
        if a["action"] != "set_name" and a["target"] not in proposals:
            raise ValueError("orphan audit proposal")
    return state
