"""Deployer agent.

Packages the verified code into a Docker image + Kubernetes manifests +
GitHub Actions workflow. Emits a `file_written` event per artifact so
the user sees the deploy bundle assemble in real time.
"""

from __future__ import annotations

import textwrap
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

        self.think(
            f"Packaging {len(files)} source file(s) for deployment. "
            "I'll add a Dockerfile, K8s manifests, GitHub Actions CI, and a DEPLOY.md "
            "if any are missing — never overwrite the Coder's choice if one already exists.",
            scope="strategy",
        )

        self._add_if_missing(files, "Dockerfile", DOCKERFILE, "dockerfile")
        self._add_if_missing(files, "requirements.txt",
                             "fastapi==0.110.0\nuvicorn[standard]==0.27.1\npydantic==2.6.1\n", "text")

        k8s = K8S_DEPLOYMENT.format(name=app_name, image=image_tag)
        files.append({"path": "k8s/deployment.yaml", "content": k8s})
        self.file_written("k8s/deployment.yaml", k8s, language="yaml")

        ci = _ci_workflow(app_name)
        files.append({"path": ".github/workflows/ci.yaml", "content": ci})
        self.file_written(".github/workflows/ci.yaml", ci, language="yaml")

        deploy_md = textwrap.dedent(f"""\
            # Deploy

            ```bash
            docker build -t {image_tag} .
            docker run --rm -p 8000:8000 {image_tag}
            kubectl apply -f k8s/deployment.yaml
            ```
            """)
        files.append({"path": "DEPLOY.md", "content": deploy_md})
        self.file_written("DEPLOY.md", deploy_md, language="markdown")

        self.decide(
            f"image tag = {image_tag}",
            "v0.1 ships untagged 'latest' for local dev; production should be content-addressed.",
        )

        self.metric("deploy_files", len(files), "")
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

    def _add_if_missing(self, files: list[dict[str, str]], path: str, content: str,
                        language: str) -> None:
        if any(f["path"] == path for f in files):
            self.log(f"{path} already present from upstream agent — keeping it")
            return
        files.append({"path": path, "content": content})
        self.file_written(path, content, language=language)


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
