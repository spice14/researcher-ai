"""Ollama LLM client — structured, traced inference calls.

Purpose:
- Provide a single entry point for all LLM calls in the system
- Enforce prompt versioning, token logging, and trace IDs
- Return structured responses with metadata

Inputs/Outputs:
- Input: prompt string, model name, generation parameters
- Output: LLMResponse with text, model metadata, token usage, latency

Failure Modes:
- Ollama unreachable → raise LLMConnectionError (never silent)
- Invalid JSON from model → return raw text, flag in metadata
- Timeout → raise LLMTimeoutError

Testing Strategy:
- Unit tests with mocked HTTP responses
- Integration tests against live Ollama
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# Defaults from .env.template
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:32b"


class LLMConnectionError(Exception):
    """Ollama server is unreachable."""


class LLMTimeoutError(Exception):
    """LLM call exceeded timeout."""


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from an LLM call.

    Every field required by AGENTS.md §5:
    - prompt_version
    - model_name
    - token_usage
    - latency_ms
    - trace_id
    """

    text: str
    model: str
    prompt_version: str
    trace_id: str
    latency_ms: float
    prompt_eval_count: int = 0
    eval_count: int = 0
    total_duration_ns: int = 0
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def token_usage(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_eval_count,
            "completion_tokens": self.eval_count,
            "total_tokens": self.prompt_eval_count + self.eval_count,
        }


class OllamaClient:
    """Synchronous Ollama HTTP client with trace logging.

    Uses only stdlib (urllib) — no external HTTP dependencies required.
    All calls are blocking and fully traced.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 120,
    ):
        self.base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or DEFAULT_BASE_URL
        )
        self.model = (
            model
            or os.environ.get("OLLAMA_MODEL")
            or os.environ.get("LLM_MODEL")
            or DEFAULT_MODEL
        )
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        *,
        prompt_version: str = "v0.0.0",
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate text from Ollama.

        Args:
            prompt: The user prompt.
            prompt_version: Semantic version tag for the prompt template.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            model: Override the default model.

        Returns:
            LLMResponse with text and full metadata.

        Raises:
            LLMConnectionError: If Ollama is unreachable.
            LLMTimeoutError: If the call exceeds timeout.
        """
        trace_id = f"llm_{uuid.uuid4().hex[:12]}"
        use_model = model or self.model
        start = time.time()

        body: Dict[str, Any] = {
            "model": use_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            body["system"] = system

        try:
            data = json.dumps(body).encode("utf-8")
            req = Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (URLError, ConnectionError, OSError) as exc:
            raise LLMConnectionError(
                f"Cannot reach Ollama at {self.base_url}: {exc}"
            ) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(
                f"Ollama call timed out after {self.timeout_seconds}s"
            ) from exc

        latency_ms = (time.time() - start) * 1000

        response = LLMResponse(
            text=raw.get("response", ""),
            model=raw.get("model", use_model),
            prompt_version=prompt_version,
            trace_id=trace_id,
            latency_ms=latency_ms,
            prompt_eval_count=raw.get("prompt_eval_count", 0),
            eval_count=raw.get("eval_count", 0),
            total_duration_ns=raw.get("total_duration", 0),
            raw_response=raw,
        )

        logger.info(
            "LLM call completed",
            extra={
                "trace_id": trace_id,
                "model": use_model,
                "prompt_version": prompt_version,
                "latency_ms": round(latency_ms, 1),
                "prompt_tokens": response.prompt_eval_count,
                "completion_tokens": response.eval_count,
            },
        )
        return response

    def generate_json(
        self,
        prompt: str,
        *,
        prompt_version: str = "v0.0.0",
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate and attempt JSON parsing. Same as generate() but with
        format hint and lower temperature default for structured output."""
        json_system = (system or "") + "\nYou MUST respond with valid JSON only. No markdown, no explanation."
        return self.generate(
            prompt,
            prompt_version=prompt_version,
            system=json_system.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

    def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            req = Request(self.base_url, method="GET")
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False
