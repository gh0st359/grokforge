# grokforge core — Rust orchestrator
# `rust:latest` keeps the toolchain current so transitive deps that bump
# their MSRV (e.g. tempfile, axum, reqwest) always compile cleanly.
FROM rust:latest AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml ./
COPY src ./src
# We don't ship a Cargo.lock by design. `--locked` will fail when the lockfile
# is absent; the `||` fallback then lets the resolver pick fresh versions.
RUN cargo build --release --locked || cargo build --release

FROM debian:bookworm-slim
# `curl` is needed for the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libssl3 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /build/target/release/grokforge-core /usr/local/bin/grokforge-core
ENV RUST_LOG=info
EXPOSE 8080 9090
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1
ENTRYPOINT ["/usr/local/bin/grokforge-core"]
