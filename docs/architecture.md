# grokforge architecture

## Goals

1. **Reliable agentic engineering.** Take an English spec, produce a working,
   tested, packaged application — without fabrication.
2. **Observability over magic.** Every decision the swarm makes is logged,
   priced, and replayable.
3. **Extensibility.** Adding a new agent role, verification strategy, or
   target stack should not require touching the core.

## Component map

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                                  │
│  - SpecInput     submits POST /jobs                                  │
│  - SwarmView     polls GET /jobs/{id}                                │
│  - AgentLog      consumes SSE GET /jobs/{id}/events                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP + SSE
┌──────────────────────────────▼───────────────────────────────────────┐
│  Core (Rust, Axum, Tokio)                                            │
│  ├── api.rs           HTTP handlers + SSE                            │
│  ├── orchestrator.rs  pipeline driver, debate loop                   │
│  ├── queue.rs         async mpsc work queue                          │
│  ├── state.rs         job store + broadcast channel + JSONL persist  │
│  ├── sandbox.rs       rlimits + tempdir + wall timeout               │
│  ├── metrics.rs       Prometheus registry + /metrics                 │
│  └── config.rs        env-driven config                              │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ POST /agents/run
┌──────────────────────────────▼───────────────────────────────────────┐
│  Agents (Python, FastAPI)                                            │
│  ├── server.py        request dispatch                               │
│  ├── grok_client.py   xAI HTTP client w/ retries + cost              │
│  ├── router.py        primary/fallback model picker                  │
│  ├── planner.py       spec → milestones                              │
│  ├── coder.py         template render + LLM patch                    │
│  ├── tester.py        materialize + run pytest                       │
│  ├── reviewer.py      static scan + LLM review                       │
│  ├── verifier.py      grounding + debate + symbolic + aggregate      │
│  ├── debate.py        proponent / skeptic / judge                    │
│  ├── symbolic.py      Z3 helpers (energy, sort, typed claims)        │
│  └── deployer.py      Dockerfile + K8s + CI                          │
└──────────────────────────────────────────────────────────────────────┘
```

## Job lifecycle

```
queued → planning → coding → testing → reviewing → verifying ──┐
                                                               │
                        ┌──────────────────────────────────────┘
                        │
             confidence ≥ 0.95 ?
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
          deploying          (debate +1 round, retry verify)
              │                    │
              ▼                    │
          succeeded                ▼
                          rounds == MAX_DEBATE_ROUNDS ? → failed
```

The orchestrator drives this state machine. Every transition emits an
`AgentEvent` with `kind ∈ {log, status, artifact, cost, error, verdict}`,
which is broadcast to SSE subscribers and appended to
`STATE_DIR/jobs/{id}.jsonl` for replay.

## Verification engine

Five signals feed the aggregated confidence score:

| Signal | Weight | Source |
|---|---|---|
| Execution grounding | 0.40 | Tester subprocess exit code |
| Debate confidence | 0.40 | Judge verdict from debate.py |
| No high-severity review issues | 0.20 | Reviewer static + LLM scan |
| Symbolic soundness | bonus, capped at 0.04 | symbolic.py Z3 results |
| Round bonus | linear up to 0.04 | Number of debate rounds completed |

The threshold (`CONFIDENCE_THRESHOLD`, default 0.95) is intentionally high.
Below threshold the Verifier runs another debate round. After
`MAX_DEBATE_ROUNDS` (default 4) without convergence, the job is failed and
the failure trace (which signals tripped low) is surfaced to the operator.

### Why debate?

Single-pass LLM self-evaluation has a well-known sycophancy bias. Splitting
the role into `proponent` and `skeptic` with adversarial prompts forces
divergent arguments into the transcript before the `judge` rules. The judge
is held to an explicit calibration ("set ≥ 0.95 only if you would stake
your reputation on shipping this as-is").

### Why symbolic?

Math-heavy claims ("conservation of energy holds for this integrator") are
exactly where LLMs hallucinate confidently. Where we can encode the claim
as an SMT formula, we should. `symbolic.py` ships ready-to-use checks for
the demo track (physics) and a stub for claim-driven proof.

## Sandboxing

`core/src/sandbox.rs` uses a defense-in-depth approach **without** requiring
root or container privileges:

- Fresh `tempfile::tempdir()` as working directory
- `env_clear()` then minimal PATH/HOME/LANG only
- Linux: `setrlimit` for `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_FSIZE`
- Linux: `setpgid(0, 0)` so timeout SIGKILL reaps the whole process tree
- Tokio `timeout` enforces wall-clock hard limit
- `Stdio::piped()` capture of stdout/stderr, with size-bounded reads

For multi-tenant production use, wrap this with nsjail / firecracker /
gVisor. The current primitives are correct defaults for trusted single-tenant
operators (CI, dev laptops, internal demos).

## Cost & routing

`agents/grokforge_agents/router.py` selects between:

- `GROK_PRIMARY_MODEL` (default `grok-4-3`) — used for high-stakes turns
  (planning, verification, review).
- `GROK_FALLBACK_MODEL` (default `grok-4-mini`) — used for low-stakes
  turns (deploy artifact synthesis) and for the first attempt of
  Coder/Tester turns.

If a fallback turn fails, the router escalates to primary. If the primary
key isn't configured, the router enters **mock mode** — deterministic
responses keyed off the stage name — so the entire stack can run offline.

Costs are estimated locally from `usage.prompt_tokens` /
`usage.completion_tokens` against a hard-coded price table (`PRICING` in
`grok_client.py`). Refresh that table when xAI changes list pricing.

## State persistence

JSONL per job under `STATE_DIR/jobs/{id}.jsonl`. Each line is one
`AgentEvent`. This is sufficient to replay the full UI for a finished job.
A future migration to SQLite or Postgres is straightforward — the
`StateStore` trait is intentionally narrow.

## Extensibility points

| Want to... | Touch... |
|---|---|
| Add a new agent role | `agents/grokforge_agents/`, register in `server.py` |
| Add a new verification strategy | extend `verifier.py` or `symbolic.py` |
| Add a new target stack | `templates/`, add adapter in `tester.py` |
| Replace Grok with another LLM | swap `grok_client.py` (keep return signature) |
| Replace the sandbox | implement same `Sandbox` API in `core/src/sandbox.rs` |
