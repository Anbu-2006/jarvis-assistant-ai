"""
JARVIS Universal OS Operator — Full Autonomous Computer Control.

Gives JARVIS the exact same capabilities a human has sitting at the computer:
1. Keyboard: typing, hotkeys, key presses, clipboard paste
2. Mouse: coordinate click, right-click, double-click, drag, scroll, movement
3. Screen & Windows: active window inspection, window focus, minimize, maximize, snap, close, screenshot
4. Applications & Processes: launch any software, kill processes, list running tasks
5. Filesystem: open files with default apps, open folders, read/write/delete/search files
6. Hardware & System: volume (CoreAudio), mute, brightness, lock, sleep, restart, shutdown, battery, system telemetry
7. Shell & PowerShell: run arbitrary commands, scripts, CLI tools with stdout/stderr capture
8. Web & Browser: navigate to URLs, web searches
"""

import os
import re
import sys
import time
import shutil
import ctypes
import logging
import asyncio
import tempfile
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pyautogui
import pyperclip

try:
    import psutil
except ImportError:
    psutil = None

try:
    from pywinauto import Desktop
except ImportError:
    Desktop = None

from jarvis.app_discovery import launch_application, discover_all_apps
from jarvis.tools.gui_controller import GUIController

log = logging.getLogger("jarvis.os_operator")

# Configure pyautogui safety
pyautogui.PAUSE = 0.03
pyautogui.FAILSAFE = True


