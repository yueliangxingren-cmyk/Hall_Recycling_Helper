"""Small OpenAI-compatible adapter with independently configured providers."""

import json
import math
import os
import socket
import ssl
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(Exception):
    """A provider is unavailable or returned an invalid response."""

    def __init__(self, message: str, *, code: str = "provider_error", status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code

    @property
    def diagnostic(self) -> str:
        """Only server-owned messages: never interpolate upstream errors or secrets."""
        hints = {
            "dns_error": "DNS lookup failed; check network access to the provider",
            "timeout": "Provider request timed out",
            "tls_error": "TLS verification failed; check the certificate chain",
            "connection_error": "Connection failed; check provider availability and network access",
            "authentication_error": "Authentication failed; check the API key and matching endpoint",
            "access_denied": "Access denied; check the account's model permissions",
            "not_found": "Endpoint or model not found; check the base URL and model ID",
            "rate_limit": "Rate or quota limit reached; check provider usage limits",
            "invalid_request": "Provider rejected the request; check model and parameter support",
            "service_error": "Provider service error; try again later",
            "invalid_config": "Invalid provider URL or request configuration",
            "invalid_json": "Provider returned invalid JSON",
            "invalid_response": "Provider response does not match the expected API format",
            "invalid_embedding_response": "Provider returned invalid embedding vectors",
            "output_truncated": "Model reached its output token limit before completing the answer",
            "content_filtered": "Provider filtered the model response",
            "not_configured": "Provider settings are incomplete; set key, base URL, and model",
        }
        status = f", HTTP {self.status_code}" if self.status_code is not None else ""
        return f"{self.code}{status}: {hints.get(self.code, 'Provider operation failed')}"


@dataclass(frozen=True)
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).parent / ".env", override=False)
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", cls.llm_base_url).strip(),
            llm_model=os.getenv("LLM_MODEL", cls.llm_model).strip(),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", "").strip(),
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "").strip(),
            embedding_model=os.getenv("EMBEDDING_MODEL", cls.embedding_model).strip(),
        )


class ModelProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def embeddings_enabled(self):
        return bool(self.settings.embedding_api_key and self.settings.embedding_base_url
                    and self.settings.embedding_model)

    @property
    def chat_enabled(self):
        return bool(self.settings.llm_api_key and self.settings.llm_base_url
                    and self.settings.llm_model)

    def _post(self, base_url, api_key, endpoint, payload):
        try:
            request = Request(
                f"{base_url.rstrip('/')}/{endpoint}",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                data=json.dumps(payload).encode("utf-8"), method="POST",
            )
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise ProviderError("Invalid provider response", code="invalid_response")
            return data
        except HTTPError as exc:
            codes = {400: "invalid_request", 401: "authentication_error", 403: "access_denied",
                     404: "not_found", 408: "timeout", 429: "rate_limit", 504: "timeout"}
            code = codes.get(exc.code, "service_error" if exc.code >= 500 else "invalid_request")
            # Close the response without reading/logging its potentially sensitive body.
            exc.close()
            raise ProviderError("Provider request failed", code=code, status_code=exc.code) from exc
        except URLError as exc:
            reason = exc.reason
            code = ("dns_error" if isinstance(reason, socket.gaierror) else
                    "tls_error" if isinstance(reason, ssl.SSLError) else
                    "timeout" if isinstance(reason, TimeoutError) else "connection_error")
            raise ProviderError("Provider request failed", code=code) from exc
        except TimeoutError as exc:
            raise ProviderError("Provider request failed", code="timeout") from exc
        except ssl.SSLError as exc:
            raise ProviderError("Provider request failed", code="tls_error") from exc
        except (OSError, HTTPException) as exc:
            raise ProviderError("Provider request failed", code="connection_error") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProviderError("Provider request failed", code="invalid_json") from exc
        except ValueError as exc:
            raise ProviderError("Provider request failed", code="invalid_config") from exc

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embeddings_enabled:
            raise ProviderError("Embeddings are not configured", code="not_configured")
        vectors = []
        # Conservative batches also support providers with a ten-input limit.
        for start in range(0, len(texts), 10):
            batch = texts[start:start + 10]
            data = self._post(
                self.settings.embedding_base_url, self.settings.embedding_api_key,
                "embeddings", {"model": self.settings.embedding_model,
                               "input": batch, "encoding_format": "float"},
            )
            try:
                rows = sorted(data["data"], key=lambda row: row["index"])
                if [row["index"] for row in rows] != list(range(len(batch))):
                    raise ValueError("Missing or repeated embedding index")
                for row in rows:
                    vector = row["embedding"]
                    if not isinstance(vector, list) or not vector or not all(
                        type(value) in (int, float) and math.isfinite(value)
                        for value in vector
                    ) or not any(vector):
                        raise ValueError("Invalid vector")
                    if vectors and len(vector) != len(vectors[0]):
                        raise ValueError("Inconsistent dimensions")
                    vectors.append(vector)
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError("Invalid embedding response", code="invalid_embedding_response") from exc
        return vectors

    def complete_json(self, system: str, rule: dict) -> dict:
        if not self.chat_enabled:
            raise ProviderError("Chat is not configured", code="not_configured")
        data = self._post(
            self.settings.llm_base_url, self.settings.llm_api_key,
            "chat/completions", {
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(rule, ensure_ascii=False)},
                ],
                "temperature": 0,
                "max_tokens": 800,
                "response_format": {"type": "json_object"},
            },
        )
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("Incomplete model output", code="output_truncated")
            if choice.get("finish_reason") == "content_filter":
                raise ProviderError("Filtered model output", code="content_filtered")
            content = choice["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Expected JSON object")
            return result
        except json.JSONDecodeError as exc:
            raise ProviderError("Invalid chat response", code="invalid_json") from exc
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise ProviderError("Invalid chat response", code="invalid_response") from exc
