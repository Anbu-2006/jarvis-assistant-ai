"""
JARVIS WhatsApp Automation Tool — Ban-Safe Native Desktop Messaging.

Uses native Windows Desktop URI protocol and UI Automation.
Zero browser scraping or reverse-engineered WebSockets to prevent Meta account bans.
"""

import os
import json
import time
import logging
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any

from jarvis.app_discovery import launch_application
from jarvis.tools.gui_controller import GUIController

log = logging.getLogger("jarvis.whatsapp")

DATA_DIR = Path(__file__).parents[1] / "data"
CONTACTS_FILE = DATA_DIR / "contacts.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONTACTS_FILE.exists():
        initial_contacts = {
            "tony": "+1234567890",
            "assistant": "+1000000000"
        }
        CONTACTS_FILE.write_text(json.dumps(initial_contacts, indent=2))


def get_contacts() -> Dict[str, str]:
    """Return dictionary of known contact names -> phone numbers."""
    _ensure_data_dir()
    try:
        return json.loads(CONTACTS_FILE.read_text())
    except Exception as e:
        log.warning(f"Error loading contacts.json: {e}")
        return {}


def save_contact(name: str, phone: str) -> bool:
    """Save or update contact name and phone number."""
    _ensure_data_dir()
    try:
        contacts = get_contacts()
        contacts[name.strip().lower()] = phone.strip()
        CONTACTS_FILE.write_text(json.dumps(contacts, indent=2))
        log.info(f"Saved contact '{name}': {phone}")
        return True
    except Exception as e:
        log.error(f"Failed to save contact: {e}")
        return False


def resolve_phone(contact_name: str) -> Optional[str]:
    """Look up a phone number by contact name or alias."""
    contacts = get_contacts()
    name_clean = contact_name.strip().lower()
    if name_clean in contacts:
        return contacts[name_clean]
    
    # Partial match
    for k, v in contacts.items():
        if k in name_clean or name_clean in k:
            return v
    return None


def send_whatsapp_message(
    contact: str,
    message: str,
    phone: Optional[str] = None,
    auto_press_enter: bool = True
) -> Dict[str, Any]:
    """Send a WhatsApp message via official Windows Desktop application.
    
    Safe against bans: Does NOT hook WhatsApp web sockets or use headless browser scraping.
    """
    _ensure_data_dir()
    gui = GUIController()
    target_phone = phone or resolve_phone(contact)
    encoded_text = urllib.parse.quote(message)

    if target_phone:
        # Clean phone digits
        phone_digits = "".join(c for c in target_phone if c.isdigit() or c == "+")
        uri = f"whatsapp://send?phone={phone_digits}&text={encoded_text}"
        log.info(f"Dispatching native WhatsApp URI protocol for {contact} ({phone_digits})")
        os.system(f'start "" "{uri}"')
        
        # Give WhatsApp window 1.5s to open and populate text
        time.sleep(1.5)
        gui.focus_window(".*WhatsApp.*")
        if auto_press_enter:
            time.sleep(0.5)
            gui.press_key("enter")
            log.info(f"Dispatched message to {contact} via URI protocol.")
        
        return {
            "success": True,
            "method": "uri_protocol",
            "contact": contact,
            "phone": phone_digits,
            "message": message,
            "status": "sent" if auto_press_enter else "drafted"
        }
    else:
        # Fallback to Desktop UI Automation: Search contact by name in WhatsApp Desktop
        log.info(f"No stored phone number for '{contact}'. Launching WhatsApp Desktop UI search...")
        launch_application("whatsapp")
        time.sleep(2.0)
        
        focused = gui.focus_window(".*WhatsApp.*")
        if not focused:
            time.sleep(1.0)
            gui.focus_window(".*WhatsApp.*")
        
        # Focus search input box (Ctrl + F)
        gui.hotkey("ctrl", "f")
        time.sleep(0.4)
        
        # Type contact name
        gui.type_text(contact, interval=0.04)
        time.sleep(0.8)
        
        # Select first search result
        gui.press_key("enter")
        time.sleep(0.5)
        
        # Paste message to support unicode, multiline, and emojis
        gui.type_unicode(message)
        time.sleep(0.3)
        
        if auto_press_enter:
            gui.press_key("enter")
            log.info(f"Dispatched message to {contact} via WhatsApp desktop UI.")
        
        return {
            "success": True,
            "method": "desktop_uia",
            "contact": contact,
            "message": message,
            "status": "sent" if auto_press_enter else "drafted"
        }
