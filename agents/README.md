# grokforge-agents

Python package implementing the specialized agents that drive grokforge: Planner, Coder, Tester, Reviewer, Verifier, Deployer.

The package exposes a FastAPI service consumed by the Rust core. Each `POST /agents/run` request specifies a `stage` and the orchestrator-supplied `input`; the agent returns its output, a confidence score, the LLM cost, and structured logs.

```bash
pip install -e .
uvicorn grokforge_agents.server:app --reload --port 8001
```

Required env:

| Variable | Purpose |
|---|---|
| `GROK_API_KEY` | xAI API key (`xai-...`) |
| `GROK_BASE_URL` | default `https://api.x.ai/v1` |
| `GROK_PRIMARY_MODEL` | default `grok-4-3` |
| `GROK_FALLBACK_MODEL` | default `grok-4-mini` |
| `MAX_DEBATE_ROUNDS` | default `4` |
| `CONFIDENCE_THRESHOLD` | default `0.95` |

If `GROK_API_KEY` is unset the service runs in *deterministic mock* mode that produces a runnable FastAPI scaffold from any spec — useful for CI and local dev.
