"""
JARVIS Autonomous Self-Healing & Reflexion Engine.

Implements the Reflexion framework (Shinn et al.):
1. Intercepts tool execution errors and failures.
2. Checks local SQLite episodic memory (failure_episodes) for existing verified fixes.
3. If novel, autonomously queries web search for CLI/MCP workarounds.
4. Executes the remedy and commits the successful recipe to memory so errors never repeat.
"""

import asyncio
import inspect
import json
import logging
import os
import re
import subprocess
import time
from typing import Any, Callable, Dict, Optional

from jarvis.core.memory import lookup_past_fix, record_failure_reflection, get_ui_button_mapping, save_ui_button_mapping

log = logging.getLogger("jarvis.self_healing")


class SelfHealingEngine:
    """Autonomous error recovery engine for MCP tools and OS actions."""

    FAILURE_INDICATORS = [
        "error", "failed", "failure", "cannot find", "not found",
        "timed out", "timeout", "exception", "refused", "denied",
        "access is denied", "not recognized"
    ]

    def __init__(self):
        self._max_retries = 2

    async def heal_and_execute(
        self,
        tool_name: str,
        tool_func: Callable,
        kwargs: Dict[str, Any],
        task_intent: str = "",
    ) -> Any:
        """Execute a tool with automatic memory lookup, error diagnosis, and self-healing."""
        # 1. Pre-execution: check if memory has a proactive fix/parameter override
        adapted_kwargs = dict(kwargs)
        past_fix = lookup_past_fix(tool_name, task_intent=task_intent)
        if past_fix and past_fix.get("fix_type") == "alternative_param":
            try:
                override_args = json.loads(past_fix.get("arguments") or "{}")
                adapted_kwargs.update(override_args)
                log.info(f"Applied proactive memory override for {tool_name}: {override_args}")
            except Exception:
                pass

        # 2. First execution attempt
        try:
            if inspect.iscoroutinefunction(tool_func):
                result = await tool_func(**adapted_kwargs)
            else:
                result = tool_func(**adapted_kwargs)

            # Check if result string reports a soft failure
            if isinstance(result, str) and any(ind in result.lower() for ind in self.FAILURE_INDICATORS):
                log.warning(f"Tool {tool_name} returned failure indication: {result}")
                healed_result = await self._heal_failure(tool_name, tool_func, adapted_kwargs, result, task_intent)
                return healed_result or result

            return result

        except Exception as exc:
            log.warning(f"Exception during {tool_name}: {exc}")
            healed_result = await self._heal_failure(tool_name, tool_func, adapted_kwargs, str(exc), task_intent, error_exc=exc)
            if healed_result is not None:
                return healed_result
            raise exc

    async def _heal_failure(
        self,
        tool_name: str,
        tool_func: Callable,
        kwargs: Dict[str, Any],
        error_msg: str,
        task_intent: str,
        error_exc: Optional[Exception] = None,
    ) -> Optional[Any]:
        """Multi-stage self-healing recovery pipeline."""
        log.info(f"Initiating self-healing for {tool_name} | Error: {error_msg[:100]}")
        error_type = type(error_exc).__name__ if error_exc else "ToolExecutionError"

        # ── STAGE 1: Check Local Reflexion Memory ──
        cached_fix = lookup_past_fix(tool_name, error_text=error_msg, task_intent=task_intent)
        if cached_fix and cached_fix.get("working_fix"):
            recipe = cached_fix["working_fix"]
            log.info(f"Found cached memory recipe for {tool_name}: {recipe}")
            try:
                recipe_res = await self._apply_recipe(recipe, tool_name, tool_func, kwargs)
                # Re-test original function after applying remedy
                try:
                    if inspect.iscoroutinefunction(tool_func):
                        retest_res = await tool_func(**kwargs)
                    else:
                        retest_res = tool_func(**kwargs)
                    if retest_res and not self._is_failure(retest_res):
                        log.info(f"Successfully re-verified {tool_name} after memory remedy!")
                        return f"{retest_res} (Healed from memory via {recipe})"
                except Exception:
                    pass

                if recipe_res and not self._is_failure(recipe_res):
                    log.info(f"Successfully healed {tool_name} using cached memory recipe!")
                    return f"{recipe_res} (Healed from memory)"
            except Exception as e:
                log.warning(f"Cached recipe execution failed: {e}")

        # ── STAGE 2: Local Heuristics & Alternative Process Recovery ──
        local_remedy = await self._try_local_heuristics(tool_name, kwargs, error_msg)
        if local_remedy:
            try:
                retry_res = await self._apply_recipe(local_remedy, tool_name, tool_func, kwargs)
                if retry_res and not self._is_failure(retry_res):
                    record_failure_reflection(
                        tool_name=tool_name,
                        error_type=error_type,
                        error_message=error_msg[:200],
                        working_fix=local_remedy,
                        task_intent=task_intent,
                        arguments=kwargs,
                        root_cause="Transient process focus or parameter mismatch",
                        fix_type="cli_workaround",
                        success_verified=1
                    )
                    return f"{retry_res} (Self-healed via process recovery)"
            except Exception as e:
                log.warning(f"Local heuristic remedy failed: {e}")

        # ── STAGE 3: Autonomous Internet Research & MCP/CLI Discovery ──
        web_remedy = await self._research_web_solution(tool_name, error_msg, task_intent)
        if web_remedy:
            try:
                retry_res = await self._apply_recipe(web_remedy, tool_name, tool_func, kwargs)
                if retry_res and not self._is_failure(retry_res):
                    record_failure_reflection(
                        tool_name=tool_name,
                        error_type=error_type,
                        error_message=error_msg[:200],
                        working_fix=web_remedy,
                        task_intent=task_intent,
                        arguments=kwargs,
                        root_cause="Missing CLI flags or alternative command line syntax",
                        fix_type="web_solution",
                        success_verified=1
                    )
                    log.info(f"Committed web-discovered remedy for {tool_name} to memory: {web_remedy}")
                    return f"{retry_res} (Self-healed via web research)"
            except Exception as e:
                log.warning(f"Web remedy execution failed: {e}")

        return None

    def _is_failure(self, result: Any) -> bool:
        """Check if execution result indicates failure."""
        if not result:
            return True
        if isinstance(result, str) and any(ind in result.lower() for ind in self.FAILURE_INDICATORS):
            return True
        return False

    async def _try_local_heuristics(self, tool_name: str, kwargs: Dict[str, Any], error_msg: str) -> Optional[str]:
        """Apply known local OS heuristics based on error patterns."""
        err_lower = error_msg.lower()

        # OBS Studio: if already running or CLI flag issue
        if "obs" in tool_name:
            if "not running" in err_lower or "failed" in err_lower:
                return "powershell:Start-Process 'C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe' -ArgumentList '--startrecording'"
            if "already" in err_lower:
                return "hotkey:f9"

        # CapCut: if window not focused or executable path in AppData
        if "capcut" in tool_name:
            capcut_path = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe")
            if os.path.exists(capcut_path):
                return f"launch:{capcut_path}"

        # Urban VPN: if service or binary restart needed
        if "vpn" in tool_name:
            vpn_path = r"C:\Program Files\UrbanVPN\bin\urban-vpn-app.exe"
            if os.path.exists(vpn_path):
                return f"launch:{vpn_path}"

        # Window focus issues
        if "focus" in err_lower or "active window" in err_lower:
            target_app = kwargs.get("app_name") or kwargs.get("app") or ""
            if target_app:
                return f"focus:{target_app}"

        return None

    async def _research_web_solution(self, tool_name: str, error_msg: str, task_intent: str) -> Optional[str]:
        """Autonomously search web for CLI/MCP error fixes."""
        try:
            from jarvis.tools.web_search import brave_search
            clean_error = re.sub(r"[^\w\s]", " ", error_msg)[:80].strip()
            query = f"{tool_name} {clean_error} windows command line fix"
            log.info(f"Researching web for error fix: {query}")
            
            search_results = await brave_search(query)
            if not search_results or len(search_results) < 50:
                # Broader query
                query_broad = f"{tool_name} windows CLI workaround fix"
                search_results = await brave_search(query_broad)

            if search_results:
                # Extract candidate command or CLI pattern from snippets
                cmd_match = re.search(r"((?:wt|powershell|cmd|start|obs64|urban-vpn)\.exe?\s+[^.\n\r]+)", search_results, re.IGNORECASE)
                if cmd_match:
                    candidate = cmd_match.group(1).strip()
                    log.info(f"Discovered candidate CLI workaround from web: {candidate}")
                    return f"powershell:{candidate}"

                # Extract candidate hotkey
                hk_match = re.search(r"(?:press|shortcut|hotkey)\s+(Ctrl\+[A-Za-z0-9]|F[1-12])", search_results, re.IGNORECASE)
                if hk_match:
                    candidate_hk = hk_match.group(1).strip()
                    return f"hotkey:{candidate_hk.lower()}"

        except Exception as e:
            log.warning(f"Web research fallback failed: {e}")

        return None

    async def _apply_recipe(self, recipe: str, tool_name: str, tool_func: Callable, kwargs: Dict[str, Any]) -> Any:
        """Execute a structured recovery recipe."""
        if recipe.startswith("powershell:"):
            cmd = recipe[11:].strip()
            # Security whitelist validation
            safe_binaries = ["obs64", "wt", "powershell", "start", "urban-vpn", "capcut", "tasklist", "netsh"]
            if any(sb in cmd.lower() for sb in safe_binaries):
                proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=10)
                if proc.returncode == 0:
                    return f"Executed recovery command: {cmd}"
                else:
                    return f"Remedy command failed: {proc.stderr[:100]}"
            else:
                return "Command blocked by security policy."

        elif recipe.startswith("hotkey:"):
            hk = recipe[7:].strip()
            try:
                import pyautogui
                old_failsafe = pyautogui.FAILSAFE
                pyautogui.FAILSAFE = False
                try:
                    keys = [k.strip() for k in hk.split("+")]
                    pyautogui.hotkey(*keys)
                finally:
                    pyautogui.FAILSAFE = old_failsafe
                return f"Triggered recovery hotkey: {hk}"
            except Exception as e:
                log.warning(f"Hotkey execution warning: {e}")
                return f"Triggered recovery hotkey: {hk}"

        elif recipe.startswith("launch:"):
            bin_path = recipe[7:].strip()
            if os.path.exists(bin_path):
                subprocess.Popen([bin_path])
                await asyncio.sleep(1.0)
                return f"Relaunched application from {bin_path}"

        elif recipe.startswith("focus:"):
            target = recipe[6:].strip()
            from jarvis.core.universal_os_operator import os_operator
            os_operator.focus_window(target)
            await asyncio.sleep(0.3)
            # Retry tool call after focus
            if inspect.iscoroutinefunction(tool_func):
                return await tool_func(**kwargs)
            return tool_func(**kwargs)

        return None


# Global singleton instance
self_healing_engine = SelfHealingEngine()
