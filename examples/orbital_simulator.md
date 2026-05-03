# Example spec: orbital mechanics simulator

Paste this into the grokforge UI.

---

> Build a real-time orbital mechanics simulator as a FastAPI service.
>
> Requirements:
> - `POST /world` accepts a list of bodies `[{name, mass_kg, pos: [x,y,z], vel: [vx,vy,vz]}]` and returns a `world_id`.
> - `POST /step/{world_id}` advances the simulation by `dt` seconds (default 60) using a velocity-Verlet integrator under Newtonian gravity (G = 6.674e-11) and returns the updated state.
> - `GET /world/{world_id}` returns current positions and velocities.
> - Total kinetic + potential energy must be conserved within 1e-6 relative tolerance over 1000 steps for a 2-body Earth–Moon test (default world).
> - Provide pytest tests covering: (a) energy conservation over 1000 steps for the 2-body default, (b) symmetry of gravitational force, (c) zero-mass body has zero acceleration.
> - Deploy as a Docker image; include a K8s deployment manifest with readiness probe on `/health`.
