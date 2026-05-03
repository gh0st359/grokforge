"""Thin async client for the Grok (xAI) chat completions API.

Uses an OpenAI-compatible endpoint shape. Prices are best-effort estimates
intended for local cost tracking; refresh against xAI's current pricing
page before relying on them for billing decisions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@dataclass(frozen=True)
class ModelPricing:
    input_per_1k: float
    output_per_1k: float


# Replace with current xAI list pricing.
PRICING: dict[str, ModelPricing] = {
    "grok-4-3": ModelPricing(input_per_1k=0.005, output_per_1k=0.015),
    "grok-4-mini": ModelPricing(input_per_1k=0.0008, output_per_1k=0.0024),
    "grok-3": ModelPricing(input_per_1k=0.003, output_per_1k=0.009),
}


class GrokError(RuntimeError):
    pass


class GrokClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.api_key = api_key or os.getenv("GROK_API_KEY")
        self.base_url = (base_url or os.getenv("GROK_BASE_URL") or "https://api.x.ai/v1").rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type((httpx.TransportError, GrokError)),
        reraise=True,
    )
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> tuple[str, float]:
        """Run a chat completion. Returns (text, estimated_cost_usd)."""
        if not self.configured:
            raise GrokError("GROK_API_KEY not set; cannot call live API")
        client = await self._get_client()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code >= 500:
            raise GrokError(f"server error {resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            # Don't retry 4xx
            raise GrokError(f"client error {resp.status_code}: {resp.text[:200]}") from None
        body = resp.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        cost = self.estimate_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        return text, cost

    @staticmethod
    def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        p = PRICING.get(model)
        if p is None:
            return 0.0
        return (prompt_tokens / 1000.0) * p.input_per_1k + (completion_tokens / 1000.0) * p.output_per_1k