class UniversalOSOperator:
    """Master OS execution engine that can perform any human desktop action."""

    def __init__(self):
        self.gui = GUIController()

    # ═══════════════════════════════════════════════════════════════════════
    # 1. SHELL / POWERSHELL EXECUTION
    # ═══════════════════════════════════════════════════════════════════════

    def run_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute any command in PowerShell and capture output."""
        log.info(f"OS Run Command: {command}")
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════
    # 2. KEYBOARD & HUMAN TYPING
    # ═══════════════════════════════════════════════════════════════════════

    def type_text(self, text: str, paste_fallback: bool = True) -> Dict[str, Any]:
        """Type text into active focused element. Uses clipboard paste for unicode/special characters."""
        log.info(f"OS Typing text: {text[:60]}...")
        try:
            if paste_fallback:
                # Clipboard paste is instantaneous, preserves casing, emojis, newlines, and unicode
                pyperclip.copy(text)
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.write(text, interval=0.02)
            return {"success": True, "action": "type_text", "length": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def press_key(self, key_name: str) -> Dict[str, Any]:
        """Press any individual key (enter, tab, esc, backspace, space, up, down, etc.)."""
        k = key_name.strip().lower()
        log.info(f"OS Press key: {k}")
        try:
            pyautogui.press(k)
            return {"success": True, "key": k}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hotkey(self, shortcut: str) -> Dict[str, Any]:
        """Execute any keyboard shortcut like 'ctrl+c', 'alt+tab', 'win+d', 'ctrl+shift+esc'."""
        keys = [k.strip().lower() for k in re.split(r"[\+\s]+", shortcut) if k.strip()]
        log.info(f"OS Hotkey: {'+'.join(keys)}")
        try:
            pyautogui.hotkey(*keys)
            return {"success": True, "keys": keys}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════
    # 3. MOUSE & CURSOR
    # ═══════════════════════════════════════════════════════════════════════

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """Click at (x, y) or at current cursor position."""
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        else:
            pyautogui.click(button=button, clicks=clicks)
        return {"success": True, "action": "click", "button": button, "clicks": clicks}

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x, y, button="left", clicks=2)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x, y, button="right", clicks=1)

    def move_mouse(self, x: int, y: int, duration: float = 0.2) -> Dict[str, Any]:
        pyautogui.moveTo(x, y, duration=duration)
        return {"success": True, "x": x, "y": y}

    def scroll(self, clicks: int) -> Dict[str, Any]:
        """Scroll vertical. Positive = up, Negative = down."""
        pyautogui.scroll(clicks)
        return {"success": True, "clicks": clicks}

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Dict[str, Any]:
        pyautogui.moveTo(x1, y1)
        pyautogui.dragTo(x2, y2, duration=0.4, button="left")
        return {"success": True, "from": (x1, y1), "to": (x2, y2)}

    # ═══════════════════════════════════════════════════════════════════════
    # 4. WINDOW MANAGEMENT & SCREEN
    # ═══════════════════════════════════════════════════════════════════════

    def list_windows(self) -> List[str]:
        """Get titles of all open visible windows."""
        if not Desktop:
            return []
        try:
            wins = Desktop(backend="uia").windows()
            return [w.window_text().strip() for w in wins if w.window_text() and len(w.window_text().strip()) > 1]
        except Exception:
            return []

    def focus_window(self, title_pattern: str) -> Dict[str, Any]:
        """Bring any open window to the foreground."""
        log.info(f"OS Focus window pattern: {title_pattern}")
        res = self.gui.focus_window(title_pattern)
        return {"success": res, "pattern": title_pattern}

    def minimize_window(self) -> Dict[str, Any]:
        pyautogui.hotkey("win", "down")
        return {"success": True, "action": "minimize"}

    def maximize_window(self) -> Dict[str, Any]:
        pyautogui.hotkey("win", "up")
        return {"success": True, "action": "maximize"}

    def close_window(self, title_pattern: Optional[str] = None) -> Dict[str, Any]:
        if title_pattern:
            self.focus_window(title_pattern)
            time.sleep(0.3)
        pyautogui.hotkey("alt", "F4")
        return {"success": True, "action": "close_window"}

    def show_desktop(self) -> Dict[str, Any]:
        pyautogui.hotkey("win", "d")
        return {"success": True, "action": "show_desktop"}

    def switch_app(self) -> Dict[str, Any]:
        pyautogui.hotkey("alt", "tab")
        return {"success": True, "action": "switch_app"}

    def capture_screen(self, save_path: Optional[str] = None) -> str:
        """Capture screenshot and return absolute file path."""
        target_path = save_path or str(Path(tempfile.gettempdir()) / f"jarvis_screen_{int(time.time())}.png")
        img = pyautogui.screenshot()
        img.save(target_path)
        log.info(f"Captured screen to {target_path}")
        return target_path

    # ═══════════════════════════════════════════════════════════════════════
    # 5. APPLICATIONS & PROCESS MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def open_app(self, app_name: str, args: str = "") -> Dict[str, Any]:
        """Launch ANY application installed on Windows."""
        log.info(f"OS Open App: {app_name} (args: {args})")
        res = launch_application(app_name, args)
        return res

    def kill_process(self, process_name_or_pid: str) -> Dict[str, Any]:
        """Terminate a running process by name or PID."""
        target = process_name_or_pid.strip()
        if target.isdigit():
            cmd = f"Stop-Process -Id {target} -Force -ErrorAction SilentlyContinue"
        else:
            p_clean = target.replace(".exe", "")
            cmd = f"Stop-Process -Name '{p_clean}' -Force -ErrorAction SilentlyContinue"
        res = self.run_command(cmd)
        return {"success": res["success"], "target": target}

    def list_processes(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Return top running processes by memory/cpu."""
        if not psutil:
            return []
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        procs.sort(key=lambda x: x.get('memory_percent') or 0, reverse=True)
        return procs[:limit]

    # ═══════════════════════════════════════════════════════════════════════
    # 6. FILESYSTEM & DOCUMENT OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def open_path(self, path_str: str) -> Dict[str, Any]:
        """Open any file, image, pdf, video, or folder with its default Windows application."""
        p = Path(os.path.expandvars(os.path.expanduser(path_str.strip())))
        if not p.exists():
            # Check Desktop or Downloads
            for base in [Path.home() / "Desktop", Path.home() / "Downloads", Path.home() / "Documents"]:
                candidate = base / path_str.strip()
                if candidate.exists():
                    p = candidate
                    break

        if p.exists():
            log.info(f"Opening path with default Windows handler: {p}")
            os.startfile(str(p))
            return {"success": True, "path": str(p), "is_dir": p.is_dir()}
        else:
            return {"success": False, "error": f"Path not found: {path_str}"}

    def read_file(self, path_str: str, max_chars: int = 4000) -> Dict[str, Any]:
        """Read content of any text, code, log, or markdown file."""
        try:
            p = Path(os.path.expandvars(os.path.expanduser(path_str.strip())))
            if not p.exists():
                return {"success": False, "error": f"File not found: {path_str}"}
            content = p.read_text(encoding="utf-8", errors="replace")
            truncated = content[:max_chars]
            return {"success": True, "content": truncated, "total_length": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, path_str: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Create or update any file on disk."""
        try:
            p = Path(os.path.expandvars(os.path.expanduser(path_str.strip())))
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with p.open(mode, encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": str(p), "bytes_written": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_path(self, path_str: str) -> Dict[str, Any]:
        """Delete a file or directory."""
        try:
            p = Path(os.path.expandvars(os.path.expanduser(path_str.strip())))
            if not p.exists():
                return {"success": False, "error": f"Path not found: {path_str}"}
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()
            return {"success": True, "path": str(p)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_files(self, filename_pattern: str, search_root: Optional[str] = None) -> List[str]:
        """Search for files by pattern across common user folders."""
        root = Path(search_root) if search_root else Path.home()
        results = []
        try:
            # Search Desktop, Downloads, Documents
            search_dirs = [root / "Desktop", root / "Downloads", root / "Documents"] if not search_root else [root]
            for s_dir in search_dirs:
                if s_dir.exists():
                    for match in s_dir.rglob(f"*{filename_pattern}*"):
                        results.append(str(match))
                        if len(results) >= 20:
                            break
        except Exception as e:
            log.warning(f"File search failed: {e}")
        return results

    # ═══════════════════════════════════════════════════════════════════════
    # 7. CLIPBOARD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════

    def set_clipboard(self, text: str) -> Dict[str, Any]:
        pyperclip.copy(text)
        return {"success": True, "length": len(text)}

    def get_clipboard(self) -> str:
        return pyperclip.paste()

    def paste(self) -> Dict[str, Any]:
        pyautogui.hotkey("ctrl", "v")
        return {"success": True}

    # ═══════════════════════════════════════════════════════════════════════
    # 8. AUDIO & SYSTEM SETTINGS
    # ═══════════════════════════════════════════════════════════════════════

    def set_volume(self, level: int) -> Dict[str, Any]:
        """Set Windows system master volume (0-100)."""
        clamped = max(0, min(100, int(level)))
        try:
            from pycaw.pycaw import AudioUtilities
            spk = AudioUtilities.GetSpeakers()
            vol = spk.EndpointVolume
            vol.SetMasterVolumeLevelScalar(float(clamped) / 100.0, None)
            return {"success": True, "volume": clamped}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mute_volume(self, mute: Optional[bool] = None) -> Dict[str, Any]:
        """Mute, unmute, or toggle volume."""
        try:
            from pycaw.pycaw import AudioUtilities
            spk = AudioUtilities.GetSpeakers()
            vol = spk.EndpointVolume
            curr = vol.GetMute()
            target = not curr if mute is None else mute
            vol.SetMute(target, None)
            return {"success": True, "is_muted": target}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def lock_workstation(self) -> Dict[str, Any]:
        ctypes.windll.user32.LockWorkStation()
        return {"success": True, "action": "lock_workstation"}

    def empty_recycle_bin(self) -> Dict[str, Any]:
        res = self.run_command("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
        return {"success": res["success"]}

    # ═══════════════════════════════════════════════════════════════════════
    # 9. BROWSER & WEB NAVIGATION
    # ═══════════════════════════════════════════════════════════════════════

    def open_url(self, url: str) -> Dict[str, Any]:
        target = url.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://{target}"
        webbrowser.open(target)
        return {"success": True, "url": target}

    def search_web(self, query: str) -> Dict[str, Any]:
        encoded = urllib.parse.quote(query.strip())
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        return {"success": True, "query": query, "url": url}


# Global singleton operator
os_operator = UniversalOSOperator()
