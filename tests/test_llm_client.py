import pytest
from unittest.mock import AsyncMock, patch
from src.llm_client import LLMClient


class TestLLMClient:
    def test_builds_messages_correctly(self):
        client = LLMClient({
            "llm": {
                "api_key": "sk-test",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            }
        })
        assert client.model == "deepseek-chat"
        assert client.base_url == "https://api.deepseek.com"

    @pytest.mark.asyncio
    async def test_chat_returns_parsed_json(self):
        client = LLMClient({
            "llm": {
                "api_key": "sk-test",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            }
        })
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"title": "test", "sections": []}'
                }
            }]
        }
        with patch.object(client._client.chat.completions, "create",
                          AsyncMock(return_value=_mock_openai_response(mock_response))):
            result = await client.chat([
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Say hi."},
            ])
            assert result == {"title": "test", "sections": []}

    @pytest.mark.asyncio
    async def test_retries_on_json_parse_failure(self):
        client = LLMClient({
            "llm": {
                "api_key": "sk-test",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            }
        })
        bad_response = {
            "choices": [{"message": {"content": "this is not valid json at all"}}]
        }
        good_response = {
            "choices": [{"message": {"content": '{"ok": true}'}}]
        }
        mock_create = AsyncMock(side_effect=[
            _mock_openai_response(bad_response),
            _mock_openai_response(good_response),
        ])
        with patch.object(client._client.chat.completions, "create", mock_create):
            result = await client.chat_with_retry([
                {"role": "user", "content": "test"},
            ])
            assert result == {"ok": True}
            assert mock_create.call_count == 2


def _mock_openai_response(data: dict):
    """Build a mock OpenAI response object."""
    class MockMessage:
        content = data["choices"][0]["message"]["content"]
    class MockChoice:
        message = MockMessage()
    class MockResponse:
        choices = [MockChoice()]
    return MockResponse()
