# Changelog

## v0.1.0 — initial scaffold

- Rust core orchestrator (Axum, Tokio, Prometheus, sandboxed exec)
- Python agent pool (Planner, Coder, Tester, Reviewer, Verifier, Deployer)
- Grok client + dynamic primary/fallback model router
- Multi-agent debate loop with judge verdict
- Z3-backed symbolic verification helpers
- Next.js frontend with live SSE log stream and stage tracker
- Docker + Kubernetes manifests, Prometheus + Grafana dashboards
- Mock-mode fallback so the full stack runs offline / in CI
- FastAPI scaffold template and pytest harness
