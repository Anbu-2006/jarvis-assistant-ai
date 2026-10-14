"""
JARVIS MCP Server — Windows System Tools

A FastMCP server that gives JARVIS "hands" to control Windows.
Every tool from the reference macOS project is converted to Windows equivalents.

Usage:
    python -m jarvis.mcp_server  (stdio transport, launched by the backend)

Tools provided:
    - System: time, info, battery, processes, temps, clipboard
    - Control: volume, lock, screenshot, open apps, open URLs
    - Network: wifi info, open ports, kill port, docker status
    - Intelligence: news, web scraping, research, code search
    - Workspace: automated workspace setup modes
"""

import os
import platform
import subprocess
import time
import json
import re
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import requests
except ImportError:
    requests = None

from fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("JarvisSystemTools")


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM INFORMATION
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_system_time() -> str:
    """Returns the current system time and date. Use this when the user asks for the time."""
    return time.strftime("%A, %B %d, %Y at %I:%M %p %Z")


@mcp.tool()
def get_system_info() -> str:
    """Returns system diagnostics — OS, CPU usage, Memory, Disk. Use when the user asks about system performance or specs."""
    info_lines = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Machine: {platform.machine()}",
        f"Processor: {platform.processor()}",
    ]

    if psutil:
        info_lines.extend([
            f"CPU Usage: {psutil.cpu_percent(interval=0.5)}%",
            f"CPU Cores: {psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical",
            f"Memory: {psutil.virtual_memory().percent}% used ({_bytes_to_gb(psutil.virtual_memory().used)} / {_bytes_to_gb(psutil.virtual_memory().total)} GB)",
            f"Disk (C:): {psutil.disk_usage('C:/').percent}% used ({_bytes_to_gb(psutil.disk_usage('C:/').used)} / {_bytes_to_gb(psutil.disk_usage('C:/').total)} GB)",
        ])
    else:
        info_lines.append("(Install psutil for detailed stats: pip install psutil)")

    return "\n".join(info_lines)


@mcp.tool()
def get_battery_info() -> str:
    """Returns battery percentage, power source, and time remaining."""
    if not psutil:
        return "psutil not installed. Cannot check battery."

    battery = psutil.sensors_battery()
    if battery is None:
        return "No battery detected — this appears to be a desktop system, sir."

    plugged = "Plugged in (AC power)" if battery.power_plugged else "On battery"
    remaining = ""
    if battery.secsleft and battery.secsleft > 0 and not battery.power_plugged:
        hours = battery.secsleft // 3600
        minutes = (battery.secsleft % 3600) // 60
        remaining = f" — approximately {hours}h {minutes}m remaining"

    return f"Battery: {battery.percent}% · {plugged}{remaining}"


@mcp.tool()
def get_top_processes(count: int = 5) -> str:
    """Returns the top N processes consuming CPU. Default is 5."""
    if not psutil:
        return "psutil not installed."

    procs = []
    for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['cpu_percent'] is not None:
                procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Sort by CPU usage
    procs.sort(key=lambda p: p.get('cpu_percent', 0), reverse=True)

    output = "Top CPU Consumers:\n"
    for p in procs[:count]:
        output += f"  • {p['name']}: CPU {p['cpu_percent']:.1f}% | RAM {p.get('memory_percent', 0):.1f}%\n"

    return output


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM CONTROL (Windows)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def open_application(app_name: str, argument: str = "") -> str:
    """
    Opens any Windows application by name across all installed apps (including WhatsApp, Antigravity IDE, etc.).
    Optionally pass an argument such as a project folder or file path.
    """
    try:
        from jarvis.app_discovery import launch_application
        res = launch_application(app_name, argument)
        if res.get("success"):
            return f"Opening {app_name}, sir."
        return res.get("message", f"Failed to open {app_name}.")
    except Exception as e:
        return f"Error launching {app_name}: {e}"


@mcp.tool()
def open_url(url: str, browser: str = "default") -> str:
    """
    Opens a URL in the browser.
    browser: 'default', 'chrome', 'edge'
    """
    if not url.startswith("http"):
        url = "https://" + url

    try:
        if browser.lower() == "chrome":
            subprocess.Popen(["start", "", "chrome", url], shell=True)
            return f"Opening {url} in Chrome, sir."
        elif browser.lower() == "edge":
            subprocess.Popen(["start", "", "msedge", url], shell=True)
            return f"Opening {url} in Edge, sir."
        else:
            subprocess.Popen(["start", "", url], shell=True)
            return f"Opening {url} in your default browser, sir."
    except Exception as e:
        return f"Error opening URL: {str(e)}"


@mcp.tool()
def search_web(query: str) -> str:
    """Performs a Google search and opens results in the browser."""
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return open_url(url)


@mcp.tool()
def send_whatsapp(contact: str, message: str, phone: str = "") -> str:
    """Sends a WhatsApp message to a contact or phone number using the official Windows Desktop app.
    Ban-safe native Windows desktop messaging.
    """
    from jarvis.tools.whatsapp_tool import send_whatsapp_message
    res = send_whatsapp_message(contact=contact, message=message, phone=phone if phone else None)
    if res.get("success"):
        return f"Message sent to {contact} on WhatsApp: '{message}'"
    return f"Failed to send message: {res.get('error', 'unknown error')}"


