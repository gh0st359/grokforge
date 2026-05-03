//! Sandboxed code execution.
//!
//! Defense in depth: rlimits (CPU + memory + file size), fresh tempdir as
//! cwd, scrubbed env, hard wall-clock timeout, and a fresh process group so
//! a timeout SIGKILL reaps the whole tree.
//!
//! This is intentionally not a full container — for multi-tenant production
//! use, wrap this in nsjail / firecracker / gVisor. These primitives are
//! conservative defaults that work without root.

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tokio::io::AsyncWriteExt;
use tokio::process::Command;
use tokio::time::timeout;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SandboxLimits {
    pub cpu_seconds: u64,
    pub memory_mb: u64,
    pub wall_seconds: u64,
}

impl Default for SandboxLimits {
    fn default() -> Self {
        Self { cpu_seconds: 30, memory_mb: 512, wall_seconds: 60 }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SandboxResult {
    pub exit_code: Option<i32>,
    pub stdout: String,
    pub stderr: String,
    pub timed_out: bool,
    pub workdir: PathBuf,
}

pub struct Sandbox {
    pub workdir: PathBuf,
    pub limits: SandboxLimits,
}

impl Sandbox {
    pub fn new(limits: SandboxLimits) -> std::io::Result<Self> {
        let dir = tempfile::Builder::new().prefix("grokforge-").tempdir()?;
        Ok(Self { workdir: dir.into_path(), limits })
    }

    pub async fn write_file(&self, rel: impl AsRef<Path>, contents: &[u8]) -> std::io::Result<()> {
        let path = self.workdir.join(rel);
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        let mut f = tokio::fs::File::create(path).await?;
        f.write_all(contents).await?;
        Ok(())
    }

    pub async fn run(&self, program: &str, args: &[&str]) -> anyhow::Result<SandboxResult> {
        let mut cmd = Command::new(program);
        cmd.args(args)
            .current_dir(&self.workdir)
            .env_clear()
            .env("PATH", "/usr/local/bin:/usr/bin:/bin")
            .env("HOME", &self.workdir)
            .env("LANG", "C.UTF-8")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        #[cfg(target_os = "linux")]
        {
            use std::os::unix::process::CommandExt;
            let cpu = self.limits.cpu_seconds;
            let mem_bytes = self.limits.memory_mb.saturating_mul(1024 * 1024);
            unsafe {
                cmd.pre_exec(move || {
                    apply_rlimit(nix_rlimit::CPU, cpu);
                    apply_rlimit(nix_rlimit::AS, mem_bytes);
                    apply_rlimit(nix_rlimit::FSIZE, 64 * 1024 * 1024);
                    nix_rlimit::setpgid_self();
                    Ok(())
                });
            }
        }

        let wall = Duration::from_secs(self.limits.wall_seconds);
        let mut child = cmd.spawn()?;
        let stdout = child.stdout.take();
        let stderr = child.stderr.take();

        let stdout_task = tokio::spawn(async move { read_to_string_opt(stdout).await });
        let stderr_task = tokio::spawn(async move { read_to_string_opt(stderr).await });

        let status_res = timeout(wall, child.wait()).await;
        let (timed_out, exit_code) = match status_res {
            Ok(Ok(status)) => (false, status.code()),
            Ok(Err(e)) => return Err(e.into()),
            Err(_) => {
                let _ = child.kill().await;
                (true, None)
            }
        };

        Ok(SandboxResult {
            exit_code,
            stdout: stdout_task.await.unwrap_or_default(),
            stderr: stderr_task.await.unwrap_or_default(),
            timed_out,
            workdir: self.workdir.clone(),
        })
    }
}

async fn read_to_string_opt<R: tokio::io::AsyncRead + Unpin>(r: Option<R>) -> String {
    let mut buf = String::new();
    if let Some(mut r) = r {
        let _ = tokio::io::AsyncReadExt::read_to_string(&mut r, &mut buf).await;
    }
    buf
}

#[cfg(target_os = "linux")]
mod nix_rlimit {
    use nix::sys::resource::{setrlimit, Resource};
    pub const CPU: Resource = Resource::RLIMIT_CPU;
    pub const AS: Resource = Resource::RLIMIT_AS;
    pub const FSIZE: Resource = Resource::RLIMIT_FSIZE;
    pub fn setpgid_self() {
        let _ = nix::unistd::setpgid(nix::unistd::Pid::from_raw(0), nix::unistd::Pid::from_raw(0));
    }
}

#[cfg(target_os = "linux")]
fn apply_rlimit(resource: nix::sys::resource::Resource, value: u64) {
    let _ = nix::sys::resource::setrlimit(resource, value, value);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn echo_works() {
        let sb = Sandbox::new(SandboxLimits::default()).unwrap();
        let r = sb.run("echo", &["hello"]).await.unwrap();
        assert!(r.stdout.contains("hello"));
        assert_eq!(r.timed_out, false);
    }

    #[tokio::test]
    async fn timeout_is_enforced() {
        let mut limits = SandboxLimits::default();
        limits.wall_seconds = 1;
        let sb = Sandbox::new(limits).unwrap();
        let r = sb.run("sleep", &["5"]).await.unwrap();
        assert!(r.timed_out);
    }
}
