"""OpenRouter LLM client for agent decision-making.

DEPRECATED: This OpenRouter-based client is deprecated. Use OpenAIClient instead.
OpenAI's GPT-5 models provide better performance and automatic prompt caching
for cost optimization.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests  # type: ignore[import-untyped]

from .exceptions import ConfigurationError
from .llm_client import BaseLLMClient


@dataclass
class OpenRouterClient(BaseLLMClient):
    """OpenRouter API client for agent decision-making.

    .. deprecated::
        This client is deprecated. Use :class:`OpenAIClient` instead for better
        performance and automatic prompt caching.

    Uses OpenRouter's API to access various LLM models without strict rate limits.
    Requires OPENROUTER_API_KEY environment variable.

    Inherits all prompt building and decision logic from BaseLLMClient,
    only implementing the API-specific __post_init__ and _generate_text methods.
    """

    model_name: str = "openai/gpt-oss-20b:free"
    temperature: float = 0.7
    api_key: str | None = None
    max_retries: int = 3
    base_retry_delay: float = 1.0
    site_url: str = "https://github.com/matthewgroves/avalon"
    site_name: str = "Avalon Game"

    def __post_init__(self) -> None:
        """Configure API client and warn about deprecation."""
        import warnings

        warnings.warn(
            "OpenRouterClient is deprecated. Use OpenAIClient with GPT-5 models instead "
            "for better performance and automatic prompt caching.",
            DeprecationWarning,
            stacklevel=2,
        )

        if self.api_key is None:
            # Try both OPENROUTER_TOKEN and OPENROUTER_API_KEY
            self.api_key = os.environ.get("OPENROUTER_TOKEN") or os.environ.get(
                "OPENROUTER_API_KEY"
            )
        if not self.api_key:
            raise ConfigurationError(
                "OPENROUTER_TOKEN or OPENROUTER_API_KEY environment variable is required. "
                "Get your API key from https://openrouter.ai/keys"
            )
        # Don't call parent __post_init__ since we're not using Gemini

    def _generate_text(self, prompt: str) -> str:
        """Generate text completion from prompt using OpenRouter API."""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": self.site_url,
                        "X-Title": self.site_name,
                    },
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": self.temperature,
                        "max_tokens": 1000,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]

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
