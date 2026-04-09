import os
import threading

from openai import APIConnectionError, APIError, AuthenticationError, NotFoundError, OpenAI, RateLimitError

_warmup_lock = threading.Lock()
_warmup_complete = False
DEFAULT_MODEL_NAME = "gpt-4.1-mini"


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def require_env(name: str) -> str:
    value = _get_env(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to your environment or .env file.")
    return value


def proxy_env_present() -> bool:
    return all(_get_env(name) for name in ("API_BASE_URL", "API_KEY"))


def build_llm_client(timeout: float = 30.0) -> OpenAI:
    return OpenAI(
        base_url=require_env("API_BASE_URL"),
        api_key=require_env("API_KEY"),
        timeout=timeout,
    )


def get_model_name() -> str:
    # Phase-2 validator guarantees API_BASE_URL and API_KEY, but may omit MODEL_NAME.
    # Fall back to a common LiteLLM/OpenAI-compatible default so at least one proxy call is attempted.
    return (
        _get_env("MODEL_NAME")
        or _get_env("OPENAI_MODEL")
        or _get_env("MODEL")
        or _get_env("LLM_MODEL")
        or DEFAULT_MODEL_NAME
    )


def warm_proxy_once() -> bool:
    global _warmup_complete

    if _warmup_complete or not proxy_env_present():
        return _warmup_complete

    with _warmup_lock:
        if _warmup_complete or not proxy_env_present():
            return _warmup_complete

        try:
            client = build_llm_client(timeout=1.0)
            # Hit the proxy using only the injected base URL and API key.
            # This avoids depending on MODEL_NAME being present during validation.
            client.models.list(timeout=1.0)
            _warmup_complete = True
        except Exception:
            return False
        return _warmup_complete
