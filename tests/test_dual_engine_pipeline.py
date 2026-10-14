"""
Automated Verification Suite for JARVIS Dual-Engine OpenRouter Architecture.

Verifies:
1. System 1: Microsoft-Decision-1 Engine via OpenRouter Decisions API (high-speed intent triage & calibrated probabilities)
2. System 2: OpenRouter Frontier Model (nvidia/nemotron-3-super-120b-a12b:free for general intelligence)
3. Markdown stripping: Zero punctuation/formatting read aloud by Edge-TTS
4. WhatsApp Tool: Ban-safe desktop protocol and contact resolution
5. YouTube Tool: Search and direct video URL resolver
6. Autonomous Planner: Compound plan decomposition and execution
"""

import os
import pytest
import asyncio
from jarvis.core.decision_client import decision_client
from jarvis.core.llm_router import LLMRouter
from jarvis.core.conversational_engine import strip_markdown_for_tts
from jarvis.tools.whatsapp_tool import resolve_phone, save_contact, get_contacts
from jarvis.tools.youtube_tool import play_youtube_video
from jarvis.core.autonomous_planner import plan_executor

llm = LLMRouter()


def test_system_1_decision_client():
    """Verify System 1 (Microsoft-Decision-1) classifies intents accurately via OpenRouter Decisions API."""
    async def _run():
        res_app = await decision_client.predict_intent("open google chrome", known_apps=["google chrome", "antigravity"])
        assert res_app["action"] == "open_app"
        assert "chrome" in res_app.get("app", "").lower()
        assert res_app["confidence"] > 0.5

        res_wa = await decision_client.predict_intent("text Tony on whatsapp that the meeting is starting")
        assert res_wa["action"] == "send_whatsapp"
        assert res_wa.get("contact") is not None
        assert "tony" in res_wa["contact"].lower()

        res_chat = await decision_client.predict_intent("Why is the sky blue during the day?")
        assert res_chat["action"] == "casual_chat"

        res_weather = await decision_client.predict_intent("How is the weather outside right now?")
        assert res_weather["action"] == "get_weather"

        res_time = await decision_client.predict_intent("What time is it right now?")
        assert res_time["action"] == "get_time"

    asyncio.run(_run())


def test_system_1_sync_interim_fast_triage():
    """Verify synchronous fast triage for 0ms speech pre-warming."""
    interim = decision_client.predict_action("open notepad", known_apps=["notepad", "spotify"])
    assert interim["action"] == "open_app"
    assert interim["app"] == "notepad"


def test_system_2_openrouter_generation():
    """Verify System 2 produces high-intelligence response via OpenRouter."""
    async def _run():
        res = await llm.generate_with_history(
            messages=[{"role": "user", "content": "In one short sentence, what is quantum computing?"}],
            system="You are JARVIS. Answer in one concise sentence without markdown.",
            max_tokens=100
        )
        assert len(res) > 10
        clean = strip_markdown_for_tts(res)
        assert "*" not in clean
        assert "#" not in clean

    asyncio.run(_run())



def test_markdown_stripping_for_tts():
    """Verify markdown stripping produces pristine natural sentences for TTS."""
    sample = "**Greetings** *Tony*, here is `#1` code `sys.exit()` with [link](http://test)."
    clean = strip_markdown_for_tts(sample)
    assert "*" not in clean
    assert "#" not in clean
    assert "`" not in clean
    assert "Greetings Tony" in clean


def test_whatsapp_tool_contacts():
    """Verify WhatsApp contact mapping and resolver."""
    save_contact("tony", "+1234567890")
    contacts = get_contacts()
    assert "tony" in contacts
    phone = resolve_phone("tony")
    assert phone == "+1234567890"


def test_youtube_tool_resolution():
    """Verify YouTube query parsing and URL generation."""
    res_direct = play_youtube_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert res_direct["success"] is True
    assert "dQw4w9WgXcQ" in res_direct["url"]


