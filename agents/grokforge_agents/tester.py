"""Tester agent.

Materializes the Coder's files into a tempdir, runs the project's tests in
a subprocess, and reports pass/fail with the captured output. The Rust
sandbox is the production isolation boundary; this agent uses a local
subprocess fallback for environments where the sandbox isn't reachable
(e.g. unit tests of the agent itself).
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .base import Agent, AgentRequest
from .router import ModelRouter

SYSTEM_PROMPT = """You are the Tester agent in grokforge.
Given the source files and plan acceptance criteria, emit additional pytest
tests that *prove* each acceptance criterion. Return JSON:
{"files": [{"path": "tests/test_acceptance.py", "content": "..."}], "command": "pytest -q"}
Tests must be deterministic, hermetic (no network), and fail fast on regression.
"""


class TesterAgent(Agent):
    name = "tester"

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self.router = router

    async def run(self, req: AgentRequest) -> dict[str, Any]:
        coder_out = req.input or {}
        files: list[dict[str, str]] = list(coder_out.get("files", []))

        # Optional: ask the LLM for additional acceptance tests.
        try:
            text, cost, model = await self.router.chat(
                "tester",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({
                        "files": [f["path"] for f in files],
                    })},
                ],
                temperature=0.1, max_tokens=2000, json_mode=True,
            )
            self.cost_usd += cost
            self.log(f"used model={model} cost=${cost:.4f}")
            extra = _safe_json(text)
            for f in extra.get("files", []):
                if "path" in f and "content" in f:
                    files.append(f)
        except Exception as e:  # noqa: BLE001
            self.log(f"LLM test generation skipped: {e}")

        # Run tests
        result = await self._run_pytest(files)
        self.log(f"pytest exit={result['exit_code']} duration={result['duration']:.2f}s")
        return {
            "files": files,
            "command": coder_out.get("test_command", "pytest -q"),
            "result": result,
        }

    async def confidence(self, output: dict[str, Any]) -> float:
        result = output.get("result", {})
        if result.get("exit_code") == 0:
            return 0.9
        if result.get("exit_code") is None:
            return 0.2
        return 0.4

    async def _run_pytest(self, files: list[dict[str, str]]) -> dict[str, Any]:
        if shutil.which("pytest") is None:
            return {"exit_code": None, "skipped": "pytest not installed", "duration": 0.0}
        with tempfile.TemporaryDirectory(prefix="grokforge-test-") as td:
            root = Path(td)
            for f in files:
                p = root / f["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f["content"])
            req = root / "requirements.txt"
            if req.exists():
                # Best-effort: install into current env (pytest itself uses host pytest).
                # Skipping pip install in-line to keep tests fast and offline-safe.
                self.log(f"requirements.txt found at {req}, skipping install in agent process")

            import time

            start = time.monotonic()
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pytest", "-q", "--maxfail=5",
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                proc.kill()
                return {"exit_code": None, "timed_out": True, "duration": time.monotonic() - start}
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode(errors="replace")[-4000:],
                "stderr": stderr.decode(errors="replace")[-2000:],
                "duration": time.monotonic() - start,
            }


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"files": []}
