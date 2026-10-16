import asyncio
import copy
import json
import re
from pathlib import Path
import httpx
import pytest
from onboarding_workspace.datasets import (
    populations,
    initialize,
    inspect_workspace,
    reset,
    validate_population,
)
from onboarding_workspace.store import Workspace, Conflict
from onboarding_workspace.native import Config
from onboarding_workspace.runtime import Runtime
from test_native import request, body, Provider


@pytest.mark.parametrize("population", populations(), ids=lambda p: p["id"])
def test_private_population_init_readback_and_reset_preserve_old_state(
    tmp_path, population
):
    file = tmp_path / "state.json"
    created = initialize(file, population["id"])
    w = Workspace(file)
    assert inspect_workspace(file, w.read())["original_seed_match"]
    assert (
        file.stat().st_mode & 0o777 == 0o600
        and Path(str(file) + ".source.json").stat().st_mode & 0o777 == 0o600
    )
    before = file.read_bytes()
    metadata = Path(str(file) + ".source.json").read_bytes()
    with pytest.raises(FileExistsError):
        initialize(file, population["id"])
    fresh = reset(file, tmp_path / "fresh.json", w.read())
    assert fresh["instance_id"] != created["instance_id"]
    assert (
        file.read_bytes() == before
        and Path(str(file) + ".source.json").read_bytes() == metadata
    )
    assert inspect_workspace(
        tmp_path / "fresh.json", Workspace(tmp_path / "fresh.json").read()
    )["original_seed_match"]


@pytest.mark.parametrize("population", populations(), ids=lambda p: p["id"])
def test_actual_native_sdk_every_population_and_separate_owner_decision(
    tmp_path, population
):
    async def check():
        file = tmp_path / "state.json"
        initialize(file, population["id"])
        w = Workspace(file)
        before = w.read()
        setup = before["setup"]
        emails = re.findall(r"[a-z0-9._+-]+@[a-z0-9.-]+\.example", population["task"])
        target = emails[-1] if emails else None
        allowed = bool(
            target
            and setup["name"]
            and target.endswith("@" + setup["allowed_domain"])
            and target != setup["owner_email"]
            and not any(i["email"] == target for i in before["invitations"])
            and not any(
                p["email"] == target and p["status"] == "pending"
                for p in before["invite_proposals"]
            )
        )

        class CaseProvider(Provider):
            async def handle_async_request(self, req):
                self.requests.append(req)
                n = len(self.requests)
                b = body(n)
                if n == 2 and (not target or not setup["name"]):
                    b = body(3)
                elif n == 2:
                    b["candidates"][0]["content"]["parts"][0]["functionCall"][
                        "args"
                    ] = {
                        "email": target,
                        "role": "admin"
                        if "as an admin" in population["task"]
                        else "member",
                    }
                if b["candidates"][0]["content"]["parts"][0].get("text"):
                    b["candidates"][0]["content"]["parts"][0]["text"] = (
                        "Reviewed the current workspace. Inspect the actual queue; invitation decisions remain with the owner."
                    )
                return httpx.Response(200, json=b, request=req)

        p = CaseProvider()
        runtime = Runtime(
            w,
            config=Config(
                "controlled-gemini",
                "synthetic-native-key",
                "https://controlled.example",
            ),
            transport_factory=lambda: p,
        )
        req = request(text=population["task"])
        message = runtime.reserve(req)
        events = [e async for e in runtime.events(req, message)]
        after = w.read()
        assert events[-1].type == "RUN_FINISHED" and len(
            after["invite_proposals"]
        ) == len(before["invite_proposals"]) + (1 if allowed else 0)
        assert after["invitations"] == before["invitations"] and p.closed
        prompts = "".join(r.content.decode() for r in p.requests)
        assert (
            "onboarding-populations" not in prompts
            and "fictional_imported_onboarding_snapshot" not in prompts
        )
        if allowed:
            proposal = after["invite_proposals"][-1]
            assert proposal["status"] == "pending"
            assert not proposal["decision"]
            w.decide(proposal["id"], 1, "approve", after["setup"]["owner_email"])
            assert len(w.read()["invitations"]) == len(before["invitations"]) + 1
            assert w.read()["invitations"][-1]["email"] == target
        else:
            assert not allowed
        if population["id"] == "maximum-revision":
            assert (
                json.loads(p.requests[1].content)["contents"][-1]["parts"][0][
                    "functionResponse"
                ]["response"]["setup"]["revision"]
                == 2**53 - 1
            )
            with pytest.raises(Conflict, match="revision_exhausted"):
                w.set_name("New name", 2**53 - 1, setup["owner_email"])
        await runtime.close()

    asyncio.run(check())


def test_busy_history_is_coherent_and_imported_provenance_never_implies_live_execution():
    busy = next(p for p in populations() if p["profile"] == "busy")
    assert (
        len(busy["state"]["invite_proposals"]) == 100
        and len(busy["state"]["invitations"]) == 64
    )
    assert (
        sum(p["status"] == "pending" for p in busy["state"]["invite_proposals"]) == 24
        and sum(p["status"] == "rejected" for p in busy["state"]["invite_proposals"])
        == 12
    )
    assert busy["provenance"]["prior_human_authentication"] is None
    for kind in ("hash", "sequence", "time", "target", "missing"):
        p = copy.deepcopy(busy)
        if kind == "hash":
            p["history"][0]["source_audit_sha256"] = "0" * 64
        if kind == "sequence":
            p["history"][1]["sequence"] = 1
        if kind == "time":
            p["history"][1]["at"] = "2026-01-01T00:00:00+00:00"
        if kind == "target":
            p["history"][1]["target"] = "missing"
        if kind == "missing":
            p["history"].pop()
        with pytest.raises(ValueError):
            validate_population(p)


def test_valid_edit_keeps_original_history_and_missing_metadata_is_never_repaired(
    tmp_path,
):
    file = tmp_path / "state.json"
    initialize(file, "ready-team")
    w = Workspace(file)
    w.set_name("Reviewed new name", 2, "owner@acme.example")
    before = file.read_bytes()
    assert not inspect_workspace(file, w.read())["original_seed_match"]
    reset(file, tmp_path / "reset.json", w.read())
    assert file.read_bytes() == before
    Path(str(file) + ".source.json").unlink()
    with pytest.raises(FileNotFoundError):
        w.read()
    assert file.read_bytes() == before


def test_foreign_source_metadata_and_new_instance_are_not_borrowed(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    initialize(a)
    initialize(b, "alternate-domain")
    wa = Workspace(a)
    Path(str(a) + ".source.json").write_bytes(
        Path(str(b) + ".source.json").read_bytes()
    )
    with pytest.raises(ValueError, match="identity differs"):
        wa.read()


def test_source_metadata_boolean_version_is_not_an_integer_authority(tmp_path):
    file = tmp_path / "state.json"
    initialize(file)
    meta_file = Path(str(file) + ".source.json")
    value = json.loads(meta_file.read_text())
    value["schema_version"] = True
    meta_file.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="exact integer"):
        Workspace(file)