def test_autonomous_planner_decomposition():
    """Verify compound commands and plans are decomposed into structured actions."""
    compound_1 = "open whatsapp and text Tony I will be late"
    assert plan_executor.is_compound_request(compound_1) is True
    steps_1 = plan_executor.decompose(compound_1)
    assert len(steps_1) >= 1
    assert steps_1[0]["action"] == "send_whatsapp"
    assert steps_1[0]["contact"].lower() == "tony"
    assert "late" in steps_1[0]["message"].lower()

    # Open and type compound
    compound_2 = "open notepad and type meeting notes at 4pm"
    assert plan_executor.is_compound_request(compound_2) is True
    steps_2 = plan_executor.decompose(compound_2)
    assert len(steps_2) == 2
    assert steps_2[0]["action"] == "open_app"
    assert steps_2[0]["app"] == "notepad"
    assert steps_2[1]["action"] == "type_text"
    assert "meeting notes" in steps_2[1]["text"]


@pytest.mark.asyncio
async def test_system_1_omni_os_actions():
    """Verify System 1 decision engine handles all omni-OS laptop capabilities."""
    # 1. Open and Type
    res_ot = await decision_client.predict_intent(
        "open notepad and type JARVIS is online",
        known_apps=["notepad"]
    )
    assert res_ot["action"] in ["open_and_type", "open_app"]
    assert res_ot.get("app") == "notepad"
    assert "JARVIS is online" in (res_ot.get("text_to_type") or "")

    # 2. Window Control
    res_win = await decision_client.predict_intent("minimize window")
    assert res_win["action"] == "window_control"
    assert res_win.get("window_action") == "minimize"

    # 3. GUI Shortcut
    res_key = await decision_client.predict_intent("save this file")
    assert res_key["action"] == "gui_shortcut"
    assert res_key.get("shortcut") == "save"

    # 4. Battery
    res_bat = await decision_client.predict_intent("check battery level")
    assert res_bat["action"] == "get_battery"

    # 5. Process Control
    res_kill = await decision_client.predict_intent("kill chrome process")
    assert res_kill["action"] == "process_control"
    assert "chrome" in (res_kill.get("process") or "").lower()


@pytest.mark.asyncio
async def test_app_specific_mcp_client_tools():
    """Verify all 11 new app-specific MCP tools are registered and callable in MCPClient."""
    from jarvis.mcp_client import get_mcp_client
    mcp_cli = get_mcp_client()
    tools = mcp_cli.available_tools
    required_tools = [
        "antigravity_prompt",
        "obs_start_recording",
        "obs_stop_recording",
        "obs_status",
        "urban_vpn_connect",
        "urban_vpn_disconnect",
        "capcut_open_editor",
        "capcut_export_project",
        "workflow_vpn_then_capcut",
        "open_terminal_run",
        "inspect_app_ui",
    ]
    for rt in required_tools:
        assert rt in tools, f"Missing MCP tool: {rt}"

    # Test status checks and dry inspects
    obs_res = await mcp_cli.call_tool("obs_status")
    assert isinstance(obs_res, str)
    assert "OBS Studio" in obs_res

    ui_res = await mcp_cli.call_tool("inspect_app_ui", app_name="nonexistent_test_app")
    assert isinstance(ui_res, str)
    assert "nonexistent_test_app" in ui_res


@pytest.mark.asyncio
async def test_app_specific_intent_and_planner():
    """Verify System 1 and Autonomous Planner handle Antigravity, OBS, VPN, and CapCut."""
    # 1. Antigravity prompt
    res_ag = await decision_client.predict_intent("open chat in antigravity and prompt build a calculator app")
    assert res_ag["action"] == "antigravity_prompt"
    assert "calculator" in (res_ag.get("prompt") or "").lower()

    # 2. OBS record
    res_obs = await decision_client.predict_intent("open obs studio and start recording")
    assert res_obs["action"] == "obs_control"
    assert res_obs.get("obs_action") == "start"

    # 3. VPN connect
    res_vpn = await decision_client.predict_intent("connect vpn to United States")
    assert res_vpn["action"] == "vpn_control"
    assert res_vpn.get("vpn_action") == "connect"

    # 4. Multi-app compound plan
    compound = "first open my vpn connect to United States then open capcut"
    assert plan_executor.is_compound_request(compound) is True
    steps = plan_executor.decompose(compound)
    assert len(steps) == 2
    assert steps[0]["action"] == "vpn_connect"
    assert steps[1]["action"] == "open_capcut"



