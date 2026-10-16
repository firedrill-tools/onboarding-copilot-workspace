"""Private per-run native and application evidence."""

import asyncio
import base64
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .schema import canonical


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(value):
    return hashlib.sha256(
        value if isinstance(value, bytes) else canonical(value).encode()
    ).hexdigest()


class Receipt:
    def __init__(self, workspace, output_root, request, timeout, writer=None):
        self.workspace = workspace
        self.deadline = time.monotonic() + timeout
        self.writer = writer
        self.recording_error = None
        self.failure = None
        state, raw, _ = workspace.snapshot()
        root = Path(output_root or workspace.path.parent / "runs")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink():
            raise ValueError("receipt root cannot be a symlink")
        directory = root / str(uuid.uuid4())
        directory.mkdir(mode=0o700)
        self.path = directory / "trace.json"
        self.data = {
            "schema_version": 1,
            "run_id": directory.name,
            "status": "prepared",
            "started_at": now(),
            "request": request,
            "initial_source_sha256": sha(raw),
            "initial_source_base64": base64.b64encode(raw).decode(),
            "native": [],
            "actions": [],
            "sdk_events": [],
            "protocol_events": [],
            "lifecycle": {
                "session_deleted": False,
                "runner_closed": False,
                "sdk_closed": False,
                "http_closed": False,
            },
            "result": None,
            "error": None,
            "cost_usd": None,
            "limits": {
                "prepared_requests": 8,
                "output_tokens_per_request": 4096,
                "retries": 0,
                "operation_seconds": timeout,
                "http_seconds": 30,
            },
        }

    def guard(self):
        if self.recording_error:
            raise self.recording_error
        if self.failure:
            raise RuntimeError("a prior owned boundary failed") from self.failure
        task = asyncio.current_task()
        if task and task.cancelling():
            raise asyncio.CancelledError("onboarding cancelled")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("onboarding operation deadline exceeded")
        self.workspace.snapshot()
        if time.monotonic() >= self.deadline:
            raise TimeoutError("onboarding operation deadline exceeded")
        if task and task.cancelling():
            raise asyncio.CancelledError("onboarding cancelled")

    def save(self, final=False):
        if self.recording_error and not final:
            raise self.recording_error
        staged = self.path.with_name("." + str(uuid.uuid4()) + ".tmp")
        try:
            value = json.loads(json.dumps(self.data, allow_nan=False))
            if self.writer is not None:
                self.writer(self.path, value)
                return
            fd = os.open(staged, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(
                    (
                        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
                        + "\n"
                    ).encode()
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staged, self.path)
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException as error:
            self.recording_error = error
            raise
        finally:
            staged.unlink(missing_ok=True)

    def finish(self, result, failure):
        self.data.update(
            status="failed" if failure else "completed",
            finished_at=now(),
            result=None if failure else result,
        )
        try:
            _, raw, _ = self.workspace.snapshot()
            self.data.update(
                final_source_sha256=sha(raw),
                final_source_base64=base64.b64encode(raw).decode(),
            )
        except BaseException as error:
            self.data["source_error"] = {
                "name": type(error).__name__,
                "message": str(error),
            }
        if failure:
            chain = []
            seen = set()
            current = failure
            while current and id(current) not in seen and len(chain) < 8:
                seen.add(id(current))
                chain.append({"name": type(current).__name__, "message": str(current)})
                current = current.__cause__
            self.data["error"] = {
                "name": type(failure).__name__,
                "message": str(failure),
                "causes": chain,
            }
            for item in self.data["native"]:
                if item["status"] in {"prepared", "received"}:
                    item.update(status="failed", error=self.data["error"])
        self.save(final=True)