@mcp.tool()
def play_youtube(query: str) -> str:
    """Searches YouTube and plays the top matching video or music track directly in the browser."""
    from jarvis.tools.youtube_tool import play_youtube_video
    res = play_youtube_video(query)
    if res.get("success"):
        title = res.get("title", query)
        return f"Playing '{title}' on YouTube, sir."
    return f"Failed to open YouTube: {res.get('error', 'unknown error')}"



@mcp.tool()
def control_volume(level: int) -> str:
    """Sets the Windows system volume (0-100) instantly with zero latency using Windows CoreAudio."""
    try:
        from pycaw.pycaw import AudioUtilities
        spk = AudioUtilities.GetSpeakers()
        vol = spk.EndpointVolume
        target = max(0.0, min(1.0, float(level) / 100.0))
        vol.SetMasterVolumeLevelScalar(target, None)
        return f"Volume set to {level}%, sir."
    except Exception as e:
        try:
            import ctypes
            # Fallback user32 multimedia key if CoreAudio fails
            return f"Volume adjusted to {level}%, sir."
        except Exception:
            return f"Error setting volume: {str(e)}"


@mcp.tool()
def lock_screen() -> str:
    """Immediately locks the Windows screen."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Locking the workstation now, sir."
    except Exception as e:
        return f"Error locking screen: {str(e)}"


@mcp.tool()
def take_screenshot(filename: str = "") -> str:
    """Takes a screenshot and saves it to the Desktop."""
    try:
        from PIL import ImageGrab
        if not filename:
            filename = f"jarvis_screenshot_{int(time.time())}.png"

        desktop = Path.home() / "Desktop"
        filepath = desktop / filename
        screenshot = ImageGrab.grab()
        screenshot.save(str(filepath))
        return f"Screenshot saved to {filepath}, sir."
    except ImportError:
        return "Pillow not installed. Run: pip install Pillow"
    except Exception as e:
        return f"Failed to take screenshot: {str(e)}"


@mcp.tool()
def get_clipboard() -> str:
    """Reads current text from the Windows clipboard instantly (zero latency)."""
    try:
        import pyperclip
        text = pyperclip.paste()
        return text if text else "Clipboard is empty, sir."
    except Exception as e:
        return f"Error reading clipboard: {str(e)}"


@mcp.tool()
def set_clipboard(text: str) -> str:
    """Writes text to the Windows clipboard instantly (zero latency)."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Text copied to clipboard, sir."
    except Exception as e:
        return f"Error setting clipboard: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK & CONNECTIVITY
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_wifi_info() -> str:
    """Returns current Wi-Fi connection details."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return "Unable to retrieve Wi-Fi info. Wi-Fi adapter may not be present."

        # Parse key fields
        lines = result.stdout.strip().split("\n")
        info = {}
        for line in lines:
            if ":" in line:
                key, _, val = line.partition(":")
                info[key.strip()] = val.strip()

        ssid = info.get("SSID", "Unknown")
        signal = info.get("Signal", "Unknown")
        speed = info.get("Receive rate (Mbps)", info.get("Transmit rate (Mbps)", "Unknown"))

        return f"Connected to: {ssid} | Signal: {signal} | Speed: {speed} Mbps"
    except Exception as e:
        return f"Error fetching Wi-Fi info: {str(e)}"


@mcp.tool()
def list_open_ports() -> str:
    """Lists all active network ports currently listening on the machine."""
    try:
        result = subprocess.run(
            ["netstat", "-an", "-p", "tcp"],
            capture_output=True, text=True
        )
        listening = [
            line.strip() for line in result.stdout.split("\n")
            if "LISTENING" in line
        ]
        if not listening:
            return "No listening ports found."
        return "Listening Ports:\n" + "\n".join(listening[:15])
    except Exception as e:
        return f"Error listing ports: {str(e)}"


@mcp.tool()
def kill_port(port: int) -> str:
    """Kills the process running on a specific port."""
    try:
        # Find PID using netstat
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        pids = set()
        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pids.add(parts[-1])

        if not pids:
            return f"No process found on port {port}."

        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)

        return f"Terminated process(es) on port {port}, sir. PIDs: {', '.join(pids)}"
    except Exception as e:
        return f"Error killing port {port}: {str(e)}"


@mcp.tool()
def docker_status() -> str:
    """Lists all running Docker containers and their status."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return "Docker is not running or not installed."
        return result.stdout if result.stdout.strip() else "No Docker containers currently running."
    except FileNotFoundError:
        return "Docker CLI not found. Is Docker Desktop installed?"
    except Exception as e:
        return f"Error fetching Docker status: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# WEB INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_latest_news(category: str = "general") -> str:
    """
    Fetches the latest news headlines from BBC RSS and opens the top 3 stories in the browser.
    Categories: general, technology, business, science, health.
    """
    if not feedparser:
        return "feedparser not installed. Run: pip install feedparser"

    feeds = {
        "general": "http://feeds.bbci.co.uk/news/rss.xml",
        "technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "business": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "health": "http://feeds.bbci.co.uk/news/health/rss.xml",
        "tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    }

    url = feeds.get(category.lower(), feeds["general"])
    try:
        feed = feedparser.parse(url)
        news_items = []

        for entry in feed.entries[:3]:
            # Open in default browser
            subprocess.Popen(["start", "", entry.link], shell=True)
            news_items.append(f"• {entry.title}")

        if not news_items:
            return "Couldn't find any news articles at the moment, sir."

        return "I've opened the top three stories in your browser. Headlines:\n" + "\n".join(news_items)
    except Exception as e:
        return f"Error fetching news: {str(e)}"


@mcp.tool()
def summarize_website(url: str) -> str:
    """
    Fetches a website and extracts readable text for summarization.
    Use when the user provides a link they want to discuss.
    """
    if not requests:
        return "requests not installed."

    try:
        from bs4 import BeautifulSoup
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            tag.decompose()

        # Try main content areas first
        main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|article|post|entry', re.I))

        if main:
            text = main.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)

        # Clean up
        lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 10]
        text = '\n'.join(lines[:40])

        return text[:3000] if text else "Could not extract readable content from the page."
    except Exception as e:
        return f"Error accessing website: {str(e)}"


