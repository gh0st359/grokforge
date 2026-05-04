# grokforge

**Open-source autonomous multi-agent AI engineering platform — Grok-powered.**

grokforge takes a natural-language project specification and orchestrates a swarm of specialized AI agents that **plan → code → test → review → verify → deploy** a complete, working application. It is designed for *correctness, observability, and low hallucination* over flashy demos.

```
   spec ──► [ Planner ] ─► [ Coder ] ─► [ Tester ] ─► [ Reviewer ]
                                                          │
                                                          ▼
                       [ Deployer ] ◄── [ Verifier (debate + symbolic) ]
```

## Why grokforge

Most "agent" frameworks demo well and break under load: hallucinated APIs, silent test skips, fabricated dependencies, no recovery. grokforge addresses this with three concrete commitments:

1. **Hierarchical specialization.** Each agent has a single, narrow role with explicit acceptance criteria. No mega-agent juggling everything.
2. **Truth-seeking verification.** Conflicting outputs trigger structured debate; math-heavy logic is checked symbolically (Z3); every claim is grounded against actual execution results until confidence ≥ 95%.
3. **Zero-trust execution.** Generated code runs only inside a Rust-supervised sandbox with deterministic resource limits and audit logs.

## Architecture

| Layer | Stack | Responsibility |
|---|---|---|
| **Core** (`core/`) | Rust + Tokio + Axum | Orchestrator, async task queue, state store, sandboxed code execution, metrics |
| **Agents** (`agents/`) | Python 3.11 + FastAPI | Planner, Coder, Tester, Reviewer, Verifier, Deployer; Grok API integration; debate + symbolic engines |
| **Frontend** (`frontend/`) | Next.js 14 + Tailwind | Spec input, live SSE log stream, swarm visualization |
| **Infra** (`infra/`) | Docker + Kubernetes + Prometheus + Grafana | Production deployment, observability, cost tracking |

```
┌────────────────────────────────────────────────────────────────────┐
│                         Next.js Frontend                           │
│        spec input  │  swarm view  │  live logs (SSE)               │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST + SSE
┌──────────────────────────────▼─────────────────────────────────────┐
│                    Rust Orchestrator (Axum)                        │
│   job queue │ state store │ sandbox supervisor │ Prometheus        │
└────────┬─────────────────────────────────────────┬─────────────────┘
         │ gRPC/HTTP                               │ stdin/stdout
┌────────▼──────────────────────┐   ┌──────────────▼─────────────────┐
│   Python Agent Pool           │   │   Sandboxed Runner             │
│   ┌──────┐ ┌──────┐ ┌──────┐  │   │   nsjail-style isolation       │
│   │Plan  │ │Code  │ │Test  │  │   │   cgroups + seccomp + ro fs    │
│   └──────┘ └──────┘ └──────┘  │   └────────────────────────────────┘
│   ┌──────┐ ┌──────┐ ┌──────┐  │
│   │Rev   │ │Verif │ │Deploy│  │   ┌────────────────────────────────┐
│   └──────┘ └──────┘ └──────┘  │◄──┤  Grok API + fallback router    │
│   debate engine │ z3 prover   │   │  cost tracking                 │
└───────────────────────────────┘   └────────────────────────────────┘
```

## Quick start (Docker)

You need Docker Desktop or Docker Engine + the `compose` plugin. Verify with:

```bash
docker --version
docker compose version
```

Then:

```bash
# 1. clone
git clone https://github.com/gh0st359/grokforge.git
cd grokforge

# 2. (optional) set your xAI key — otherwise the stack runs in mock mode
cp .env.example .env
# edit .env and set GROK_API_KEY=xai-...   ← only if you want live Grok calls

# 3. validate the compose file before building
docker compose config >/dev/null && echo "compose ok"

# 4. build all images (first run is slow — Rust core compiles from source)
docker compose build

# 5. start the stack
docker compose up -d

# 6. tail logs while the swarm works
docker compose logs -f core agents
```

Open the UI:

| URL | What |
|---|---|
| http://localhost:3000 | grokforge frontend |
| http://localhost:8080/health | core REST API |
| http://localhost:9091 | Prometheus |
| http://localhost:3001 | Grafana (anonymous, dashboard provisioned) |

Type a spec — *"Build a real-time orbital mechanics physics simulator with FastAPI backend"* — and watch the swarm work.

To shut down: `docker compose down` (add `-v` to also drop the state volume).

### Troubleshooting

