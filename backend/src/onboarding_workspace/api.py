"""Workspace API plus ADK-to-AG-UI stream for CopilotKit."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from ag_ui.core import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from google.adk.models.base_llm import BaseLlm

from .runtime import Runtime
from .http_boundary import StrictJSONMiddleware
from .store import Conflict, Workspace
from .schema import Strict, Revision, Email


class NameUpdate(Strict):
    name: str
    revision: Revision
    actor: Email


class Decision(Strict):
    revision: Revision
    decision: str
    actor: Email


def create_app(
    workspace_path: Path,
    include_agent: bool = True,
    agent_model: BaseLlm | None = None,
    *,
    native_config=None,
    transport_factory=None,
    output_root=None,
    timeout_seconds=120,
    writer=None,
) -> FastAPI:
    workspace = Workspace(workspace_path)
    runtime = (
        Runtime(
            workspace,
            config=native_config,
            agent_model=agent_model,
            transport_factory=transport_factory,
            output_root=output_root,
            timeout_seconds=timeout_seconds,
            writer=writer,
        )
        if include_agent
        else None
    )

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            if runtime is not None:
                await runtime.close()

    app = FastAPI(title="Onboarding copilot workspace", lifespan=lifespan)
    app.state.runtime = runtime
    app.add_middleware(StrictJSONMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("ONBOARDING_WEB_ORIGIN", "http://localhost:3000")],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )

    @app.get("/workspace")
    def detail():
        return workspace.detail()

    @app.patch("/workspace/name")
    def set_name(body: NameUpdate):
        try:
            return workspace.set_name(body.name, body.revision, body.actor)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/proposals/{proposal_id}/decision")
    def decide(proposal_id: str, body: Decision):
        try:
            return workspace.decide(
                proposal_id, body.revision, body.decision, body.actor
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    if include_agent:

        @app.post("/agent")
        async def agent_endpoint(input_data: RunAgentInput, request: Request):
            try:
                message = runtime.reserve(input_data)
            except ValueError as error:
                raise HTTPException(409, str(error)) from error
            encoder = EventEncoder(accept=request.headers.get("accept"))

            async def stream():
                from contextlib import aclosing

                async with aclosing(runtime.events(input_data, message)) as events:
                    async for event in events:
                        yield encoder.encode(event)

            return StreamingResponse(
                stream(),
                media_type=encoder.get_content_type(),
                background=BackgroundTask(
                    runtime.release_reservation, input_data.thread_id
                ),
            )

    return app


def cli():
    import argparse
    import json
    import uvicorn
    from .datasets import initialize, inspect_workspace, reset, list_cases

    parser = argparse.ArgumentParser(
        description="Synthetic onboarding workspace and owned ADK/Gemini server"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["datasets", "init", "workspace", "reset", "serve"],
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(
            os.getenv("ONBOARDING_WORKSPACE_FILE", "run-output/workspace.json")
        ),
    )
    parser.add_argument("--case", default="incomplete-setup")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--port", type=int, default=8125)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.command == "datasets":
        result = list_cases()
    elif args.command == "init":
        result = initialize(args.workspace, args.case)
    elif args.command == "workspace":
        result = inspect_workspace(args.workspace, Workspace(args.workspace).read())
    elif args.command == "reset":
        if args.destination is None:
            parser.error("reset needs --destination")
        result = reset(
            args.workspace, args.destination, Workspace(args.workspace).read()
        )
    else:
        uvicorn.run(
            create_app(
                args.workspace,
                include_agent=not args.offline
                and os.getenv("ONBOARDING_OFFLINE") != "1",
            ),
            host="127.0.0.1",
            port=args.port,
            timeout_graceful_shutdown=1,
        )
        return
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    import json

    try:
        cli()
    except (ValueError, OSError) as error:
        print(
            json.dumps(
                {"ok": False, "error": type(error).__name__, "message": str(error)}
            )
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
