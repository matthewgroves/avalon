"""OpenAI LLM client for agent decision-making."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests  # type: ignore[import-untyped]

from .exceptions import ConfigurationError
from .llm_client import BaseLLMClient


@dataclass
class OpenAIClient(BaseLLMClient):
    """OpenAI API client for agent decision-making.

    Uses OpenAI's API to access GPT models.
    Requires OPENAI_API_KEY environment variable.

    Inherits all prompt building and decision logic from BaseLLMClient,
    only implementing the API-specific __post_init__ and _generate_text methods.
    """

    model_name: str = "gpt-5-mini-2025-08-07"
    temperature: float = 1.0
    api_key: str | None = None
    max_retries: int = 3
    base_retry_delay: float = 1.0

    def __post_init__(self) -> None:
        """Configure API client."""
        if self.api_key is None:
            self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY environment variable is required. "
                "Get your API key from https://platform.openai.com/api-keys"
            )

    def _generate_text(self, prompt: str) -> str:
        """Generate text completion from prompt using OpenAI API."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url="https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": self.temperature,
                        "max_completion_tokens": 1000,
                        "reasoning_effort": "minimal",  # Minimize reasoning tokens to reduce cost
                    },
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()

                # For reasoning models like GPT-5, check for truncated responses
                choice = result["choices"][0]
                content = choice["message"]["content"]

                # Debug: Check for empty responses
                if not content or not content.strip():
                    finish_reason = choice.get("finish_reason")
                    if finish_reason == "length":
                        print(
                            "Warning: Response cut off due to length limit. "
                            "Increase max_completion_tokens."
                        )
                    print("Warning: Empty response from API.")

                return content if content else ""

            except requests.exceptions.HTTPError as exc:
                last_exception = exc
                # Check if it's a rate limit error (429)
                if exc.response.status_code == 429:
                    retry_delay = self.base_retry_delay * (2**attempt)

                    if attempt < self.max_retries - 1:
                        retry_msg = (
                            f"Rate limit hit. Waiting {retry_delay:.1f}s "
                            f"before retry {attempt + 1}/{self.max_retries}..."
                        )
                        print(retry_msg)
                        time.sleep(retry_delay)
                    else:
                        raise
                else:
                    # For non-rate-limit HTTP errors, fail immediately
                    raise

            except (requests.exceptions.RequestException, KeyError, ValueError) as exc:
                # For connection errors or malformed responses, retry
                last_exception = exc
                if attempt < self.max_retries - 1:
                    retry_delay = self.base_retry_delay * (2**attempt)
                    print(f"Request failed: {exc}. Retrying in {retry_delay:.1f}s...")
                    time.sleep(retry_delay)
                else:
                    raise

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected state in _generate_text retry logic")


__all__ = ["OpenAIClient"]
