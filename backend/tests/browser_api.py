"""Owned browser test servers: actual Gemini SDK HTTP, no paid/model fallback."""

import asyncio
import logging
import json
import re
import tempfile
import uuid
import threading
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from onboarding_workspace.api import create_app
from onboarding_workspace.native import Config
from onboarding_workspace.store import Workspace
from onboarding_workspace.datasets import initialize

logging.getLogger("google_adk").setLevel(logging.CRITICAL)
ROOT = Path(__file__).parents[2]
directory = Path(tempfile.mkdtemp(prefix="onboarding-browser-"))
file = directory / "state.json"
file.write_bytes((ROOT / "fixtures/starter.json").read_bytes())
controls = {"mode": "normal", "requests": [], "old_receipts": set()}
release = threading.Event()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        controls["requests"].append(body)
        if (
            self.path != "/v1beta/models/controlled-gemini:generateContent"
            or self.headers.get("x-goog-api-key") != "synthetic-browser-key"
        ):
            self.send_error(400)
            return
        mode = controls["mode"]
        if mode == "pending":
            release.wait(30)
        calls = [
            part["functionResponse"]
            for c in body.get("contents", [])
            for part in c.get("parts", [])
            if "functionResponse" in part
        ]
        messages = [
            part["text"]
            for c in body.get("contents", [])
            if c.get("role") == "user"
            for part in c.get("parts", [])
            if "text" in part
        ]
        text = messages[-1] if messages else ""
        emails = re.findall(r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.example", text)
        if not calls:
            parts = [
                {
                    "functionCall": {
                        "name": "read_workspace",
                        "args": {},
                        "id": "read-current",
                    }
                }
            ]
        elif calls[-1]["name"] == "read_workspace":
            state = Workspace(file).read()
            if not state["setup"]["name"]:
                parts = [
                    {
                        "text": "Please save a workspace name before I can propose an invitation."
                    }
                ]
            elif not emails:
                parts = [
                    {
                        "text": "Please provide the exact teammate email and member or admin role."
                    }
                ]
            else:
                parts = [
                    {
                        "functionCall": {
                            "name": "propose_invite",
                            "args": {
                                "email": emails[-1],
                                "role": "admin"
                                if "admin" in text.lower()
                                else "member",
                            },
                            "id": "propose-current",
                        }
                    }
                ]
        else:
            result = calls[-1].get("response", {})
            parts = [
                {
                    "text": "The local invitation proposal is ready for owner review. No external email was delivered."
                    if "proposal" in result
                    else "The proposal could not be saved: "
                    + str(result.get("error", "unknown error"))
                }
            ]
        if mode == "markup" and calls and calls[-1]["name"] == "propose_invite":
            parts = [
                {
                    "text": "Local proposal ready. Calculation:\n\n$$x^2 + 1$$\n\n$$\\notacommand$$\n\n<script>window.syntheticUnsafe=true</script> [unsafe](javascript:alert(1))"
                }
            ]
        raw = {
            "candidates": [
                {
                    "index": 0,
                    "content": {"role": "model", "parts": parts},
                    "finishReason": "MAX_TOKENS" if mode == "truncated" else "STOP",
                }
            ],
            "modelVersion": "controlled-browser",
            "responseId": f"browser-{len(controls['requests'])}",
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 2,
                "totalTokenCount": 12,
            },
        }
        if mode == "outage":
            raw = {
                "error": {"message": "Controlled provider unavailable"},
                "usageMetadata": {
                    "promptTokenCount": 1,
                    "candidatesTokenCount": 0,
                    "totalTokenCount": 1,
                },
            }
        encoded = json.dumps(raw).encode()
        self.send_response(503 if mode == "outage" else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError):
            pass


http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
http.daemon_threads = True
thread = threading.Thread(target=http.serve_forever, daemon=True)
thread.start()
config = Config(
    "controlled-gemini", "synthetic-browser-key", f"http://127.0.0.1:{http.server_port}"
)
current = create_app(file, native_config=config)


@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        release.set()
        await current.state.runtime.close()
        http.shutdown()
        http.server_close()
        thread.join(2)


app = FastAPI(lifespan=lifespan)


@app.post("/__test/reset")
async def reset(case_id: str = "incomplete-setup"):
    global current, file
    await current.state.runtime.close()
    file = directory / str(uuid.uuid4()) / "state.json"
    initialize(file, case_id)
    controls.update(
        mode="normal",
        requests=[],
        old_receipts={str(p) for p in directory.rglob("trace.json")},
    )
    release.set()
    release.clear()
    current = create_app(file, native_config=config)
    return {"ok": True}


@app.post("/__test/mode/{mode}")
async def mode(mode: str):
    controls["mode"] = mode
    if mode != "pending":
        release.set()
    else:
        release.clear()
    return {"mode": mode}


@app.get("/__test/evidence")
async def evidence():
    return {
        "requests": len(controls["requests"]),
        "receipts": sorted(
            [
                json.loads(p.read_text())
                for p in directory.rglob("trace.json")
                if str(p) not in controls["old_receipts"]
            ],
            key=lambda value: value["started_at"],
        ),
        "active": len(current.state.runtime.active),
    }


class Gateway:
    async def __call__(self, scope, receive, send):
        await current(scope, receive, send)


app.mount("/", Gateway())
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=38125,
        log_level="warning",
        timeout_graceful_shutdown=1,
    )
