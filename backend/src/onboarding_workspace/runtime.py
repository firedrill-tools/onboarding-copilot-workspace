"""Owned ADK runner and official AG-UI translator, without global sessions."""

from __future__ import annotations
import asyncio
import copy
import json
import math
import uuid
import anyio
from contextlib import aclosing
from ag_ui.core import (
    EventType,
    RunStartedEvent,
    RunFinishedEvent,
    RunErrorEvent,
    StateSnapshotEvent,
)
from ag_ui_adk import EventTranslator
from google.adk.apps import App
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types
from .agent import build_agent, context
from .native import Native, from_environment
from .evidence import Receipt, sha
from .schema import canonical


class Owner:
    def __init__(self, workspace, receipt, injected=False):
        self.workspace = workspace
        self.receipt = receipt
        self.injected = injected
        self.read_setup = None
        self.active = None
        self.consumed = set()

    def before_tool(self, name, args):
        r = self.receipt
        try:
            r.guard()
            if self.active is not None:
                raise ValueError("parallel application tools are unsupported")
            original = None
            if not self.injected:
                call = r.data["native"][-1]
                original = call.get("accepted")
                if (
                    call["status"] != "accepted"
                    or not original
                    or original["kind"] != "tool"
                    or original["name"] != name
                    or canonical(original["args"]) != canonical(args)
                    or call["number"] in self.consumed
                ):
                    raise ValueError("tool lacks original accepted native authority")
                self.consumed.add(call["number"])
            if name != "read_workspace" and self.read_setup is None:
                raise ValueError("workspace must be read before proposing")
            self.active = {
                "name": name,
                "args": copy.deepcopy(args),
                "original_function_id": original.get("original_id")
                if original
                else None,
                "status": "prepared",
                "source_sha256": sha(self.workspace.snapshot()[1]),
            }
            r.data["actions"].append(self.active)
            r.save()
            r.guard()
        except BaseException as error:
            r.failure = r.failure or error
            raise

    def after_tool(self, name, args, result):
        r = self.receipt
        try:
            if self.active is None or self.active["name"] != name:
                raise ValueError("unmatched application tool completion")
            self.active.update(
                status="finished",
                result=copy.deepcopy(result),
                source_sha256_after=sha(self.workspace.snapshot()[1]),
            )
            r.save()
            if name == "read_workspace":
                self.read_setup = copy.deepcopy(result["setup"])
            self.active = None
            r.guard()
        except BaseException as error:
            r.failure = r.failure or error
            raise


