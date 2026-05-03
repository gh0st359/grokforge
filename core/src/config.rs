//! Runtime configuration sourced from environment variables.

use std::path::PathBuf;

#[derive(Clone, Debug)]
pub struct Config {
    pub api_port: u16,
    pub metrics_port: u16,
    pub agents_url: String,
    pub state_dir: PathBuf,
    pub worker_concurrency: usize,
    pub sandbox_cpu_seconds: u64,
    pub sandbox_memory_mb: u64,
    pub sandbox_wall_seconds: u64,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            api_port: env_u16("API_PORT", 8080),
            metrics_port: env_u16("METRICS_PORT", 9090),
            agents_url: std::env::var("AGENTS_URL")
                .unwrap_or_else(|_| "http://localhost:8001".to_string()),
            state_dir: std::env::var("STATE_DIR")
                .unwrap_or_else(|_| ".grokforge_state".to_string())
                .into(),
            worker_concurrency: env_usize("WORKER_CONCURRENCY", 4),
            sandbox_cpu_seconds: env_u64("SANDBOX_CPU_SECONDS", 30),
            sandbox_memory_mb: env_u64("SANDBOX_MEMORY_MB", 512),
            sandbox_wall_seconds: env_u64("SANDBOX_WALL_SECONDS", 60),
        }
    }
}

fn env_u16(key: &str, default: u16) -> u16 {
    std::env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}
fn env_u64(key: &str, default: u64) -> u64 {
    std::env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}
fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key).ok().and_then(|v| v.parse().ok()).unwrap_or(default)
}
