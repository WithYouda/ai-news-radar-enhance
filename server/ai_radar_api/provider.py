from __future__ import annotations

import httpx

from .config import AppConfig


class AIProviderUnavailable(RuntimeError):
    pass


class AIProvider:
    def __init__(self, config: AppConfig):
        self.config = config

    async def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        if not self.config.ai_base_url or not self.config.ai_api_key:
            raise AIProviderUnavailable("AI_BASE_URL and AI_API_KEY are required")

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    f"{self.config.ai_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.config.ai_api_key}"},
                    json={
                        "model": self.config.ai_model,
                        "messages": messages,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderUnavailable(f"AI provider request failed: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderUnavailable("AI provider returned invalid JSON") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderUnavailable("AI response did not include message content") from exc
        return str(content)
