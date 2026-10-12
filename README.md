<h1 align="center">AI Code Planner</h1>

<p align="center">
  A human-in-the-loop CLI coding agent that safely inspects repositories, formulates risk-aware implementation plans,
  and executes verified code modifications using <strong>PydanticAI</strong> and <strong>Google Gemini</strong>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Pydantic_AI-Latest-E92063.svg" alt="Pydantic AI">
  <img src="https://img.shields.io/badge/Google_Gemini-2.0_Flash-4285F4.svg" alt="Google Gemini">
  <img src="https://img.shields.io/badge/Observability-Logfire-FF6F00.svg" alt="Logfire">
  <img src="https://img.shields.io/badge/uv-Package_Manager-purple.svg" alt="uv">
  <img src="https://img.shields.io/badge/CLI-Tool-009688.svg" alt="CLI">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## Overview

**AI Code Planner** is an autonomous yet strictly governed CLI pair programmer built for existing codebases. Unlike traditional AI coding tools that immediately edit code without review, AI Code Planner introduces a predictable **Plan $\rightarrow$ Approve $\rightarrow$ Execute** lifecycle:

1. **Read-Only Inspection**: Analyzes project trees, symbols, and files without touching disk.
2. **Deterministic Step Planning**: Produces a structured implementation blueprint with fine-grained risk ratings.
3. **Human Approval Gate**: Awaits user authorization before touching a single line of code.
4. **Verified Atomic Execution**: Performs exact in-file replacements and halts immediately if unexpected drift occurs.

---

## Why This Project Exists

Autonomous coding assistants frequently fail by:
- Overwriting critical configuration or unrelated functions.
- Performing uncontrolled edits across multiple files without rollbacks.
- Operating as an opaque "black box" where developers cannot anticipate modifications.

**AI Code Planner** addresses these concerns with architectural boundaries:
- **Zero Surprises**: You inspect the full sequence of actions and risk levels before execution begins.
- **Fail-Safe Replacements**: Every file modification requires strict content matching and post-write verification.
- **Strict Sandbox**: Path traversal protections prevent file reads or writes outside the target workspace.

---

## Key Features

### 🔍 Read-Only Discovery
- Deep directory scanning and pattern searches.
- Symbol-aware file reads without modification side effects.
- Complete workspace sandboxing preventing path escape (`../`).

### 📋 Risk-Aware Planning
- Multi-step task decomposition before execution.
- Automated risk classification:
  - 🟢 **Low**: Read operations, new file additions, documentation updates.
  - 🟡 **Medium**: Modifying existing functions, adding new imports.
  - 🔴 **High**: File deletions, structural refactoring, irreversible modifications.

### 🛡️ Human-in-the-Loop Approval Gate
- Interactive terminal REPL for interactive task authoring.
- Explicit approval prompt (`Approve [y] / Reject [n] / Revise [r]`).
- Non-interactive modes for automated pipelines (`--plan-only`, single prompt).

### ⚡ Verified Exact In-File Replacements
- Uses deterministic string matching rather than blind file overwrites.
- Immediate halted execution if target lines or signatures have drifted.
- Optional shell execution (`--allow-shell`) disabled by default for security.

### 🔭 Full Observability with Logfire
- Distributed tracing powered by **Pydantic Logfire**.
- Step-by-step latency, token consumption, and agent decision tracking.

---

## Architecture & Workflow

```
┌────────────────────────────────────────────────────────┐
│                      User Request                      │
│      "Add health check endpoint and update docs"       │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Planner Agent                       │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │   Workspace Explorer  │   │     File Reader      │  │
│  │      (Read-Only)      │   │      (Sandboxed)     │  │
│  └───────────┬───────────┘   └──────────┬───────────┘  │
│              └────────────┬─────────────┘              │
│                           ▼                            │
│           Structured Implementation Plan               │
│          - Step 1: Create health route (Low)           │
│          - Step 2: Register in main.py (Medium)        │
│          - Step 3: Append docs in README (Low)         │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│              Human Approval Gate (CLI REPL)            │
│       [y] Approve   |   [n] Reject   |   [r] Revise    │
└───────────────────────────┬────────────────────────────┘
                            │ Approved
┌───────────────────────────▼────────────────────────────┐
│                    Executor Agent                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. Read target slice from disk                  │  │
│  │  2. Exact match target block                     │  │
│  │  3. Atomic replacement write                     │  │
│  │  4. Post-write verification & syntax check       │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────┬────────────────────────────┘
                            │ Success
┌───────────────────────────▼────────────────────────────┐
│                 Verified Codebase State                │
└────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.12+ | High-performance async CLI runtime |
| PydanticAI | Multi-agent framework for planning and execution |
| Google Gemini 2.0 Flash | Ultra-fast planning and structured code generation |
| Pydantic Logfire | Production observability, tracing, and agent telemetry |
| Rich | Beautiful terminal tables, syntax highlighting, and progress bars |
| uv | Blazing-fast virtual environment and dependency manager |
| python-dotenv | Safe environment variable management |

---

## Project Structure

```text
AI-Code-Planner/
├── agent_cli.py          # Interactive and single-prompt CLI entrypoint
├── code_agent.py         # Planner/Executor agent logic & sandboxed tools
├── pyproject.toml        # Project dependencies, tools, and metadata
├── requirements.txt      # Standard pip requirements definition
├── .python-version       # Python version pin (3.12)
├── .gitignore            # Git exclusion rules
├── uv.lock               # Deterministic dependency lockfile
└── README.md             # Project documentation
```

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- A Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/))
- `uv` (recommended) or `pip`

Install **uv**:

```bash
pip install uv
```

---

### 1. Clone the Repository

```bash
git clone https://github.com/wcyashdarji-spec/AI-Code-Planner.git
cd AI-Code-Planner
```

### 2. Set Up Virtual Environment

Using **uv**:
```bash
uv venv
```

Activate the environment:

**macOS / Linux:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

Using **uv**:
```bash
uv sync
```

Using **pip**:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Required: Google Gemini API Key
GEMINI_API_KEY=your-gemini-api-key-here

# Model Selection
MODEL_NAME=gemini-2.0-flash

# Default Target Workspace (Optional: defaults to current directory)
AGENT_WORKSPACE=.

# Observability (Optional: Logfire token)
LOGFIRE_TOKEN=
```

