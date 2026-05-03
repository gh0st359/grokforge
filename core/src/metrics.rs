//! Prometheus metrics + scrape endpoint.

use std::net::SocketAddr;

use axum::{routing::get, Router};
use prometheus::{
    opts, register_counter, register_histogram_vec, register_int_counter, Counter, Encoder,
    HistogramVec, IntCounter, TextEncoder,
};

lazy_static::lazy_static! {
    pub static ref JOBS_SUBMITTED: IntCounter =
        register_int_counter!("grokforge_jobs_submitted_total", "Jobs accepted by API").unwrap();
    pub static ref JOBS_SUCCEEDED: IntCounter =
        register_int_counter!("grokforge_jobs_succeeded_total", "Jobs that completed deploy").unwrap();
    pub static ref JOBS_FAILED: IntCounter =
        register_int_counter!("grokforge_jobs_failed_total", "Jobs that errored or failed verification").unwrap();
    pub static ref TOKEN_COST_USD: Counter =
        register_counter!(opts!("grokforge_token_cost_usd_total", "Cumulative LLM spend across all jobs")).unwrap();
    pub static ref STAGE_LATENCY: HistogramVec = register_histogram_vec!(
        "grokforge_stage_latency_seconds",
        "Wall time of each pipeline stage",
        &["stage"]
    ).unwrap();
}

pub fn init() {
    // Touch each metric so it's registered even if never incremented.
    let _ = &*JOBS_SUBMITTED;
    let _ = &*JOBS_SUCCEEDED;
    let _ = &*JOBS_FAILED;
    let _ = &*TOKEN_COST_USD;
    let _ = &*STAGE_LATENCY;
}

pub async fn serve(addr: SocketAddr) -> anyhow::Result<()> {
    let app = Router::new().route("/metrics", get(handler));
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(%addr, "metrics listening");
    axum::serve(listener, app).await?;
    Ok(())
}

async fn handler() -> (axum::http::StatusCode, [(axum::http::HeaderName, &'static str); 1], Vec<u8>) {
    let metric_families = prometheus::gather();
    let encoder = TextEncoder::new();
    let mut buffer = Vec::new();
    let _ = encoder.encode(&metric_families, &mut buffer);
    (
        axum::http::StatusCode::OK,
        [(axum::http::header::CONTENT_TYPE, "text/plain; version=0.0.4")],
        buffer,
    )
}
