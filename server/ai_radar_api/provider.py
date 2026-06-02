from __future__ import annotations

import httpx

from .config import AppConfig


class AIProviderUnavailable(RuntimeError):
    pass


def _responses_content(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    parts: list[str] = []
    for output in payload.get("output") or []:
        if not isinstance(output, dict):
            continue
        for content in output.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)
    if parts:
        return "\n".join(parts)
    raise AIProviderUnavailable("AI response did not include output text")


class AIProvider:
    def __init__(self, config: AppConfig):
        self.config = config

    async def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        if not self.config.ai_base_url or not self.config.ai_api_key:
            raise AIProviderUnavailable("AI_BASE_URL and AI_API_KEY are required")

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                if self.config.ai_api_format == "responses":
                    response = await client.post(
                        f"{self.config.ai_base_url}/responses",
                        headers={"Authorization": f"Bearer {self.config.ai_api_key}"},
                        json={
                            "model": self.config.ai_model,
                            "input": messages,
                            "temperature": temperature,
                        },
                    )
                else:
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
        if self.config.ai_api_format == "responses":
            return _responses_content(payload)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderUnavailable("AI response did not include message content") from exc
        return str(content)
