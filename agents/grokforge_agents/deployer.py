"""Deployer agent.

Packages the verified code into a Docker image + Kubernetes manifests.
Does not actually push to a registry or apply to a cluster — that is
intentionally left to the operator. Output is a directory of artifacts
and the commands needed to ship them.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .base import Agent, AgentRequest

DOCKERFILE = """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

K8S_DEPLOYMENT = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels: {{ app: {name} }}
spec:
  replicas: 2
  selector:
    matchLabels: {{ app: {name} }}
  template:
    metadata:
      labels: {{ app: {name} }}
    spec:
      containers:
        - name: app
          image: {image}
          ports:
            - containerPort: 8000
          readinessProbe:
            httpGet: {{ path: /health, port: 8000 }}
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            requests: {{ cpu: "100m", memory: "128Mi" }}
            limits:   {{ cpu: "500m", memory: "512Mi" }}
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector: {{ app: {name} }}
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
"""


class DeployerAgent(Agent):
    name = "deployer"

    async def run(self, req: AgentRequest) -> dict[str, Any]:
        code = req.input.get("code", {}) or {}
        files = list(code.get("files", []))
        app_name = "grokforge-output"
        image_tag = f"{app_name}:latest"

        # Ensure Dockerfile present.
        if not any(f["path"] == "Dockerfile" for f in files):
            files.append({"path": "Dockerfile", "content": DOCKERFILE})
            self.log("added Dockerfile")

        # Ensure requirements.txt present.
        if not any(f["path"] == "requirements.txt" for f in files):
            files.append({"path": "requirements.txt", "content": "fastapi\nuvicorn[standard]\n"})
            self.log("added requirements.txt")

        # K8s manifest
        k8s = K8S_DEPLOYMENT.format(name=app_name, image=image_tag)
        files.append({"path": "k8s/deployment.yaml", "content": k8s})

        # GitHub Actions for CI/CD
        files.append({"path": ".github/workflows/ci.yaml", "content": _ci_workflow(app_name)})

        # README
        files.append({"path": "DEPLOY.md", "content": textwrap.dedent(f"""\
            # Deploy

            Build:
            ```
            docker build -t {image_tag} .
            ```

            Run locally:
            ```
            docker run --rm -p 8000:8000 {image_tag}
            ```

            Kubernetes:
            ```
            kubectl apply -f k8s/deployment.yaml
            ```
            """)})

        self.log(f"packaged {len(files)} files for deployment")
        return {
            "files": files,
            "image": image_tag,
            "k8s_manifest": "k8s/deployment.yaml",
            "deploy_commands": [
                f"docker build -t {image_tag} .",
                f"docker push {image_tag}",
                "kubectl apply -f k8s/deployment.yaml",
            ],
        }

    async def confidence(self, output: dict[str, Any]) -> float:
        files = output.get("files", [])
        has_docker = any(f["path"] == "Dockerfile" for f in files)
        has_k8s = any("k8s/" in f["path"] for f in files)
        return 0.5 + 0.25 * has_docker + 0.25 * has_k8s


def _ci_workflow(app_name: str) -> str:
    return textwrap.dedent(f"""\
        name: ci
        on:
          push: {{ branches: [main] }}
          pull_request: {{ branches: [main] }}
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - uses: actions/setup-python@v5
                with: {{ python-version: "3.11" }}
              - run: pip install -r requirements.txt pytest
              - run: pytest -q
          docker:
            needs: test
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - run: docker build -t {app_name}:${{{{ github.sha }}}} .
        """)