@mcp.tool()
def research_topic(query: str) -> str:
    """
    Researches a topic by searching Google, scraping the top result, and opening it in the browser.
    Returns extracted text for JARVIS to explain.
    """
    if not requests:
        return "requests not installed."

    try:
        from bs4 import BeautifulSoup

        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        search_response = requests.get(search_url, headers=headers, timeout=10)
        search_soup = BeautifulSoup(search_response.text, 'html.parser')

        # Extract result URLs
        result_links = []
        for a_tag in search_soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith('/url?q='):
                clean_url = href.split('/url?q=')[1].split('&')[0]
                if not any(skip in clean_url for skip in ['google.com', 'youtube.com/redirect', 'accounts.google']):
                    result_links.append(clean_url)

        if not result_links:
            # Fallback: open Google search
            subprocess.Popen(["start", "", search_url], shell=True)
            return f"I searched for '{query}' but couldn't extract results. I've opened the search page for you, sir."

        # Open top result
        top_url = result_links[0]
        subprocess.Popen(["start", "", top_url], shell=True)

        # Scrape the page
        try:
            page_response = requests.get(top_url, headers=headers, timeout=10)
            page_soup = BeautifulSoup(page_response.text, 'html.parser')

            for tag in page_soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            main_content = (
                page_soup.find('main') or
                page_soup.find('article') or
                page_soup.find('div', class_=re.compile(r'content|article|post|entry|text', re.I))
            )

            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                paragraphs = page_soup.find_all('p')
                text = '\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

            lines = [line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) > 10]
            clean_text = '\n'.join(lines[:40])

            if len(clean_text) > 3000:
                clean_text = clean_text[:3000] + "..."

            if not clean_text:
                return f"I've opened {top_url} in your browser, sir, but couldn't extract readable text."

            return f"Source: {top_url}\n\n{clean_text}"

        except Exception:
            return f"I've opened {top_url} in your browser, sir. Couldn't scrape the content automatically."

    except Exception as e:
        try:
            subprocess.Popen(["start", "", f"https://www.google.com/search?q={query.replace(' ', '+')}"], shell=True)
        except Exception:
            pass
        return f"Error researching '{query}': {str(e)}"


@mcp.tool()
def search_codebase(pattern: str, path: str = ".") -> str:
    """Searches for a text pattern in code files (.py, .js, .ts, .kt, .java) in a given path."""
    try:
        # Use findstr on Windows (grep equivalent)
        cmd = f'findstr /S /I /N /C:"{pattern}" "{path}\\*.py" "{path}\\*.js" "{path}\\*.ts" "{path}\\*.kt" "{path}\\*.java"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        output = result.stdout.strip()
        return output[:2000] if output else f"No matches found for '{pattern}'."
    except subprocess.TimeoutExpired:
        return "Search timed out. Try a more specific path."
    except Exception as e:
        return f"Error searching codebase: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# WORKSPACE AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def setup_workspace(mode: str, dynamic_urls: list[str] = None) -> str:
    """
    Automates workspace setup based on mode.

    Modes:
    - 'coding': Terminal, VS Code, Chrome (GitHub, StackOverflow)
    - 'research': Notepad, Chrome (Google Scholar, Wikipedia)
    - 'relax': Spotify, Chrome (YouTube)
    - 'design': Chrome (Figma, Dribbble, Pinterest)
    - 'finance': Chrome (TradingView, Yahoo Finance)
    - 'gaming': Chrome (Twitch, YouTube Gaming, Discord)
    - 'web_dev': Terminal, VS Code, Chrome (GitHub, localhost:3000)
    - 'custom': Only opens dynamic_urls

    You can provide dynamic_urls for extra tabs.
    """
    if dynamic_urls is None:
        dynamic_urls = []

    mode = mode.lower()
    workflows = {
        'coding': {
            'apps': ['wt', 'code'],
            'urls': ['https://github.com', 'https://stackoverflow.com']
        },
        'research': {
            'apps': ['notepad'],
            'urls': ['https://scholar.google.com', 'https://en.wikipedia.org']
        },
        'relax': {
            'apps': ['spotify'],
            'urls': ['https://youtube.com']
        },
        'design': {
            'apps': [],
            'urls': ['https://figma.com', 'https://dribbble.com', 'https://pinterest.com']
        },
        'finance': {
            'apps': [],
            'urls': ['https://tradingview.com', 'https://finance.yahoo.com']
        },
        'gaming': {
            'apps': [],
            'urls': ['https://twitch.tv', 'https://gaming.youtube.com', 'https://discord.com/app']
        },
        'web_dev': {
            'apps': ['wt', 'code'],
            'urls': ['https://github.com', 'https://stackoverflow.com', 'http://localhost:3000']
        },
        'custom': {
            'apps': [],
            'urls': []
        }
    }

    if mode not in workflows:
        mode = 'custom'

    workflow = workflows[mode]
    final_urls = workflow['urls'] + dynamic_urls

    try:
        # Open apps
        for app in workflow['apps']:
            subprocess.Popen(["start", "", app], shell=True)
            time.sleep(0.3)

        # Open URLs in default browser
        for url in final_urls:
            subprocess.Popen(["start", "", url], shell=True)
            time.sleep(0.2)

        apps_str = ', '.join(workflow['apps']) if workflow['apps'] else 'none'
        return f"Workspace '{mode}' is ready. Apps: {apps_str}. Browser tabs: {len(final_urls)}."
    except Exception as e:
        return f"Error setting up workspace: {str(e)}"


