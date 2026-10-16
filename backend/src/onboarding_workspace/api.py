"""Workspace API plus ADK-to-AG-UI stream for CopilotKit."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.adk.models.base_llm import BaseLlm

from .agent import build_agent
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
    workspace_path: Path, include_agent: bool = True, agent_model: BaseLlm | None = None
) -> FastAPI:
    workspace = Workspace(workspace_path)
    app = FastAPI(title="Onboarding copilot workspace")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
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
        from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

        adk_agent = build_agent(workspace, agent_model)
        bridge = ADKAgent(
            adk_agent=adk_agent,
            app_name="onboarding_workspace",
            user_id="local_operator",
        )
        add_adk_fastapi_endpoint(app, bridge, path="/agent")
    return app


def main():
    import uvicorn

    path = Path(
        os.getenv(
            "ONBOARDING_WORKSPACE_FILE",
            str(Path(__file__).parents[3] / "workspace.json"),
        )
    )
    uvicorn.run(
        create_app(path, include_agent=os.getenv("ONBOARDING_OFFLINE") != "1"),
        host="127.0.0.1",
        port=8125,
    )


if __name__ == "__main__":
    main()
