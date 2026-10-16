"""Owned native Gemini JSON, original completion before ADK tool dispatch."""

from __future__ import annotations
import base64
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit
import httpx
from google import genai
from google.genai import types
from .evidence import sha
from .store import strict_json

MAX_BODY = 1048576


@dataclass(frozen=True)
class Config:
    model: str
    api_key: str = field(repr=False)
    base_url: str = "https://generativelanguage.googleapis.com"

    def validate(self):
        if not isinstance(self.model, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}", self.model
        ):
            raise ValueError("GEMINI_MODEL must name an explicit enabled model")
        if (
            not isinstance(self.api_key, str)
            or not self.api_key
            or len(self.api_key) > 4096
            or any(not 33 <= ord(c) <= 126 for c in self.api_key)
        ):
            raise ValueError("GOOGLE_API_KEY is required; no model/key fallback")
        u = urlsplit(self.base_url)
        if (
            not u.hostname
            or u.username
            or u.password
            or u.query
            or u.fragment
            or not (
                u.scheme == "https"
                or u.scheme == "http"
                and u.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError(
                "endpoint requires explicit HTTPS or owned loopback HTTP without credentials/query/fragment"
            )
        u.port
        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() not in {
            "false",
            "0",
            "",
        } or os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in {"true", "1"}:
            raise ValueError("only explicit Gemini Developer API is qualified")
        return self

    def public(self):
        return {
            "model": self.model,
            "base_url": self.base_url,
            "provider": "gemini_developer_api",
        }


def from_environment():
    return Config(
        os.getenv("GEMINI_MODEL"),
        os.getenv("GOOGLE_API_KEY"),
        os.getenv("ONBOARDING_GEMINI_BASE_URL")
        or "https://generativelanguage.googleapis.com",
    ).validate()


def measurements(body):
    usage = body.get("usageMetadata") if isinstance(body, dict) else None
    fields = {}
    for name in (
        "promptTokenCount",
        "candidatesTokenCount",
        "totalTokenCount",
        "cachedContentTokenCount",
        "thoughtsTokenCount",
    ):
        value = usage.get(name) if isinstance(usage, dict) else None
        valid = type(value) is int and 0 <= value <= 2**53 - 1
        fields[name] = {
            "state": "observed" if valid else "unknown" if value is None else "invalid",
            "value": value if valid else None,
        }
    return {
        "source": "original decoded HTTP JSON before SDK defaults",
        "raw": usage,
        "fields": fields,
        "cost_usd": None,
    }


def completion(body, seen):
    if not isinstance(body, dict):
        raise ValueError("Gemini JSON must be an object")
    feedback = body.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason") not in {
        None,
        "BLOCK_REASON_UNSPECIFIED",
    }:
        raise ValueError("Gemini prompt blocked")
    candidates = body.get("candidates")
    if (
        not isinstance(candidates, list)
        or len(candidates) != 1
        or not isinstance(candidates[0], dict)
    ):
        raise ValueError("one Gemini candidate required")
    candidate = candidates[0]
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if (
        candidate.get("finishReason") != "STOP"
        or candidate.get("index", 0) != 0
        or type(candidate.get("index", 0)) is not int
        or not isinstance(content, dict)
        or content.get("role") not in {None, "model"}
        or not isinstance(parts, list)
        or not 1 <= len(parts) <= 32
    ):
        raise ValueError("native candidate is not a coherent STOP result")
    calls = []
    text = ""
    for part in parts:
        if not isinstance(part, dict) or any(
            k not in {"text", "thought", "thoughtSignature", "functionCall"}
            for k in part
        ):
            raise ValueError("unsupported provider content")
        if "functionCall" in part:
            call = part["functionCall"]
            if (
                not isinstance(call, dict)
                or not isinstance(call.get("args"), dict)
                or call.get("name") not in {"read_workspace", "propose_invite"}
            ):
                raise ValueError("unsupported provider function call")
            args = call["args"]
            name = call["name"]
            if name == "read_workspace" and args:
                raise ValueError("read_workspace takes no arguments")
            if name == "propose_invite" and (
                set(args) != {"email", "role"}
                or not isinstance(args.get("email"), str)
                or not 1 <= len(args["email"]) <= 254
                or args.get("role") not in {"member", "admin"}
            ):
                raise ValueError("invalid proposal function arguments")
            call_id = call.get("id")
            if call_id is not None and (
                not isinstance(call_id, str) or not call_id.strip() or call_id in seen
            ):
                raise ValueError("invalid/replayed original function ID")
            calls.append({"name": name, "args": args, "original_id": call_id})
        if "text" in part:
            if not isinstance(part["text"], str):
                raise ValueError("invalid provider text")
            if part.get("thought") is not True:
                text += part["text"]
    if calls:
        if len(calls) != 1 or text.strip():
            raise ValueError("parallel/mixed proposal turns are unsupported")
        if calls[0]["original_id"] is not None:
            seen.add(calls[0]["original_id"])
        return {"kind": "tool", **calls[0]}
    if not text.strip():
        raise ValueError("completed final text is required")
    return {"kind": "answer", "text": text}


class Native:
    def __init__(self, config, receipt):
        self.config = config
        self.receipt = receipt
        self.seen = set()
        self.closed = False
        self.sdk = None
        self.http = None
        self.sync = None

    async def request(self, request):
        self.receipt.guard()
        c = self.config
        if (
            request.method != "POST"
            or str(request.url)
            != c.base_url.rstrip("/") + f"/v1beta/models/{c.model}:generateContent"
        ):
            raise ValueError("unqualified provider request path/method")
        if len(self.receipt.data["native"]) >= 8:
            raise ValueError("eight prepared native requests exhausted")
        raw = await request.aread()
        if len(raw) > MAX_BODY:
            raise ValueError("native decoded request exceeds retained limit")
        body = strict_json(raw.decode("utf-8"))
        if (
            body.get("generationConfig", {}).get("maxOutputTokens") != 4096
            or body.get("generationConfig", {}).get("candidateCount") != 1
        ):
            raise ValueError("unqualified generation limits")
        item = {
            "number": len(self.receipt.data["native"]) + 1,
            "status": "prepared",
            "request_sha256": sha(raw),
            "request_body": body,
            "response": None,
            "reported_usage": measurements(None),
        }
        self.receipt.data["native"].append(item)
        self.receipt.save()
        self.receipt.guard()

    async def response(self, response):
        item = self.receipt.data["native"][-1]
        item.update(
            status="received",
            http_status=response.status_code,
            request_id=response.headers.get("x-request-id"),
        )
        try:
            raw = await response.aread()
            item.update(
                decoded_body_base64=base64.b64encode(raw[:MAX_BODY]).decode(),
                body_sha256=sha(raw),
                decoded_bytes=len(raw),
                truncated=len(raw) > MAX_BODY,
            )
            if len(raw) > MAX_BODY:
                self.receipt.save()
                raise ValueError("native decoded response exceeds retained limit")
            body = strict_json(raw.decode("utf-8"))
            item.update(response=body, reported_usage=measurements(body))
            self.receipt.save()
            self.receipt.guard()
            if response.status_code != 200:
                raise ValueError(f"Gemini HTTP {response.status_code}")
            item["accepted"] = completion(body, self.seen)
            if (
                len(self.receipt.data["native"]) == 8
                and item["accepted"]["kind"] == "tool"
            ):
                raise ValueError("final native request cannot dispatch another tool")
            item["status"] = "accepted"
            self.receipt.save()
            self.receipt.guard()
        except BaseException as error:
            self.receipt.failure = self.receipt.failure or error
            item.update(
                status="rejected",
                error={"name": type(error).__name__, "message": str(error)},
            )
            self.receipt.save()
            raise
        finally:
            await response.aclose()

    async def start(self, transport=None):
        self.config.validate()
        self.http = httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(30, connect=5),
            event_hooks={"request": [self.request], "response": [self.response]},
        )

        class NoSync(httpx.BaseTransport):
            def handle_request(self, request):
                raise RuntimeError("only owned async Gemini requests are qualified")

        self.sync = httpx.Client(
            transport=NoSync(), trust_env=False, follow_redirects=False
        )
        self.sdk = genai.Client(
            api_key=self.config.api_key,
            vertexai=False,
            http_options=types.HttpOptions(
                base_url=self.config.base_url,
                httpx_async_client=self.http,
                httpx_client=self.sync,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        return self.sdk

    async def close(self):
        if self.closed:
            raise RuntimeError("native close already attempted")
        self.closed = True
        errors = []
        try:
            if self.sdk is not None:
                await self.sdk.aio.aclose()
                self.sdk.close()
            self.receipt.data["lifecycle"]["sdk_closed"] = True
        except BaseException as error:
            errors.append(error)
        try:
            if self.http is not None:
                await self.http.aclose()
            if self.sync is not None:
                self.sync.close()
            self.receipt.data["lifecycle"]["http_closed"] = True
        except BaseException as error:
            errors.append(error)
        if errors:
            raise errors[0]
