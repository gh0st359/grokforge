//! Lightweight async work queue.
//!
//! Multiple producers push `Uuid`s onto an mpsc channel; the orchestrator
//! drains them with a fixed worker concurrency. We deliberately keep this
//! in-process — distributed scheduling is out of scope for v0.1.

use tokio::sync::mpsc;
use uuid::Uuid;

#[derive(Clone)]
pub struct JobQueue {
    tx: mpsc::Sender<Uuid>,
}

pub struct JobQueueRx {
    pub rx: mpsc::Receiver<Uuid>,
}

pub fn channel(capacity: usize) -> (JobQueue, JobQueueRx) {
    let (tx, rx) = mpsc::channel(capacity);
    (JobQueue { tx }, JobQueueRx { rx })
}

impl JobQueue {
    pub async fn push(&self, id: Uuid) -> anyhow::Result<()> {
        self.tx.send(id).await.map_err(|e| anyhow::anyhow!(e.to_string()))
    }
}
