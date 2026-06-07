from __future__ import annotations

import json
import re

from openai import AsyncOpenAI


class LLMError(Exception):
    """Raised when LLM call fails after retries."""


class LLMClient:
    def __init__(self, config: dict):
        llm_config = config.get("llm", {})
        self.model = llm_config.get("model", "deepseek-chat")
        self.base_url = llm_config.get("base_url", "https://api.deepseek.com")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.timeout = llm_config.get("timeout_seconds", 60)
        self._client = AsyncOpenAI(
            api_key=llm_config.get("api_key", ""),
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def chat(self, messages: list[dict]) -> dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.choices[0].message.content or ""
        return _parse_json(content)

    async def chat_with_retry(self, messages: list[dict], max_retries: int = 2) -> dict:
        messages = list(messages)  # shallow copy to avoid mutating caller's list
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.chat(messages)
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                if attempt < max_retries:
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON. "
                            f"Error: {e}. "
                            "Please output ONLY valid JSON this time."
                        ),
                    })
        raise LLMError(f"LLM failed to return valid JSON after {max_retries + 1} attempts: {last_error}")


def _parse_json(content: str) -> dict:
    """Extract JSON from LLM response. Tries direct parse first, then markdown code block extraction."""
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())
    raise ValueError(f"Cannot parse JSON from: {text[:200]}...")
