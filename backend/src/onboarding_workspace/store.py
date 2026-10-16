"""Reviewed invitation proposals, synthetic owner decisions and atomic source."""

from __future__ import annotations
import json, os, sqlite3, tempfile, threading
from pathlib import Path
from contextlib import contextmanager
from pydantic import TypeAdapter
from .schema import (
    Setup,
    Email,
    Revision,
    MAX,
    canonical,
    proposal_digest,
    validate_state,
)


class Conflict(Exception):
    pass


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def invalid(value):
        raise ValueError(f"nonfinite JSON value: {value}")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _source(path):
    initial = path.lstat()
    if path.is_symlink() or not path.is_file() or initial.st_size > 8 * 1024 * 1024:
        raise ValueError("state must be a bounded regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        with os.fdopen(os.dup(fd), "rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        after, current = os.fstat(fd), path.lstat()
        if (
            len(raw) > 8 * 1024 * 1024
            or (before.st_dev, before.st_ino) != (initial.st_dev, initial.st_ino)
            or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
            or (before.st_size, before.st_mtime_ns)
            != (after.st_size, after.st_mtime_ns)
            or before.st_size != len(raw)
        ):
            raise ValueError("state changed during read")
        state = validate_state(strict_json(raw.decode("utf-8")))
        if state.get("dataset"):
            from .datasets import authority

            authority(path, state)
        return state, raw, (before.st_dev, before.st_ino)
    finally:
        os.close(fd)


class Workspace:
    def __init__(self, path: str | Path):
        self.path = Path(path).absolute()
        state = self.read()
        self.path = self.path.resolve()
        self.instance = state["instance_id"]
        self.lock_path = self.path.with_name(
            f".{self.path.name}.onboarding-lock.sqlite"
        )
        self._thread_lock = threading.RLock()
        self._prior = None

    def read(self) -> dict:
        state, _, _ = _source(self.path)
        if hasattr(self, "instance") and state["instance_id"] != self.instance:
            raise ValueError("workspace_instance_changed")
        return state

    def snapshot(self):
        state, raw, identity = _source(self.path)
        if state["instance_id"] != self.instance:
            raise ValueError("workspace_instance_changed")
        return state, raw, identity

    @contextmanager
    def transaction(self):
        with self._thread_lock:
            try:
                fd = os.open(
                    self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
                os.close(fd)
            except FileExistsError:
                if self.lock_path.is_symlink() or not self.lock_path.is_file():
                    raise ValueError("invalid persistent workspace mutex")
            db = sqlite3.connect(self.lock_path, timeout=5)
            try:
                db.execute("BEGIN IMMEDIATE")
                self._prior = self.snapshot()
                yield self._prior[0]
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                self._prior = None
                db.close()

    def _write(self, state: dict) -> None:
        if self._prior is None:
            raise RuntimeError("state write requires an owned transaction")
        state = validate_state(state)
        raw = (
            json.dumps(state, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        ).encode()
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("state size limit")
        fd, temporary = tempfile.mkstemp(prefix=".onboarding-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            current = self.snapshot()
            if current[1:] != self._prior[1:]:
                raise ValueError("state_changed_before_commit")
            os.replace(temporary, self.path)
            parent = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def detail(self):
        return self.read()

    def set_name(self, name, expected_revision, actor):
        TypeAdapter(Revision).validate_python(expected_revision, strict=True)
        if not isinstance(name, str):
            raise ValueError("name must be text")
        name = name.strip()
        if not 3 <= len(name) <= 60:
            raise ValueError("workspace name must be 3 to 60 characters")
        with self.transaction() as state:
            setup = state["setup"]
            if actor != setup["owner_email"]:
                raise Conflict("owner_required")
            if setup["revision"] != expected_revision:
                raise Conflict("stale_setup_revision")
            if setup["revision"] == MAX:
                raise Conflict("revision_exhausted")
            setup["name"] = name
            setup["revision"] += 1
            state["audit"].append(
                {
                    "action": "set_name",
                    "actor": actor,
                    "target": None,
                    "outcome": "saved",
                }
            )
            self._write(state)
            return setup

    def propose_invite(self, email, role, *, expected_setup=None):
        if not isinstance(email, str):
            raise ValueError("email must be text")
        email = email.strip().lower()
        try:
            TypeAdapter(Email).validate_python(email, strict=True)
        except ValueError:
            raise Conflict("email_outside_allowed_domain") from None
        if role not in {"member", "admin"}:
            raise ValueError("role must be member or admin")
        with self.transaction() as state:
            setup = state["setup"]
            if expected_setup is not None and canonical(setup) != canonical(
                expected_setup
            ):
                raise Conflict("setup_changed_since_read")
            if not setup["name"]:
                raise Conflict("setup_incomplete")
            if email.split("@")[1] != setup["allowed_domain"]:
                raise Conflict("email_outside_allowed_domain")
            if email == setup["owner_email"]:
                raise Conflict("owner_already_present")
            if any(i["email"] == email for i in state["invitations"]):
                raise Conflict("already_invited")
            if any(
                p["email"] == email and p["status"] == "pending"
                for p in state["invite_proposals"]
            ):
                raise Conflict("proposal_already_pending")
            ids = {p["id"] for p in state["invite_proposals"]}
            n = 1
            while f"P-{n}" in ids:
                n += 1
            proposal = {
                "id": f"P-{n}",
                "email": email,
                "role": role,
                "setup_revision": setup["revision"],
                "revision": 1,
                "status": "pending",
                "decision_actor": None,
                "source_setup": json.loads(json.dumps(setup)),
                "decision": None,
            }
            proposal["content_sha256"] = proposal_digest(proposal)
            state["invite_proposals"].append(proposal)
            state["audit"].append(
                {
                    "action": "propose_invite",
                    "target": proposal["id"],
                    "outcome": "pending",
                    "actor": None,
                }
            )
            self._write(state)
            return proposal

    def decide(self, proposal_id, revision, decision, actor):
        TypeAdapter(Revision).validate_python(revision, strict=True)
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        with self.transaction() as state:
            setup = state["setup"]
            if actor != setup["owner_email"]:
                raise Conflict("owner_required")
            p = next(
                (p for p in state["invite_proposals"] if p["id"] == proposal_id), None
            )
            if p is None:
                raise KeyError("unknown proposal")
            if p["status"] != "pending" or p["revision"] != revision:
                raise Conflict("proposal_not_current")
            if p["revision"] == MAX:
                raise Conflict("revision_exhausted")
            if decision == "approve":
                if (
                    canonical(p["source_setup"]) != canonical(setup)
                    or not setup["name"]
                ):
                    raise Conflict("setup_changed")
                if (
                    p["email"].split("@")[1] != setup["allowed_domain"]
                    or p["email"] == setup["owner_email"]
                ):
                    raise Conflict("email_outside_allowed_domain")
                if any(i["email"] == p["email"] for i in state["invitations"]):
                    raise Conflict("already_invited")
                ids = {i["id"] for i in state["invitations"]}
                n = 1
                while f"INV-{n}" in ids:
                    n += 1
                state["invitations"].append(
                    {
                        "id": f"INV-{n}",
                        "proposal_id": p["id"],
                        "email": p["email"],
                        "role": p["role"],
                    }
                )
            p["status"] = "approved" if decision == "approve" else "rejected"
            p["decision_actor"] = actor
            p["decision"] = {
                "kind": "synthetic_owner_decision",
                "actor": actor,
                "action": decision,
                "proposal_sha256": p["content_sha256"],
                "proposal_revision": revision,
                "decision_setup": json.loads(json.dumps(setup)),
            }
            p["revision"] += 1
            state["audit"].append(
                {
                    "action": "decide",
                    "target": p["id"],
                    "outcome": p["status"],
                    "actor": actor,
                }
            )
            self._write(state)
            return {"proposal": p, "invitations": state["invitations"]}
