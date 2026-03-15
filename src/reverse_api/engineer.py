"""Reverse engineering module with SDK dispatch."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    PermissionResultAllow,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    query,
)

from .base_engineer import BaseEngineer

# Suppress claude_agent_sdk logs
logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
logging.getLogger("claude_agent_sdk._internal.transport.subprocess_cli").setLevel(logging.WARNING)


class ClaudeEngineer(BaseEngineer):
    """Uses Claude Agent SDK to analyze HAR files and generate Python API scripts."""

    async def _handle_tool_permission(self, tool_name: str, input_data: dict[str, Any], context: ToolPermissionContext) -> PermissionResultAllow:
        """Handle tool permission requests, with interactive UI for AskUserQuestion."""
        if tool_name == "AskUserQuestion":
            questions = input_data.get("questions", [])
            answers = await self._ask_user_interactive(questions)
            return PermissionResultAllow(
                updated_input={"questions": questions, "answers": answers},
            )

        # Auto-approve all other tools
        return PermissionResultAllow(updated_input=input_data)

    async def analyze_and_generate(self) -> dict[str, Any] | None:
        """Run the reverse engineering analysis with Claude."""
        self.ui.header(self.run_id, self.prompt, self.model, self.sdk, mode="engineer")
        self.ui.start_analysis()
        self.message_store.save_prompt(self._build_analysis_prompt())

        # Required: dummy hook keeps the stream open for can_use_tool
        # See: https://platform.claude.com/docs/en/agent-sdk/user-input
        async def _dummy_hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
            return {"continue_": True}

        async def _prompt_stream():
            yield {
                "type": "user",
                "message": {"role": "user", "content": self._build_analysis_prompt()},
            }

        options = ClaudeAgentOptions(
            can_use_tool=self._handle_tool_permission,
            hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[_dummy_hook])]},
            cwd=str(self.scripts_dir.parent.parent),  # Project root
            model=self.model,
            env={"CLAUDECODE": "", "CLAUDE_CODE_STREAM_CLOSE_TIMEOUT": "1800000"},
        )

        final_result: dict[str, Any] | None = None

        try:
            # Do not break/return inside this loop — the SDK requires the
            # async generator to be fully consumed to avoid cancel-scope errors.
            async for message in query(prompt=_prompt_stream(), options=options):
                # Check for usage metadata in message if applicable
                if hasattr(message, "usage") and isinstance(message.usage, dict):
                    self.usage_metadata.update(message.usage)

                if isinstance(message, AssistantMessage):
                    last_tool_name = None
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            last_tool_name = block.name
                            self.ui.tool_start(block.name, block.input)
                            self.message_store.save_tool_start(block.name, block.input)
                        elif isinstance(block, ToolResultBlock):
                            is_error = block.is_error if block.is_error else False

                            # Extract output from ToolResultBlock
                            output = None
                            if hasattr(block, "content"):
                                output = block.content
                            elif hasattr(block, "result"):
                                output = block.result
                            elif hasattr(block, "output"):
                                output = block.output

                            tool_name = last_tool_name or "Tool"
                            self.ui.tool_result(tool_name, is_error, output)
                            self.message_store.save_tool_result(tool_name, is_error, str(output) if output else None)
                        elif isinstance(block, TextBlock):
                            self.ui.thinking(block.text)
                            self.message_store.save_thinking(block.text)

                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        self.ui.error(message.result or "Unknown error")
                        self.message_store.save_error(message.result or "Unknown error")
                    else:
                        script_path = str(self.scripts_dir / self._get_client_filename())
                        local_path = str(self.local_scripts_dir / self._get_client_filename()) if self.local_scripts_dir else None
                        self.ui.success(script_path, local_path)

                        # Calculate estimated cost if we have usage data
                        if self.usage_metadata:
                            input_tokens = self.usage_metadata.get("input_tokens", 0)
                            output_tokens = self.usage_metadata.get("output_tokens", 0)
                            cache_creation_tokens = self.usage_metadata.get("cache_creation_input_tokens", 0)
                            cache_read_tokens = self.usage_metadata.get("cache_read_input_tokens", 0)

                            from .pricing import calculate_cost

                            cost = calculate_cost(
                                model_id=self.model,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                cache_creation_tokens=cache_creation_tokens,
                                cache_read_tokens=cache_read_tokens,
                            )
                            self.usage_metadata["estimated_cost_usd"] = cost

                            self.ui.console.print("  [dim]Usage:[/dim]")
                            if input_tokens > 0:
                                self.ui.console.print(f"  [dim]  input: {input_tokens:,} tokens[/dim]")
                            if cache_creation_tokens > 0:
                                self.ui.console.print(f"  [dim]  cache creation: {cache_creation_tokens:,} tokens[/dim]")
                            if cache_read_tokens > 0:
                                self.ui.console.print(f"  [dim]  cache read: {cache_read_tokens:,} tokens[/dim]")
                            if output_tokens > 0:
                                self.ui.console.print(f"  [dim]  output: {output_tokens:,} tokens[/dim]")
                            self.ui.console.print(f"  [dim]  total cost: ${cost:.4f}[/dim]")

                        final_result = {
                            "script_path": script_path,
                            "usage": self.usage_metadata,
                        }
                        self.message_store.save_result(final_result)

        except Exception as e:
            self.ui.error(str(e))
            self.message_store.save_error(str(e))
            self.ui.console.print("\n[dim]Make sure Claude Code CLI is installed: npm install -g @anthropic-ai/claude-code[/dim]")
            return None

        return final_result


# Keep old class name for backwards compatibility
APIReverseEngineer = ClaudeEngineer


def run_reverse_engineering(
    run_id: str,
    har_path: Path,
    prompt: str,
    model: str | None = None,
    additional_instructions: str | None = None,
    output_dir: str | None = None,
    verbose: bool = True,
    sdk: str = "claude",
    opencode_provider: str | None = None,
    opencode_model: str | None = None,
    copilot_model: str | None = None,
    enable_sync: bool = False,
    is_fresh: bool = False,
    output_language: str = "python",
    output_mode: str = "client",
) -> dict[str, Any] | None:
    """Run reverse engineering with the specified SDK.

    Args:
        sdk: "claude", "opencode", or "copilot" - determines which SDK to use
        opencode_provider: Provider ID for OpenCode (e.g., "anthropic")
        opencode_model: Model ID for OpenCode (e.g., "claude-sonnet-4-6")
        copilot_model: Model ID for Copilot (e.g., "gpt-5")
        enable_sync: Enable real-time file syncing during engineering
        is_fresh: Whether to start fresh (ignore previous scripts)
        output_language: Target language - "python", "javascript", or "typescript"
        output_mode: Output mode - "client" for API client code, "docs" for OpenAPI specification
    """
    if sdk == "opencode":
        from .opencode_engineer import OpenCodeEngineer

        engineer = OpenCodeEngineer(
            run_id=run_id,
            har_path=har_path,
            prompt=prompt,
            model=model,
            additional_instructions=additional_instructions,
            output_dir=output_dir,
            verbose=verbose,
            opencode_provider=opencode_provider,
            opencode_model=opencode_model,
            enable_sync=enable_sync,
            sdk=sdk,
            is_fresh=is_fresh,
            output_language=output_language,
            output_mode=output_mode,
        )
    elif sdk == "copilot":
        from .copilot_engineer import CopilotEngineer

        engineer = CopilotEngineer(
            run_id=run_id,
            har_path=har_path,
            prompt=prompt,
            model=model,
            additional_instructions=additional_instructions,
            output_dir=output_dir,
            verbose=verbose,
            enable_sync=enable_sync,
            sdk=sdk,
            is_fresh=is_fresh,
            output_language=output_language,
            output_mode=output_mode,
            copilot_model=copilot_model,
        )
    else:
        engineer = ClaudeEngineer(
            run_id=run_id,
            har_path=har_path,
            prompt=prompt,
            model=model,
            additional_instructions=additional_instructions,
            output_dir=output_dir,
            verbose=verbose,
            enable_sync=enable_sync,
            sdk=sdk,
            is_fresh=is_fresh,
            output_language=output_language,
            output_mode=output_mode,
        )

    # Start sync before analysis
    engineer.start_sync()

    try:
        result = asyncio.run(engineer.analyze_and_generate())
    finally:
        # Always stop sync when done
        engineer.stop_sync()

    return result
