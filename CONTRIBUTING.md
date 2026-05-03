# Contributing

grokforge is built for speed of iteration. PRs welcome — especially:

- New agent roles or verification strategies (`agents/grokforge_agents/`)
- New stack templates (`agents/grokforge_agents/templates/` + `tester.py` adapter)
- Improvements to the sandbox (`core/src/sandbox.rs`)
- New benchmark suites (`docs/benchmarks.md`)

## Workflow

1. Fork and create a branch (`feat/...`, `fix/...`).
2. Run `make test` and `make lint` locally.
3. Open a PR with a clear summary; link to any related issue.
4. CI must be green (Rust + Python + frontend lint).

## Style

- Rust: `cargo fmt`, `cargo clippy -- -D warnings`.
- Python: `ruff check .`, `mypy grokforge_agents`.
- Frontend: `npm run lint`.

## Before touching the verification engine

The verifier is the heart of the project's correctness story. Before
modifying it, please open an issue describing the change and post a
benchmark run (`docs/benchmarks.md`) on `main` and on your branch so we
can see the delta.
