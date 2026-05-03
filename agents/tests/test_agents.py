"""Smoke tests for the agent pool in mock mode (no GROK_API_KEY required)."""

from __future__ import annotations

import os
import uuid

import pytest

# Force mock mode regardless of host env
os.environ.pop("GROK_API_KEY", None)

from grokforge_agents.base import AgentRequest  # noqa: E402
from grokforge_agents.coder import CoderAgent  # noqa: E402
from grokforge_agents.deployer import DeployerAgent  # noqa: E402
from grokforge_agents.grok_client import GrokClient  # noqa: E402
from grokforge_agents.planner import PlannerAgent  # noqa: E402
from grokforge_agents.reviewer import ReviewerAgent  # noqa: E402
from grokforge_agents.router import ModelRouter  # noqa: E402
from grokforge_agents.symbolic import (  # noqa: E402
    check_conservation_of_energy,
    check_sort_invariant,
)
from grokforge_agents.verifier import VerifierAgent  # noqa: E402


@pytest.fixture
def router() -> ModelRouter:
    return ModelRouter(GrokClient(api_key=None))


@pytest.mark.asyncio
async def test_planner_returns_milestones(router: ModelRouter) -> None:
    agent = PlannerAgent(router)
    resp = await agent.execute(AgentRequest(
        job_id=uuid.uuid4(), stage="planner",
        input={"spec": "Build a REST API that returns the current time."},
    ))
    assert resp.output.get("milestones"), resp
    assert resp.confidence > 0.5


@pytest.mark.asyncio
async def test_coder_emits_files(router: ModelRouter) -> None:
    agent = CoderAgent(router)
    resp = await agent.execute(AgentRequest(
        job_id=uuid.uuid4(), stage="coder",
        input={"stack": "python+fastapi", "summary": "demo", "milestones": []},
    ))
    paths = {f["path"] for f in resp.output["files"]}
    assert "app/main.py" in paths
    assert "requirements.txt" in paths


@pytest.mark.asyncio
async def test_reviewer_flags_eval(router: ModelRouter) -> None:
    agent = ReviewerAgent(router)
    bad = {"files": [{"path": "app/main.py", "content": "x = eval(input())"}]}
    resp = await agent.execute(AgentRequest(
        job_id=uuid.uuid4(), stage="reviewer",
        input={"plan": {}, "code": bad, "tests": {}},
    ))
    severities = {i.get("severity") for i in resp.output["issues"]}
    assert "high" in severities


@pytest.mark.asyncio
async def test_verifier_aggregates(router: ModelRouter) -> None:
    agent = VerifierAgent(router)
    resp = await agent.execute(AgentRequest(
        job_id=uuid.uuid4(), stage="verifier",
        input={
            "plan": {"spec": "physics simulator"},
            "code": {"files": [{"path": "app/main.py"}]},
            "tests": {"result": {"exit_code": 0}},
            "review": {"issues": []},
            "round": 1,
        },
    ))
    assert "confidence" in resp.output


@pytest.mark.asyncio
async def test_deployer_packages(router: ModelRouter) -> None:
    agent = DeployerAgent()
    resp = await agent.execute(AgentRequest(
        job_id=uuid.uuid4(), stage="deployer",
        input={"code": {"files": [{"path": "app/main.py", "content": "x=1"}]}},
    ))
    paths = {f["path"] for f in resp.output["files"]}
    assert "Dockerfile" in paths
    assert "k8s/deployment.yaml" in paths


def test_symbolic_sort() -> None:
    assert check_sort_invariant([1, 2, 3]).proved is True
    assert check_sort_invariant([3, 1, 2]).proved is False


def test_symbolic_energy() -> None:
    r = check_conservation_of_energy([1.0], [[2.0]], [[2.0]])
    assert r.proved is True
    r2 = check_conservation_of_energy([1.0], [[2.0]], [[3.0]])
    assert r2.proved is False
