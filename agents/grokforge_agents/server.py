"""FastAPI server exposing the agent pool to the Rust core."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .base import AgentResponse
from .coder import CoderAgent
from .deployer import DeployerAgent
from .grok_client import GrokClient
from .planner import PlannerAgent
from .reviewer import ReviewerAgent
from .router import ModelRouter
from .tester import TesterAgent
from .verifier import VerifierAgent

logger = logging.getLogger("grokforge.agents")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class RunRequest(BaseModel):
    job_id: UUID
    stage: str
    input: dict[str, Any] = {}


class State:
    grok: GrokClient
    router: ModelRouter
    agents: dict[str, Any]


state = State()


@asynccontextmanager
async def lifespan(_: FastAPI):
    state.grok = GrokClient()
    state.router = ModelRouter(state.grok)
    state.agents = {
        "planner": PlannerAgent(state.router),
        "coder": CoderAgent(state.router),
        "tester": TesterAgent(state.router),
        "reviewer": ReviewerAgent(state.router),
        "verifier": VerifierAgent(state.router),
        "deployer": DeployerAgent(),
    }
    logger.info(
        "grokforge-agents ready (live=%s primary=%s fallback=%s)",
        state.grok.configured,
        ModelRouter.PRIMARY,
        ModelRouter.FALLBACK,
    )
    try:
        yield
    finally:
        await state.grok.aclose()


app = FastAPI(title="grokforge-agents", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "live_grok": state.grok.configured if hasattr(state, "grok") else False,
        "agents": list(state.agents.keys()) if hasattr(state, "agents") else [],
    }


@app.post("/agents/run", response_model=AgentResponse)
async def run(req: RunRequest) -> AgentResponse:
    agent = state.agents.get(req.stage)
    if agent is None:
        raise HTTPException(404, f"unknown stage: {req.stage}")
    try:
        from .base import AgentRequest as InternalReq
        return await agent.execute(InternalReq(job_id=req.job_id, stage=req.stage, input=req.input))
    except Exception as e:  # noqa: BLE001
        logger.exception("agent %s failed", req.stage)
        raise HTTPException(500, f"agent {req.stage} failed: {e}") from e
