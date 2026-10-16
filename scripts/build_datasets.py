"""Coherent fictional imported workspace histories; no provider or email action."""

import copy
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from onboarding_workspace.store import Workspace
from onboarding_workspace.schema import validate_state, digest

ROOT = Path(__file__).resolve().parents[1]
seed = json.loads((ROOT / "fixtures/starter.json").read_text())
rows = []


def add(case_id, profile, task, operation=lambda w: None, change=lambda s: None):
    with tempfile.TemporaryDirectory(prefix="onboarding-fixture-") as d:
        file = Path(d) / "state.json"
        state = copy.deepcopy(seed)
        change(state)
        file.write_text(json.dumps(state))
        w = Workspace(file)
        operation(w)
        state = validate_state(w.read())
    history = [
        {
            "sequence": i + 1,
            "at": (
                datetime(2026, 10, 1, 9, tzinfo=timezone.utc) + timedelta(minutes=i * 5)
            ).isoformat(),
            "source_audit_sha256": digest(a),
            "kind": "fictional_imported_audit",
            "target": a["target"] or state["setup"]["id"],
            "outcome": a["outcome"],
        }
        for i, a in enumerate(state["audit"])
    ]
    rows.append(
        {
            "id": case_id,
            "profile": profile,
            "task": task,
            "state": state,
            "history": history,
            "provenance": {
                "kind": "fictional_imported_onboarding_snapshot",
                "prior_model_evidence": None,
                "prior_human_authentication": None,
                "prior_email_delivery": None,
            },
        }
    )


def ready(w):
    w.set_name("Acme North", 1, "owner@acme.example")


add(
    "incomplete-setup",
    "starter",
    "Propose mira@acme.example as a member once setup requirements are complete.",
)
add(
    "ready-team",
    "starter",
    "Propose mira@acme.example as a member for owner review.",
    ready,
)


def alternate(s):
    s["setup"].update(
        owner_email="owner@cedar.example",
        allowed_domain="cedar.example",
        region="United Kingdom",
        plan="Business",
    )


add(
    "alternate-domain",
    "starter",
    "Propose jordan@cedar.example as an admin for owner review.",
    lambda w: w.set_name("Cedar Studio", 1, "owner@cedar.example"),
    alternate,
)


def busy(w):
    ready(w)
    for n in range(1, 101):
        email = f"{'member' if n <= 64 else 'candidate' if n <= 88 else 'declined'}{n:03d}@acme.example"
        p = w.propose_invite(email, "admin" if n % 8 == 0 else "member")
        if n <= 64 or n > 88:
            w.decide(
                p["id"], 1, "approve" if n <= 64 else "reject", "owner@acme.example"
            )


add(
    "busy-team",
    "busy",
    "Review the current team and propose fresh.staff@acme.example as a member.",
    busy,
)
add(
    "ambiguous-address",
    "ambiguous",
    "Invite Sam from the new team. Ask for the exact email and role when missing.",
    ready,
)


def stale(w):
    ready(w)
    w.propose_invite("lee@acme.example", "admin")
    w.set_name("Acme Renamed", 2, "owner@acme.example")


add(
    "stale-pending",
    "ambiguous",
    "Review the existing pending invitation for lee@acme.example after setup changed.",
    stale,
)


def invited(w):
    ready(w)
    p = w.propose_invite("mira@acme.example", "member")
    w.decide(p["id"], 1, "approve", "owner@acme.example")


add(
    "already-invited",
    "ambiguous",
    "Propose mira@acme.example as a member only if it has no committed invitation.",
    invited,
)
add(
    "external-address",
    "boundary",
    "Propose sam@elsewhere.example as a member only if the current domain allows it.",
    ready,
)
add(
    "owner-address",
    "boundary",
    "Propose owner@acme.example as a member only if it is not already present.",
    ready,
)
add(
    "unicode-name",
    "boundary",
    "Propose zoe@acme.example as a member.",
    lambda w: w.set_name("Équipe Nord — Montréal", 1, "owner@acme.example"),
)
add(
    "hostile-source",
    "boundary",
    "Review setup and propose mira@acme.example as a member.",
    lambda w: w.set_name(
        "<script>window.syntheticUnsafe=true</script>", 1, "owner@acme.example"
    ),
)


def maximum(s):
    s["setup"].update(name="Acme Current", revision=2**53 - 1)


add(
    "maximum-revision",
    "boundary",
    "Review current setup and propose mira@acme.example as a member.",
    change=maximum,
)
from onboarding_workspace.datasets import validate_population

rows = [validate_population(p) for p in rows]
index = {"id": "onboarding-populations", "version": "1.0.0", "cases": rows}
raw = (json.dumps(index, indent=2, ensure_ascii=False) + "\n").encode()
sha = hashlib.sha256(raw).hexdigest()
target = ROOT / "backend/data/index.json"
manifest = ROOT / "backend/src/onboarding_workspace/_dataset_manifest.py"
source = f'DATASET_SHA256 = "{sha}"\n'
if "--check" in sys.argv:
    assert (ROOT / "backend/fixtures/starter.json").read_bytes() == (
        ROOT / "fixtures/starter.json"
    ).read_bytes(), "original fixture resource differs"
    assert target.read_bytes() == raw, "dataset regeneration differs"
    assert manifest.read_text() == source, "dataset authority differs"
else:
    target.write_bytes(raw)
    manifest.write_text(source)
print(json.dumps({"cases": len(rows), "bytes": len(raw), "sha256": sha}))
