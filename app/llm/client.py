# Abstract interface so callers do not depend on a specific LLM vendor or live network calls during testing.
from abc import ABC, abstractmethod
import os


class LLMClient(ABC):
    """Abstract interface for LLM text completion."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Sends prompt to language model and returns raw text completion."""
        pass


def create_default_llm_client() -> LLMClient:
    """Creates GeminiClient if GEMINI_API_KEY is configured, otherwise FakeLLMClient."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from app.llm.gemini_client import GeminiClient
            return GeminiClient(api_key=api_key)
        except Exception:
            pass
    from app.llm.fake_client import FakeLLMClient
    return FakeLLMClient()

