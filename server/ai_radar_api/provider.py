from __future__ import annotations

import json

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
    def __init__(self, config: AppConfig, profile: dict | None = None):
        self.config = config
        self.profile = profile or {}

    def _request_config(self) -> tuple[str, str, str, str, float, dict]:
        api_base_url = str(self.profile.get("base_url") or self.config.ai_base_url or "").rstrip("/")
        api_key = str(self.profile.get("api_key") or self.config.ai_api_key or "")
        ai_model = str(self.profile.get("model") or self.config.ai_model)
        api_format = str(self.profile.get("type") or self.config.ai_api_format).strip().lower().replace("-", "_")
        timeout = float(self.profile.get("timeout_seconds") or 45)
        headers = dict(self.profile.get("headers") or {})
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        if not api_base_url or not api_key:
            raise AIProviderUnavailable("AI_BASE_URL and AI_API_KEY are required")
        return api_base_url, api_key, ai_model, api_format, timeout, headers

    async def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        api_base_url, _api_key, ai_model, api_format, timeout, headers = self._request_config()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if api_format == "responses":
                    response = await client.post(
                        f"{api_base_url}/responses",
                        headers=headers,
                        json={
                            "model": ai_model,
                            "input": messages,
                            "temperature": temperature,
                        },
                    )
                else:
                    response = await client.post(
                        f"{api_base_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": ai_model,
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
        if api_format == "responses":
            return _responses_content(payload)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderUnavailable("AI response did not include message content") from exc
        return str(content)

    async def stream_chat(self, messages: list[dict], temperature: float = 0.2):
        api_base_url, _api_key, ai_model, api_format, timeout, headers = self._request_config()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if api_format == "responses":
                    async with client.stream(
                        "POST",
                        f"{api_base_url}/responses",
                        headers=headers,
                        json={
                            "model": ai_model,
                            "input": messages,
                            "temperature": temperature,
                            "stream": True,
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            text = _responses_stream_delta(line)
                            if text:
                                yield text
                else:
                    async with client.stream(
                        "POST",
                        f"{api_base_url}/chat/completions",
                        headers=headers,
                        json={
                            "model": ai_model,
                            "messages": messages,
                            "temperature": temperature,
                            "stream": True,
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            text = _chat_completions_stream_delta(line)
                            if text:
                                yield text
        except httpx.HTTPError as exc:
            raise AIProviderUnavailable(f"AI provider stream failed: {exc}") from exc


def _sse_payload(line: str) -> dict | None:
    stripped = str(line or "").strip()
    if not stripped.startswith("data:"):
        return None
    data = stripped[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _chat_completions_stream_delta(line: str) -> str:
    payload = _sse_payload(line)
    if not payload:
        return ""
    try:
        return str(payload["choices"][0].get("delta", {}).get("content") or "")
    except (KeyError, IndexError, TypeError):
        return ""


def _responses_stream_delta(line: str) -> str:
    payload = _sse_payload(line)
    if not payload:
        return ""
    if payload.get("type") == "response.output_text.delta":
        return str(payload.get("delta") or "")
    if payload.get("type") == "response.output_text.done":
        return ""
    return ""
