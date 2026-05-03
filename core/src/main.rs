//! grokforge core — Rust orchestrator entrypoint.
//!
//! Boots the HTTP/SSE API, starts the job runner that drains the async queue,
//! and exposes Prometheus metrics on a separate port.

use std::net::SocketAddr;
use std::sync::Arc;

use anyhow::Result;
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

mod api;
mod config;
mod metrics;
mod orchestrator;
mod queue;
mod sandbox;
mod state;

use crate::orchestrator::Orchestrator;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(fmt::layer().json())
        .init();

    let cfg = config::Config::from_env();
    tracing::info!(?cfg, "grokforge core starting");

    metrics::init();

    let orchestrator = Arc::new(Orchestrator::new(cfg.clone()));
    orchestrator.clone().spawn_worker_pool();

    let api_addr: SocketAddr = format!("0.0.0.0:{}", cfg.api_port).parse()?;
    let metrics_addr: SocketAddr = format!("0.0.0.0:{}", cfg.metrics_port).parse()?;

    let api_handle = tokio::spawn(api::serve(orchestrator.clone(), api_addr));
    let metrics_handle = tokio::spawn(metrics::serve(metrics_addr));

    tracing::info!(%api_addr, %metrics_addr, "grokforge core ready");

    tokio::select! {
        r = api_handle      => { r??; }
        r = metrics_handle  => { r??; }
        _ = tokio::signal::ctrl_c() => {
            tracing::info!("shutdown signal received");
        }
    }
    Ok(())
}
