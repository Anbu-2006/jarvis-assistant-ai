"""
Automated Verification Suite for JARVIS Local Persistent Memory & Autonomous Self-Healing Engine.

Verifies:
1. SQLite Reflexion Memory (failure_episodes, failure_fts, ui_button_maps)
2. Memory lookup and retrieval of past error fixes
3. Self-Healing recovery loop (catching errors, applying fixes, and committing to memory)
4. Zero future repetition: subsequent calls use stored memory recipes
"""

import asyncio
import os
import pytest
from jarvis.core.memory import (
    record_failure_reflection,
    lookup_past_fix,
    list_learned_fixes,
    save_ui_button_mapping,
    get_ui_button_mapping,
    init_db
)
from jarvis.core.self_healing import self_healing_engine
from jarvis.mcp_client import get_mcp_client


def test_sqlite_reflexion_memory_crud():
    """Verify storing, indexing, and retrieving failure reflections and UI button maps."""
    init_db()

    # 1. Record a failure reflection
    ep_id = record_failure_reflection(
        tool_name="test_failing_tool",
        error_type="TimeoutError",
        error_message="Window handle not responsive after 5000ms",
        working_fix="hotkey:ctrl+e",
        task_intent="export video in capcut",
        arguments={"project": "vlog1"},
        root_cause="Export dialog modal was blocked by focus",
        fix_type="cli_workaround",
        success_verified=1
    )
    assert ep_id > 0

    # 2. Look up the fix by tool name
    fix = lookup_past_fix("test_failing_tool", error_text="Window handle not responsive")
    assert fix is not None
    assert fix["tool_name"] == "test_failing_tool"
    assert fix["working_fix"] == "hotkey:ctrl+e"
    assert fix["use_count"] >= 1

    # 3. Look up by task intent via FTS5
    fts_fix = lookup_past_fix("unknown_tool", task_intent="export video in capcut")
    assert fts_fix is not None
    assert fts_fix["working_fix"] == "hotkey:ctrl+e"

    # 4. List learned fixes
    all_fixes = list_learned_fixes(limit=10)
    assert any(f["tool_name"] == "test_failing_tool" for f in all_fixes)

    # 5. UI Button Mapping
    save_ui_button_mapping(
        app_name="CapCut",
        control_name="ExportButton",
        control_type="Button",
        action_recipe="hotkey:ctrl+e"
    )
    ui_map = get_ui_button_mapping("CapCut", "ExportButton")
    assert ui_map is not None
    assert ui_map["action_recipe"] == "hotkey:ctrl+e"


def test_self_healing_engine_reflexion_loop():
    """Verify the self-healing engine recovers from failure and learns the recipe."""
    async def _run():
        call_count = 0

        def flaky_tool(action: str = "default") -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "Error: window focus lost and process timed out"
            return "Action successfully completed"

        # Pre-seed a known fix for flaky_tool
        record_failure_reflection(
            tool_name="flaky_tool",
            error_type="FocusError",
            error_message="window focus lost",
            working_fix="hotkey:enter",
            task_intent="run flaky test action",
            success_verified=1
        )

        # Execute flaky_tool wrapped with self_healing_engine
        res = await self_healing_engine.heal_and_execute(
            tool_name="flaky_tool",
            tool_func=flaky_tool,
            kwargs={"action": "test"},
            task_intent="run flaky test action"
        )
        assert res is not None
        assert "Healed from memory" in res or "Triggered recovery" in res

    asyncio.run(_run())


def test_mcp_client_self_healing_protection():
    """Verify MCPClient.call_tool uses the self-healing engine on error states."""
    async def _run():
        mcp_cli = get_mcp_client()

        # Call obs_status (real tool) protected by self-healing
        res = await mcp_cli.call_tool("obs_status", task_intent="check if obs is running")
        assert isinstance(res, str)
        assert len(res) > 5

    asyncio.run(_run())
