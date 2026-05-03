//! HTTP + SSE API exposed to the frontend.

use std::convert::Infallible;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::sse::{Event, KeepAlive, Sse},
    routing::{get, post},
    Json, Router,
};
use futures::stream::{Stream, StreamExt};
use serde::{Deserialize, Serialize};
use tokio_stream::wrappers::BroadcastStream;
use tower_http::cors::{Any, CorsLayer};
use uuid::Uuid;

use crate::orchestrator::Orchestrator;
use crate::state::Job;

#[derive(Deserialize)]
pub struct SubmitRequest {
    pub spec: String,
}

#[derive(Serialize)]
pub struct SubmitResponse {
    pub id: Uuid,
}

pub async fn serve(orch: Arc<Orchestrator>, addr: SocketAddr) -> anyhow::Result<()> {
    let cors = CorsLayer::new().allow_origin(Any).allow_methods(Any).allow_headers(Any);
    let app = Router::new()
        .route("/health", get(|| async { "ok" }))
        .route("/jobs", post(submit_job).get(list_jobs))
        .route("/jobs/:id", get(get_job))
        .route("/jobs/:id/events", get(job_events))
        .with_state(orch)
        .layer(cors);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(%addr, "api listening");
    axum::serve(listener, app).await?;
    Ok(())
}

async fn submit_job(
    State(orch): State<Arc<Orchestrator>>,
    Json(body): Json<SubmitRequest>,
) -> Result<Json<SubmitResponse>, (StatusCode, String)> {
    let id = orch.submit(body.spec).await.map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(SubmitResponse { id }))
}

async fn list_jobs(State(orch): State<Arc<Orchestrator>>) -> Json<Vec<Job>> {
    Json(orch.store.list())
}

async fn get_job(
    State(orch): State<Arc<Orchestrator>>,
    Path(id): Path<Uuid>,
) -> Result<Json<Job>, StatusCode> {
    orch.store.get(id).map(Json).ok_or(StatusCode::NOT_FOUND)
}

async fn job_events(
    State(orch): State<Arc<Orchestrator>>,
    Path(id): Path<Uuid>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, StatusCode> {
    let rx = orch.store.subscribe(id).ok_or(StatusCode::NOT_FOUND)?;
    let stream = BroadcastStream::new(rx).filter_map(|res| async move {
        match res {
            Ok(ev) => {
                let payload = serde_json::to_string(&ev).ok()?;
                Some(Ok(Event::default().event(ev.kind.clone()).data(payload)))
            }
            Err(_) => None,
        }
    });
    Ok(Sse::new(stream).keep_alive(KeepAlive::new().interval(Duration::from_secs(15))))
}
