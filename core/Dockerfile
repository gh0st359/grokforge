# grokforge core — Rust orchestrator
FROM rust:1.78-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release --locked || cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libssl3 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /build/target/release/grokforge-core /usr/local/bin/grokforge-core
ENV RUST_LOG=info
EXPOSE 8080 9090
ENTRYPOINT ["/usr/local/bin/grokforge-core"]