---

## Usage & Execution Modes

### 1. Interactive Mode (Recommended)
Launches an interactive session where you formulate tasks, review formatted plans, and approve them interactively:

```bash
python agent_cli.py -w "/absolute/path/to/project" --allow-shell
```

### 2. Single-Prompt Mode
Generates a plan and executes it autonomously without human interruption (ideal for CI/CD or scripted chores):

```bash
python agent_cli.py -w "/absolute/path/to/project" -p "Add type annotations to all methods in services/auth.py"
```

### 3. Plan-Only Mode
Performs deep workspace inspection and prints the implementation plan and risk assessment without making changes:

```bash
python agent_cli.py -w "/absolute/path/to/project" --plan-only -p "Refactor database connection pool to asyncpg"
```

---

## CLI Reference

| Flag | Type | Default | Description |
|---|---|---|---|
| `-w`, `--workspace` | `string` | `.` | Absolute or relative path to the target repository |
| `-p`, `--prompt` | `string` | `None` | Direct task prompt (runs in headless mode) |
| `--plan-only` | `flag` | `False` | Generates and prints the plan without executing changes |
| `--allow-shell` | `flag` | `False` | Permits the executor agent to run terminal commands |
| `--model` | `string` | `gemini-2.0-flash`| Override the configured Gemini model |
| `--verbose` | `flag` | `False` | Outputs detailed agent diagnostics and debug logs |

---

## Example Walkthrough

```text
$ python agent_cli.py -w "D:/Projects/EcommerceService"

AI Code Planner initialized for workspace: D:/Projects/EcommerceService
Model: gemini-2.0-flash | Shell Execution: DISABLED

Enter your task: Add a GET /health check endpoint to app/main.py

[Planner] Inspecting workspace tree...
[Planner] Reading app/main.py (54 lines)...
[Planner] Synthesizing execution plan...

================================ IMPLEMENTATION PLAN ================================
Goal: Add health check endpoint returning system status and uptime.
Risk Assessment: LOW

Steps:
1. [app/main.py] Import HealthResponse schema from app.schemas.response [Risk: LOW]
2. [app/main.py] Register @app.get('/health', response_model=HealthResponse) [Risk: LOW]
3. [tests/test_health.py] Create unit test verifying 200 OK status [Risk: LOW]
====================================================================================

Do you approve this plan? (y/n/revise): y

[Executor] Applying Step 1 in app/main.py... Verified.
[Executor] Applying Step 2 in app/main.py... Verified.
[Executor] Writing tests/test_health.py... Created.

All 3 steps executed and verified successfully in 1.42s.
```

---

## Safety & Risk Model

Every plan item is scored through an automated heuristic and semantic risk analyzer:

| Risk Level | Trigger Criteria | Safety Action |
|:---|---|---|
| 🟢 **LOW** | Creating new files, appending documentation, non-breaking additions | Standard file writing with path containment check |
| 🟡 **MEDIUM** | In-place modifications to existing functions, schema updates | Strict target block matching; fails if code has drifted |
| 🔴 **HIGH** | File deletions, configuration rewrites, irreversible shell operations | Explicit secondary confirmation; strict sandbox assertion |

### Built-in Guardrails:
- **Path Traversal Shield**: Paths resolving outside the defined `--workspace` throw a fatal security error.
- **Atomic Rollback**: If an exact code slice replacement cannot find a 100% character match, the operation aborts with zero modifications written.
- **Opt-in Shell**: Terminal commands cannot be executed unless `--allow-shell` is explicitly provided by the user.

---

## Logging & Observability

AI Code Planner natively instruments all planner, executor, and tool calls with **Pydantic Logfire**:

```bash
# Optional: Authenticate Logfire for cloud telemetry
logfire auth
```

Captured Telemetry:
- Exact LLM prompts, completions, and token counts.
- Time spent in read-only discovery vs code execution.
- Tool call inputs, outputs, and diff verification results.

---

## License

This project is licensed under the [MIT License](LICENSE).