class Runtime:
    def __init__(
        self,
        workspace,
        *,
        config=None,
        agent_model=None,
        transport_factory=None,
        output_root=None,
        timeout_seconds=120,
        writer=None,
    ):
        if (
            type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 300
        ):
            raise ValueError("operation budget must be finite in (0,300]")
        if config is not None and agent_model is not None:
            raise ValueError("select owned native config or caller-injected model")
        self.workspace = workspace
        self.config = config
        self.agent_model = agent_model
        self.transport_factory = transport_factory
        self.output_root = output_root
        self.timeout = timeout_seconds
        self.writer = writer
        self.histories = {}
        self.active = {}
        self.run_ids = set()
        self.closed = False

    def reserve(self, input):
        if self.closed:
            raise ValueError("runtime is closed")
        if (
            not input.thread_id
            or len(input.thread_id) > 200
            or not input.run_id
            or len(input.run_id) > 200
        ):
            raise ValueError("bounded thread/run IDs required")
        if input.run_id in self.run_ids:
            raise ValueError("run ID already attempted; use a fresh explicit run")
        if input.thread_id in self.active:
            raise ValueError("thread already has an active run")
        if len(self.active) >= 4:
            raise ValueError("four active runs maximum")
        if input.thread_id not in self.histories and len(self.histories) >= 32:
            raise ValueError("32 conversation threads maximum")
        if len(self.run_ids) >= 512:
            raise ValueError(
                "512 attempted runs maximum; restart the local runtime for a new session"
            )
        if len(input.messages) > 128 or len(input.model_dump_json().encode()) > 262144:
            raise ValueError("retained AG-UI request exceeds message/size limits")
        if input.tools:
            raise ValueError(
                "client-supplied tools are unsupported; server owns proposal permissions"
            )
        users = [m for m in input.messages if m.role == "user"]
        last = users[-1] if users else None
        if (
            last is None
            or not isinstance(last.content, str)
            or not last.content.strip()
            or len(last.content) > 8000
        ):
            raise ValueError(
                "one latest nonblank user message of at most8000 characters is required"
            )
        self.workspace.snapshot()
        self.run_ids.add(input.run_id)
        self.active[input.thread_id] = None
        self.histories.setdefault(input.thread_id, [])
        return last.content

    async def events(self, input, message):
        current = asyncio.current_task()
        self.active[input.thread_id] = current
        receipt = None
        native = None
        runner = None
        stream = None
        session_id = str(uuid.uuid4())
        app_name = "onboarding_owned"
        translator = EventTranslator()
        failure = None
        result = None
        final_event = None
        close_errors = []
        session_created = False
        terminal = []
        try:
            receipt = Receipt(
                self.workspace,
                self.output_root,
                {
                    "thread_id": input.thread_id,
                    "client_run_id": input.run_id,
                    "user_text": message,
                    "history": copy.deepcopy(self.histories[input.thread_id]),
                },
                self.timeout,
                self.writer,
            )
            receipt.data["execution_kind"] = (
                "caller_injected_model"
                if self.agent_model is not None
                else "native_adk_gemini"
            )
            receipt.save()
            receipt.guard()
            yield RunStartedEvent(
                type=EventType.RUN_STARTED,
                thread_id=input.thread_id,
                run_id=input.run_id,
            )
            owner = Owner(self.workspace, receipt, self.agent_model is not None)
            if self.agent_model is not None:
                model = self.agent_model
            else:
                config = (self.config or from_environment()).validate()
                receipt.data["configuration"] = config.public()
                receipt.save()
                native = Native(config, receipt)
                sdk = await native.start(
                    self.transport_factory() if self.transport_factory else None
                )
                model = Gemini(model=config.model, client=sdk)
            agent = build_agent(
                self.workspace,
                model,
                owner=owner,
                history=self.histories[input.thread_id],
            )
            runner = InMemoryRunner(app=App(name=app_name, root_agent=agent))
            await runner.session_service.create_session(
                app_name=app_name, user_id="local_operator", session_id=session_id
            )
            session_created = True
            receipt.guard()
            async with asyncio.timeout_at(receipt.deadline):
                async with aclosing(
                    runner.run_async(
                        user_id="local_operator",
                        session_id=session_id,
                        new_message=types.Content(
                            role="user", parts=[types.Part.from_text(text=message)]
                        ),
                        run_config=RunConfig(
                            max_llm_calls=8, streaming_mode=StreamingMode.NONE
                        ),
                    )
                ) as events:
                    async for event in events:
                        receipt.guard()
                        receipt.data["sdk_events"].append(
                            event.model_dump(mode="json", exclude_none=True)
                        )
                        receipt.save()
                        if event.error_code:
                            raise ValueError(
                                f"ADK error {event.error_code}: {event.error_message}"
                            )
                        if event.is_final_response():
                            final_event = event
                            # Terminal answer is held until run resources are closed.
                            continue
                        async for translated in translator.translate(
                            event, input.thread_id, input.run_id
                        ):
                            receipt.data["protocol_events"].append(
                                translated.model_dump(mode="json", exclude_none=True)
                            )
                            receipt.save()
                            receipt.guard()
                            yield translated
            receipt.guard()
            if (
                final_event is None
                or not final_event.content
                or not any(
                    p.text and not p.thought for p in final_event.content.parts or []
                )
            ):
                raise ValueError("ADK ended without a completed final text")
            if native is not None:
                accepted = receipt.data["native"][-1].get("accepted")
                if not accepted or accepted["kind"] != "answer":
                    raise ValueError("final answer lacks original native completion")
            answer = "".join(
                p.text
                for p in final_event.content.parts or []
                if p.text and not p.thought
            )
            async for translated in translator.translate(
                final_event, input.thread_id, input.run_id
            ):
                terminal.append(translated)
            contents = [e for e in terminal if e.type == EventType.TEXT_MESSAGE_CONTENT]
            starts = [e for e in terminal if e.type == EventType.TEXT_MESSAGE_START]
            ends = [e for e in terminal if e.type == EventType.TEXT_MESSAGE_END]
            if (
                len(starts) != 1
                or len(ends) != 1
                or not contents
                or starts[0].message_id != ends[0].message_id
                or any(e.message_id != starts[0].message_id for e in contents)
                or "".join(e.delta for e in contents) != answer
            ):
                raise ValueError(
                    "final ADK translation is incomplete or differs from original answer"
                )
            receipt.data["terminal_events_prepared"] = [
                e.model_dump(mode="json", exclude_none=True) for e in terminal
            ]
            receipt.data["protocol_delivery"] = (
                "prepared; client delivery is not acknowledged"
            )
            result = {
                "answer": answer,
                "state": context(self.workspace),
                "receipt_path": str(receipt.path),
            }
        except BaseException as error:
            failure = receipt.failure if receipt and receipt.failure else error
        finally:
            with anyio.CancelScope(shield=True):
                # Every cleanup is attempted once. A failed close remains unconfirmed.
                if runner is not None:
                    if session_created:
                        try:
                            await runner.session_service.delete_session(
                                app_name=app_name,
                                user_id="local_operator",
                                session_id=session_id,
                            )
                            receipt.data["lifecycle"]["session_deleted"] = True
                        except BaseException as error:
                            close_errors.append(error)
                    try:
                        await runner.close()
                        receipt.data["lifecycle"]["runner_closed"] = True
                    except BaseException as error:
                        close_errors.append(error)
                elif receipt is not None:
                    receipt.data["lifecycle"].update(
                        session_deleted=True, runner_closed=True
                    )
                if native is not None:
                    try:
                        await native.close()
                    except BaseException as error:
                        close_errors.append(error)
                elif receipt is not None:
                    receipt.data["lifecycle"].update(sdk_closed=True, http_closed=True)
                if close_errors:
                    failure = failure or close_errors[0]
                if receipt is not None:
                    receipt.data["cleanup_errors"] = [
                        {"name": type(e).__name__, "message": str(e)}
                        for e in close_errors
                    ]
                    try:
                        if failure is None:
                            receipt.guard()
                        receipt.finish(result, failure)
                    except BaseException as error:
                        failure = failure or error
                        receipt.data.update(
                            status="failed",
                            result=None,
                            durable_status="failed",
                            recording_error={
                                "name": type(error).__name__,
                                "message": str(error),
                            },
                        )
                        try:
                            receipt.save(final=True)
                        except BaseException:
                            receipt.data["durable_status"] = "unknown"
                self.active.pop(input.thread_id, None)
        if failure is not None:
            if isinstance(failure, (asyncio.CancelledError, GeneratorExit)):
                if receipt is not None:
                    failure.receipt_path = str(receipt.path)
                    failure.evidence = receipt.data
                raise failure
            yield RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=f"{type(failure).__name__}: {failure}",
                code="ONBOARDING_FAILED",
            )
            return
        self.histories[input.thread_id] = (
            self.histories[input.thread_id]
            + [{"user": message, "assistant": result["answer"]}]
        )[-8:]
        for event in terminal:
            yield event
        yield StateSnapshotEvent(
            type=EventType.STATE_SNAPSHOT, snapshot=result["state"]
        )
        yield RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=input.thread_id,
            run_id=input.run_id,
            result={"receipt_path": str(receipt.path)},
        )

    def release_reservation(self, thread_id):
        if self.active.get(thread_id, "missing") is None:
            self.active.pop(thread_id, None)

    async def close(self):
        self.closed = True
        tasks = {
            t
            for t in self.active.values()
            if t is not None and t is not asyncio.current_task()
        }
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.active.clear()
        self.histories.clear()
