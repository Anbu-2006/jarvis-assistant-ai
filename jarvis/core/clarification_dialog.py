"""
JARVIS Interactive Clarification Dialog & Parameter State Machine.

Handles interactive multi-turn voice dialogs when Laya detects that a command
is incomplete or ambiguous (e.g., "Text him on WhatsApp" -> missing contact & message,
or "Open this folder in Antigravity" -> missing specific folder).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

log = logging.getLogger("jarvis.clarification")


@dataclass
class PendingAction:
    action_type: str                   # 'open_app', 'send_message', 'open_folder', 'mcp_call', etc.
    app_name: str = ""                 # e.g., 'whatsapp', 'antigravity', 'chrome'
    contact: Optional[str] = None      # e.g., 'Tony', 'Mom'
    message_text: Optional[str] = None # e.g., 'I will be there in 10 minutes'
    folder_path: Optional[str] = None  # e.g., 'C:\Projects\my-app'
    options: List[Dict[str, str]] = field(default_factory=list) # Visual options for UI
    missing_field: Optional[str] = None # 'contact', 'message', 'folder', 'confirmation'
    raw_query: str = ""


class ClarificationManager:
    """Manages multi-turn clarification state for voice interaction."""

    def __init__(self):
        self._pending: Optional[PendingAction] = None

    @property
    def is_active(self) -> bool:
        """Returns True if JARVIS is currently waiting for a clarification response."""
        return self._pending is not None

    @property
    def current_action(self) -> Optional[PendingAction]:
        return self._pending

    def cancel(self) -> str:
        """Cancel current pending action."""
        self._pending = None
        return "Action cancelled, sir."

    def start_clarification(
        self,
        action_type: str,
        app_name: str = "",
        raw_query: str = "",
        contact: Optional[str] = None,
        message_text: Optional[str] = None,
        folder_path: Optional[str] = None,
        candidate_options: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Initialize a clarification session for an incomplete action."""
        pending = PendingAction(
            action_type=action_type,
            app_name=app_name.lower(),
            contact=contact,
            message_text=message_text,
            folder_path=folder_path,
            options=candidate_options or [],
            raw_query=raw_query,
        )

        spoken_prompt = ""
        visual_prompt = None

        if action_type == "send_message":
            if not pending.contact:
                pending.missing_field = "contact"
                spoken_prompt = f"Whom would you like to message on {app_name.title() or 'WhatsApp'}, sir?"
                visual_prompt = {
                    "type": "interactive_prompt",
                    "title": f"Send Message via {app_name.title() or 'WhatsApp'}",
                    "message": spoken_prompt,
                    "prompt_type": "input",
                    "field": "contact",
                }
            elif not pending.message_text:
                pending.missing_field = "message"
                spoken_prompt = f"What would you like to text {pending.contact}, sir?"
                visual_prompt = {
                    "type": "interactive_prompt",
                    "title": f"Message for {pending.contact}",
                    "message": spoken_prompt,
                    "prompt_type": "input",
                    "field": "message",
                }

        elif action_type == "open_folder":
            pending.missing_field = "folder"
            if pending.options:
                option_names = ", ".join(opt.get("name", "") for opt in pending.options[:3])
                spoken_prompt = f"Which project folder would you like to open: {option_names}?"
            else:
                spoken_prompt = "Which folder or project would you like to open?"

            visual_prompt = {
                "type": "interactive_prompt",
                "title": f"Open in {app_name.title() or 'Explorer'}",
                "message": spoken_prompt,
                "prompt_type": "choice",
                "field": "folder",
                "options": pending.options,
            }

        else:
            pending.missing_field = "confirmation"
            spoken_prompt = f"Please confirm if you would like me to proceed with {action_type}."
            visual_prompt = {
                "type": "interactive_prompt",
                "title": "Confirmation Required",
                "message": spoken_prompt,
                "prompt_type": "confirm",
            }

        self._pending = pending
        log.info(f"Clarification started for {action_type}: missing {pending.missing_field}")

        return {
            "status": "clarifying",
            "spoken_prompt": spoken_prompt,
            "visual_prompt": visual_prompt,
        }

    def process_reply(self, user_reply: str) -> Dict[str, Any]:
        """Process user's spoken answer to the clarification question."""
        if not self._pending:
            return {"ready": False, "cancelled": True, "error": "No pending action"}

        text = user_reply.strip()
        lower = text.lower()

        # Check for user cancellation
        if any(c in lower for c in ["cancel", "never mind", "stop", "abort", "forget it", "no"]):
            msg = self.cancel()
            return {"ready": False, "cancelled": True, "spoken_prompt": msg}

        p = self._pending

        if p.missing_field == "contact":
            # Extract contact name
            cleaned_contact = text
            for prefix in ["send to ", "text ", "message ", "to "]:
                if cleaned_contact.lower().startswith(prefix):
                    cleaned_contact = cleaned_contact[len(prefix):].strip()
            p.contact = cleaned_contact.title()

            if not p.message_text:
                p.missing_field = "message"
                spoken_prompt = f"And what would you like to text {p.contact}, sir?"
                visual_prompt = {
                    "type": "interactive_prompt",
                    "title": f"Message for {p.contact}",
                    "message": spoken_prompt,
                    "prompt_type": "input",
                    "field": "message",
                }
                return {
                    "ready": False,
                    "cancelled": False,
                    "spoken_prompt": spoken_prompt,
                    "visual_prompt": visual_prompt,
                }

        elif p.missing_field == "message":
            p.message_text = text
            p.missing_field = None

        elif p.missing_field == "folder":
            # Match against options if available
            matched_path = None
            if p.options:
                for opt in p.options:
                    if opt.get("name", "").lower() in lower or opt.get("path", "").lower() in lower:
                        matched_path = opt.get("path")
                        break
            p.folder_path = matched_path or text
            p.missing_field = None

        # Check if action is now fully populated
        if not p.missing_field:
            completed_action = p
            self._pending = None
            log.info(f"Clarification complete for {completed_action.action_type}")
            return {
                "ready": True,
                "cancelled": False,
                "action": completed_action,
                "spoken_prompt": "Executing now, sir.",
            }

        return {
            "ready": False,
            "cancelled": False,
            "spoken_prompt": "Could you please specify further, sir?",
        }


# Global singleton manager
clarification_manager = ClarificationManager()
