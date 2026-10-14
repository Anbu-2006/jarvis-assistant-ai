"""
JARVIS Autonomous Multi-Step Planner & Execution Engine.

Decomposes complex, multi-action goals and plans into structured sub-actions
and executes them sequentially using JARVIS's toolset.
"""

import re
import asyncio
import logging
from typing import List, Dict, Any, Optional

import webbrowser

from jarvis.app_discovery import launch_application
from jarvis.tools.whatsapp_tool import send_whatsapp_message
from jarvis.tools.youtube_tool import play_youtube_video
from jarvis.core.universal_os_operator import os_operator

log = logging.getLogger("jarvis.planner")


class AutonomousPlanExecutor:
    """Executes multi-step user plans and compound commands."""

    PLAN_SPLITTERS = [
        r"\s+and\s+then\s+",
        r"\s+then\s+",
        r"\s+after\s+that\s+",
        r"\s+first\s+",
        r"\s+second\s+",
        r"\s+finally\s+",
        r";\s*",
        r"\n+",
    ]

    def is_compound_request(self, text: str) -> bool:
        """Detect if the user prompt is a multi-step plan or compound action."""
        text_lower = text.lower().strip()
        
        # Explicit plan keywords
        if any(kw in text_lower for kw in ["plan:", "steps:", "first ", "then ", "and then", "after that"]):
            return True
            
        # Check for multiple action verbs joined by "and"
        # e.g., "open chrome and play interstellar on youtube"
        # e.g., "open whatsapp and text tony hello"
        action_verbs = ["open", "launch", "search", "play", "text", "message", "write", "type", "close", "minimize", "maximize", "find", "record", "prompt", "connect"]
        found_verbs = [v for v in action_verbs if re.search(rf"\b{v}\b", text_lower)]
        if len(found_verbs) >= 2 and (" and " in text_lower or "," in text_lower):
            # Special case: "open whatsapp and text..." is a compound action
            return True
            
        return False

    def decompose(self, text: str) -> List[Dict[str, Any]]:
        """Parse raw user input into an ordered list of executable step intents."""
        steps = []
        raw = text.strip()

        has_multi_transitions = (
            " then " in raw.lower()
            or " and then " in raw.lower()
            or ";" in raw
            or raw.lower().startswith("first ")
            or bool(re.search(r"^\d+\.", raw, re.MULTILINE))
        )

        if not has_multi_transitions:
            # Check for open and type compound pattern: "open <app> and type/write <text>"
            ot_match = re.search(
                r"\b(?:open|launch)\s+([a-zA-Z0-9_\-\s]+?)\s+(?:and|,)?\s*(?:type|write|enter)\s+(.+)",
                raw,
                re.IGNORECASE
            )
            if ot_match:
                app_target = ot_match.group(1).strip()
                content = ot_match.group(2).strip()
                return [
                    {
                        "step": 1,
                        "action": "open_app",
                        "app": app_target,
                        "description": f"Open {app_target.title()}"
                    },
                    {
                        "step": 2,
                        "action": "type_text",
                        "app": app_target,
                        "text": content,
                        "description": f"Type '{content}' in {app_target.title()}"
                    }
                ]

            # Check for single-intent WhatsApp compound pattern: "open whatsapp and text/message <contact> <message>"
            wa_match = re.search(
                r"(?:open|launch)?\s*whatsapp\s*(?:and|,)?\s*(?:text|message|send\s+(?:a\s+)?message\s+to)\s+([a-zA-Z0-9_\s]+?)\s+(?:saying|that|with)?\s*(.+)",
                raw,
                re.IGNORECASE
            )
            if wa_match:
                contact = wa_match.group(1).strip()
                msg = wa_match.group(2).strip()
                # Clean filler words
                contact = re.sub(r"^(to|for)\s+", "", contact, flags=re.I).strip()
                msg = re.sub(r"^(saying|that|with|message)\s+", "", msg, flags=re.I).strip()
                return [
                    {
                        "step": 1,
                        "action": "send_whatsapp",
                        "contact": contact,
                        "message": msg,
                        "description": f"Send WhatsApp message to {contact}"
                    }
                ]

            # Check for single-intent YouTube compound pattern: "open youtube and play <query>" or "open chrome and play <query> on youtube"
            yt_match = re.search(
                r"(?:open|search|play)?\s*(?:chrome\s+and\s+)?(?:youtube\s+and\s+)?play\s+(.+?)(?:\s+on\s+youtube)?$",
                raw,
                re.IGNORECASE
            )
            if yt_match and ("youtube" in raw.lower() or "play " in raw.lower()):
                yt_query = yt_match.group(1).strip()
                yt_query = re.sub(r"\s+on\s+youtube$", "", yt_query, flags=re.I).strip()
                return [
                    {
                        "step": 1,
                        "action": "play_youtube",
                        "query": yt_query,
                        "description": f"Play '{yt_query}' on YouTube"
                    }
                ]

        # General step splitter
        # Split by numbered lists ("1.", "2.") or transition words / actionable conjunctions
        parts = []
        if re.search(r"^\d+\.\s+", raw, re.MULTILINE):
            parts = [p.strip() for p in re.split(r"\d+\.\s+", raw) if p.strip()]
        else:
            # Split by "then", "and then", semicolons, and "and" followed by an action verb
            split_regex = r"(?:\s+and\s+then\s+|\s+then\s+|\s+after\s+that\s+|;\s*|\s+and\s+(?=(?:open|launch|search|play|text|message)\b))"
            candidate_parts = re.split(split_regex, raw, flags=re.IGNORECASE)
            for cp in candidate_parts:
                cp_clean = cp.strip()
                if cp_clean.lower().startswith("first "):
                    cp_clean = cp_clean[6:].strip()
                if cp_clean:
                    parts.append(cp_clean)

        for i, part in enumerate(parts, 1):
            p_lower = part.lower()
            if "whatsapp" in p_lower and any(w in p_lower for w in ["text", "message", "send"]):
                sub_wa = re.search(r"(?:text|message|send\s+to)\s+([a-zA-Z0-9_\s]+?)\s+(?:saying|that)?\s*(.+)", part, re.I)
                if sub_wa:
                    steps.append({
                        "step": i,
                        "action": "send_whatsapp",
                        "contact": sub_wa.group(1).strip(),
                        "message": sub_wa.group(2).strip(),
                        "description": f"Text {sub_wa.group(1).strip()} on WhatsApp"
                    })
                else:
                    steps.append({
                        "step": i,
                        "action": "open_app",
                        "app": "whatsapp",
                        "description": "Open WhatsApp"
                    })
            elif "youtube" in p_lower and ("play" in p_lower or "watch" in p_lower):
                q = re.sub(r".*?(?:play|watch)\s+", "", part, flags=re.I)
                q = re.sub(r"\s+on\s+youtube.*", "", q, flags=re.I).strip()
                steps.append({
                    "step": i,
                    "action": "play_youtube",
                    "query": q,
                    "description": f"Play '{q}' on YouTube"
                })
            elif p_lower.startswith("play "):
                q = part[5:].strip()
                steps.append({
                    "step": i,
                    "action": "play_youtube",
                    "query": q,
                    "description": f"Play '{q}' on YouTube"
                })
            elif p_lower.startswith("search ") or "search for " in p_lower or "google " in p_lower:
                q = re.sub(r"^(?:search\s+(?:for\s+)?|google\s+)", "", part, flags=re.I).strip()
                steps.append({
                    "step": i,
                    "action": "search_web",
                    "query": q,
                    "description": f"Search the web for '{q}'"
                })
            # Antigravity prompt
            elif "antigravity" in p_lower and any(w in p_lower for w in ["chat", "prompt", "type", "ask", "tell"]):
                p_text = re.sub(r".*?(?:chat|prompt|type|say|tell|ask)\s+", "", part, flags=re.I).strip()
                steps.append({
                    "step": i,
                    "action": "antigravity_prompt",
                    "prompt": p_text,
                    "description": f"Prompt Antigravity: '{p_text}'"
                })
            # OBS Studio record
            elif "obs" in p_lower and any(w in p_lower for w in ["record", "recording", "start"]):
                steps.append({
                    "step": i,
                    "action": "obs_record",
                    "description": "Start OBS recording"
                })
            # VPN connect
            elif "vpn" in p_lower and any(w in p_lower for w in ["connect", "open", "selected"]):
                c_match = re.search(r"\b(?:to|in)\s+([a-zA-Z\s]+)", part, re.I)
                country = c_match.group(1).strip() if c_match else "United States"
                steps.append({
                    "step": i,
                    "action": "vpn_connect",
                    "country": country,
                    "description": f"Connect VPN to {country}"
                })
            # Capcut open
            elif "capcut" in p_lower:
                steps.append({
                    "step": i,
                    "action": "open_capcut",
                    "description": "Open CapCut Video Editor"
                })
            # Terminal
            elif "terminal" in p_lower or "command prompt" in p_lower:
                steps.append({
                    "step": i,
                    "action": "open_terminal",
                    "description": "Open Windows Terminal"
                })
            elif p_lower.startswith("open ") or p_lower.startswith("launch "):
                app_target = re.sub(r"^(?:open|launch)\s+", "", part, flags=re.I).strip()
                steps.append({
                    "step": i,
                    "action": "open_app",
                    "app": app_target,
                    "description": f"Open {app_target.title()}"
                })
            else:
                # General action
                steps.append({
                    "step": i,
                    "action": "general",
                    "raw": part,
                    "description": part
                })

        return steps

    async def execute_plan(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a decomposed plan step-by-step."""
        results = []
        executed_summaries = []

        for step in steps:
            act = step.get("action")
            desc = step.get("description", "")
            log.info(f"Executing plan step {step.get('step')}: {desc}")

            if act == "send_whatsapp":
                res = send_whatsapp_message(
                    contact=step.get("contact", ""),
                    message=step.get("message", ""),
                    auto_press_enter=True
                )
                results.append(res)
                executed_summaries.append(f"Messaged {step.get('contact')} on WhatsApp")

            elif act == "play_youtube":
                res = play_youtube_video(step.get("query", ""))
                results.append(res)
                executed_summaries.append(f"Playing '{step.get('query')}' on YouTube")

            elif act == "search_web":
                url = f"https://www.google.com/search?q={step.get('query', '')}"
                webbrowser.open(url)
                results.append({"success": True, "url": url})
                executed_summaries.append(f"Searched for '{step.get('query')}'")

            elif act == "open_app":
                app_name = step.get("app", "")
                res = launch_application(app_name)
                results.append(res)
                executed_summaries.append(f"Opened {app_name.title()}")

            elif act == "type_text":
                app_target = step.get("app")
                if app_target:
                    os_operator.focus_window(app_target)
                    await asyncio.sleep(0.3)
                txt = step.get("text", "")
                os_operator.type_text(txt)
                results.append({"success": True, "action": "type_text", "length": len(txt)})
                executed_summaries.append(f"Typed '{txt[:25]}...'")

            elif act == "antigravity_prompt":
                from jarvis.mcp_client import get_mcp_client
                mcp_cli = get_mcp_client()
                p = step.get("prompt", "")
                res = await mcp_cli.call_tool("antigravity_prompt", task_intent=desc, prompt=p, auto_submit=True)
                results.append(res)
                executed_summaries.append(f"Prompted Antigravity: '{p[:25]}...'")

            elif act == "obs_record":
                from jarvis.mcp_client import get_mcp_client
                mcp_cli = get_mcp_client()
                res = await mcp_cli.call_tool("obs_start_recording", task_intent=desc)
                results.append(res)
                executed_summaries.append("Started OBS Studio recording")

            elif act == "vpn_connect":
                from jarvis.mcp_client import get_mcp_client
                mcp_cli = get_mcp_client()
                country = step.get("country", "United States")
                res = await mcp_cli.call_tool("urban_vpn_connect", task_intent=desc, country=country)
                results.append(res)
                executed_summaries.append(f"Connected VPN to {country}")

            elif act == "open_capcut":
                from jarvis.mcp_client import get_mcp_client
                mcp_cli = get_mcp_client()
                res = await mcp_cli.call_tool("capcut_open_editor", task_intent=desc)
                results.append(res)
                executed_summaries.append("Opened CapCut Editor")

            elif act == "open_terminal":
                from jarvis.mcp_client import get_mcp_client
                mcp_cli = get_mcp_client()
                res = await mcp_cli.call_tool("open_terminal_run", task_intent=desc)
                results.append(res)
                executed_summaries.append("Opened Windows Terminal")

            # Small delay between plan steps to allow OS windows to settle
            await asyncio.sleep(0.8)

        spoken_confirmation = "Plan executed, sir: " + "; ".join(executed_summaries) + "."
        return {
            "success": True,
            "total_steps": len(steps),
            "results": results,
            "spoken_confirmation": spoken_confirmation
        }


# Shared singleton instance
plan_executor = AutonomousPlanExecutor()
