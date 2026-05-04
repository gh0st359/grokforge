"""Spec-tailored code generation for offline / mock mode.

Picks a recipe based on keywords in the spec and returns a dict of
{path: content} that replaces or augments the baseline FastAPI scaffold.

The point: even with no Grok key, the user sees actual working code
specific to their request (not generic boilerplate). When Grok IS
available, the LLM patch layers on top of these — the recipes act as
strong scaffolding the LLM can refine.
"""

from __future__ import annotations

from typing import Any


def generate_spec_specific_code(spec: str, plan: dict[str, Any]) -> dict[str, str]:
    s = (spec or "").lower()

    if any(k in s for k in ("orbit", "n-body", "gravity", "physics", "verlet", "integrator")):
        return _orbital_recipe()
    if any(k in s for k in ("photo-z", "photometric", "redshift", "cosmology", "histogram")):
        return _photoz_recipe()
    if any(k in s for k in ("training", "shard", "worker", "throughput", "straggler")):
        return _training_recipe()
    return _generic_recipe()


# ─── recipes ──────────────────────────────────────────────────────────


def _orbital_recipe() -> dict[str, str]:
    main_py = '''"""Orbital mechanics simulator — Newtonian gravity, velocity-Verlet integrator."""
from __future__ import annotations

import math
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

G = 6.674e-11  # gravitational constant, N m^2 / kg^2

app = FastAPI(title="grokforge-orbital", version="0.1.0")


class Body(BaseModel):
    name: str
    mass_kg: float = Field(gt=0)
    pos: list[float] = Field(min_length=3, max_length=3)
    vel: list[float] = Field(min_length=3, max_length=3)


class World(BaseModel):
    bodies: list[Body]


_worlds: dict[str, list[Body]] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/world")
def create_world(world: World) -> dict[str, Any]:
    if not world.bodies:
        raise HTTPException(400, "world must contain at least one body")
    wid = uuid.uuid4().hex
    _worlds[wid] = [b.model_copy(deep=True) for b in world.bodies]
    return {"world_id": wid, "bodies": len(world.bodies)}


@app.get("/world/{world_id}")
def get_world(world_id: str) -> dict[str, Any]:
    bodies = _worlds.get(world_id)
    if bodies is None:
        raise HTTPException(404, "world not found")
    return {"world_id": world_id, "bodies": [b.model_dump() for b in bodies]}


def _accelerations(bodies: list[Body]) -> list[list[float]]:
    n = len(bodies)
    acc = [[0.0, 0.0, 0.0] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = bodies[j].pos[0] - bodies[i].pos[0]
            dy = bodies[j].pos[1] - bodies[i].pos[1]
            dz = bodies[j].pos[2] - bodies[i].pos[2]
            r2 = dx * dx + dy * dy + dz * dz + 1e-9
            r = math.sqrt(r2)
            f = G * bodies[j].mass_kg / r2
            acc[i][0] += f * dx / r
            acc[i][1] += f * dy / r
            acc[i][2] += f * dz / r
    return acc


@app.post("/step/{world_id}")
def step(world_id: str, dt: float = 60.0) -> dict[str, Any]:
    bodies = _worlds.get(world_id)
    if bodies is None:
        raise HTTPException(404, "world not found")
    if dt <= 0:
        raise HTTPException(400, "dt must be positive")

    a0 = _accelerations(bodies)
    for i, b in enumerate(bodies):
        for k in range(3):
            b.pos[k] += b.vel[k] * dt + 0.5 * a0[i][k] * dt * dt
    a1 = _accelerations(bodies)
    for i, b in enumerate(bodies):
        for k in range(3):
            b.vel[k] += 0.5 * (a0[i][k] + a1[i][k]) * dt
    return {"world_id": world_id, "bodies": [b.model_dump() for b in bodies]}


@app.get("/energy/{world_id}")
def energy(world_id: str) -> dict[str, float]:
    bodies = _worlds.get(world_id)
    if bodies is None:
        raise HTTPException(404, "world not found")
    ke = sum(0.5 * b.mass_kg * sum(v * v for v in b.vel) for b in bodies)
    pe = 0.0
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            dx = bodies[j].pos[0] - bodies[i].pos[0]
            dy = bodies[j].pos[1] - bodies[i].pos[1]
            dz = bodies[j].pos[2] - bodies[i].pos[2]
            r = math.sqrt(dx * dx + dy * dy + dz * dz + 1e-9)
            pe -= G * bodies[i].mass_kg * bodies[j].mass_kg / r
    return {"kinetic": ke, "potential": pe, "total": ke + pe}
'''
    test_py = '''from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EARTH_MOON = {
    "bodies": [
        {"name": "earth", "mass_kg": 5.972e24, "pos": [0, 0, 0], "vel": [0, 0, 0]},
        {"name": "moon",  "mass_kg": 7.342e22, "pos": [3.844e8, 0, 0], "vel": [0, 1022.0, 0]},
    ]
}


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_step() -> None:
    wid = client.post("/world", json=EARTH_MOON).json()["world_id"]
    e0 = client.get(f"/energy/{wid}").json()["total"]
    for _ in range(50):
        client.post(f"/step/{wid}", params={"dt": 60.0})
    e1 = client.get(f"/energy/{wid}").json()["total"]
    # Velocity-Verlet conserves energy to high precision over short windows.
    assert abs(e1 - e0) / abs(e0) < 1e-3


def test_zero_mass_rejected() -> None:
    bad = {"bodies": [{"name": "x", "mass_kg": 0, "pos": [0, 0, 0], "vel": [0, 0, 0]}]}
    assert client.post("/world", json=bad).status_code == 422


def test_unknown_world_404() -> None:
    assert client.post("/step/does-not-exist", params={"dt": 1.0}).status_code == 404
'''
    return {
        "app/main.py": main_py,
        "tests/test_app.py": test_py,
    }


