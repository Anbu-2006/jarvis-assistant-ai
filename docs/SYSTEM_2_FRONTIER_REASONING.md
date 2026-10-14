# Deep Research: System 2 Frontier Reasoning Brain & Cognitive Use Cases

## Executive Summary

JARVIS employs a **Dual-Engine Cognitive Architecture** modeled after human psychology (*Thinking, Fast and Slow*):
- **System 1 (Reflex Arc)**: Driven by non-autoregressive encoder classification (`microsoft/microsoft-decision-1` & `scaledown/classify-1`). Operates in **~85ms**, costs **0 output tokens**, and executes deterministic physical operations directly via Windows APIs (151 installed applications, window management, keyboard typing, hotkeys, hardware telemetry, WhatsApp, YouTube).
- **System 2 (Frontier Reasoning Brain)**: Driven by premier autoregressive foundation models via OpenRouter (`nvidia/nemotron-3-super-120b-a12b:free`, cascading to `openrouter/free`). Operates with deep cognitive reasoning, multi-token prediction (MTP), multimodal screen vision, and autonomous software engineering.

This document details the exact use cases, operational contracts, prompt architecture, and hand-off boundaries for System 2.

---

## 1. Cognitive Architecture & Division of Labor

```
                                ┌────────────────────────────────────────┐
                                │          User Voice Utterance          │
                                └───────────────────┬────────────────────┘
                                                    │
                                                    ▼
                                ┌────────────────────────────────────────┐
                                │     System 1: Microsoft-Decision-1     │
                                │   Fast Intent Triage (~85ms, 0 tokens) │
                                └───────┬────────────────────────┬───────┘
                                        │                        │
                   Deterministic Action │                        │ Open-Ended Reasoning /
                   Confidence >= 0.75   │                        │ Coding / Knowledge Query
                                        ▼                        ▼
               ┌──────────────────────────────────┐    ┌──────────────────────────────────┐
               │         System 1 Fast Path       │    │      System 2 Frontier Brain     │
               │       UniversalOSOperator        │    │    Nemotron-3 Super 120B MTP     │
               │                                  │    │                                  │
               │ • Launch 151 installed apps      │    │ • Autonomous coding (Copilot/AGY)│
               │ • Type text into active window   │    │ • Deep conceptual explanations   │
               │ • Minimize / Maximize / Snap     │    │ • Shell script formulation       │
               │ • Hotkeys: Ctrl+S/C/V/Z          │    │ • Multimodal screen vision       │
               │ • Volume / Mute / Lock / Battery │    │ • Web research synthesis         │
               │ • WhatsApp text / YouTube video  │    │ • Long-term memory & tasking     │
               │                                  │    │ • British butler persona & wit   │
               │ Execution Latency: <100ms        │    │ Execution Latency: ~600-1200ms   │
               │ Token Cost: 0 tokens ($0.00)     │    │ Token Cost: 0 cost (Free Tier)   │
               └────────────────┬─────────────────┘    └────────────────┬─────────────────┘
                                │                                       │
                                └───────────────────┬───────────────────┘
                                                    │
                                                    ▼
                                ┌────────────────────────────────────────┐
                                │     Edge-TTS (en-GB-RyanNeural)        │
                                │   Pristine Spoken Confirmation (~35ms) │
                                └────────────────────────────────────────┘
```

---

## 2. The 8 Core Use Cases of System 2

System 2 is summoned whenever a task requires **creative synthesis, code generation, ambiguous goal decomposition, or conversational depth**.

### Use Case 1: Autonomous Multi-File Software Development (`[ACTION:COPILOT]` & `[ACTION:BUILD]`)
- **Intent Triggers**: *"Build me a modern dashboard in React"*, *"Debug the memory leak in my server"*, *"Add unit tests for the auth service"*, *"Refactor this module into clean architecture"*.
- **Why System 1 Cannot Do This**: Writing software requires semantic syntax generation, file dependency resolution, language idioms, and multi-file project scaffolding.
- **System 2 Execution**:
  1. System 2 parses the target directory (`~/Desktop/new-project` or existing active workspace).
  2. Formulates the task specification.
  3. Appends `[ACTION:COPILOT] <task> ||| <directory>`.
  4. The background agent launches GitHub Copilot CLI in terminal or Antigravity IDE with `.antigravity_instructions.md`.
  5. JARVIS confirms calmly in voice: *"On it, sir. Copilot is building your dashboard now."*

### Use Case 2: Deep Conceptual Reasoning, Science, Logic & Synthesis
- **Intent Triggers**: *"Why is the sky blue?"*, *"Explain how quantum entanglement works in simple terms"*, *"What are the trade-offs between PostgreSQL and MongoDB?"*, *"How does backpropagation calculate gradients?"*.
- **Why System 1 Cannot Do This**: Decision-1 is a non-autoregressive encoder classifier; it physically cannot generate explanatory prose.
- **System 2 Execution**:
  1. Employs large 120B parameter reasoning to break down the concept.
  2. Synthesizes the core intuition into **1-2 elegant sentences**.
  3. Eliminates all markdown, bullet points, and jargon.

