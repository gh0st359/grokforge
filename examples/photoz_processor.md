# Example spec: photometric redshift processor

> Build a FastAPI service that processes a CSV of photometric measurements and returns photometric-redshift estimates.
>
> Requirements:
> - `POST /ingest` accepts a CSV upload with columns `id, u, g, r, i, z` (SDSS-style magnitudes). Persist to a temp directory keyed by a generated `dataset_id`.
> - `POST /estimate/{dataset_id}` runs a placeholder photo-z estimator (e.g. simple linear regression on (g-r, r-i, i-z)) and returns `[{id, z_phot, z_phot_err}]`.
> - `GET /histogram/{dataset_id}` returns a 50-bin histogram over `z_phot ∈ [0, 2]` as `{bins: [...], counts: [...]}`.
> - Tests: (a) histogram bin counts sum to dataset size; (b) z_phot stays within [-0.5, 5.0] for any input within reasonable magnitude bounds; (c) malformed CSV returns 400.
> - Deploy as Docker + K8s with readiness probe.
