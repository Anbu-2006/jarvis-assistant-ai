"""
JARVIS App Discovery — Auto-scan ALL installed applications on Windows.

Scans:
1. Start Menu shortcuts (.lnk files)
2. Registry uninstall entries
3. Common installation directories
4. PATH executables
5. UWP/Store apps

Outputs a JSON map of app_name → executable_path for JARVIS to use.
"""

import os
import json
import glob
import shutil
import subprocess
import winreg
import logging
from pathlib import Path

log = logging.getLogger("jarvis.app_discovery")

_DISCOVERED_APPS_CACHE: dict[str, str] = {}

try:
    import win32com.client
    _wshell = win32com.client.Dispatch("WScript.Shell")
except Exception:
    _wshell = None


def _resolve_lnk(lnk_path: str) -> str | None:
    """Resolve a .lnk shortcut to its target path using WScript.Shell (or fallback to PowerShell)."""
    global _wshell
    if _wshell:
        try:
            target = _wshell.CreateShortcut(lnk_path).TargetPath
            if target and os.path.isfile(target):
                return target
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}').TargetPath"],
            capture_output=True, text=True, timeout=2
        )
        target = result.stdout.strip()
        if target and os.path.isfile(target):
            return target
    except Exception:
        pass
    return None


def scan_start_menu() -> dict[str, str]:
    """Scan Start Menu for all application shortcuts."""
    apps = {}
    start_menu_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    
    for base_dir in start_menu_dirs:
        if not os.path.isdir(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for f in files:
                if f.lower().endswith(".lnk"):
                    name = f[:-4].lower().strip()
                    # Skip uninstallers and updaters
                    if any(skip in name for skip in ["uninstall", "update", "readme", "help", "manual", "license"]):
                        continue
                    lnk_path = os.path.join(root, f)
                    target = _resolve_lnk(lnk_path)
                    if target:
                        apps[name] = target
    return apps


def scan_registry() -> dict[str, str]:
    """Scan Windows registry for installed applications."""
    apps = {}
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    
    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        try:
                            icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                            # DisplayIcon often points to the .exe
                            exe_path = icon.split(",")[0].strip('"').strip()
                            if exe_path and os.path.isfile(exe_path) and exe_path.lower().endswith(".exe"):
                                apps[name.lower().strip()] = exe_path
                        except (FileNotFoundError, OSError):
                            try:
                                install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                if install_loc and os.path.isdir(install_loc):
                                    # Find main .exe in install directory
                                    exes = glob.glob(os.path.join(install_loc, "*.exe"))
                                    if exes:
                                        apps[name.lower().strip()] = exes[0]
                            except (FileNotFoundError, OSError):
                                pass
                    except (FileNotFoundError, OSError):
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                except (OSError, PermissionError):
                    continue
            winreg.CloseKey(key)
        except (OSError, PermissionError):
            continue
    return apps


def scan_common_dirs() -> dict[str, str]:
    """Scan common installation directories."""
    apps = {}
    dirs_to_scan = [
        os.path.expandvars(r"%PROGRAMFILES%"),
        os.path.expandvars(r"%PROGRAMFILES(x86)%"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
    ]
    
    for base in dirs_to_scan:
        if not os.path.isdir(base):
            continue
        try:
            for entry in os.scandir(base):
                if entry.is_dir():
                    # Look for a main .exe
                    exes = glob.glob(os.path.join(entry.path, "*.exe"))
                    if exes:
                        name = entry.name.lower()
                        # Pick the exe that best matches the folder name
                        best = None
                        for exe in exes:
                            exe_name = os.path.basename(exe).lower()
                            if name in exe_name or exe_name.replace(".exe", "") in name:
                                best = exe
                                break
                        apps[name] = best or exes[0]
        except PermissionError:
            continue
    return apps


def scan_uwp_apps() -> dict[str, str]:
    """Scan UWP/Store apps via PowerShell."""
    apps = {}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-AppxPackage | Where-Object {$_.IsFramework -eq $false} | "
             "Select-Object Name, PackageFamilyName | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for app in data:
                name = app.get("Name", "").lower()
                pfn = app.get("PackageFamilyName", "")
                if name and pfn and not any(skip in name for skip in [
                    "framework", "runtime", "vclibs", "appx", "extension",
                    "microsoft.ui", "microsoft.net", "microsoft.windows"
                ]):
                    # UWP apps can be launched via shell:AppsFolder\{PFN}!App
                    apps[name] = f"shell:AppsFolder\\{pfn}!App"
    except Exception as e:
        log.warning(f"UWP scan failed: {e}")
    return apps


def discover_all_apps(force_refresh: bool = False) -> dict[str, str]:
    """Run all scanners and merge results (cached in-memory for zero latency).
    
    Returns a deduplicated dict of {app_name: executable_path}.
    """
    global _DISCOVERED_APPS_CACHE
    if _DISCOVERED_APPS_CACHE and not force_refresh:
        return _DISCOVERED_APPS_CACHE

    all_apps = {}
    
    # Priority order: Start Menu > Registry > Common dirs > UWP
    print("Scanning Start Menu shortcuts...")
    all_apps.update(scan_common_dirs())
    print(f"  Found {len(all_apps)} apps so far")
    
    print("Scanning registry...")
    all_apps.update(scan_registry())
    print(f"  Found {len(all_apps)} apps so far")
    
    print("Scanning Start Menu...")
    all_apps.update(scan_start_menu())
    print(f"  Found {len(all_apps)} apps so far")

    # Also add PATH executables for common tools
    common_tools = [
        "python", "python3", "node", "npm", "git", "code", "cursor",
        "docker", "kubectl", "terraform", "aws", "gcloud", "az",
        "ffmpeg", "vlc", "ssh", "scp", "curl", "wget",
    ]
    for tool in common_tools:
        path = shutil.which(tool)
        if path:
            all_apps[tool] = path
    
    # Ensure key productivity apps and aliases are explicitly registered
    antigravity_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe")
    if os.path.isfile(antigravity_path):
        all_apps["antigravity"] = antigravity_path
        all_apps["antigravity ide"] = antigravity_path

    # Standard Windows Utilities
    for win_tool, win_exe in [
        ("notepad", "notepad.exe"),
        ("calculator", "calc.exe"),
        ("paint", "mspaint.exe"),
        ("explorer", "explorer.exe"),
        ("file explorer", "explorer.exe"),
        ("task manager", "taskmgr.exe"),
        ("taskmgr", "taskmgr.exe"),
        ("terminal", "wt.exe"),
        ("windows terminal", "wt.exe"),
        ("cmd", "cmd.exe"),
        ("command prompt", "cmd.exe"),
        ("powershell", "powershell.exe"),
        ("chrome", "chrome.exe"),
        ("google chrome", "chrome.exe"),
        ("edge", "msedge.exe"),
        ("microsoft edge", "msedge.exe"),
        ("vs code", "code.exe"),
        ("visual studio code", "code.exe"),
        ("obs", "obs64.exe"),
        ("obs studio", "obs64.exe"),
    ]:
        resolved = shutil.which(win_exe)
        if resolved:
            all_apps[win_tool] = resolved
        elif win_tool not in all_apps:
            all_apps[win_tool] = win_exe

    # Windows Store WhatsApp
    all_apps["whatsapp"] = r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"

    # Clean up names
    cleaned = {}
    for name, path in all_apps.items():
        # Normalize name
        clean_name = name.strip().lower()
        # Skip empty or system entries
        if not clean_name or len(clean_name) < 2:
            continue
        cleaned[clean_name] = path
    
    _DISCOVERED_APPS_CACHE = dict(sorted(cleaned.items()))
    return _DISCOVERED_APPS_CACHE


def launch_application(app_name: str, argument: str = "") -> dict:
    """Launch an application by its name or alias, optionally passing an argument (e.g. folder or URL)."""
    clean = app_name.strip().lower()
    # Guard against generic filler words
    INVALID_TARGETS = {
        "this", "that", "it", "something", "an app", "program", "app",
        "do", "do this", "do that", "things", "thing", "random", "anything", "application"
    }
    if clean in INVALID_TARGETS or len(clean) < 2:
        log.warning(f"Refusing to launch generic target or filler token: '{app_name}'")
        return {"success": False, "message": f"'{app_name}' is not a valid application name."}

    app_map = discover_all_apps()
    # Direct match or exact token match
    target_path = app_map.get(clean)
    if not target_path and len(clean) >= 3:
        for name, path in app_map.items():
            if clean == name or re.search(r'\b' + re.escape(clean) + r'\b', name):
                target_path = path
                break

    if not target_path:
        # Fallback to system protocol or PATH
        if clean == "whatsapp":
            target_path = "whatsapp:"
        else:
            which_path = shutil.which(clean)
            if which_path:
                target_path = which_path

    if not target_path:
        log.warning(f"Application '{app_name}' not found on system.")
        return {"success": False, "message": f"Application '{app_name}' was not found on your PC."}

    log.info(f"Launching '{app_name}' via: {target_path} (arg: {argument})")

    try:
        if target_path.startswith("shell:") or target_path.endswith(":"):
            # UWP app or protocol
            cmd = f'start "" "{target_path}"'
            subprocess.Popen(cmd, shell=True)
            return {"success": True, "message": f"{app_name.title()} launched."}
        
        elif argument and os.path.exists(argument):
            # Launch executable with folder/file path
            subprocess.Popen([target_path, argument])
            return {"success": True, "message": f"Opened in {app_name.title()}."}
        elif argument:
            subprocess.Popen([target_path, argument])
            return {"success": True, "message": f"{app_name.title()} launched."}
        else:
            os.startfile(target_path)
            return {"success": True, "message": f"{app_name.title()} opened."}
    except Exception as e:
        log.error(f"Failed to launch {app_name}: {e}")
        return {"success": False, "message": f"Error opening {app_name}: {e}"}


def save_app_map(output_path: str = None):
    """Scan all apps and save to JSON."""
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "tools", "data", "app_paths.json"
        )
    
    apps = discover_all_apps()
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"  Discovered {len(apps)} applications")
    print(f"  Saved to: {output_path}")
    print(f"{'='*60}")
    
    return apps


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    apps = save_app_map()

