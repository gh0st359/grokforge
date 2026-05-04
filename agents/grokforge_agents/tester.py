"""Tester agent.

Materializes the Coder's files into a tempdir, runs pytest, and emits
typed events so the user can watch the test suite assemble, install
dependencies (when applicable), execute, and report pass/fail with the
captured output.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
import time
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

        self.think(
            f"The Coder produced {len(files)} file(s). I'll write them to a tempdir, "
            "run pytest, and report back with the exit code and captured output. "
            "If acceptance criteria are missing tests, I'll synthesize extras from the plan.",
            scope="strategy",
        )
        for f in files[:10]:
            self.log(f"received: {f['path']} ({len(f.get('content', ''))} bytes)")

        if self.router.client.configured:
            self.tool_call("grok.chat", {"stage": "tester", "json_mode": True})
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
                self.metric("tokens_cost_usd", round(cost, 4), "$")
                self.tool_call("grok.chat.return", {"model": model, "cost_usd": cost})
                extra = _safe_json(text)
                for f in extra.get("files", []):
                    if "path" in f and "content" in f:
                        files.append(f)
                        self.file_written(f["path"], f["content"], language="python")
            except Exception as e:
                self.think(f"acceptance-test synthesis skipped: {e}", scope="fallback")

        self.decide(
            "run pytest in subprocess inside a tempdir",
            "Hermetic by construction (no install side-effects on the host); "
            "120s wall timeout guards against runaway tests.",
        )

        result = await self._run_pytest(files)

        if result.get("exit_code") == 0:
            self.think(
                f"pytest passed in {result['duration']:.2f}s. Forwarding to the Reviewer.",
                scope="success",
            )
        elif result.get("timed_out"):
            self.think("pytest hit the 120s wall timeout — likely an infinite loop or hang.", scope="fail")
        else:
            self.think(
                f"pytest failed (exit={result.get('exit_code')}). "
                f"Captured tail of stderr:\n{(result.get('stderr') or '')[-800:]}",
                scope="fail",
            )

        self.metric("test_duration_seconds", round(result.get("duration", 0.0), 3), "s")
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
            self.think("pytest is not installed in the agent container — skipping execution.",
                       scope="environment")
            return {"exit_code": None, "skipped": "pytest not installed", "duration": 0.0}
        with tempfile.TemporaryDirectory(prefix="grokforge-test-") as td:
            root = Path(td)
            for f in files:
                p = root / f["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f["content"])

            self.tool_call("subprocess", {
                "cmd": [sys.executable, "-m", "pytest", "-q", "--maxfail=5"],
                "cwd": str(root),
            })
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

            duration = time.monotonic() - start
            self.tool_call("subprocess.return", {
                "exit_code": proc.returncode,
                "duration_seconds": round(duration, 3),
            })
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode(errors="replace")[-4000:],
                "stderr": stderr.decode(errors="replace")[-2000:],
                "duration": duration,
            }


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"files": []}
