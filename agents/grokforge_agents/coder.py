"""Coder agent.

Renders a runnable project skeleton from a Jinja2 template selected by the
plan's `stack` field, then optionally asks Grok to fill in the
domain-specific endpoint(s) from the spec. Returns a list of
{path, content} pairs which the Tester will materialize on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .base import Agent, AgentRequest
from .router import ModelRouter

TEMPLATE_DIR = Path(__file__).parent / "templates"

SYSTEM_PROMPT = """You are the Coder agent in grokforge.
Given a project plan, emit production-grade source files as strict JSON:
{"files": [{"path": "app/main.py", "content": "..."}], "entrypoint": "uvicorn app.main:app"}

Rules:
- All file contents must be self-consistent and runnable as-is.
- Imports must reference real, currently-pinned packages.
- No placeholders ("TODO", "...", "your code here"). Fill everything.
- Include a `requirements.txt` and a `Dockerfile`.
- Keep it small: <= 8 files, <= 600 lines total.
Return only JSON.
"""


class CoderAgent(Agent):
    name = "coder"

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self.router = router
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
            keep_trailing_newline=True,
        )

    async def run(self, req: AgentRequest) -> dict[str, Any]:
        plan = req.input or {}
        stack = plan.get("stack", "python+fastapi")
        self.log(f"coding stack={stack}")

        # Always start from the deterministic template so we have a known-good baseline.
        files = self._render_template(stack, plan)

        # Then ask the LLM to layer on the spec-specific logic.
        prompt = (
            "PLAN:\n" + json.dumps(plan, indent=2)
            + "\n\nBaseline files already exist (FastAPI scaffold). "
            + "Replace ONLY the contents of `app/main.py` and add new files under `app/` "
            + "that implement the spec's milestones. Return JSON in the schema described."
        )
        try:
            text, cost, model = await self.router.chat(
                "coder",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
                json_mode=True,
            )
            self.cost_usd += cost
            self.log(f"used model={model} cost=${cost:.4f}")
            patch = _safe_json(text)
            for f in patch.get("files", []):
                if "path" in f and "content" in f:
                    files[f["path"]] = f["content"]
        except Exception as e:  # noqa: BLE001
            self.log(f"LLM patch failed, using baseline scaffold: {e}")

        return {
            "files": [{"path": p, "content": c} for p, c in sorted(files.items())],
            "entrypoint": "uvicorn app.main:app --host 0.0.0.0 --port 8000",
            "stack": stack,
        }

    async def confidence(self, output: dict[str, Any]) -> float:
        files = output.get("files", [])
        if not files:
            return 0.1
        has_main = any(f["path"].endswith("main.py") for f in files)
        has_req = any(f["path"].endswith("requirements.txt") for f in files)
        has_test = any("test" in f["path"] for f in files)
        return 0.4 + 0.2 * has_main + 0.2 * has_req + 0.2 * has_test

    def _render_template(self, stack: str, plan: dict[str, Any]) -> dict[str, str]:
        # Map stack id to template directory; we ship python+fastapi as the only one.
        stack_dir = {
            "python+fastapi": "python_fastapi",
            "rust+axum": "python_fastapi",  # fallback until rust+axum template ships
            "typescript+next": "python_fastapi",
        }.get(stack, "python_fastapi")

        root = TEMPLATE_DIR / stack_dir
        out: dict[str, str] = {}
        if not root.exists():
            return out
        ctx = {
            "summary": plan.get("summary", "grokforge generated service"),
            "milestones": plan.get("milestones", []),
        }
        for path in root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                if rel.endswith(".j2"):
                    rel = rel[:-3]
                    template = self.env.get_template(f"{stack_dir}/{path.relative_to(root).as_posix()}")
                    out[rel] = template.render(**ctx)
                else:
                    out[rel] = path.read_text()
        return out


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"files": []}
