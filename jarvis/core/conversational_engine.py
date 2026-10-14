"""
JARVIS Conversational Engine — On-Device System 2 Generative Intelligence.

Provides a truly intelligent, conversational brain running 100% locally via llama_cpp / GGUF.
Capable of:
1. Answering arbitrary open-domain questions with human-like depth and British wit
2. Free-form conversational banter and self-awareness
3. Multi-step goal planning and autonomous execution
4. Calling MCP and Windows desktop tools (WhatsApp, YouTube, App Launch, System Control)
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "4"
import re
import time
import json
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator, AsyncGenerator

log = logging.getLogger("jarvis.conversational_engine")

try:
    from llama_cpp import Llama
    _HAS_LLAMA_CPP = True
except ImportError:
    Llama = None
    _HAS_LLAMA_CPP = False

try:
    from huggingface_hub import hf_hub_download
    _HAS_HF_HUB = True
except ImportError:
    hf_hub_download = None
    _HAS_HF_HUB = False


def strip_markdown_for_tts(text: str) -> str:
    """Strip markdown formatting so voice TTS does not pronounce asterisks, backticks, or hashes."""
    if not text:
        return ""
    # Strip action tags for clean speech
    cleaned = re.sub(r"\[ACTION:[^\]]+\]", "", text)
    # Remove code blocks
    cleaned = re.sub(r"```[a-zA-Z]*\n?|```", "", cleaned)
    # Remove inline code backticks
    cleaned = cleaned.replace("`", "")
    # Remove bold/italic asterisks and underscores
    cleaned = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", cleaned)
    # Remove remaining lone asterisks, underscores, and hashes
    cleaned = cleaned.replace("*", "").replace("_", "").replace("#", "")
    # Clean multiple spaces or redundant line breaks
    cleaned = re.sub(r"\n{2,}", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


class LocalConversationalEngine:
    """System 2 On-Device Generative Engine for JARVIS."""

    DEFAULT_SYSTEM_PROMPT = """You are JARVIS, Tony's personal AI desktop assistant and loyal digital majordomo.
You speak with calm, sophisticated British wit and understated intelligence.
You are running 100% locally on this machine with full system access and tool capabilities.

STRICT VOICE RULES:
1. NEVER use markdown symbols (no asterisks '*', no hashes '#', no backticks, no bullet points). TTS will read them aloud.
2. Keep spoken answers concise, elegant, and natural (1 to 3 spoken sentences maximum, unless a detailed breakdown is explicitly requested).
3. Be helpful, direct, and conversational. Answer normal questions with genuine intelligence, factual clarity, and personality.
4. If the user gives you a plan, multi-step instruction, or wants you to perform an action, you CAN do it.

