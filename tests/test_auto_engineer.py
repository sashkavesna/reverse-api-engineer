"""Tests for auto_engineer.py - Auto mode engineers."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from reverse_api.auto_engineer import ClaudeAutoEngineer, OpenCodeAutoEngineer


class TestClaudeAutoEngineerInit:
    """Test ClaudeAutoEngineer initialization."""

    def test_init(self, tmp_path):
        """Initializes with HAR path and MCP run_id."""
        with patch("reverse_api.auto_engineer.get_har_dir", return_value=tmp_path / "har"):
            with patch("reverse_api.base_engineer.get_scripts_dir", return_value=tmp_path / "scripts"):
                with patch("reverse_api.base_engineer.MessageStore"):
                    eng = ClaudeAutoEngineer(
                        run_id="test123",
                        prompt="browse and capture",
                        model="claude-sonnet-4-6",
                        output_dir=str(tmp_path),
                    )
                    assert eng.mcp_run_id == "test123"
                    assert eng.har_path == tmp_path / "har" / "recording.har"


class TestClaudeAutoEngineerPrompt:
    """Test auto prompt building."""

    def _make_engineer(self, tmp_path, **kwargs):
        defaults = {
            "run_id": "test123",
            "prompt": "browse and capture",
            "model": "claude-sonnet-4-6",
            "output_dir": str(tmp_path),
        }
        defaults.update(kwargs)
        with patch("reverse_api.auto_engineer.get_har_dir", return_value=tmp_path / "har"):
            with patch("reverse_api.base_engineer.get_scripts_dir", return_value=tmp_path / "scripts"):
                with patch("reverse_api.base_engineer.MessageStore"):
                    return ClaudeAutoEngineer(**defaults)

    def test_python_prompt(self, tmp_path):
        """Python prompt includes correct language references."""
        eng = self._make_engineer(tmp_path)
        prompt = eng._build_auto_prompt()
        assert "Python" in prompt
        assert "requests" in prompt
        assert "api_client.py" in prompt

    def test_javascript_prompt(self, tmp_path):
        """JavaScript prompt includes JS-specific instructions."""
        eng = self._make_engineer(tmp_path, output_language="javascript")
        prompt = eng._build_auto_prompt()
        assert "JavaScript" in prompt
        assert "fetch" in prompt
        assert "api_client.js" in prompt
        assert "package.json" in prompt

    def test_typescript_prompt(self, tmp_path):
        """TypeScript prompt includes TS-specific instructions."""
        eng = self._make_engineer(tmp_path, output_language="typescript")
        prompt = eng._build_auto_prompt()
        assert "TypeScript" in prompt
        assert "interfaces" in prompt
        assert "api_client.ts" in prompt

    def test_prompt_includes_mcp_tools(self, tmp_path):
        """Prompt includes MCP browser tool references."""
        eng = self._make_engineer(tmp_path)
        prompt = eng._build_auto_prompt()
        assert "browser_navigate" in prompt
        assert "browser_click" in prompt
        assert "browser_close" in prompt
        assert "browser_network_requests" in prompt

    def test_prompt_includes_har_path(self, tmp_path):
        """Prompt includes HAR file path."""
        eng = self._make_engineer(tmp_path)
        prompt = eng._build_auto_prompt()
        assert "recording.har" in prompt

    def test_prompt_includes_screenshot_guidelines(self, tmp_path):
        """Prompt includes screenshot guidelines."""
        eng = self._make_engineer(tmp_path)
        prompt = eng._build_auto_prompt()
        assert "Screenshot" in prompt
        assert "1MB" in prompt


class TestClaudeAutoEngineerAnalyze:
    """Test ClaudeAutoEngineer analyze_and_generate."""

    def _make_engineer(self, tmp_path, **kwargs):
        defaults = {
            "run_id": "test123",
            "prompt": "browse and capture",
            "model": "claude-sonnet-4-6",
            "output_dir": str(tmp_path),
        }
        defaults.update(kwargs)
        with patch("reverse_api.auto_engineer.get_har_dir", return_value=tmp_path / "har"):
            with patch("reverse_api.base_engineer.get_scripts_dir", return_value=tmp_path / "scripts"):
                with patch("reverse_api.base_engineer.MessageStore") as mock_ms:
                    mock_ms.return_value = MagicMock()
                    eng = ClaudeAutoEngineer(**defaults)
                    eng.scripts_dir = tmp_path / "scripts"
                    eng.scripts_dir.mkdir(parents=True, exist_ok=True)
                    return eng

    @pytest.mark.asyncio
    async def test_exception_generic(self, tmp_path):
        """Generic exception returns None."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(side_effect=Exception("SDK error"))
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_exception_buffer_size(self, tmp_path):
        """Buffer size exception shows specific message."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("exceeded maximum buffer size 1048576")
            )
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_exception_mcp_server(self, tmp_path):
        """MCP server exception shows npm install hint."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("MCP server failed to start")
            )
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_exception_other(self, tmp_path):
        """Other exception shows generic message."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("some other error")
            )
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_result_message_error(self, tmp_path):
        """ResultMessage with error returns None."""
        eng = self._make_engineer(tmp_path)

        from claude_agent_sdk import ResultMessage
        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = True
        mock_result.result = "Error occurred"

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_result_message_success(self, tmp_path):
        """ResultMessage with success returns result dict."""
        eng = self._make_engineer(tmp_path)

        from claude_agent_sdk import ResultMessage
        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = False
        mock_result.result = "Success"

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is not None
            assert "script_path" in result

    @pytest.mark.asyncio
    async def test_result_with_usage(self, tmp_path):
        """Result with usage metadata calculates cost."""
        eng = self._make_engineer(tmp_path)
        eng.usage_metadata = {
            "input_tokens": 5000,
            "output_tokens": 2000,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 50,
        }

        from claude_agent_sdk import ResultMessage
        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = False

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            if result is not None:
                assert "usage" in result

    @pytest.mark.asyncio
    async def test_assistant_message_with_tools(self, tmp_path):
        """AssistantMessage with ToolUseBlock, ToolResultBlock, TextBlock are processed."""
        eng = self._make_engineer(tmp_path)

        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
        )

        mock_tool_use = MagicMock(spec=ToolUseBlock)
        mock_tool_use.name = "Read"
        mock_tool_use.input = {"file_path": "/test.py"}

        mock_tool_result = MagicMock(spec=ToolResultBlock)
        mock_tool_result.is_error = False
        mock_tool_result.content = "file contents"

        mock_text = MagicMock(spec=TextBlock)
        mock_text.text = "Analyzing the file..."

        mock_assistant = MagicMock(spec=AssistantMessage)
        mock_assistant.content = [mock_tool_use, mock_tool_result, mock_text]
        del mock_assistant.usage

        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = False

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_assistant
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is not None
            assert "script_path" in result

    @pytest.mark.asyncio
    async def test_assistant_message_with_usage(self, tmp_path):
        """AssistantMessage with usage metadata updates tracking."""
        eng = self._make_engineer(tmp_path)

        from claude_agent_sdk import AssistantMessage, ResultMessage

        mock_assistant = MagicMock(spec=AssistantMessage)
        mock_assistant.content = []
        mock_assistant.usage = {"input_tokens": 500, "output_tokens": 200}

        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = False

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_assistant
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is not None
            assert eng.usage_metadata.get("input_tokens") == 500

    @pytest.mark.asyncio
    async def test_tool_result_with_result_attr(self, tmp_path):
        """ToolResultBlock with result attribute (not content) is handled."""
        eng = self._make_engineer(tmp_path)

        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            ToolResultBlock,
            ToolUseBlock,
        )

        mock_tool_use = MagicMock(spec=ToolUseBlock)
        mock_tool_use.name = "Bash"
        mock_tool_use.input = {"command": "ls"}

        mock_tool_result = MagicMock(spec=ToolResultBlock)
        mock_tool_result.is_error = True
        del mock_tool_result.content
        mock_tool_result.result = "command not found"

        mock_assistant = MagicMock(spec=AssistantMessage)
        mock_assistant.content = [mock_tool_use, mock_tool_result]
        del mock_assistant.usage

        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = False

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_assistant
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is not None

    @pytest.mark.asyncio
    async def test_tool_result_with_output_attr(self, tmp_path):
        """ToolResultBlock with output attribute (not content/result) is handled."""
        eng = self._make_engineer(tmp_path)

        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            ToolResultBlock,
            ToolUseBlock,
        )

        mock_tool_use = MagicMock(spec=ToolUseBlock)
        mock_tool_use.name = "Grep"
        mock_tool_use.input = {"pattern": "test"}

        mock_tool_result = MagicMock(spec=ToolResultBlock)
        mock_tool_result.is_error = False
        del mock_tool_result.content
        del mock_tool_result.result
        mock_tool_result.output = "grep output here"

        mock_assistant = MagicMock(spec=AssistantMessage)
        mock_assistant.content = [mock_tool_use, mock_tool_result]
        del mock_assistant.usage

        mock_result = MagicMock(spec=ResultMessage)
        mock_result.is_error = False

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield mock_assistant
            yield mock_result

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is not None

    @pytest.mark.asyncio
    async def test_no_result_message_returns_none(self, tmp_path):
        """Empty stream with no ResultMessage returns None (line 365)."""
        eng = self._make_engineer(tmp_path)

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            return
            yield

        mock_client.receive_response = mock_receive

        with patch("reverse_api.auto_engineer.ClaudeSDKClient") as mock_sdk:
            mock_sdk.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_sdk.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None


class TestOpenCodeAutoEngineerInit:
    """Test OpenCodeAutoEngineer initialization."""

    def test_init(self, tmp_path):
        """Initializes with MCP run_id."""
        with patch("reverse_api.auto_engineer.get_har_dir", return_value=tmp_path / "har"):
            with patch("reverse_api.base_engineer.get_scripts_dir", return_value=tmp_path / "scripts"):
                with patch("reverse_api.base_engineer.MessageStore"):
                    with patch("reverse_api.opencode_engineer.OpenCodeUI"):
                        eng = OpenCodeAutoEngineer(
                            run_id="test123",
                            prompt="browse and capture",
                            output_dir=str(tmp_path),
                            opencode_provider="anthropic",
                            opencode_model="claude-opus-4-6",
                        )
                        assert eng.mcp_run_id == "test123"
                        assert eng.mcp_name is None

    def test_build_auto_prompt_reuses_claude_prompt(self, tmp_path):
        """OpenCode auto prompt reuses ClaudeAutoEngineer prompt."""
        with patch("reverse_api.auto_engineer.get_har_dir", return_value=tmp_path / "har"):
            with patch("reverse_api.base_engineer.get_scripts_dir", return_value=tmp_path / "scripts"):
                with patch("reverse_api.base_engineer.MessageStore"):
                    with patch("reverse_api.opencode_engineer.OpenCodeUI"):
                        eng = OpenCodeAutoEngineer(
                            run_id="test123",
                            prompt="browse and capture",
                            output_dir=str(tmp_path),
                            opencode_provider="anthropic",
                            opencode_model="claude-opus-4-6",
                        )
                        prompt = eng._build_auto_prompt()
                        assert "browser_navigate" in prompt
                        assert "Python" in prompt


class TestOpenCodeAutoEngineerAnalyze:
    """Test OpenCodeAutoEngineer analyze_and_generate."""

    def _make_engineer(self, tmp_path):
        with patch("reverse_api.auto_engineer.get_har_dir", return_value=tmp_path / "har"):
            with patch("reverse_api.base_engineer.get_scripts_dir", return_value=tmp_path / "scripts"):
                with patch("reverse_api.base_engineer.MessageStore") as mock_ms:
                    mock_ms.return_value = MagicMock()
                    with patch("reverse_api.opencode_engineer.OpenCodeUI") as mock_ui:
                        mock_ui.return_value = MagicMock()
                        eng = OpenCodeAutoEngineer(
                            run_id="test123",
                            prompt="browse and capture",
                            output_dir=str(tmp_path),
                            opencode_provider="anthropic",
                            opencode_model="claude-opus-4-6",
                        )
                        eng.scripts_dir = tmp_path / "scripts"
                        eng.scripts_dir.mkdir(parents=True, exist_ok=True)
                        return eng

    @pytest.mark.asyncio
    async def test_health_check_401(self, tmp_path):
        """401 on health check returns None."""
        eng = self._make_engineer(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_connect_error(self, tmp_path):
        """ConnectError returns None."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_general_exception(self, tmp_path):
        """General exception returns None."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(
                side_effect=RuntimeError("unexpected")
            )
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_buffer_size_exception(self, tmp_path):
        """Buffer size exception shows specific message."""
        eng = self._make_engineer(tmp_path)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("exceeded maximum buffer size 1048576")
            )
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_http_error_non_401(self, tmp_path):
        """HTTP error with non-401 status."""
        eng = self._make_engineer(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.reason_phrase = "Internal Server Error"
        error = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(side_effect=error)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_health_check_401_with_custom_username(self, tmp_path):
        """401 with custom username shows username in output."""
        eng = self._make_engineer(tmp_path)
        eng.opencode_username = "custom_user"

        mock_response = MagicMock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_health_check_success_then_session_fail(self, tmp_path):
        """Health check succeeds but session creation raises."""
        eng = self._make_engineer(tmp_path)

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_client = AsyncMock()

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            raise Exception("unexpected get")

        mock_client.get = mock_get
        mock_client.post = AsyncMock(side_effect=Exception("session creation failed"))

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_health_check_general_exception(self, tmp_path):
        """General exception on health check shows server not responding."""
        eng = self._make_engineer(tmp_path)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_full_success_flow(self, tmp_path):
        """Full success flow with MCP registration, streaming, and result."""
        eng = self._make_engineer(tmp_path)

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.json.return_value = {"id": "sess_success"}
        mock_session.raise_for_status = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.raise_for_status = MagicMock()

        mock_prompt = MagicMock()
        mock_prompt.raise_for_status = MagicMock()

        mock_messages = MagicMock()
        mock_messages.status_code = 200
        mock_messages.json.return_value = [
            {
                "info": {"role": "assistant", "providerID": "anthropic", "modelID": "claude-opus-4-6"},
                "parts": [{"type": "text", "text": "API client"}],
            }
        ]

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            if "/message" in path:
                return mock_messages
            return MagicMock()

        post_calls = [0]

        async def mock_post(path, **kwargs):
            post_calls[0] += 1
            if path == "/session":
                return mock_session
            if path == "/mcp":
                return mock_mcp
            return mock_prompt

        mock_stream_resp = AsyncMock()

        async def mock_aiter_lines():
            yield 'data: {"type":"session.idle","properties":{"sessionID":"sess_success"}}'

        mock_stream_resp.aiter_lines = mock_aiter_lines
        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.delete = AsyncMock()

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is not None
            assert "script_path" in result
            assert result["session_id"] == "sess_success"

    @pytest.mark.asyncio
    async def test_http_401_outer_with_username(self, tmp_path):
        """Outer 401 HTTPStatusError with custom username shows username."""
        eng = self._make_engineer(tmp_path)
        eng.opencode_username = "custom_user"

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.json.return_value = {"id": "sess_auth"}
        mock_session.raise_for_status = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.raise_for_status = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 401

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            raise httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)

        async def mock_post(path, **kwargs):
            if path == "/session":
                return mock_session
            if path == "/mcp":
                return mock_mcp
            raise httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)

        mock_stream_resp = AsyncMock()

        async def mock_aiter_lines():
            yield 'data: {"type":"session.idle","properties":{"sessionID":"sess_auth"}}'

        mock_stream_resp.aiter_lines = mock_aiter_lines
        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.delete = AsyncMock()

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_event_timeout(self, tmp_path):
        """Event stream timeout sets last error and returns None."""
        eng = self._make_engineer(tmp_path)

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.json.return_value = {"id": "sess_timeout"}
        mock_session.raise_for_status = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.raise_for_status = MagicMock()

        mock_prompt = MagicMock()
        mock_prompt.raise_for_status = MagicMock()

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            return MagicMock(status_code=200, json=MagicMock(return_value=[]))

        async def mock_post(path, **kwargs):
            if path == "/session":
                return mock_session
            if path == "/mcp":
                return mock_mcp
            return mock_prompt

        mock_stream_resp = AsyncMock()

        async def mock_aiter_lines():
            # Never yield session.idle - simulates hanging
            await asyncio.sleep(100)
            yield "never reached"

        mock_stream_resp.aiter_lines = mock_aiter_lines
        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.delete = AsyncMock()

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            # Patch asyncio.wait_for to raise TimeoutError immediately
            async def mock_wait_for(coro, timeout=None):
                coro.close()  # Clean up the coroutine
                raise TimeoutError()

            with patch("reverse_api.auto_engineer.asyncio.wait_for", side_effect=mock_wait_for):
                result = await eng.analyze_and_generate()
                assert result is None

    @pytest.mark.asyncio
    async def test_mcp_deregistration_exception(self, tmp_path):
        """MCP deregistration exception is silently ignored."""
        eng = self._make_engineer(tmp_path)

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.json.return_value = {"id": "sess_dereg"}
        mock_session.raise_for_status = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.raise_for_status = MagicMock()

        mock_prompt = MagicMock()
        mock_prompt.raise_for_status = MagicMock()

        mock_messages = MagicMock()
        mock_messages.status_code = 200
        mock_messages.json.return_value = [
            {"info": {"role": "assistant", "providerID": "anthropic", "modelID": "claude-sonnet-4-6"}, "parts": []}
        ]

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            if "/message" in path:
                return mock_messages
            return MagicMock()

        async def mock_post(path, **kwargs):
            if path == "/session":
                return mock_session
            if path == "/mcp":
                return mock_mcp
            return mock_prompt

        mock_stream_resp = AsyncMock()

        async def mock_aiter_lines():
            yield 'data: {"type":"session.idle","properties":{"sessionID":"sess_dereg"}}'

        mock_stream_resp.aiter_lines = mock_aiter_lines
        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.delete = AsyncMock(side_effect=Exception("deregister failed"))

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            # Should succeed despite deregistration failure
            assert result is not None
            assert "script_path" in result

    @pytest.mark.asyncio
    async def test_message_fetch_exception(self, tmp_path):
        """Message fetch exception is silently handled."""
        eng = self._make_engineer(tmp_path)

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.json.return_value = {"id": "sess_msgfail"}
        mock_session.raise_for_status = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.raise_for_status = MagicMock()

        mock_prompt = MagicMock()
        mock_prompt.raise_for_status = MagicMock()

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            return MagicMock()

        async def mock_post(path, **kwargs):
            if path == "/session":
                return mock_session
            if path == "/mcp":
                return mock_mcp
            return mock_prompt

        mock_stream_resp = AsyncMock()

        async def mock_aiter_lines():
            yield 'data: {"type":"session.idle","properties":{"sessionID":"sess_msgfail"}}'

        mock_stream_resp.aiter_lines = mock_aiter_lines
        mock_stream_cm = AsyncMock()
        mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_resp)
        mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.stream = MagicMock(return_value=mock_stream_cm)
        mock_client.delete = AsyncMock()

        # Patch the second httpx.AsyncClient (for message fetch) to fail
        original_async_client = httpx.AsyncClient

        call_count = [0]

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    # First call - the main client
                    cm = MagicMock()
                    cm.__aenter__ = AsyncMock(return_value=mock_client)
                    cm.__aexit__ = AsyncMock(return_value=False)
                    return cm
                else:
                    # Second call - message fetch client
                    cm = MagicMock()
                    cm.__aenter__ = AsyncMock(side_effect=Exception("fetch failed"))
                    cm.__aexit__ = AsyncMock(return_value=False)
                    return cm

            mock_async.side_effect = side_effect

            result = await eng.analyze_and_generate()
            # Should still succeed despite message fetch failure
            assert result is not None
            assert "script_path" in result

    @pytest.mark.asyncio
    async def test_finally_cleanup_with_mcp_name(self, tmp_path):
        """Finally block cleans up MCP server even on exception."""
        eng = self._make_engineer(tmp_path)
        eng.mcp_name = "playwright-test_sess"

        # Trigger exception to go through finally block
        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(
                side_effect=RuntimeError("test error")
            )
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None

    @pytest.mark.asyncio
    async def test_health_check_non_401_reraise(self, tmp_path):
        """Non-401 HTTPStatusError in health check is re-raised (line 414)."""
        eng = self._make_engineer(tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        error = httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            # Non-401 is re-raised and caught by outer HTTPStatusError handler
            assert result is None

    @pytest.mark.asyncio
    async def test_mcp_registration_failure(self, tmp_path):
        """MCP server registration failure returns None."""
        eng = self._make_engineer(tmp_path)

        mock_health = MagicMock()
        mock_health.json.return_value = {"status": "ok"}
        mock_health.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.json.return_value = {"id": "sess_123"}
        mock_session.raise_for_status = MagicMock()

        async def mock_get(path, **kwargs):
            if path == "/global/health":
                return mock_health
            raise Exception("unexpected get")

        async def mock_post(path, **kwargs):
            if path == "/session":
                return mock_session
            if path == "/mcp":
                raise Exception("MCP registration failed")
            raise Exception(f"unexpected post to {path}")

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.post = mock_post

        with patch("reverse_api.auto_engineer.httpx.AsyncClient") as mock_async:
            mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await eng.analyze_and_generate()
            assert result is None
