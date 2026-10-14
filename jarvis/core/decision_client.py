"""
JARVIS OpenRouter Decision Client — System 1 Intent Engine.

Powered by Microsoft-Decision-1 (microsoft/microsoft-decision-1) via OpenRouter Decisions API.
Evaluates user voice queries in a single, calibrated forward pass (~85ms, zero output tokens).
"""

import os
import re
import time
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Automatically load .env if available
_env_path = Path(__file__).parents[2] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

log = logging.getLogger("jarvis.decision_client")

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"


class OpenRouterDecisionClient:
    """Client for Microsoft-Decision-1 on OpenRouter."""

    INVALID_APP_NAMES = {
        "this", "that", "it", "something", "an app", "program", "app",
        "do", "do this", "do that", "things", "thing", "random", "random things",
        "anything", "application", "a", "the", "my", "me", "him", "her",
        "open", "launch", "start", "here", "there"
    }

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("OPENROUTER_DECISION_MODEL", "microsoft/microsoft-decision-1")
        self.http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=2.5)
        return self.http_client

    def predict_action(self, text: str, known_apps: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fast synchronous intent prediction (ideal for real-time speech interim pre-warming)."""
        return self._regex_fallback(text, known_apps)


    async def predict_intent(
        self,
        text: str,
        known_apps: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify user intent using Microsoft-Decision-1 with calibrated probabilities."""
        start_time = time.time()
        api_key = os.getenv("OPENROUTER_API_KEY", self.api_key)

        if not api_key:
            log.warning("OPENROUTER_API_KEY not set. Using fast regex fallback.")
            return self._regex_fallback(text, known_apps)

        payload = {
            "model": self.model,
            "state": text.strip(),
            "questions": {
                "action": {
                    "type": "choice",
                    "instructions": "What primary action is the user requesting?",
                    "criteria": {
                        "open_and_type": "Open an application and type or write specific text into it (e.g. 'open notepad and type hello', 'open word and write a letter').",
                        "type_text": "Type, write, or enter text into the active focused window (e.g. 'type hello world', 'write test message').",
                        "window_control": "Manage desktop windows: minimize, maximize, snap left/right, show desktop, switch window, close window.",
                        "gui_shortcut": "Trigger keyboard shortcut: save, copy, paste, select all, undo, enter, backspace.",
                        "open_app": "Open or launch a desktop application or browser (e.g. Chrome, Notepad, VS Code, Spotify, WhatsApp, Terminal).",
                        "open_file": "Open a specific file, document, photo, video, or PDF with default Windows program.",
                        "process_control": "Close or terminate an application or process (e.g. 'kill chrome', 'close notepad', 'terminate python').",
                        "send_whatsapp": "Compose or send a message to a person on WhatsApp.",
                        "play_youtube": "Play a specific song, artist, video, or music track on YouTube.",
                        "system_control": "Hardware or OS control: volume, mute, brightness, lock screen, empty recycle bin, shutdown.",
                        "get_weather": "Ask about current weather, temperature, rain forecast, or outdoor conditions.",
                        "get_time": "Ask what time it is, the date, day of the week, or current year.",
                        "get_battery": "Ask about laptop battery percentage, power level, or charging state.",
                        "open_folder": "Open a workspace folder, project directory, or code repo in Antigravity or VS Code.",
                        "antigravity_prompt": "Send prompt, text, or instructions directly into Antigravity IDE chat or open chat.",
                        "obs_control": "Start, stop, or check recording/streaming in OBS Studio.",
                        "vpn_control": "Connect, disconnect, or switch location in Urban VPN.",
                        "workflow_vpn_then_capcut": "Compound workflow: connect VPN first, then launch or open CapCut.",
                        "capcut_control": "Open CapCut video editor or trigger CapCut export dialog.",
                        "open_terminal": "Open Windows Terminal (wt.exe) or command line prompt.",
                        "copilot_code": "Build an app, write code files, debug code, or run programming scripts in terminal.",
                        "web_search": "Search the web or Google for a topic, facts, or live news.",
                        "capabilities": "Ask what JARVIS can do, what features are supported, or self-introduction.",
                        "casual_chat": "General conversational query, explanation, banter, greetings, facts, or planning questions."
                    }
                },
                "is_dangerous": {
                    "type": "noul",
                    "instructions": "Does this action involve deleting data, terminating processes, or high-risk computer operations?"
                },
                "needs_clarification": {
                    "type": "noul",
                    "instructions": "Is the user request missing essential targets or parameters (e.g., saying 'open it', 'message him', 'open folder' without specifying which one)?"
                }
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jarvis-assistant.local",
            "X-OpenRouter-Title": "JARVIS AI Assistant"
        }

        client = self._get_http_client()
        resp = None

        # 1. Primary Attempt: Microsoft-Decision-1
        try:
            resp = await client.post(DECISIONS_URL, json=payload, headers=headers)
        except Exception as e:
            log.warning(f"Decision-1 request error: {e}")

        # 2. Secondary Attempt: ScaleDown Classify-1 if primary failed
        if resp is None or resp.status_code != 200:
            try:
                log.info("Flipping to secondary decision engine: scaledown/classify-1")
                fallback_payload = dict(payload)
                fallback_payload["model"] = "scaledown/classify-1"
                resp = await client.post(DECISIONS_URL, json=fallback_payload, headers=headers)
            except Exception as fe:
                log.warning(f"Fallback decision model failed: {fe}")

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        if resp is not None and resp.status_code == 200:
            try:
                data = resp.json()
                answers = data.get("answers", {})
                action_data = answers.get("action", {})
                action = action_data.get("choice", "casual_chat")
                confidence = action_data.get("confidence", 0.0)
                probabilities = action_data.get("probabilities", {})

                is_dangerous_data = answers.get("is_dangerous", {})
                is_dangerous = is_dangerous_data.get("noul", 0.0)

                needs_clar_data = answers.get("needs_clarification", {})
                needs_clarification = needs_clar_data.get("noul", 0.0) > 0.65

                log.info(
                    f"✓ Decision Engine ({elapsed_ms}ms) [{data.get('model', self.model)}]: "
                    f"action={action} (conf={confidence:.2f}, dangerous={is_dangerous:.2f}, needs_clar={needs_clarification})"
                )

                extracted = self._extract_slots(text, action, known_apps)
                return {
                    "action": action,
                    "confidence": confidence,
                    "probabilities": probabilities,
                    "is_dangerous": is_dangerous,
                    "needs_clarification": needs_clarification,
                    "latency_ms": elapsed_ms,
                    "model": data.get("model", self.model),
                    **extracted
                }
            except Exception as pe:
                log.warning(f"Failed parsing decision response: {pe}")
                return self._regex_fallback(text, known_apps)
        else:
            code = resp.status_code if resp else "None"
            log.warning(f"Decision API failed ({code}). Falling back to regex.")
            return self._regex_fallback(text, known_apps)


    def _extract_slots(self, text: str, action: str, known_apps: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract app name, contact, message, text, shortcut, or query from the user utterance."""
        slots: Dict[str, Any] = {
            "app": None,
            "text_to_type": None,
            "contact": None,
            "message": None,
            "query": None,
            "folder": None,
            "window_action": None,
            "shortcut": None,
            "process": None,
            "path": None,
            "sub_action": None,
            "value": None,
        }

        raw = text.strip()
        raw_lower = raw.lower()

        if action == "open_and_type":
            # Match "open <app> and type/write <text>"
            ot_match = re.search(
                r"\b(?:open|launch|start)\s+([a-zA-Z0-9_\-\s]+?)\s+(?:and|,)?\s*(?:type|write|enter)\s+(.+)",
                raw,
                re.IGNORECASE
            )
            if ot_match:
                candidate_app = ot_match.group(1).strip()
                slots["text_to_type"] = ot_match.group(2).strip()
            else:
                # Fallback: check if there is "and type"
                parts = re.split(r"\s+(?:and\s+)?(?:type|write|enter)\s+", raw, maxsplit=1, flags=re.IGNORECASE)
                candidate_app = re.sub(r"^(?:open|launch|start)\s+", "", parts[0], flags=re.IGNORECASE).strip()
                slots["text_to_type"] = parts[1].strip() if len(parts) > 1 else None

            candidate_app = re.sub(r"\b(app|application|please|now)\b", "", candidate_app, flags=re.IGNORECASE).strip()
            if candidate_app.lower() not in self.INVALID_APP_NAMES and len(candidate_app) >= 2:
                slots["app"] = candidate_app
                if known_apps:
                    for a in known_apps:
                        if a.lower() == candidate_app.lower() or a.lower() in candidate_app.lower():
                            slots["app"] = a
                            break

        elif action == "type_text":
            t_match = re.search(r"^(?:type|write|enter)\s+(.+)", raw, re.IGNORECASE)
            slots["text_to_type"] = t_match.group(1).strip() if t_match else raw

        elif action == "window_control":
            if "minimize" in raw_lower:
                slots["window_action"] = "minimize"
            elif "maximize" in raw_lower or "fullscreen" in raw_lower:
                slots["window_action"] = "maximize"
            elif "snap left" in raw_lower:
                slots["window_action"] = "snap_left"
            elif "snap right" in raw_lower:
                slots["window_action"] = "snap_right"
            elif "show desktop" in raw_lower or "hide windows" in raw_lower:
                slots["window_action"] = "show_desktop"
            elif "switch" in raw_lower or "alt tab" in raw_lower:
                slots["window_action"] = "switch_app"
            elif "close" in raw_lower:
                slots["window_action"] = "close"
                # Check if target app mentioned (e.g. "close chrome")
                c_match = re.search(r"\bclose\s+([a-zA-Z0-9_\-\s]+)", raw, re.IGNORECASE)
                if c_match:
                    cand = c_match.group(1).strip()
                    cand = re.sub(r"\b(window|app|this|the)\b", "", cand, flags=re.IGNORECASE).strip()
                    if cand and len(cand) >= 2:
                        slots["app"] = cand
            else:
                slots["window_action"] = "show_desktop"

        elif action == "gui_shortcut":
            if any(w in raw_lower for w in ["save", "ctrl+s", "ctrl s"]):
                slots["shortcut"] = "save"
            elif any(w in raw_lower for w in ["copy", "ctrl+c", "ctrl c"]):
                slots["shortcut"] = "copy"
            elif any(w in raw_lower for w in ["paste", "ctrl+v", "ctrl v"]):
                slots["shortcut"] = "paste"
            elif any(w in raw_lower for w in ["select all", "ctrl+a", "ctrl a"]):
                slots["shortcut"] = "select_all"
            elif any(w in raw_lower for w in ["undo", "ctrl+z", "ctrl z"]):
                slots["shortcut"] = "undo"
            elif "new tab" in raw_lower or "ctrl+t" in raw_lower:
                slots["shortcut"] = "ctrl+t"
            elif "enter" in raw_lower:
                slots["shortcut"] = "enter"
            else:
                slots["shortcut"] = "ctrl+s"

        elif action == "process_control":
            k_match = re.search(r"\b(?:kill|terminate|stop|end|close)\s+([a-zA-Z0-9_\-\s]+)", raw, re.IGNORECASE)
            if k_match:
                cand = k_match.group(1).strip()
                cand = re.sub(r"\b(process|task|app|program|please)\b", "", cand, flags=re.IGNORECASE).strip()
                slots["process"] = cand
                slots["app"] = cand

        elif action == "open_file":
            f_match = re.search(r"\b(?:open\s+(?:file|document|image|pdf)?\s*)(.+)", raw, re.IGNORECASE)
            if f_match:
                slots["path"] = f_match.group(1).strip()

        elif action == "open_app":
            app_match = re.search(r"\b(?:open|launch|start)\s+([a-zA-Z0-9_\-\s]+)", raw, re.IGNORECASE)
            candidate = app_match.group(1).strip() if app_match else raw
            # Clean common words
            candidate = re.sub(r"\b(app|application|please|now)\b", "", candidate, flags=re.IGNORECASE).strip()

            if candidate.lower() in self.INVALID_APP_NAMES or len(candidate) < 2:
                slots["app"] = None
            else:
                slots["app"] = candidate
                # Match against known apps if provided
                if known_apps:
                    for a in known_apps:
                        if a.lower() == candidate.lower() or a.lower() in candidate.lower():
                            slots["app"] = a
                            break

        elif action in ["send_whatsapp", "send_message"]:
            # Pattern: text/message <contact> [saying/that/with] <message>
            wa_match = re.search(
                r"(?:text|message|send\s+(?:a\s+)?message\s+to)\s+([a-zA-Z0-9_\s]+?)\s+(?:saying|that|with)?\s*(.+)?",
                raw,
                re.IGNORECASE
            )
            if wa_match:
                slots["contact"] = wa_match.group(1).strip()
                slots["message"] = (wa_match.group(2) or "").strip()
            else:
                slots["contact"] = None
                slots["message"] = None

        elif action == "play_youtube":
            yt_q = re.sub(r".*?(?:play|watch)\s+", "", raw, flags=re.IGNORECASE)
            yt_q = re.sub(r"\s+on\s+youtube.*", "", yt_q, flags=re.IGNORECASE).strip()
            slots["query"] = yt_q

        elif action == "web_search":
            q = re.sub(r"^(?:search\s+(?:for\s+)?|google\s+)", "", raw, flags=re.IGNORECASE).strip()
            slots["query"] = q

        elif action == "open_folder":
            f_match = re.search(r"\b(?:open\s+(?:folder|project|directory)?\s*)([a-zA-Z0-9_\-\s]+)", raw, re.IGNORECASE)
            cand = f_match.group(1).strip() if f_match else raw
            cand = re.sub(r"\b(folder|project|directory|in antigravity|in vs code|please)\b", "", cand, flags=re.IGNORECASE).strip()
            slots["folder"] = cand

        elif action == "system_control":
            if "volume" in raw_lower:
                slots["sub_action"] = "volume"
                vol_num = re.search(r"\b(\d{1,3})\b", raw)
                if vol_num:
                    slots["value"] = int(vol_num.group(1))

        elif action == "antigravity_prompt":
            # Extract prompt text
            p_match = re.search(r"(?:prompt|type|say|chat|tell)\s+(?:in\s+)?(?:antigravity\s+)?(?:chat\s+)?(?:to\s+|that\s+)?(.+)", raw, re.IGNORECASE)
            slots["prompt"] = p_match.group(1).strip() if p_match else raw

        elif action == "obs_control":
            if "stop" in raw_lower:
                slots["obs_action"] = "stop"
            elif "status" in raw_lower or "check" in raw_lower:
                slots["obs_action"] = "status"
            else:
                slots["obs_action"] = "start"

        elif action == "vpn_control":
            if any(w in raw_lower for w in ["disconnect", "off", "stop"]):
                slots["vpn_action"] = "disconnect"
            else:
                slots["vpn_action"] = "connect"
                country_match = re.search(r"\b(?:to|in)\s+([a-zA-Z\s]+)", raw, re.IGNORECASE)
                slots["country"] = country_match.group(1).strip() if country_match else "United States"

        elif action == "workflow_vpn_then_capcut":
            country_match = re.search(r"\b(?:to|in)\s+([a-zA-Z\s]+?)(?:\s+then|\s+and|\s*$)", raw, re.IGNORECASE)
            slots["country"] = country_match.group(1).strip() if country_match else "United States"

        elif action == "capcut_control":
            if "export" in raw_lower:
                slots["capcut_action"] = "export"
            else:
                slots["capcut_action"] = "open"

        elif action == "open_terminal":
            cmd_match = re.search(r"(?:run|execute)\s+(.+)", raw, re.IGNORECASE)
            slots["command"] = cmd_match.group(1).strip() if cmd_match else None

        return slots

    def _regex_fallback(self, text: str, known_apps: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fast fallback when internet is offline or OpenRouter is unreachable."""
        t_lower = text.lower().strip()

        # 1. Open and type
        if re.search(r"\b(?:open|launch)\s+[a-zA-Z0-9_\-\s]+\s+(?:and|,)?\s*(?:type|write)\b", t_lower):
            slots = self._extract_slots(text, "open_and_type", known_apps)
            return {"action": "open_and_type", "confidence": 0.95, "latency_ms": 1.0, **slots}

        # 2. Type text
        if t_lower.startswith("type ") or t_lower.startswith("write "):
            slots = self._extract_slots(text, "type_text", known_apps)
            return {"action": "type_text", "confidence": 0.90, "latency_ms": 1.0, **slots}

        # 3. Window management
        if any(w in t_lower for w in ["minimize", "maximize", "show desktop", "snap left", "snap right", "switch window", "alt tab"]):
            slots = self._extract_slots(text, "window_control", known_apps)
            return {"action": "window_control", "confidence": 0.92, "latency_ms": 1.0, **slots}

        # 4. Keyboard shortcuts
        if any(w in t_lower for w in ["save file", "save that", "copy that", "copy this", "paste that", "paste this", "select all", "undo that", "undo this", "press ctrl", "hotkey"]):
            slots = self._extract_slots(text, "gui_shortcut", known_apps)
            return {"action": "gui_shortcut", "confidence": 0.90, "latency_ms": 1.0, **slots}

        # 5. Process termination
        if t_lower.startswith("kill ") or t_lower.startswith("terminate ") or (t_lower.startswith("close ") and not any(w in t_lower for w in ["window", "tab"])):
            slots = self._extract_slots(text, "process_control", known_apps)
            return {"action": "process_control", "confidence": 0.88, "latency_ms": 1.0, **slots}

        # 6. WhatsApp
        if "whatsapp" in t_lower and any(w in t_lower for w in ["text", "message", "send"]):
            slots = self._extract_slots(text, "send_whatsapp", known_apps)
            return {"action": "send_whatsapp", "confidence": 0.85, "latency_ms": 1.0, **slots}

        # 7. YouTube
        if ("youtube" in t_lower and any(w in t_lower for w in ["play", "watch", "song"])) or t_lower.startswith("play "):
            slots = self._extract_slots(text, "play_youtube", known_apps)
            return {"action": "play_youtube", "confidence": 0.85, "latency_ms": 1.0, **slots}

        # 8. Weather, Time, Battery
        if any(w in t_lower for w in ["weather", "temperature", "forecast", "rain outside"]):
            return {"action": "get_weather", "confidence": 0.95, "latency_ms": 1.0}
        if any(w in t_lower for w in ["what time", "current time", "what date", "day of week", "what day"]):
            return {"action": "get_time", "confidence": 0.95, "latency_ms": 1.0}
        if any(w in t_lower for w in ["battery", "battery percentage", "charging level", "power status"]):
            return {"action": "get_battery", "confidence": 0.95, "latency_ms": 1.0}

        # 9. Hardware & System
        if any(w in t_lower for w in ["volume", "mute", "unmute", "brightness", "lock screen", "recycle bin"]):
            slots = self._extract_slots(text, "system_control", known_apps)
            return {"action": "system_control", "confidence": 0.90, "latency_ms": 1.0, **slots}

        # Antigravity chat & prompt
        if "antigravity" in t_lower and any(w in t_lower for w in ["chat", "prompt", "type", "ask", "tell"]):
            slots = self._extract_slots(text, "antigravity_prompt", known_apps)
            return {"action": "antigravity_prompt", "confidence": 0.95, "latency_ms": 1.0, **slots}

        # OBS Studio recording & status
        if "obs" in t_lower and any(w in t_lower for w in ["record", "recording", "start", "stop", "status"]):
            slots = self._extract_slots(text, "obs_control", known_apps)
            return {"action": "obs_control", "confidence": 0.95, "latency_ms": 1.0, **slots}

        # Workflow: VPN then CapCut
        if ("vpn" in t_lower and "capcut" in t_lower) or ("connect vpn" in t_lower and "capcut" in t_lower):
            slots = self._extract_slots(text, "workflow_vpn_then_capcut", known_apps)
            return {"action": "workflow_vpn_then_capcut", "confidence": 0.95, "latency_ms": 1.0, **slots}

        # VPN control
        if "vpn" in t_lower and any(w in t_lower for w in ["connect", "disconnect", "turn on", "turn off", "open vpn"]):
            slots = self._extract_slots(text, "vpn_control", known_apps)
            return {"action": "vpn_control", "confidence": 0.92, "latency_ms": 1.0, **slots}

        # CapCut editor / export
        if "capcut" in t_lower:
            slots = self._extract_slots(text, "capcut_control", known_apps)
            return {"action": "capcut_control", "confidence": 0.90, "latency_ms": 1.0, **slots}

        # Open terminal / command prompt
        if ("terminal" in t_lower or "command prompt" in t_lower or "powershell" in t_lower) and any(w in t_lower for w in ["open", "launch", "start"]):
            slots = self._extract_slots(text, "open_terminal", known_apps)
            return {"action": "open_terminal", "confidence": 0.92, "latency_ms": 1.0, **slots}

        # 10. Open app
        if t_lower.startswith("open ") or t_lower.startswith("launch "):
            slots = self._extract_slots(text, "open_app", known_apps)
            return {"action": "open_app", "confidence": 0.80, "latency_ms": 1.0, **slots}

        return {"action": "casual_chat", "confidence": 0.70, "latency_ms": 1.0, "app": None}


# Global singleton instance
decision_client = OpenRouterDecisionClient()