### Use Case 3: Autonomous Terminal & Shell Command Formulation (`[ACTION:RUN_COMMAND]`)
- **Intent Triggers**: *"Find all git branches merged in the last week"*, *"Check which port 8340 is running on and kill it"*, *"Pull latest changes and run migrations"*, *"Compress all PNG files in my downloads folder"*.
- **System 2 Execution**:
  1. Generates syntactically correct PowerShell or Bash command lines.
  2. Appends `[ACTION:RUN_COMMAND] <command>`.
  3. JARVIS executes via `os_operator.run_command()` and speaks the exit status.

### Use Case 4: Multimodal Screen Inspection & Visual Understanding (`[ACTION:SCREEN]`)
- **Intent Triggers**: *"What is currently showing on my screen?"*, *"Is that error in the terminal fatal?"*, *"Read the error message on that popup"*.
- **System 2 Execution**:
  1. Appends `[ACTION:SCREEN]`.
  2. Triggers screen capture via `os_operator.capture_screen()`.
  3. Inspects UI hierarchy and visual OCR to synthesize a concise voice explanation.

### Use Case 5: Real-Time Live Web Information Retrieval & Digest (`[ACTION:BROWSE]`)
- **Intent Triggers**: *"What were the key announcements from today's tech keynote?"*, *"Look up recent reviews of the RTX 5080"*, *"Find the latest stock price for NVIDIA"*.
- **System 2 Execution**:
  1. Appends `[ACTION:BROWSE] <url_or_query>`.
  2. Reads and summarizes external web data into a single coherent sentence.

### Use Case 6: Memory Retention & Contextual Association (`[ACTION:REMEMBER]`, `[ACTION:ADD_TASK]`)
- **Intent Triggers**: *"Remember that Tony prefers dark mode and TypeScript"*, *"Add a task to submit the project report by Friday 5 PM"*.
- **System 2 Execution**:
  1. Extracts the core factual memory or structured task parameters (priority, title, due date).
  2. Appends `[ACTION:REMEMBER] <fact>` or `[ACTION:ADD_TASK] <priority> ||| <title> ||| <desc> ||| <due>`.
  3. Commits to SQLite persistent memory store.

### Use Case 7: High-Level Goal Decomposition & Strategic Planning
- **Intent Triggers**: *"I want to prepare my laptop for machine learning development"*, *"Help me plan our product release checklist"*.
- **System 2 Execution**:
  - Instead of firing a single rigid script, engages in structured conversational planning, asking clarifying questions or laying out the step-by-step roadmap.

### Use Case 8: British Butler Persona, Elegance & Conversational Wit
- **Intent Triggers**: Casual banter, greetings, compliments, philosophical queries.
- **Personality Contract**:
  - Modeled after Tony Stark's iconic JARVIS.
  - Economy of language: say more with less (1-2 sentences maximum).
  - Calm under pressure, understated dry wit, zero generic AI clichés (*"As an AI..."*, *"Certainly!"*, *"Great question!"* are banned).

---

## 3. Model Specifications & Economics

| Dimension | System 1 (Reflex Arc) | System 2 (Frontier Brain) |
| :--- | :--- | :--- |
| **Model** | `microsoft/microsoft-decision-1` | `nvidia/nemotron-3-super-120b-a12b:free` |
| **Secondary Model** | `scaledown/classify-1` | `openrouter/free` |
| **API Endpoint** | `POST https://openrouter.ai/api/alpha/decisions` | `POST https://openrouter.ai/api/v1/chat/completions` |
| **Architecture** | Non-autoregressive encoder classifier | 120B parameter MoE + Multi-Token Prediction |
| **Context Window** | Utterance level (512 tokens) | 131,072 tokens (full project/screen context) |
| **Latency** | **~85ms** | **~600–1200ms** |
| **Cost** | 0 output tokens ($0.00) | 100% Free Tier ($0.00) |
| **Output Format** | Calibrated probability distribution | Natural conversational speech + Action Tag |

---

## 4. Prompt Engineering & Voice Brevity Contract

System 2 operates under strict prompt constraints in `jarvis/api/main.py`:
1. **Voice-Only Rule**: 1-2 sentences MAXIMUM.
2. **Zero Markdown**: No asterisks (`*`), hashtags (`#`), backticks (`` ` ``), bullet points (`-`), or numbered lists.
3. **Action Tag Placement**: Action tags MUST be placed at the very END of the response:
   ```text
   On it, sir. [ACTION:COPILOT] build landing page ||| ~/Desktop/site
   ```
4. **Markdown Stripping for TTS**: All output passes through `strip_markdown_for_tts()` before Edge-TTS converts it to audio, ensuring zero syntax symbols are read aloud to the user.
