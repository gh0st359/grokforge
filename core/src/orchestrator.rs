//! Orchestrator: drives a job through the agent pipeline.
//!
//! The pipeline is intentionally explicit (no DAG library yet — the stages
//! are a known sequence). Each stage is a call to the Python agents service;
//! the Verifier stage may loop with debate rounds until confidence ≥ threshold
//! or the round budget is exhausted.

use std::sync::Arc;

use anyhow::{anyhow, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::json;
use uuid::Uuid;

use crate::config::Config;
use crate::queue::{self, JobQueue, JobQueueRx};
use crate::sandbox::{Sandbox, SandboxLimits, SandboxResult};
use crate::state::{AgentEvent, JobStatus, StateStore};

const MAX_DEBATE_ROUNDS: u32 = 4;
const CONFIDENCE_THRESHOLD: f32 = 0.95;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AgentRequest {
    pub job_id: Uuid,
    pub stage: String,
    pub input: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ForwardedEvent {
    pub kind: String,
    pub agent: String,
    pub ts: String,
    pub payload: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct AgentResponse {
    pub stage: String,
    pub output: serde_json::Value,
    #[serde(default)]
    pub confidence: f32,
    #[serde(default)]
    pub cost_usd: f64,
    #[serde(default)]
    pub logs: Vec<String>,
    #[serde(default)]
    pub events: Vec<ForwardedEvent>,
}

pub struct Orchestrator {
    pub cfg: Config,
    pub store: Arc<StateStore>,
    queue_tx: JobQueue,
    queue_rx: tokio::sync::Mutex<Option<JobQueueRx>>,
    http: reqwest::Client,
}

impl Orchestrator {
    pub fn new(cfg: Config) -> Self {
        let store = StateStore::new(&cfg.state_dir);
        let (tx, rx) = queue::channel(1024);
        Self {
            cfg,
            store,
            queue_tx: tx,
            queue_rx: tokio::sync::Mutex::new(Some(rx)),
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(300))
                .build()
                .expect("reqwest client"),
        }
    }

    /// Construct a Sandbox configured from this orchestrator's Config.
    /// Used by `/sandbox/exec` and (in future) by Coder/Tester for isolated runs.
    pub fn make_sandbox(&self) -> std::io::Result<Sandbox> {
        Sandbox::new(SandboxLimits {
            cpu_seconds: self.cfg.sandbox_cpu_seconds,
            memory_mb: self.cfg.sandbox_memory_mb,
            wall_seconds: self.cfg.sandbox_wall_seconds,
        })
    }

    /// Run a single command in a fresh sandbox. Files in `files` are written
    /// before execution. Returns the structured sandbox result.
    pub async fn sandbox_exec(
        &self,
        program: &str,
        args: &[&str],
        files: &[(String, String)],
    ) -> Result<SandboxResult> {
        let sb = self.make_sandbox()?;
        for (rel, contents) in files {
            sb.write_file(rel, contents.as_bytes()).await?;
        }
        sb.run(program, args).await
    }

    pub async fn submit(&self, spec: String) -> Result<Uuid> {
        let job = self.store.create_job(spec);
        self.queue_tx.push(job.id).await?;
        crate::metrics::JOBS_SUBMITTED.inc();
        Ok(job.id)
    }

    pub fn spawn_worker_pool(self: Arc<Self>) {
        let n = self.cfg.worker_concurrency.max(1);
        let rx = self
            .queue_rx
            .try_lock()
            .expect("queue rx lock")
            .take()
            .expect("worker pool already started");
        let rx = Arc::new(tokio::sync::Mutex::new(rx.rx));
        for worker_id in 0..n {
            let this = self.clone();
            let rx = rx.clone();
            tokio::spawn(async move {
                loop {
                    let id = {
                        let mut guard = rx.lock().await;
                        match guard.recv().await {
                            Some(id) => id,
                            None => break,
                        }
                    };
                    tracing::info!(worker_id, %id, "picked up job");
                    if let Err(e) = this.run_job(id).await {
                        tracing::error!(error = %e, %id, "job failed");
                        let _ = this.store.update(id, |j| j.status = JobStatus::Failed);
                        crate::metrics::JOBS_FAILED.inc();
                    }
                }
            });
        }
    }

    async fn run_job(&self, id: Uuid) -> Result<()> {
        // Pipeline stages in order
        let plan = self.run_stage(id, JobStatus::Planning, "planner", json!({})).await?;
        let code = self.run_stage(id, JobStatus::Coding, "coder", plan.output.clone()).await?;
        let tests = self.run_stage(id, JobStatus::Testing, "tester", code.output.clone()).await?;
        let review = self.run_stage(id, JobStatus::Reviewing, "reviewer", json!({
            "plan": plan.output, "code": code.output, "tests": tests.output
        })).await?;

        // Verify with debate loop
        let mut confidence = review.confidence;
        let mut round = 0u32;
        let mut last_verify = review.clone();
        while confidence < CONFIDENCE_THRESHOLD && round < MAX_DEBATE_ROUNDS {
            round += 1;
            self.store.update(id, |j| j.debate_rounds = round);
            let verify = self.run_stage(id, JobStatus::Verifying, "verifier", json!({
                "plan": plan.output, "code": code.output,
                "tests": tests.output, "review": review.output,
                "round": round,
            })).await?;
            confidence = verify.confidence;
            last_verify = verify;
        }
        self.store.update(id, |j| j.confidence = confidence);

        if confidence < CONFIDENCE_THRESHOLD {
            self.store.emit(AgentEvent {
                job_id: id, ts: Utc::now(),
                agent: "orchestrator".into(),
                kind: "error".into(),
                payload: json!({
                    "reason": "confidence threshold not met",
                    "confidence": confidence,
                    "rounds": round,
                }),
            }).await;
            self.store.update(id, |j| j.status = JobStatus::Failed);
            crate::metrics::JOBS_FAILED.inc();
            return Err(anyhow!("verifier did not converge"));
        }

        let _deploy = self.run_stage(id, JobStatus::Deploying, "deployer", json!({
            "code": code.output, "verdict": last_verify.output,
        })).await?;

        self.store.update(id, |j| j.status = JobStatus::Succeeded);
        crate::metrics::JOBS_SUCCEEDED.inc();
        self.store.emit(AgentEvent {
            job_id: id, ts: Utc::now(),
            agent: "orchestrator".into(),
            kind: "status".into(),
            payload: json!({"status": "succeeded", "confidence": confidence}),
        }).await;
        Ok(())
    }

    async fn run_stage(
        &self,
        id: Uuid,
        status: JobStatus,
        stage: &str,
        input: serde_json::Value,
    ) -> Result<AgentResponse> {
        self.store.update(id, |j| j.status = status.clone());
        self.store.emit(AgentEvent {
            job_id: id, ts: Utc::now(),
            agent: stage.into(),
            kind: "status".into(),
            payload: json!({"stage": stage, "phase": "start"}),
        }).await;

        let req = AgentRequest { job_id: id, stage: stage.into(), input };
        let url = format!("{}/agents/run", self.cfg.agents_url.trim_end_matches('/'));
        let timer = crate::metrics::STAGE_LATENCY.with_label_values(&[stage]).start_timer();
        let resp = self.http.post(&url).json(&req).send().await?;
        timer.observe_duration();

        if !resp.status().is_success() {
            let body = resp.text().await.unwrap_or_default();
            return Err(anyhow!("agent {} returned non-2xx: {}", stage, body));
        }
        let parsed: AgentResponse = resp.json().await?;

        // Fan typed events into the SSE stream first (rich UI rendering).
        for ev in &parsed.events {
            self.store.emit(AgentEvent {
                job_id: id, ts: Utc::now(),
                agent: ev.agent.clone(),
                kind: ev.kind.clone(),
                payload: ev.payload.clone(),
            }).await;
        }
        // Plain logs are emitted only if there were no typed events from
        // the agent (older or simpler agents without rich emitters).
        if parsed.events.is_empty() {
            for line in &parsed.logs {
                self.store.emit(AgentEvent {
                    job_id: id, ts: Utc::now(),
                    agent: stage.into(),
                    kind: "log".into(),
                    payload: json!({"line": line}),
                }).await;
            }
        }
        if parsed.cost_usd > 0.0 {
            self.store.update(id, |j| j.cost_usd += parsed.cost_usd);
            self.store.emit(AgentEvent {
                job_id: id, ts: Utc::now(),
                agent: stage.into(),
                kind: "cost".into(),
                payload: json!({"delta_usd": parsed.cost_usd}),
            }).await;
            crate::metrics::TOKEN_COST_USD.inc_by(parsed.cost_usd);
        }
        self.store.emit(AgentEvent {
            job_id: id, ts: Utc::now(),
            agent: stage.into(),
            kind: "artifact".into(),
            payload: parsed.output.clone(),
        }).await;
        Ok(parsed)
    }
}
