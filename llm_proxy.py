import os
import threading

from openai import APIConnectionError, APIError, AuthenticationError, NotFoundError, OpenAI, RateLimitError

_warmup_lock = threading.Lock()
_warmup_complete = False


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
    return all(_get_env(name) for name in ("API_BASE_URL", "API_KEY", "MODEL_NAME"))


def build_llm_client(timeout: float = 30.0) -> OpenAI:
    return OpenAI(
        base_url=require_env("API_BASE_URL"),
        api_key=require_env("API_KEY"),
        timeout=timeout,
    )


def get_model_name() -> str:
    return require_env("MODEL_NAME")


def warm_proxy_once() -> bool:
    global _warmup_complete

    if _warmup_complete or not proxy_env_present():
        return _warmup_complete

    with _warmup_lock:
        if _warmup_complete or not proxy_env_present():
            return _warmup_complete

        try:
            client = build_llm_client(timeout=8.0)
            response = client.chat.completions.create(
                model=get_model_name(),
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=3,
                temperature=0,
            )
            _warmup_complete = bool(response.choices)
        except (RuntimeError, NotFoundError, APIError, APIConnectionError, AuthenticationError, RateLimitError):
            return False
        return _warmup_complete
