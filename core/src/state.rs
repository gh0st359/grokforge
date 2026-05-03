//! In-memory job state store with optional disk persistence.
//!
//! Persistence format is JSON-lines under `STATE_DIR/jobs/<id>.jsonl`. Each
//! event is appended atomically so a crashed core can rebuild on restart.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use tokio::fs;
use tokio::io::AsyncWriteExt;
use tokio::sync::broadcast;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    Planning,
    Coding,
    Testing,
    Reviewing,
    Verifying,
    Deploying,
    Succeeded,
    Failed,
    Cancelled,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentEvent {
    pub job_id: Uuid,
    pub ts: DateTime<Utc>,
    pub agent: String,
    pub kind: String,    // "log" | "artifact" | "status" | "error" | "cost" | "verdict"
    pub payload: serde_json::Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Job {
    pub id: Uuid,
    pub spec: String,
    pub status: JobStatus,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub confidence: f32,
    pub artifacts_dir: Option<String>,
    pub cost_usd: f64,
    pub debate_rounds: u32,
}

impl Job {
    pub fn new(spec: String) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            spec,
            status: JobStatus::Queued,
            created_at: now,
            updated_at: now,
            confidence: 0.0,
            artifacts_dir: None,
            cost_usd: 0.0,
            debate_rounds: 0,
        }
    }
}

pub struct StateStore {
    jobs: DashMap<Uuid, Job>,
    channels: DashMap<Uuid, broadcast::Sender<AgentEvent>>,
    state_dir: PathBuf,
}

impl StateStore {
    pub fn new(state_dir: impl AsRef<Path>) -> Arc<Self> {
        let state_dir = state_dir.as_ref().to_path_buf();
        let _ = std::fs::create_dir_all(state_dir.join("jobs"));
        Arc::new(Self {
            jobs: DashMap::new(),
            channels: DashMap::new(),
            state_dir,
        })
    }

    pub fn create_job(&self, spec: String) -> Job {
        let job = Job::new(spec);
        self.jobs.insert(job.id, job.clone());
        let (tx, _rx) = broadcast::channel(1024);
        self.channels.insert(job.id, tx);
        job
    }

    pub fn get(&self, id: Uuid) -> Option<Job> {
        self.jobs.get(&id).map(|j| j.clone())
    }

    pub fn list(&self) -> Vec<Job> {
        self.jobs.iter().map(|e| e.value().clone()).collect()
    }

    pub fn update<F: FnOnce(&mut Job)>(&self, id: Uuid, f: F) -> Option<Job> {
        let mut entry = self.jobs.get_mut(&id)?;
        f(&mut entry);
        entry.updated_at = Utc::now();
        Some(entry.clone())
    }

    pub fn subscribe(&self, id: Uuid) -> Option<broadcast::Receiver<AgentEvent>> {
        self.channels.get(&id).map(|tx| tx.subscribe())
    }

    pub async fn emit(&self, event: AgentEvent) {
        if let Some(tx) = self.channels.get(&event.job_id) {
            let _ = tx.send(event.clone());
        }
        if let Err(e) = self.persist_event(&event).await {
            tracing::warn!(error = %e, "failed to persist event");
        }
    }

    async fn persist_event(&self, event: &AgentEvent) -> std::io::Result<()> {
        let path = self.state_dir.join("jobs").join(format!("{}.jsonl", event.job_id));
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .await?;
        let line = serde_json::to_string(event).unwrap_or_default();
        file.write_all(line.as_bytes()).await?;
        file.write_all(b"\n").await?;
        Ok(())
    }
}
