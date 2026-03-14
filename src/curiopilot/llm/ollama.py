"""Thin async client for the Ollama HTTP API with retry logic."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)


class OllamaClient:
    """Wraps the Ollama ``/api/generate`` and ``/api/embeddings`` endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 120,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self._http: httpx.AsyncClient | None = None

    async def open(self) -> None:
        """Create a shared httpx client for the lifetime of this instance."""
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        """Close the shared httpx client."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> "OllamaClient":
        await self.open()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(timeout=self.timeout)

    async def generate_json(
        self,
        model: str,
        prompt: str,
        *,
        keep_alive: int | str | None = None,
    ) -> dict[str, Any]:
        """Call ``/api/generate`` and parse the response as JSON.

        The ``format`` parameter is set to ``"json"`` so Ollama constrains
        output to valid JSON.  We then parse the text ourselves to surface
        errors early.
        """

        owns_client = self._http is None

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(min=2, max=30),
            retry=retry_if_exception_type((httpx.HTTPError, json.JSONDecodeError)),
            reraise=True,
        )
        async def _call() -> dict[str, Any]:
            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            }
            if keep_alive is not None:
                payload["keep_alive"] = keep_alive

            client = self._get_client()
            try:
                resp = await client.post(
                    f"{self.base_url}/api/generate", json=payload
                )
                resp.raise_for_status()
                body = resp.json()
                text = body.get("response", "")
                return json.loads(text)
            finally:
                if owns_client:
                    await client.aclose()

        return await _call()

    async def generate_text(
        self,
        model: str,
        prompt: str,
        *,
        keep_alive: int | str | None = None,
    ) -> str:
        """Call ``/api/generate`` and return the raw text response."""

        owns_client = self._http is None

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(min=2, max=30),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async def _call() -> str:
            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
            if keep_alive is not None:
                payload["keep_alive"] = keep_alive

            client = self._get_client()
            try:
                resp = await client.post(
                    f"{self.base_url}/api/generate", json=payload
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
            finally:
                if owns_client:
                    await client.aclose()

        return await _call()

    async def embed(
        self,
        model: str,
        text: str,
        *,
        keep_alive: int | str | None = None,
    ) -> list[float]:
        """Call ``/api/embeddings`` and return the embedding vector."""

        owns_client = self._http is None

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(min=2, max=30),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async def _call() -> list[float]:
            payload: dict[str, Any] = {
                "model": model,
                "prompt": text,
            }
            if keep_alive is not None:
                payload["keep_alive"] = keep_alive

            client = self._get_client()
            try:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings", json=payload
                )
                resp.raise_for_status()
                return resp.json()["embedding"]
            finally:
                if owns_client:
                    await client.aclose()

        return await _call()

    async def unload_model(self, model: str) -> None:
        """Send a ``keep_alive=0`` request to force Ollama to unload a model."""
        owns_client = self._http is None
        client = self._get_client()
        try:
            await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "",
                    "keep_alive": 0,
                    "stream": False,
                },
            )
            log.info("Requested unload for model %s", model)
        except httpx.HTTPError:
            log.warning("Could not unload model %s (may already be unloaded)", model)
        finally:
            if owns_client:
                await client.aclose()

    async def swap_model(
        self, from_model: str, to_model: str, *, embedding: bool = False
    ) -> None:
        """Unload *from_model* then warm up *to_model* with a trivial request.

        Set ``embedding=True`` when *to_model* is an embedding model so the
        warm-up hits ``/api/embeddings`` instead of ``/api/generate``.
        """
        log.info("Swapping model: %s -> %s", from_model, to_model)
        await self.unload_model(from_model)
        try:
            if embedding:
                await self.embed(to_model, "warmup", keep_alive="5m")
            else:
                await self.generate_text(to_model, "Hello", keep_alive="5m")
            log.info("Model %s warmed up", to_model)
        except Exception:
            log.warning("Warm-up request for %s failed (model may still load on first real call)", to_model)
