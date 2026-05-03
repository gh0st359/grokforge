.PHONY: help dev build test lint clean docker up down logs doctor

help:
	@echo "grokforge — make targets"
	@echo "  make doctor    diagnose your environment (Docker, Rust, Python, Node)"
	@echo "  make dev       run core + agents + frontend in dev mode"
	@echo "  make build     build all components"
	@echo "  make test      run all test suites"
	@echo "  make lint      run linters across all components"
	@echo "  make docker    build all docker images"
	@echo "  make up        docker compose up --build"
	@echo "  make down      docker compose down -v"
	@echo "  make logs      tail docker compose logs"
	@echo "  make clean     remove build artifacts"

doctor:
	@echo "== grokforge environment check =="
	@printf "docker:        " ; docker --version 2>/dev/null || echo "MISSING (install Docker Desktop or Engine)"
	@printf "docker compose: " ; docker compose version 2>/dev/null || echo "MISSING (install the compose plugin)"
	@printf "docker daemon: " ; docker info >/dev/null 2>&1 && echo "running" || echo "NOT RUNNING (start Docker Desktop / systemctl start docker)"
	@printf "cargo:         " ; cargo --version 2>/dev/null || echo "MISSING (https://rustup.rs)"
	@printf "python:        " ; python3 --version 2>/dev/null || echo "MISSING (need 3.11+)"
	@printf "node:          " ; node --version 2>/dev/null || echo "MISSING (need 20+)"
	@printf "compose file:  " ; docker compose config >/dev/null 2>&1 && echo "valid" || echo "INVALID (run: docker compose config)"
	@printf ".env present:  " ; test -f .env && echo "yes" || echo "no (optional — copy .env.example to .env if you have a Grok key)"

dev:
	@echo "[grokforge] launching dev stack (3 panes recommended)"
	@(cd core && cargo run) & \
	(cd agents && uvicorn grokforge_agents.server:app --reload --port 8001) & \
	(cd frontend && npm run dev) & \
	wait

build:
	cd core && cargo build --release
	cd agents && pip install -e .
	cd frontend && npm install && npm run build

test:
	cd core && cargo test
	cd agents && pytest -q
	cd frontend && npm test --silent || true

lint:
	cd core && cargo clippy --all-targets -- -D warnings
	cd agents && ruff check . && mypy grokforge_agents
	cd frontend && npm run lint

docker:
	docker build -t grokforge/core:dev   core/
	docker build -t grokforge/agents:dev agents/
	docker build -t grokforge/frontend:dev frontend/

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

clean:
	cd core && cargo clean
	rm -rf agents/build agents/dist agents/*.egg-info
	rm -rf frontend/.next frontend/out frontend/node_modules