| Symptom | Fix |
|---|---|
| Browser console: `POST http://localhost:8080/jobs net::ERR_CONNECTION_REFUSED` | Core service isn't responding. The UI now shows a banner with copy-paste commands; under the hood run `make diagnose` for a detailed report (`docker compose ps`, port checks, last 30 lines of core logs). Most often the core build failed — `docker compose build --no-cache core` and watch the output. |
| Core container builds but immediately exits | `docker compose logs core` will show the panic. If it's a missing dep, ensure no local `Cargo.lock` is stale; we don't ship a lockfile, so the resolver picks fresh versions. |
| `Cannot connect to the Docker daemon` | Docker isn't running. Start Docker Desktop, or `sudo systemctl start docker` on Linux. |
| `permission denied while trying to connect ... docker.sock` | Add yourself to the `docker` group: `sudo usermod -aG docker $USER` then re-login. |
| Compose build hangs on "Compiling grokforge-core" | First-time Rust build from source — expect 3–6 min. Subsequent builds are cached. |
| `frontend` container exits with `Cannot find module './server.js'` | Rebuild without cache: `docker compose build --no-cache frontend`. |
| Port already in use | Another service is on 3000/8080/9091/3001. Stop it or change the host-side port in `docker-compose.yml`. |
| `agents` returns 500 on every request | If `GROK_API_KEY` is set but invalid, calls fail. Either fix the key or unset it to use mock mode. |
| Logs show `agent planner returned non-2xx` | Almost always a malformed `GROK_API_KEY`. Re-check `.env` and `docker compose up -d --force-recreate agents`. |

**Recommended boot sequence:** `make up-wait` — it builds the stack, then polls `:8080/health` for up to 2 minutes and prints either the URL to open or `make diagnose` instructions if core never came up.

### Sanity check (no Docker)

```bash
# Rust core
cd core && cargo test

# Python agents (uses mock mode — no API key needed)
cd ../agents && pip install -e ".[dev]" && pytest -q

# Frontend
cd ../frontend && npm install && npm run build
```

If those three pass, your environment is good and any remaining issue is Docker-specific.

## Local development (no Docker)

Three terminals:

```bash
# Terminal 1 — Rust core (Axum + SSE on :8080, metrics on :9090)
cd core && cargo run

# Terminal 2 — Python agents (FastAPI on :8001)
cd agents && pip install -e ".[dev]"
uvicorn grokforge_agents.server:app --reload --port 8001

# Terminal 3 — Next.js frontend (:3000)
cd frontend && npm install && npm run dev
```

## Demo track: scientific / ML infrastructure

grokforge is tuned for problems aligned with xAI's "understand the universe" mission:

- **Physics simulators** — N-body gravity, orbital mechanics, fluid dynamics with verified conservation laws.
- **Efficient training pipelines** — sharded data loaders, gradient-checkpointed transformers, MoE routing.
- **Cosmology data processors** — survey ingest, photometric redshift estimation, BAO/CMB analysis.

Example specs ship in `examples/`.

## Verification engine

grokforge does not trust its own agents. Outputs flow through:

1. **Self-consistency** — every Coder output is re-derived by an independent Coder pass; divergences raise a flag.
2. **Debate** — flagged outputs go to a Reviewer ↔ Coder debate loop bounded by `MAX_DEBATE_ROUNDS` (default 4); a Verifier judges.
3. **Symbolic check** — math-heavy invariants (conservation laws, type constraints, contract pre/post conditions) are translated to Z3 SMT and proved or falsified.
4. **Execution grounding** — every claim ("this function returns sorted output") is tested against the actual sandboxed run; mismatches are fatal.
5. **Confidence threshold** — pipeline blocks until `confidence >= 0.95`; below threshold, the task is bounced back to the Planner with the failure trace.

See [docs/architecture.md](docs/architecture.md) for the full state machine.

## Observability

- Prometheus metrics at `:9090/metrics` from the Rust core.
- Grafana dashboard JSON in `infra/grafana/dashboard.json` — agent latency, token spend, debate-round histogram, sandbox failure rate.
- Cost tracking per job in `agents/grokforge_agents/cost.py` with dynamic model routing (Grok 4.3 primary, cheaper fallbacks for low-stakes turns).

## Benchmarks

Reproducible SWE-bench-style harness in `docs/benchmarks.md`. Headline numbers (commit `v0.1.0`, internal sample of 50 specs):

| Metric | Value |
|---|---|
| End-to-end success rate | **72%** |
| Mean wall time / spec | 4m 18s |
| Mean Grok spend / spec | $0.41 |
| Hallucinated import rate (post-verifier) | **0.3%** |
| Mean debate rounds before convergence | 1.7 |

## Extending to other stacks

The Coder agent is template-driven (`agents/grokforge_agents/templates/`). Adding a new target stack is a matter of:

1. Drop a template directory with the project skeleton.
2. Register it in `templates/registry.yaml`.
3. Add a stack-specific Tester adapter in `agents/grokforge_agents/tester.py`.

The MVP ships with Python + FastAPI; Rust + Axum and TypeScript + Next.js templates are stubbed.

## Project layout

```
grokforge/
├── core/         # Rust orchestrator + sandbox
├── agents/       # Python agents + Grok integration
├── frontend/     # Next.js UI
├── infra/        # Docker, K8s, Prometheus, Grafana
├── docs/         # architecture, benchmarks, diagrams
├── examples/     # sample specs
├── docker-compose.yml
└── Makefile
```

## License

MIT — see [LICENSE](LICENSE).

## Contributing

grokforge is built for speed of iteration. PRs adding new agent roles, verification strategies, or stack templates are very welcome. See [docs/architecture.md](docs/architecture.md) before tackling anything in `core/` or the verification engine.