SUPPORTED ACTIONS (append to the very end of your response when needed):
- [ACTION:OPEN_APP] app_name
- [ACTION:WHATSAPP] contact ||| message
- [ACTION:PLAY_YOUTUBE] video or music query
- [ACTION:SEARCH_WEB] query
- [ACTION:RUN_COMMAND] command
- [ACTION:PLAN] step 1; step 2; step 3
"""

    def __init__(self):
        self.model: Optional[Any] = None
        self.model_path: Optional[str] = None
        self._init_lock = threading.Lock()
        self._is_loading = False
        self._is_ready = False
        self.user_name = os.getenv("USER_NAME", "Tony")

    def find_cached_model(self) -> Optional[str]:
        """Locate an available local GGUF model file on disk."""
        # 1. Check workspace models/ directory
        workspace_models = Path(__file__).parents[2] / "models"
        if workspace_models.exists():
            for f in workspace_models.glob("*.gguf"):
                return str(f)

        # 2. Check HuggingFace cache directory
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        if hf_cache.exists():
            # Prefer 1.5B model if downloaded
            m15 = list(hf_cache.glob("**/qwen2.5-1.5b-instruct-*.gguf"))
            if m15:
                return str(m15[0])
            # Next check 0.5B model
            m05 = list(hf_cache.glob("**/qwen2.5-0.5b-instruct-*.gguf"))
            if m05:
                return str(m05[0])
            # Any other gguf
            other = list(hf_cache.glob("**/*.gguf"))
            if other:
                return str(other[0])

        return None

    def initialize(self, block: bool = False) -> bool:
        """Load the local GGUF model in background or blocking."""
        if self._is_ready and self.model is not None:
            return True

        if not _HAS_LLAMA_CPP:
            log.warning("llama_cpp not available for LocalConversationalEngine.")
            return False

        if self._is_loading:
            return False

        def _loader():
            with self._init_lock:
                if self._is_ready:
                    return
                self._is_loading = True
                try:
                    candidates = []
                    m_path = self.find_cached_model()
                    if m_path:
                        candidates.append(m_path)

                    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
                    if hf_cache.exists():
                        for f in hf_cache.glob("**/*.gguf"):
                            s = str(f)
                            if s not in candidates:
                                candidates.append(s)

                    if not candidates and _HAS_HF_HUB:
                        log.info("Downloading Qwen2.5-0.5B-Instruct GGUF model...")
                        dl = hf_hub_download(
                            repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                            filename="qwen2.5-0.5b-instruct-q4_k_m.gguf"
                        )
                        candidates.append(dl)

                    for cand in candidates:
                        try:
                            log.info(f"Loading local SLM model: {cand}")
                            self.model = Llama(
                                model_path=cand,
                                n_ctx=2048,
                                n_batch=256,
                                n_threads=4,
                                verbose=False
                            )
                            self.model_path = cand
                            self._is_ready = True
                            log.info(f"✓ Local System 2 Conversational Engine active & hot in memory! ({Path(cand).name})")
                            break
                        except Exception as ce:
                            log.warning(f"Candidate {cand} failed to load ({ce}), trying next candidate...")

                    if not self._is_ready:
                        log.warning("No local GGUF model candidate could be initialized.")
                except Exception as e:
                    log.error(f"Failed to load local conversational engine: {e}")
                finally:
                    self._is_loading = False

        if block:
            _loader()
            return self._is_ready
        else:
            t = threading.Thread(target=_loader, daemon=True, name="SLMLoader")
            t.start()
            return True

    def build_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Construct prompt with dynamic desktop and temporal context."""
        now_str = time.strftime("%A, %B %d, %Y at %I:%M %p")
        ctx_parts = [
            self.DEFAULT_SYSTEM_PROMPT.replace("Tony", self.user_name),
            f"Current Local Time: {now_str}",
        ]
        if context:
            if context.get("active_windows"):
                ctx_parts.append(f"Active Desktop Windows: {context['active_windows']}")
            if context.get("open_apps"):
                ctx_parts.append(f"Installed Apps Sample: {', '.join(context['open_apps'][:15])}")

        return "\n\n".join(ctx_parts)

    def generate(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 350,
        temperature: float = 0.7,
    ) -> str:
        """Generate a complete text response to the user's prompt."""
        if not self._is_ready or self.model is None:
            # Attempt synchronous initialization
            self.initialize(block=True)

        if not self._is_ready or self.model is None:
            # Fallback response if engine cannot load
            return "I am right here, sir, though my local neural brain is still warming up. How may I be of assistance?"

        messages = [{"role": "system", "content": self.build_system_prompt(context)}]
        if history:
            # Keep last 6 turns for context
            for h in history[-6:]:
                messages.append({"role": h["role"], "content": h["content"]})

        messages.append({"role": "user", "content": prompt})

        try:
            res = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["<|im_end|>", "<|endoftext|>", "User:", "\nUser"]
            )
            raw_text = res["choices"][0]["message"]["content"].strip()
            return raw_text
        except Exception as e:
            log.error(f"Generation error in local engine: {e}")
            return f"I experienced a slight neural fault, sir. However, I am standing by to assist."

    def extract_embedded_actions(self, response_text: str) -> List[Dict[str, str]]:
        """Extract all [ACTION:...] tags from the response."""
        actions = []
        pattern = r"\[ACTION:([A-Z_]+)\]\s*([^\[]+)"
        for match in re.finditer(pattern, response_text):
            act_type = match.group(1).lower().strip()
            act_payload = match.group(2).strip()
            actions.append({"action": act_type, "payload": act_payload})
        return actions


# Shared singleton instance
conversational_engine = LocalConversationalEngine()