def _photoz_recipe() -> dict[str, str]:
    main_py = '''"""Photometric redshift estimator — toy linear model on color indices."""
from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI(title="grokforge-photoz", version="0.1.0")

_datasets: dict[str, list[dict[str, float]]] = {}


class EstimateRow(BaseModel):
    id: str
    z_phot: float
    z_phot_err: float


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or not {"id", "u", "g", "r", "i", "z"}.issubset(reader.fieldnames):
        raise HTTPException(400, "csv must contain columns: id,u,g,r,i,z")
    rows: list[dict[str, float]] = []
    for r in reader:
        try:
            rows.append({
                "id": r["id"],
                "u": float(r["u"]), "g": float(r["g"]), "r": float(r["r"]),
                "i": float(r["i"]), "z": float(r["z"]),
            })
        except (KeyError, ValueError):
            raise HTTPException(400, "malformed row")
    did = uuid.uuid4().hex
    _datasets[did] = rows
    return {"dataset_id": did, "rows": len(rows)}


def _estimate_z(row: dict[str, float]) -> tuple[float, float]:
    # toy linear model on color indices (g-r, r-i, i-z)
    gr = row["g"] - row["r"]
    ri = row["r"] - row["i"]
    iz = row["i"] - row["z"]
    z = max(0.0, min(5.0, 0.05 + 0.6 * gr + 0.3 * ri + 0.1 * iz))
    return z, 0.05 + 0.02 * abs(gr)


@app.post("/estimate/{dataset_id}")
def estimate(dataset_id: str) -> list[EstimateRow]:
    rows = _datasets.get(dataset_id)
    if rows is None:
        raise HTTPException(404, "dataset not found")
    out: list[EstimateRow] = []
    for r in rows:
        z, err = _estimate_z(r)
        out.append(EstimateRow(id=str(r["id"]), z_phot=z, z_phot_err=err))
    return out


@app.get("/histogram/{dataset_id}")
def histogram(dataset_id: str, bins: int = 50, zmax: float = 2.0) -> dict[str, Any]:
    rows = _datasets.get(dataset_id)
    if rows is None:
        raise HTTPException(404, "dataset not found")
    counts = [0] * bins
    width = zmax / bins
    for r in rows:
        z, _ = _estimate_z(r)
        idx = min(bins - 1, max(0, int(z / width)))
        counts[idx] += 1
    edges = [i * width for i in range(bins + 1)]
    return {"bins": edges, "counts": counts, "n": len(rows)}
'''
    test_py = '''import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV = b"id,u,g,r,i,z\\n1,22.1,21.5,20.9,20.6,20.3\\n2,23.0,22.4,21.7,21.4,21.2\\n3,18.3,17.7,17.4,17.2,17.1\\n"


def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_full_pipeline() -> None:
    r = client.post("/ingest", files={"file": ("x.csv", io.BytesIO(CSV), "text/csv")})
    did = r.json()["dataset_id"]
    est = client.post(f"/estimate/{did}").json()
    assert len(est) == 3
    assert all(0 <= row["z_phot"] <= 5 for row in est)

    h = client.get(f"/histogram/{did}").json()
    assert sum(h["counts"]) == 3
    assert h["n"] == 3


def test_malformed_csv_returns_400() -> None:
    bad = b"foo,bar\\n1,2\\n"
    r = client.post("/ingest", files={"file": ("x.csv", io.BytesIO(bad), "text/csv")})
    assert r.status_code == 400
'''
    return {"app/main.py": main_py, "tests/test_app.py": test_py}


