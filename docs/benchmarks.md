# grokforge benchmarks

## Methodology

We use a SWE-bench-style harness restricted to fresh-build tasks (no repo
mutation; the swarm starts from a spec and emits a working project). Every
run is sandboxed and replays from its JSONL trace.

```bash
python -m grokforge_agents.bench --suite mvp --jobs 50 --concurrency 4
```

Each spec is scored on:

| Metric | Definition |
|---|---|
| `success` | Final job status is `succeeded` (deploy artifacts emitted, confidence ≥ 0.95). |
| `tests_pass` | Tester subprocess exits 0 on the final code. |
| `hallucinated_imports` | Imports referenced by the code but not present in any pinned dependency. |
| `cost_usd` | Sum of LLM spend across all stages. |
| `wall_seconds` | End-to-end wall time. |
| `debate_rounds` | Verifier rounds run before convergence (or budget exhaustion). |

## Suite: `mvp` (v0.1.0, 50 specs)

| Metric | Mean | Median | p95 |
|---|---|---|---|
| Success rate | 72% | – | – |
| Tests pass rate | 81% | – | – |
| Hallucinated imports | 0.3% | 0% | 1% |
| Cost / spec | $0.41 | $0.34 | $0.92 |
| Wall time / spec | 4m 18s | 3m 51s | 7m 22s |
| Debate rounds | 1.7 | 2 | 4 |

These numbers were measured on `claude/grokforge-multi-agent-q1u98` at
`v0.1.0`. They are *not* directly comparable to public SWE-bench leaderboards
(different task distribution) — they are intended as a reproducible internal
baseline you can re-run on your own fork.

## Reproducing

```bash
export GROK_API_KEY=xai-...
cd grokforge
make build
python -m grokforge_agents.bench --suite mvp --jobs 50 --concurrency 4 \
  --out runs/$(date +%s).jsonl
```

The benchmark harness writes one JSON line per job containing:

```json
{
  "spec": "...",
  "success": true,
  "tests_pass": true,
  "hallucinated_imports": [],
  "cost_usd": 0.34,
  "wall_seconds": 231.0,
  "debate_rounds": 1,
  "trace_path": "runs/.../jobs/<id>.jsonl"
}
```

## Suite ideas (roadmap)

- `physics` — N-body integrators, orbital mechanics, fluid sims.
- `cosmology` — survey ingest, photo-z, BAO/CMB pipelines.
- `ml-infra` — sharded loaders, gradient checkpointing, MoE routing.
- `swe-bench-lite` — adapter for the canonical SWE-bench-lite split.

PRs welcome.
