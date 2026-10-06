# AI Code Planner

A Python CLI coding agent that helps you plan and execute code changes in an existing repository using a structured Plan → Approve → Execute workflow.

It is built with PydanticAI and Google Gemini, and is designed to work as a human-in-the-loop assistant for software maintenance tasks such as feature implementation, refactoring, bug fixes, and documentation updates.

## Why this project exists

Many coding agents jump straight into editing code without giving the user a clear view of what will change. This project introduces a safer pattern:

1. The planner reads the project structure and relevant files.
2. It creates a step-by-step implementation plan.
3. You review the plan and approve, reject, or revise it.
4. The executor applies the approved changes and verifies them.

This keeps the workflow transparent and reduces accidental or destructive edits.

## Key features

- Structured planning before changes are made
- Read-only analysis in the planning phase
- Human approval before execution
- Exact in-file replacements with validation
- Optional shell execution via `--allow-shell`
- Workspace sandboxing to prevent path traversal outside the project root
- Rich terminal UI with risk levels and execution tracking
- Logfire-based observability for tracing and debugging

## How it works

The tool follows a two-phase workflow:

### Phase 1: Planning

The planner agent:
- lists the workspace structure
- searches for relevant symbols and patterns
- reads the specific files involved
- produces a structured implementation plan with risk assessment

### Phase 2: Execution

After approval, the executor agent:
- performs the steps in order
- reads files before replacing content
- verifies the change after writing
- stops immediately if a replacement fails

## Requirements

- Python 3.12+
- Google Gemini API key
- `uv` (recommended for dependency management)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/wcyashdarji-spec/AI-Code-Planner.git
cd AI-Code-Planner
```

### 2. Create and activate a virtual environment

```bash
uv venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your-gemini-api-key-here
MODEL_NAME=gemini-2.0-flash

# Optional: defaults to the current directory
AGENT_WORKSPACE=.
```

## Usage

### Interactive mode

```bash
python agent_cli.py -w "/absolute/path/to/your/project" --allow-shell
```

This opens a REPL where you can type a task, review the generated plan, and approve or reject it before execution.

### Single prompt mode

```bash
python agent_cli.py -w "/absolute/path/to/your/project" -p "Add docstrings to all public functions"
```

This generates a plan and auto-executes it without pausing for approval.

### Plan-only mode

```bash
python agent_cli.py -w "/absolute/path/to/your/project" --plan-only -p "Refactor the database service"
```

This displays the plan but does not execute any code changes.

## CLI arguments

- `-p`, `--prompt`: single prompt for non-interactive mode
- `-w`, `--workspace`: absolute path to the target project root
- `--allow-shell`: enables shell command execution in the executor phase
- `--plan-only`: generates and displays the plan without applying changes

## Example workflow

```bash
python agent_cli.py -w "/Users/me/my-app"
```

Then enter a request such as:

```text
Add a health check endpoint and update the README with usage instructions.
```

The agent will analyse the project, show a risk-aware plan, and wait for your decision before making changes.

## Safety and risk model

Every generated plan includes a risk level:

- Low: adding files or new content only
- Medium: modifying existing code
- High: deleting or overwriting files or performing irreversible work

The tool is designed to be conservative and to stop when an exact edit cannot be verified.

## Project structure

```text
.
├── agent_cli.py          # CLI entry point
├── code_agent.py         # Planner/executor logic and tool implementations
├── pyproject.toml        # Python project metadata and dependencies
├── README.md             # Project documentation
├── .env                  # Local environment configuration
├── .python-version       # Python version pin
├── .gitignore            # Git ignore rules
└── uv.lock               # Locked dependency versions
```

## Stack

- Python 3.12+
- PydanticAI
- Google Gemini
- Pydantic Logfire
- `uv` for environment management
- `python-dotenv` for configuration

## Notes

- Shell execution is intentionally disabled by default.
- The workspace is validated to ensure edits stay within the target directory.
- The planner is read-only; it cannot modify files.

This project is best suited for developers who want an AI assistant that explains and confirms its actions before writing code.
