# Example spec: distributed training coordinator

> Build a small training-pipeline coordinator as a FastAPI service.
>
> Requirements:
> - `POST /jobs` accepts `{dataset_size, world_size, batch_size}` and returns a `job_id` plus the per-worker shard ranges `[(start, end), ...]` of length `world_size`.
> - `POST /heartbeat/{job_id}/{worker_id}` accepts `{step, throughput_samples_per_s}` and updates per-worker stats.
> - `GET /jobs/{job_id}` returns aggregate throughput, per-worker last-seen timestamps, and a "stragglers" list (workers > 2σ below the median throughput).
> - All shards must be contiguous, non-overlapping, and cover `[0, dataset_size)`.
> - Tests: (a) shard math is correct for prime dataset sizes; (b) straggler detection flags an obviously-slow worker; (c) heartbeat for an unknown job_id returns 404.
> - Deploy as Docker + K8s.
