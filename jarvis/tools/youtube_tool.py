"""
JARVIS YouTube & Media Automation Tool.

Allows JARVIS to search for videos, play specific songs/videos directly in the browser,
and manage playback controls.
"""

import re
import logging
import urllib.parse
import webbrowser
from typing import Dict, Any, Optional

import httpx
from jarvis.tools.gui_controller import GUIController

log = logging.getLogger("jarvis.youtube")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def play_youtube_video(query: str, auto_play: bool = True) -> Dict[str, Any]:
    """Search YouTube and play the top matching video directly in the user's browser."""
    query_clean = query.strip()
    
    # Check if user passed a direct URL
    if query_clean.startswith("http://") or query_clean.startswith("https://") or "youtube.com" in query_clean or "youtu.be" in query_clean:
        target_url = query_clean
        if not target_url.startswith("http"):
            target_url = f"https://{target_url}"
        log.info(f"Opening direct YouTube URL: {target_url}")
        webbrowser.open(target_url)
        return {
            "success": True,
            "url": target_url,
            "query": query_clean,
            "title": "Direct YouTube Link",
            "action": "play_direct"
        }

    encoded_query = urllib.parse.quote(query_clean)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=5.0, follow_redirects=True) as client:
            resp = client.get(search_url)
            if resp.status_code == 200:
                html = resp.text
                
                # Find video IDs
                video_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", html)
                # Filter out obvious non-video or repeat tokens
                valid_ids = []
                for vid in video_ids:
                    if vid not in valid_ids:
                        valid_ids.append(vid)
                
                if valid_ids:
                    chosen_id = valid_ids[0]
                    watch_url = f"https://www.youtube.com/watch?v={chosen_id}"
                    
                    # Try to extract title
                    title_match = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', html)
                    video_title = title_match.group(1) if title_match else query_clean
                    
                    log.info(f"Playing top YouTube result: '{video_title}' -> {watch_url}")
                    webbrowser.open(watch_url)
                    return {
                        "success": True,
                        "url": watch_url,
                        "video_id": chosen_id,
                        "title": video_title,
                        "query": query_clean,
                        "action": "play_top_match"
                    }
    except Exception as e:
        log.warning(f"Headless YouTube top-result lookup failed ({e}), opening search results page.")

    # Fallback to search results
    log.info(f"Opening YouTube search: {search_url}")
    webbrowser.open(search_url)
    return {
        "success": True,
        "url": search_url,
        "query": query_clean,
        "action": "open_search_results"
    }


def search_youtube(query: str) -> Dict[str, Any]:
    """Search YouTube and open results page in browser."""
    encoded_query = urllib.parse.quote(query.strip())
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    webbrowser.open(search_url)
    return {
        "success": True,
        "url": search_url,
        "query": query.strip()
    }


def control_youtube(action: str) -> Dict[str, Any]:
    """Control YouTube playback if browser window is active.
    
    Actions:
    - 'toggle' or 'play' or 'pause': Space / 'k'
    - 'mute': 'm'
    - 'fullscreen': 'f'
    - 'next': 'shift+n'
    """
    gui = GUIController()
    action_lower = action.lower().strip()
    
    gui.focus_window(".*YouTube.*")
    if action_lower in ["play", "pause", "toggle"]:
        gui.press_key("k")
    elif action_lower in ["mute", "unmute"]:
        gui.press_key("m")
    elif action_lower in ["fullscreen"]:
        gui.press_key("f")
    elif action_lower in ["next", "skip"]:
        gui.hotkey("shift", "n")
    else:
        return {"success": False, "error": f"Unknown action: {action}"}
        
    return {"success": True, "action": action_lower}
