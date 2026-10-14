import os
from pathlib import Path
from dotenv import load_dotenv
import httpx

from app.llm.client import LLMClient

# Load .env file from project root or parent directories if present
load_dotenv()


class GeminiClient(LLMClient):
    """Client for Google Gemini REST API."""

    DEFAULT_MODEL = "gemini-1.5-flash"
    API_URL_TEMPLATE = (
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    )

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set it in .env or pass it to GeminiClient."
            )
        self.model = model or os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)

    def complete(self, prompt: str) -> str:
        url = self.API_URL_TEMPLATE.format(model=self.model, key=self.api_key)
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(url, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Gemini API returned status {response.status_code}: {response.text[:200]}"
                    )
                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Gemini API returned an empty candidates list.")

                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts or "text" not in content_parts[0]:
                    raise RuntimeError("Gemini API candidate response missing text content.")

                return content_parts[0]["text"]
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Gemini API request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Gemini API network error: {exc}") from exc
