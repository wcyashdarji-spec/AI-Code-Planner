<h1 align="center">CLI Coding Agent</h1>

<p align="center">
  A PydanticAI-powered CLI coding agent that reads your codebase, generates a structured implementation plan, and executes approved changes — all through an interactive <strong>Plan → Approve → Execute</strong> workflow.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/PydanticAI-Agent_Framework-E620E9.svg" alt="PydanticAI">
  <img src="https://img.shields.io/badge/Google_Gemini-LLM-4285F4.svg" alt="Google Gemini">
  <img src="https://img.shields.io/badge/Logfire-Observability-FF6B35.svg" alt="Logfire">
  <img src="https://img.shields.io/badge/uv-Package_Manager-7C3AED.svg" alt="uv">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## Features

- 🔍 **Structured Planning** – The planner agent reads, greps, and lists your codebase to produce a detailed, step-by-step implementation plan before any changes are made.
- ✅ **Human-in-the-Loop Approval** – Every plan is displayed for your review. Approve, reject, or revise the prompt before execution begins.
- 🚀 **Safe Execution** – The executor agent follows the approved plan step-by-step, verifying each change against the actual file contents.
- 📖 **Read-Only Analysis Tools** – Grep search, file reading, and directory listing are available in both planning and execution phases.
- ✏️ **Surgical Code Edits** – Write new files or perform exact snippet replacements inside existing files with collision-safe path traversal guards.
- ⚡ **Optional Shell Execution** – Run shell commands during execution (opt-in via `--allow-shell` flag).
- 🎨 **Rich CLI Interface** – Color-coded output with risk indicators, action icons, and a clean REPL experience.
- 🔥 **Logfire Observability** – Full tracing and latency tracking for all LLM calls via Pydantic Logfire.
- 🛡️ **Path Traversal Protection** – All file operations are sandboxed to the workspace root directory.

---

## Getting Started

Follow these steps to set up the project locally.

### Prerequisites

Make sure the following are installed:

- Python 3.12 or later
- Google Gemini API Key
- **uv** (Recommended package manager)

Install **uv** if you don't already have it:

```bash
pip install uv
```

---

## Installation

### Clone the Repository

```bash
git clone <repository-url>
cd CLI_Coding_Agent
```

### Create a Virtual Environment

```bash
uv venv
```

Activate the virtual environment:

**Windows (PowerShell)**
```powershell
.venv\Scripts\activate
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

### Install Dependencies

```bash
uv sync
```

---

## Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your-gemini-api-key-here
MODEL_NAME=gemini-2.0-flash

# Optional: workspace default (defaults to current directory)
AGENT_WORKSPACE=.
```

---

## Usage

### Interactive REPL (Plan → Approve → Execute)

```bash
python agent_cli.py -w "D:\YourProject" --allow-shell
```

This launches an interactive session where you can type change requests, review plans, and approve or revise before execution.

### Single Prompt (Non-Interactive)

```bash
python agent_cli.py -w "D:\YourProject" -p "Add docstrings to all public functions"
```

The plan is displayed and then auto-executed without waiting for manual approval.

### Plan-Only Mode (Review Without Executing)

```bash
python agent_cli.py -w "D:\YourProject" --plan-only -p "Refactor the database service"
```

Displays the generated plan but does **not** execute any changes — useful for reviewing what the agent would do.

### CLI Arguments

| Argument | Short | Description |
|---|---|---|
| `--prompt` | `-p` | Single prompt for non-interactive mode |
| `--workspace` | `-w` | Absolute path to the workspace root (default: current directory) |
| `--allow-shell` | | Enable shell command execution during the execute phase |
| `--plan-only` | | Display the plan but skip execution |

---

## How It Works

The agent operates in a structured two-phase workflow:

### Phase 1: Planning 🔍

The **Planner Agent** (read-only) analyses your codebase:
1. Lists the top-level directory structure
2. Greps for relevant code patterns and identifiers
3. Reads every file it plans to modify
4. Produces a structured `Plan` with ordered steps, risk assessment, and exact code snippets

### Phase 2: Execution 🚀

After you approve the plan, the **Executor Agent** carries out each step:
1. Executes steps in strict order
2. Verifies file contents before every replacement
3. Confirms changes were applied correctly after each write
4. Stops immediately on any failure and reports the error

### Approval Options

When a plan is displayed, you can respond with:
- **`yes`** – Execute the plan as-is
- **`no`** – Cancel without making any changes
- **`edit`** – Revise your prompt and re-generate the plan

---

## Project Structure

```text
├── agent_cli.py          # CLI entry point — REPL, argument parsing, plan display
├── code_agent.py         # PydanticAI agents (planner + executor), tools, and models
├── .env                  # Environment variables (API keys, model config)
├── .gitignore            # Git ignore rules
├── .python-version       # Python version pin (3.12)
├── pyproject.toml        # Project metadata and dependencies
├── uv.lock               # Locked dependency versions
└── README.md             # Project documentation
```

---

## Architecture

The application follows a clean two-agent architecture:

```
User Prompt
    │
    ▼
┌──────────────┐     read / grep / list     ┌──────────────┐
│   Planner    │ ◄──────────────────────────►│   Codebase   │
│   Agent      │                             │   (Files)    │
│  (read-only) │                             └──────────────┘
└──────┬───────┘
       │ Structured Plan
       ▼
┌──────────────┐
│   User       │  approve / reject / edit
│   Review     │
└──────┬───────┘
       │ Approved Plan
       ▼
┌──────────────┐  read / write / replace    ┌──────────────┐
│   Executor   │ ◄─────────────────────────►│   Codebase   │
│   Agent      │         / shell            │   (Files)    │
│ (full access)│                            └──────────────┘
└──────────────┘
```

- **Planner Agent** – Read-only access. Analyses code and produces a structured `Plan` with steps, risk level, and exact snippets.
- **Executor Agent** – Full access. Follows the approved plan step-by-step, verifying each change before and after application.
- **Shared Tool Implementations** – Both agents use the same underlying `_*_impl` functions to avoid code duplication.
- **Path Sandbox** – All file paths are resolved and validated against the workspace root to prevent directory traversal attacks.

---

## Technology Stack

- **Core**: Python 3.12+, PydanticAI, Pydantic
- **LLM**: Google Gemini (configurable model via `MODEL_NAME` env var)
- **Observability**: Pydantic Logfire
- **CLI**: argparse, colorama
- **Tooling**: uv, python-dotenv

---

## Risk Levels

Every generated plan includes a risk assessment:

| Level | Icon | Meaning |
|---|---|---|
| **Low** | 🟢 | Adding new code or files only — no existing code modified |
| **Medium** | 🟡 | Modifying existing code via replacements |
| **High** | 🔴 | Deleting or overwriting files, or irreversible changes |