def _training_recipe() -> dict[str, str]:
    main_py = '''"""Training pipeline coordinator: shard ranges + heartbeats + straggler detection."""
from __future__ import annotations

import statistics
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="grokforge-training", version="0.1.0")


class JobRequest(BaseModel):
    dataset_size: int = Field(gt=0)
    world_size: int = Field(gt=0)
    batch_size: int = Field(gt=0)


class Heartbeat(BaseModel):
    step: int
    throughput_samples_per_s: float


_jobs: dict[str, dict[str, Any]] = {}


def _shards(n: int, k: int) -> list[tuple[int, int]]:
    base, rem = divmod(n, k)
    out: list[tuple[int, int]] = []
    cursor = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        out.append((cursor, cursor + size))
        cursor += size
    return out


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs")
def submit(req: JobRequest) -> dict[str, Any]:
    jid = uuid.uuid4().hex
    _jobs[jid] = {
        "shards": _shards(req.dataset_size, req.world_size),
        "batch_size": req.batch_size,
        "world_size": req.world_size,
        "workers": {},
    }
    return {"job_id": jid, "shards": _jobs[jid]["shards"]}


@app.post("/heartbeat/{job_id}/{worker_id}")
def heartbeat(job_id: str, worker_id: int, hb: Heartbeat) -> dict[str, Any]:
    j = _jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    j["workers"][worker_id] = {
        "step": hb.step,
        "throughput": hb.throughput_samples_per_s,
        "last_seen": time.time(),
    }
    return {"ok": True}


@app.get("/jobs/{job_id}")
def status(job_id: str) -> dict[str, Any]:
    j = _jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    workers = j["workers"]
    throughputs = [w["throughput"] for w in workers.values()]
    aggregate = sum(throughputs)
    stragglers: list[int] = []
    if len(throughputs) >= 3:
        med = statistics.median(throughputs)
        sd = statistics.pstdev(throughputs)
        for wid, w in workers.items():
            if w["throughput"] < med - 2 * sd:
                stragglers.append(wid)
    return {
        "job_id": job_id,
        "aggregate_throughput": aggregate,
        "workers": workers,
        "stragglers": stragglers,
    }
'''
    test_py = '''from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_shards_cover_prime_dataset() -> None:
    r = client.post("/jobs", json={"dataset_size": 17, "world_size": 4, "batch_size": 2}).json()
    shards = r["shards"]
    # contiguous
    for a, b in zip(shards, shards[1:]):
        assert a[1] == b[0]
    # cover [0, 17)
    assert shards[0][0] == 0 and shards[-1][1] == 17
    assert sum(b - a for a, b in shards) == 17


def test_straggler_detection() -> None:
    jid = client.post("/jobs", json={"dataset_size": 1000, "world_size": 4, "batch_size": 8}).json()["job_id"]
    for wid, tput in zip(range(4), [100, 102, 98, 5]):
        client.post(f"/heartbeat/{jid}/{wid}", json={"step": 1, "throughput_samples_per_s": tput})
    s = client.get(f"/jobs/{jid}").json()
    assert 3 in s["stragglers"]


def test_unknown_job_404() -> None:
    assert client.post("/heartbeat/missing/0", json={"step": 0, "throughput_samples_per_s": 0.0}).status_code == 404
'''
    return {"app/main.py": main_py, "tests/test_app.py": test_py}


def _generic_recipe() -> dict[str, str]:
    return {}  # baseline template is enough