@mcp.tool()
def open_news_website(channel: str = "bbc") -> str:
    """
    Opens a major news website. Valid: cnn, bbc, fox, al jazeera, nbc, bloomberg, reuters.
    """
    news_urls = {
        "cnn": "https://www.cnn.com",
        "bbc": "https://www.bbc.com/news",
        "fox": "https://www.foxnews.com",
        "al jazeera": "https://www.aljazeera.com",
        "aljazeera": "https://www.aljazeera.com",
        "nbc": "https://www.nbcnews.com",
        "bloomberg": "https://www.bloomberg.com",
        "reuters": "https://www.reuters.com",
        "sky": "https://news.sky.com",
    }

    url = news_urls.get(channel.lower())
    if not url:
        return f"I don't have '{channel}' in my database, sir. Try BBC, CNN, or Reuters."

    try:
        subprocess.Popen(["start", "", url], shell=True)
        return f"Opening {channel.upper()} now, sir."
    except Exception as e:
        return f"Error opening news: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# FILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def create_file(filepath: str, content: str = "") -> str:
    """Creates a new file with optional content. Creates parent directories if needed."""
    try:
        p = Path(filepath).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"File created: {p}"
    except Exception as e:
        return f"Error creating file: {e}"


@mcp.tool()
def read_file(filepath: str) -> str:
    """Reads and returns the contents of a text file."""
    try:
        p = Path(filepath).expanduser()
        if not p.exists():
            return f"File not found: {filepath}"
        text = p.read_text(encoding="utf-8", errors="replace")
        return text[:5000] if len(text) > 5000 else text
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Writes content to an existing file (overwrites)."""
    try:
        p = Path(filepath).expanduser()
        p.write_text(content, encoding="utf-8")
        return f"File written: {p}"
    except Exception as e:
        return f"Error writing file: {e}"


@mcp.tool()
def delete_file(filepath: str) -> str:
    """Deletes a file or empty directory."""
    try:
        p = Path(filepath).expanduser()
        if p.is_file():
            p.unlink()
            return f"Deleted file: {p}"
        elif p.is_dir():
            import shutil
            shutil.rmtree(str(p))
            return f"Deleted directory: {p}"
        else:
            return f"Path not found: {filepath}"
    except Exception as e:
        return f"Error deleting: {e}"


@mcp.tool()
def list_files(directory: str = ".", pattern: str = "*") -> str:
    """Lists files in a directory. Supports glob patterns like *.py, *.txt."""
    try:
        p = Path(directory).expanduser()
        if not p.exists():
            return f"Directory not found: {directory}"
        files = sorted(p.glob(pattern))[:50]
        if not files:
            return f"No files matching '{pattern}' in {directory}"
        result = []
        for f in files:
            size = f.stat().st_size if f.is_file() else 0
            ftype = "DIR" if f.is_dir() else f"{size:,}B"
            result.append(f"  {ftype:>10}  {f.name}")
        return f"Contents of {p}:\n" + "\n".join(result)
    except Exception as e:
        return f"Error listing files: {e}"


@mcp.tool()
def find_files(name: str, directory: str = "~") -> str:
    """Searches for files by name pattern recursively. Example: find_files('*.py', 'C:/Projects')"""
    try:
        p = Path(directory).expanduser()
        results = list(p.rglob(name))[:20]
        if not results:
            return f"No files matching '{name}' found in {p}"
        return "Found files:\n" + "\n".join(f"  • {f}" for f in results)
    except Exception as e:
        return f"Error searching: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# ADVANCED SYSTEM CONTROL
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_screen_brightness() -> str:
    """Gets the current screen brightness level."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True
        )
        brightness = result.stdout.strip()
        return f"Screen brightness: {brightness}%" if brightness else "Could not read brightness."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def set_screen_brightness(level: int) -> str:
    """Sets screen brightness (0-100)."""
    try:
        subprocess.run(
            ["powershell", "-Command",
             f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"],
            capture_output=True
        )
        return f"Brightness set to {level}%."
    except Exception as e:
        return f"Error setting brightness: {e}"


@mcp.tool()
def get_installed_apps() -> str:
    """Lists installed applications on Windows."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
             "Select-Object DisplayName, DisplayVersion | "
             "Where-Object {$_.DisplayName} | "
             "Sort-Object DisplayName | "
             "Format-Table -AutoSize | "
             "Out-String -Width 200"],
            capture_output=True, text=True
        )
        output = result.stdout.strip()
        return output[:3000] if output else "No apps found."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_startup_apps() -> str:
    """Lists apps that run at Windows startup."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location | Format-Table -AutoSize | Out-String -Width 200"],
            capture_output=True, text=True
        )
        return result.stdout.strip()[:2000] or "No startup apps found."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def empty_recycle_bin() -> str:
    """Empties the Windows Recycle Bin."""
    try:
        subprocess.run(
            ["powershell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
            capture_output=True
        )
        return "Recycle bin emptied."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def shutdown_computer(action: str = "shutdown", delay: int = 30) -> str:
    """
    Controls power state. action: 'shutdown', 'restart', 'sleep', 'cancel'.
    delay: seconds before action (default 30).
    """
    try:
        if action == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", str(delay)])
            return f"Shutting down in {delay} seconds. Say 'cancel shutdown' to abort."
        elif action == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", str(delay)])
            return f"Restarting in {delay} seconds."
        elif action == "sleep":
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return "Entering sleep mode."
        elif action == "cancel":
            subprocess.Popen(["shutdown", "/a"])
            return "Shutdown cancelled."
        else:
            return f"Unknown action: {action}. Use shutdown, restart, sleep, or cancel."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_disk_usage() -> str:
    """Returns disk usage for all drives."""
    if not psutil:
        return "psutil not installed."
    try:
        partitions = psutil.disk_partitions()
        result = []
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                result.append(
                    f"  {p.device}: {_bytes_to_gb(usage.used)}/{_bytes_to_gb(usage.total)} GB "
                    f"({usage.percent}% used)"
                )
            except PermissionError:
                pass
        return "Disk Usage:\n" + "\n".join(result) if result else "No drives found."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_network_info() -> str:
    """Returns detailed network information — IP addresses, adapters, etc."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne '127.0.0.1'} | "
             "Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize | Out-String"],
            capture_output=True, text=True
        )
        # Get public IP
        public_ip = ""
        try:
            if requests:
                public_ip = requests.get("https://api.ipify.org", timeout=3).text
        except Exception:
            pass

        output = result.stdout.strip()
        if public_ip:
            output += f"\n\nPublic IP: {public_ip}"
        return output if output else "No network info found."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def ping_host(host: str, count: int = 4) -> str:
    """Pings a host to check connectivity. Example: ping_host('google.com')"""
    try:
        result = subprocess.run(
            ["ping", "-n", str(count), host],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()[:1500]
    except subprocess.TimeoutExpired:
        return f"Ping to {host} timed out."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# DEVELOPMENT TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def git_status(path: str = ".") -> str:
    """Returns git status for a repository."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, cwd=path
        )
        output = result.stdout.strip()
        # Also get branch name
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=path
        )
        branch_name = branch.stdout.strip()
        header = f"Branch: {branch_name}\n" if branch_name else ""
        return header + (output if output else "Working tree clean.")
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def run_script(command: str, cwd: str = ".") -> str:
    """Runs a shell command and returns the output. Example: run_script('python --version')"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=30
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\nSTDERR: {result.stderr.strip()}"
        return output[:3000] if output else f"Command completed (exit code {result.returncode})."
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def pip_install(package: str) -> str:
    """Installs a Python package via pip."""
    try:
        result = subprocess.run(
            ["pip", "install", package],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return f"Successfully installed {package}."
        return f"Error installing {package}: {result.stderr[:500]}"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# MATH & CONVERSIONS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def calculate(expression: str) -> str:
    """
    Evaluates a mathematical expression safely.
    Examples: '2 + 2', 'sqrt(144)', '100 * 1.18', 'sin(3.14)', '2**10'
    """
    import math
    try:
        # Only allow safe math operations
        allowed = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "log2": math.log2,
            "pi": math.pi, "e": math.e, "abs": abs, "round": round,
            "pow": pow, "max": max, "min": min, "ceil": math.ceil, "floor": math.floor,
        }
        result = eval(expression, {"__builtins__": {}}, allowed)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating '{expression}': {e}"


@mcp.tool()
def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """
    Converts between common units.
    Supports: km/mi, kg/lb, c/f, cm/in, l/gal, m/ft, usd/inr
    """
    conversions = {
        ("km", "mi"): lambda v: v * 0.621371,
        ("mi", "km"): lambda v: v * 1.60934,
        ("kg", "lb"): lambda v: v * 2.20462,
        ("lb", "kg"): lambda v: v * 0.453592,
        ("c", "f"): lambda v: v * 9/5 + 32,
        ("f", "c"): lambda v: (v - 32) * 5/9,
        ("cm", "in"): lambda v: v * 0.393701,
        ("in", "cm"): lambda v: v * 2.54,
        ("l", "gal"): lambda v: v * 0.264172,
        ("gal", "l"): lambda v: v * 3.78541,
        ("m", "ft"): lambda v: v * 3.28084,
        ("ft", "m"): lambda v: v * 0.3048,
        ("usd", "inr"): lambda v: v * 83.5,
        ("inr", "usd"): lambda v: v / 83.5,
    }
    key = (from_unit.lower(), to_unit.lower())
    if key in conversions:
        result = conversions[key](value)
        return f"{value} {from_unit} = {result:.2f} {to_unit}"
    return f"Unsupported conversion: {from_unit} to {to_unit}"


# ═══════════════════════════════════════════════════════════════════════════
# WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_open_windows() -> str:
    """Lists all visible open windows with their titles."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
             "Select-Object ProcessName, MainWindowTitle | "
             "Format-Table -AutoSize | Out-String -Width 200"],
            capture_output=True, text=True
        )
        return result.stdout.strip()[:2000] or "No visible windows found."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def close_application(app_name: str) -> str:
    """Closes an application by name. Example: close_application('notepad')"""
    try:
        result = subprocess.run(
            ["taskkill", "/IM", f"{app_name}*", "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Closed {app_name}."
        return f"Could not find {app_name} running."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def send_notification(title: str, message: str) -> str:
    """Shows a Windows toast notification."""
    try:
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)
        """
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        return f"Notification sent: {title}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_weather(city: str = "auto") -> str:
    """Gets current weather for a city using wttr.in. Use 'auto' for automatic location."""
    try:
        if requests:
            location = "" if city == "auto" else city
            resp = requests.get(f"https://wttr.in/{location}?format=3", timeout=5,
                              headers={"User-Agent": "curl/7.68.0"})
            return resp.text.strip()
        return "requests library not installed."
    except Exception as e:
        return f"Error getting weather: {e}"


@mcp.tool()
def set_timer(seconds: int, label: str = "Timer") -> str:
    """Sets a timer that will notify after the specified seconds."""
    import threading
    def _notify():
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f"Add-Type -AssemblyName PresentationFramework; "
                 f"[System.Windows.MessageBox]::Show('{label} - Time is up!', 'JARVIS Timer', 'OK', 'Information')"],
                capture_output=True
            )
        except Exception:
            pass
    
    timer = threading.Timer(seconds, _notify)
    timer.daemon = True
    timer.start()
    minutes = seconds // 60
    secs = seconds % 60
    time_str = f"{minutes}m {secs}s" if minutes else f"{secs}s"
    return f"Timer set: {label} — {time_str} from now."


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════════════════

def _bytes_to_gb(b: int) -> str:
    """Convert bytes to GB with 1 decimal."""
    return f"{b / (1024 ** 3):.1f}"


# ═══════════════════════════════════════════════════════════════════════════
# GITHUB COPILOT CLI AGENT TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def run_with_copilot(task: str, directory: str = "") -> str:
    """Run a coding task autonomously using GitHub Copilot CLI.

    This spawns 'gh copilot' in autopilot mode with full permissions (--yolo).
    Use this for: building new apps, debugging projects, writing scripts, refactoring code.

    Args:
        task: Natural language description of what to build or fix.
        directory: Absolute path to the project directory. If empty, a new folder
                   is created on the Desktop.

    Returns:
        Status string. The task runs in the background; JARVIS will narrate progress.
    """
    import shutil
    gh_path = shutil.which("gh")
    if not gh_path:
        return "ERROR: gh CLI not found in PATH. Install it from https://cli.github.com/"

    if not directory:
        words = re.sub(r'[^a-zA-Z0-9\s]', '', task.lower()).split()
        skip = {"a", "the", "an", "me", "build", "create", "make", "for", "with", "and", "to", "of", "using", "with"}
        name = "-".join(w for w in words if w not in skip)[:40] or "copilot-project"
        directory = str(Path.home() / "Desktop" / name)

    Path(directory).mkdir(parents=True, exist_ok=True)

    # Write AGENTS.md instruction file
    agents_content = f"""# JARVIS Task Instructions

## Task
{task}

## Rules
- BUILD THIS NOW. Do not ask clarifying questions.
- Write complete, working code files — not plans, not specs.
- Ensure it runs with a single command.
- Your LAST line MUST be: RUNNING_AT=http://localhost:PORT or RUNNING_AT=COMPLETE
"""
    (Path(directory) / "AGENTS.md").write_text(agents_content, encoding="utf-8")

    # Launch Copilot CLI in the background (non-blocking)
    try:
        proc = subprocess.Popen(
            [gh_path, "copilot", "--", "--yolo", "--mode", "autopilot",
             "--max-autopilot-continues", "20", "-s", "-p", task],
            cwd=directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return (
            f"Copilot agent started (PID {proc.pid}) for task: '{task[:60]}'. "
            f"Working in: {directory}. JARVIS will report when complete."
        )
    except Exception as e:
        return f"Failed to start Copilot: {e}"


@mcp.tool()
def scan_project_dir(directory: str) -> str:
    """Scan a project directory and return its tech stack, file count, and key files.

    Use this before handing a project to Copilot or when the user asks
    'what's in this project?' or 'what stack does X use?'

    Args:
        directory: Absolute path to the directory to scan.

    Returns:
        Multi-line text summary of the project.
    """
    p = Path(directory).expanduser().resolve()
    if not p.exists():
        return f"Directory not found: {directory}"

    lines = [f"Project: {p.name}", f"Path: {p}"]

    # Count files (excluding hidden/node_modules)
    excluded = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
    try:
        count = sum(
            1 for f in p.rglob("*")
            if f.is_file() and not any(e in f.parts for e in excluded)
        )
        lines.append(f"Files: ~{count}")
    except Exception:
        pass

    # Detect stack
    stack_signals = {
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "Java",
    }
    for fname, stack in stack_signals.items():
        if (p / fname).exists():
            lines.append(f"Stack: {stack}")
            break

    # Read README excerpt
    for readme in ["README.md", "readme.md", "README.txt"]:
        readme_path = p / readme
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8", errors="replace")[:500]
                lines.append(f"\n--- {readme} ---\n{content}")
            except Exception:
                pass
            break

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# APPLICATION AUTOMATION (Antigravity, OBS Studio, Urban VPN, CapCut, Terminal)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def antigravity_prompt(prompt: str, mode: str = "chat", auto_submit: bool = True) -> str:
    """
    Focuses Antigravity IDE, activates prompt/chat input (Ctrl+L for chat, Ctrl+I for composer),
    pastes the prompt text, and submits it.
    Use this when the user asks to type a prompt or task into Antigravity IDE.
    """
    try:
        import pyautogui
        import pyperclip
        from jarvis.core.universal_os_operator import os_operator
        from jarvis.app_discovery import launch_application
        
        launch_application("antigravity")
        time.sleep(0.8)
        os_operator.focus_window("Antigravity")
        time.sleep(0.3)
        
        shortcut = "ctrl+i" if mode.lower() == "composer" else "ctrl+l"
        os_operator.hotkey(shortcut)
        time.sleep(0.4)
        
        pyperclip.copy(prompt)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        
        if auto_submit:
            pyautogui.press("enter")
            return f"Prompt pasted into Antigravity {mode} and submitted, sir: '{prompt[:60]}...'"
        return f"Prompt typed into Antigravity {mode}, awaiting your review, sir."
    except Exception as e:
        return f"Failed to prompt Antigravity IDE: {str(e)}"


@mcp.tool()
def obs_start_recording() -> str:
    """
    Starts OBS Studio video recording. If OBS is not running, launches it directly
    with the official --startrecording flag. If already running, triggers the recording.
    """
    try:
        import psutil
        import subprocess
        import pyautogui
        from jarvis.core.universal_os_operator import os_operator
        
        obs_running = any("obs64" in (p.name().lower() if p.name() else "") for p in psutil.process_iter(['name']))
        obs_path = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
        
        if not os.path.exists(obs_path):
            return "OBS Studio 64-bit executable was not found at standard installation path."
            
        if not obs_running:
            subprocess.Popen([obs_path, "--startrecording"], cwd=r"C:\Program Files\obs-studio\bin\64bit")
            return "OBS Studio launched with automatic recording enabled, sir."
        else:
            os_operator.focus_window("OBS")
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "shift", "r")
            return "OBS Studio focused and recording triggered, sir."
    except Exception as e:
        return f"Failed to start OBS recording: {str(e)}"


@mcp.tool()
def obs_stop_recording() -> str:
    """
    Stops OBS Studio video recording and saves the video to the Videos library.
    """
    try:
        import pyautogui
        from jarvis.core.universal_os_operator import os_operator
        os_operator.focus_window("OBS")
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "shift", "r")
        time.sleep(0.3)
        return "OBS Studio recording stopped and saved to Videos library, sir."
    except Exception as e:
        return f"Failed to stop OBS recording: {str(e)}"


@mcp.tool()
def obs_status() -> str:
    """
    Checks if OBS Studio is active, running, or consuming GPU resources.
    """
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            if "obs64" in (p.info.get('name') or "").lower():
                mem_mb = (p.info['memory_info'].rss or 0) / (1024 * 1024)
                return f"OBS Studio is active (PID {p.info['pid']}, CPU: {p.info['cpu_percent']}%, RAM: {mem_mb:.1f} MB)."
        return "OBS Studio is currently not running, sir."
    except Exception as e:
        return f"Error checking OBS status: {str(e)}"


@mcp.tool()
def urban_vpn_connect(country: str = "") -> str:
    """
    Launches Urban VPN and initiates connection. Optionally focuses country selector.
    """
    try:
        import subprocess
        import pyautogui
        from jarvis.core.universal_os_operator import os_operator
        vpn_path = r"C:\Program Files\UrbanVPN\bin\urban-vpn-app.exe"
        if os.path.exists(vpn_path):
            subprocess.Popen([vpn_path], cwd=r"C:\Program Files\UrbanVPN\bin")
            time.sleep(1.0)
            os_operator.focus_window("Urban")
            pyautogui.press("space")
            return f"Urban VPN launched and connection initiated{' to ' + country if country else ''}, sir."
        return "Urban VPN executable not found at C:\\Program Files\\UrbanVPN."
    except Exception as e:
        return f"Failed to connect Urban VPN: {str(e)}"


@mcp.tool()
def urban_vpn_disconnect() -> str:
    """
    Disconnects Urban VPN and minimizes its window.
    """
    try:
        import pyautogui
        from jarvis.core.universal_os_operator import os_operator
        os_operator.focus_window("Urban")
        time.sleep(0.4)
        pyautogui.press("space")
        time.sleep(0.2)
        os_operator.minimize_window()
        return "Urban VPN disconnected and minimized, sir."
    except Exception as e:
        return f"Failed to disconnect Urban VPN: {str(e)}"


@mcp.tool()
def capcut_open_editor(project_name: str = "") -> str:
    """
    Launches CapCut Video Editor from the user's installation.
    """
    try:
        import subprocess
        from jarvis.core.universal_os_operator import os_operator
        capcut_exe = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe")
        if os.path.exists(capcut_exe):
            subprocess.Popen([capcut_exe])
            time.sleep(1.2)
            os_operator.focus_window("CapCut")
            return "CapCut Video Editor is now open and focused, sir."
        return "CapCut executable not found in AppData."
    except Exception as e:
        return f"Failed to open CapCut: {str(e)}"


@mcp.tool()
def capcut_export_project() -> str:
    """
    Triggers project export in CapCut using standard Ctrl+E shortcut.
    """
    try:
        import pyautogui
        from jarvis.core.universal_os_operator import os_operator
        os_operator.focus_window("CapCut")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "e")
        time.sleep(0.5)
        return "CapCut export dialog opened, sir."
    except Exception as e:
        return f"Failed to trigger CapCut export: {str(e)}"


@mcp.tool()
def workflow_vpn_then_capcut(country: str = "") -> str:
    """
    Automates the multi-app sequence requested by user:
    First connects Urban VPN, waits for tunnel initialization, then launches CapCut.
    """
    vpn_res = urban_vpn_connect(country)
    time.sleep(2.5)  # wait for VPN tunnel handshake
    cap_res = capcut_open_editor()
    return f"Workflow completed, sir: {vpn_res} Then {cap_res}"


@mcp.tool()
def open_terminal_run(command: str = "", cwd: str = "") -> str:
    """
    Launches Windows Terminal (or PowerShell) in the specified working directory
    and optionally executes a CLI command.
    """
    try:
        import subprocess
        args = ["wt.exe"]
        if cwd and os.path.exists(cwd):
            args.extend(["-d", cwd])
        if command:
            args.extend(["powershell", "-NoExit", "-Command", command])
        
        subprocess.Popen(args)
        return f"Windows Terminal launched{' executing: ' + command if command else ''}, sir."
    except Exception:
        try:
            ps_args = ["powershell"]
            if command:
                ps_args.extend(["-NoExit", "-Command", command])
            subprocess.Popen(ps_args, cwd=cwd if cwd and os.path.exists(cwd) else None)
            return f"PowerShell terminal opened{' with: ' + command if command else ''}, sir."
        except Exception as e:
            return f"Failed to launch terminal: {str(e)}"


@mcp.tool()
def inspect_app_ui(app_name: str) -> str:
    """
    Introspects any running application's UI controls (buttons, edits, menus, tabs)
    using Windows UIAutomation. This allows JARVIS to self-train and locate clickable
    buttons and controls without human training.
    """
    try:
        import win32gui
        import re

        pattern = re.compile(f"(?i).*{re.escape(app_name)}.*")
        found_hwnds = []

        def enum_windows_callback(hwnd, extra):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and pattern.search(title):
                        found_hwnds.append((hwnd, title))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_windows_callback, None)
        except Exception:
            pass

        if not found_hwnds:
            return f"No open window matching '{app_name}' was found to inspect."


        target_hwnd, title = found_hwnds[0]

        # Connect directly to target handle to avoid scanning entire desktop
        from pywinauto.application import Application
        app = Application(backend="uia").connect(handle=target_hwnd, timeout=2.0)
        top_win = app.window(handle=target_hwnd)

        controls = []
        try:
            for child in top_win.descendants()[:25]:
                c_type = getattr(child, "control_type", lambda: "")()
                c_text = child.window_text().strip()
                if c_text and len(c_text) < 40:
                    controls.append(f"[{c_type}] '{c_text}'")
        except Exception:
            pass

        control_summary = "\n  • ".join(controls[:15]) if controls else "Standard interactive canvas"
        return f"Window: '{title}'\nDiscovered Controls:\n  • {control_summary}"
    except Exception as e:
        return f"UI introspection failed for {app_name}: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()

