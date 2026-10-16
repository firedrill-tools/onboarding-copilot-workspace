"""Pinned imported source and exclusive private model-free workspaces."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from pydantic import Field, StringConstraints, field_validator
from ._dataset_manifest import DATASET_SHA256
from .schema import Strict, Id, Revision, digest, validate_state
from .store import strict_json


class History(Strict):
    sequence: Revision
    at: str
    source_audit_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    kind: Literal["fictional_imported_audit"]
    target: Id
    outcome: Literal["saved", "pending", "approved", "rejected"]


class Provenance(Strict):
    kind: Literal["fictional_imported_onboarding_snapshot"]
    prior_model_evidence: None
    prior_human_authentication: None
    prior_email_delivery: None


class Population(Strict):
    id: Id
    profile: Literal["starter", "busy", "ambiguous", "boundary"]
    task: Annotated[str, StringConstraints(min_length=1, max_length=8000)]
    state: dict
    history: Annotated[list[History], Field(max_length=4000)]
    provenance: Provenance


class Metadata(Strict):
    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("metadata schema_version must be an exact integer")
        return value

    schema_version: Literal[1]
    instance_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
    dataset_sha256: Literal[DATASET_SHA256]
    case_id: Id
    seed_state_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    scope: Literal["original_imported_seed_snapshot"]


def read_regular(path, limit=1048576):
    path = Path(path)
    before = path.lstat()
    if path.is_symlink() or not path.is_file() or before.st_size > limit:
        raise ValueError("bounded regular source required")
    raw = path.read_bytes()
    after = path.lstat()
    if len(raw) > limit or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during read")
    return raw


def validate_population(value):
    p = Population.model_validate(value).model_dump()
    state = validate_state(p["state"])
    p["state"] = state
    if len(p["history"]) != len(state["audit"]):
        raise ValueError("imported history population differs from source audit")
    last = None
    for n, (history, audit) in enumerate(
        zip(p["history"], state["audit"], strict=True), 1
    ):
        at = datetime.fromisoformat(history["at"])
        if (
            at.tzinfo is None
            or at.isoformat() != history["at"]
            or last is not None
            and at < last
        ):
            raise ValueError("history chronology must be explicit and ordered")
        last = at
        if (
            history["sequence"] != n
            or history["source_audit_sha256"] != digest(audit)
            or history["target"] != (audit["target"] or state["setup"]["id"])
            or history["outcome"] != audit["outcome"]
        ):
            raise ValueError("imported history differs from current source audit")
    return p


def populations():
    path = Path(__file__).parent / "sample_data" / "index.json"
    if not path.exists():
        path = Path(__file__).parents[2] / "data" / "index.json"
    raw = read_regular(path)
    if hashlib.sha256(raw).hexdigest() != DATASET_SHA256:
        raise ValueError("dataset authority hash differs")
    value = strict_json(raw.decode("utf-8"))
    if (
        not isinstance(value, dict)
        or set(value) != {"id", "version", "cases"}
        or value["id"] != "onboarding-populations"
        or value["version"] != "1.0.0"
        or not isinstance(value["cases"], list)
        or len(value["cases"]) != 12
    ):
        raise ValueError("invalid dataset index")
    rows = [validate_population(p) for p in value["cases"]]
    if len({p["id"] for p in rows}) != 12:
        raise ValueError("duplicate dataset case")
    return rows


def list_cases():
    return [
        {
            "id": p["id"],
            "profile": p["profile"],
            "task": p["task"],
            "proposals": len(p["state"]["invite_proposals"]),
            "invitations": len(p["state"]["invitations"]),
        }
        for p in populations()
    ]


def authority(file, state):
    if not state.get("dataset"):
        return None
    meta = Metadata.model_validate(
        strict_json(read_regular(str(file) + ".source.json", 32768).decode("utf-8"))
    ).model_dump()
    p = next((p for p in populations() if p["id"] == meta["case_id"]), None)
    d = state["dataset"]
    if (
        not p
        or state["instance_id"] is None
        or meta["instance_id"] != state["instance_id"]
        or d["case_id"] != p["id"]
        or d["source_sha256"] != DATASET_SHA256
        or meta["seed_state_sha256"] != digest(p["state"])
    ):
        raise ValueError("workspace/source identity differs")
    return meta, p


def exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def initialize(file, case_id="incomplete-setup"):
    file = Path(file).absolute()
    p = next((p for p in populations() if p["id"] == case_id), None)
    if p is None:
        raise ValueError("unknown dataset case")
    meta_file = Path(str(file) + ".source.json")
    mutex = file.with_name("." + file.name + ".onboarding-lock.sqlite")
    if any(path.exists() or path.is_symlink() for path in (file, meta_file, mutex)):
        raise FileExistsError("workspace destination exists")
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = copy.deepcopy(p["state"])
    state["instance_id"] = str(uuid.uuid4())
    state["dataset"] = {
        "id": "onboarding-populations",
        "version": "1.0.0",
        "case_id": case_id,
        "source_sha256": DATASET_SHA256,
    }
    state = validate_state(state)
    meta = {
        "schema_version": 1,
        "instance_id": state["instance_id"],
        "dataset_sha256": DATASET_SHA256,
        "case_id": case_id,
        "seed_state_sha256": digest(p["state"]),
        "scope": "original_imported_seed_snapshot",
    }
    created = False
    try:
        exclusive(meta_file, meta)
        created = True
        exclusive(file, state)
    except BaseException:
        if created:
            meta_file.unlink(missing_ok=True)
        raise
    fd = os.open(file.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {
        "workspace": str(file),
        "case_id": case_id,
        "instance_id": state["instance_id"],
        "task": p["task"],
        "proposals": len(state["invite_proposals"]),
        "invitations": len(state["invitations"]),
    }


def inspect_workspace(file, state):
    bound = authority(file, state)
    current = copy.deepcopy(state)
    current["instance_id"] = None
    current["dataset"] = None
    return {
        "workspace": str(Path(file).absolute()),
        "instance_id": state["instance_id"],
        "case_id": bound[1]["id"] if bound else None,
        "scope": bound[0]["scope"] if bound else "caller_supplied_legacy_source",
        "original_seed_match": digest(current) == bound[0]["seed_state_sha256"]
        if bound
        else None,
        "current_source_sha256": digest(state),
        "proposals": len(state["invite_proposals"]),
        "invitations": len(state["invitations"]),
        "imported_history": bound[1]["history"] if bound else None,
        "prior_model_evidence": None,
        "prior_human_authentication": None,
        "prior_email_delivery": None,
    }


def reset(file, destination, state):
    bound = authority(file, state)
    if not bound:
        raise ValueError("reset requires a hash-bound dataset workspace")
    if Path(file).absolute() == Path(destination).absolute():
        raise ValueError("reset needs a fresh destination")
    return initialize(destination, bound[1]["id"])
