"""
Coding Agent powered by PydanticAI — Plan → Approve → Execute workflow.

Two-phase design:
  PLAN phase   : planner_agent reads files (grep / read / list only) and
                 returns a structured Plan for the user to review.
  EXECUTE phase: coding_agent runs all tools (including write / replace / shell)
                 only after the user has approved the plan.

Both agents share the same model (MODEL_NAME env var) and the same low-level
tool implementations (_*_impl functions) to avoid code duplication.
"""

from __future__ import annotations

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Literal, Optional

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

logfire.configure()
logger = logging.getLogger(__name__)

# Configuration

DEFAULT_WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", ".")).resolve()
MAX_READ_CHARS = 80_000


# Dependency model

class AgentDeps(BaseModel):
    """Runtime context injected into every tool call."""

    workspace: str = Field(
        default_factory=lambda: str(DEFAULT_WORKSPACE),
        description="Absolute path to the workspace root.",
    )
    allow_shell: bool = Field(
        default=False,
        description="Enable the run_shell tool when True.",
    )
    mode: Literal["plan", "execute"] = Field(
        default="plan",
        description="'plan' = read-only phase; 'execute' = all tools enabled.",
    )

    model_config = {"arbitrary_types_allowed": True}


# Plan output models

class PlanStep(BaseModel):
    """A single action step inside an implementation plan."""

    step_number: int = Field(description="Ordered step index, starting at 1.")
    action: Literal["read", "grep", "list", "write", "replace", "shell"] = Field(
        description="Type of operation this step performs."
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Target file path (relative to workspace) for read/write/replace actions.",
    )
    description: str = Field(
        description="Human-readable explanation of what this step does and why."
    )
    old_snippet: Optional[str] = Field(
        default=None,
        description="Exact text block to be replaced (for 'replace' actions). "
                    "Must be copied verbatim from the file that was read.",
    )
    new_snippet: Optional[str] = Field(
        default=None,
        description="New text to write (for 'write' and 'replace' actions).",
    )
    command: Optional[str] = Field(
        default=None,
        description="Shell command to run (for 'shell' actions).",
    )


class Plan(BaseModel):
    """Structured implementation plan produced by the planner agent."""

    title: str = Field(description="Short title summarising the task (≤ 10 words).")
    reasoning: str = Field(
        description="Why these changes are needed — root cause, not just what is being done."
    )
    affected_files: list[str] = Field(
        description="List of file paths (relative) that will be created or modified."
    )
    steps: list[PlanStep] = Field(
        description="Ordered list of steps to execute after user approval."
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description=(
            "low = adding new content only; "
            "medium = modifying existing code; "
            "high = deleting or overwriting files."
        )
    )
    risk_notes: str = Field(
        description="Brief description of potential side-effects or rollback steps."
    )


# Path-traversal guard

def _resolve_path(workspace: str, rel_or_abs: str) -> Path:
    """
    Resolve *rel_or_abs* relative to *workspace*.
    Raises ValueError if the path escapes the workspace root.
    """
    workspace_path = Path(workspace).resolve()
    resolved = (workspace_path / rel_or_abs).resolve()
    try:
        resolved.relative_to(workspace_path)
    except ValueError:
        raise ValueError(
            f"Path '{rel_or_abs}' resolves to '{resolved}' which is outside "
            f"the allowed workspace root '{workspace_path}'."
        )
    return resolved


# Shared tool implementations (private — called by both agents)

async def _grep_search_impl(
    workspace: str,
    pattern: str,
    directory: str = ".",
    file_glob: str = "*",
    case_insensitive: bool = False,
    max_results: int = 50,
) -> str:
    search_root = _resolve_path(workspace, directory)
    if not search_root.is_dir():
        return f"ERROR: '{directory}' is not a directory within the workspace."
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return f"ERROR: Invalid regex pattern '{pattern}': {exc}"
    matches: list[str] = []
    for file_path in sorted(search_root.rglob(file_glob)):
        if not file_path.is_file():
            continue
        if file_path.stat().st_size > 5 * 1024 * 1024:
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = file_path.relative_to(Path(workspace))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if compiled.search(line):
                matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                if len(matches) >= max_results:
                    matches.append(f"... (truncated at {max_results} results)")
                    return "\n".join(matches)
    if not matches:
        return f"No matches found for pattern '{pattern}' in '{directory}'."
    return "\n".join(matches)


async def _read_file_impl(
    workspace: str,
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    resolved = _resolve_path(workspace, file_path)
    if not resolved.exists():
        return f"ERROR: File '{file_path}' does not exist."
    if not resolved.is_file():
        return f"ERROR: '{file_path}' is a directory, not a file."
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"ERROR: Could not read '{file_path}': {exc}"
    lines = text.splitlines(keepends=True)
    total = len(lines)
    s = max(0, (start_line or 1) - 1)
    e = min(total, end_line or total)
    numbered: list[str] = []
    chars = 0
    for i, line in enumerate(lines[s:e], start=s + 1):
        entry = f"{i:>5}: {line}"
        numbered.append(entry)
        chars += len(entry)
        if chars > MAX_READ_CHARS:
            numbered.append("... (truncated — content exceeds read limit)\n")
            break
    header = (
        f"File: {file_path}  (lines {s+1}–{min(e, total)} of {total})\n"
        + "-" * 60 + "\n"
    )
    return header + "".join(numbered)


async def _list_directory_impl(
    workspace: str,
    directory: str = ".",
    recursive: bool = False,
    file_glob: str = "*",
) -> str:
    search_root = _resolve_path(workspace, directory)
    if not search_root.is_dir():
        return f"ERROR: '{directory}' is not a directory within the workspace."
    iterator = search_root.rglob(file_glob) if recursive else search_root.glob(file_glob)
    entries: list[str] = []
    for p in sorted(iterator):
        rel = p.relative_to(Path(workspace))
        kind = "DIR " if p.is_dir() else "FILE"
        size = f"  ({p.stat().st_size:,} B)" if p.is_file() else ""
        entries.append(f"  {kind}  {rel}{size}")
    if not entries:
        return f"Directory '{directory}' is empty (no matches for '{file_glob}')."
    return f"Listing of '{directory}'  ({len(entries)} entries):\n" + "\n".join(entries)


# Model setup (single model for both agents, configurable via .env)

_api_key = os.getenv("GEMINI_API_KEY")
_model_name = os.getenv("MODEL_NAME", "gemini-2.0-flash")
_provider = GoogleProvider(api_key=_api_key)
_model = GoogleModel(_model_name, provider=_provider)


# Planner Agent — read-only, returns structured Plan

PLANNER_SYSTEM_PROMPT = """\
You are an expert AI code analyst. Your ONLY job is to PLAN changes — never execute them.

## Mandatory Exploration Workflow
Follow these steps in order before producing a plan:

1. Call list_directory_planner(".", recursive=False) to understand the top-level structure.
2. Call grep_search_planner to find exactly where relevant code lives.
   - Search for function/class names, error messages, or key identifiers.
3. Call read_file_planner on EVERY file you plan to modify.
   - Read the specific sections around the target code.
   - Copy old_snippet verbatim from the file — do not paraphrase or abbreviate.
4. Only after you have read all relevant code, produce your structured Plan.

## Rules for the Plan output
- old_snippet in every "replace" step MUST be copied character-for-character from the
  file you read (same whitespace, indentation, and line endings).
- new_snippet must be the complete replacement block.
- steps must be in execution order.
- risk_level:
    "low"    = only adding new code/files, no existing code touched.
    "medium" = modifying existing code (replace or partial write).
    "high"   = deleting files, overwriting entire files, or irreversible changes.
- reasoning must explain WHY the change is needed (root cause), not just what it does.
- Be conservative: prefer replace_in_file over write_file for existing files.

## What you CANNOT do
- You cannot call write_file, replace_in_file, or run_shell.
- You cannot make any assumption about file contents without reading them first.
"""

planner_agent: Agent[AgentDeps, Plan] = Agent(
    _model,
    deps_type=AgentDeps,
    output_type=Plan,
    system_prompt=PLANNER_SYSTEM_PROMPT,
)

logfire.instrument_pydantic_ai(planner_agent)


@planner_agent.tool
async def grep_search_planner(
    ctx: RunContext[AgentDeps],
    pattern: str,
    directory: str = ".",
    file_glob: str = "*",
    case_insensitive: bool = False,
    max_results: int = 50,
) -> str:
    """
    Search for *pattern* in files under *directory*.

    Args:
        pattern: Regex or literal string to find.
        directory: Sub-directory to search (default: workspace root).
        file_glob: Filename filter (e.g. "*.py").
        case_insensitive: Case-insensitive search when True.
        max_results: Max matching lines returned.
    """
    return await _grep_search_impl(
        ctx.deps.workspace, pattern, directory, file_glob, case_insensitive, max_results
    )


@planner_agent.tool
async def read_file_planner(
    ctx: RunContext[AgentDeps],
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    Read a file with optional line range.

    Args:
        file_path: Path relative to workspace root.
        start_line: First line to include (1-indexed, inclusive).
        end_line: Last line to include (1-indexed, inclusive).
    """
    return await _read_file_impl(ctx.deps.workspace, file_path, start_line, end_line)


@planner_agent.tool
async def list_directory_planner(
    ctx: RunContext[AgentDeps],
    directory: str = ".",
    recursive: bool = False,
    file_glob: str = "*",
) -> str:
    """
    List files and directories inside *directory*.

    Args:
        directory: Directory to list (default: workspace root).
        recursive: Recurse into sub-directories when True.
        file_glob: Filename filter (e.g. "*.py").
    """
    return await _list_directory_impl(ctx.deps.workspace, directory, recursive, file_glob)


# Executor Agent — all tools, runs only after plan is approved

EXECUTOR_SYSTEM_PROMPT = """\
You are an expert AI coding assistant operating in EXECUTION mode.
You have been given a user request and a pre-approved implementation Plan.

## Execution Rules (non-negotiable)
1. Execute plan steps IN ORDER — do not skip or reorder them.
2. Before every replace_in_file call:
   - Call read_file on the target file to confirm the exact old_snippet still exists.
   - If it doesn't match, STOP and report which step failed.
3. After every write_file or replace_in_file call:
   - Call read_file on the modified section to verify the change was applied correctly.
4. If any step fails (snippet not found, file missing, permission error):
   - STOP immediately.
   - Do NOT attempt to continue with later steps.
   - Report the failure clearly with the exact error message.
5. Do NOT make any changes beyond what the approved plan specifies.
6. For "shell" steps, verify that allow_shell is enabled before calling run_shell.

## Final Summary Format
After completing all steps, always produce this exact summary:

✅ Succeeded:
  - Step N: [description]

❌ Failed:
  - Step N: [description] — Reason: [error]

📌 Next steps:
  - [anything the user should do manually, e.g. restart server, run migrations]
"""

coding_agent: Agent[AgentDeps, str] = Agent(
    _model,
    deps_type=AgentDeps,
    system_prompt=EXECUTOR_SYSTEM_PROMPT,
)

logfire.instrument_pydantic_ai(coding_agent)


# --- Read tools (executor) ---

@coding_agent.tool
async def grep_search(
    ctx: RunContext[AgentDeps],
    pattern: str,
    directory: str = ".",
    file_glob: str = "*",
    case_insensitive: bool = False,
    max_results: int = 50,
) -> str:
    """
    Search for *pattern* in files under *directory*.

    Args:
        pattern: Regex or literal string to find.
        directory: Sub-directory to search (default: workspace root).
        file_glob: Filename filter (e.g. "*.py").
        case_insensitive: Case-insensitive search when True.
        max_results: Max matching lines returned.
    """
    return await _grep_search_impl(
        ctx.deps.workspace, pattern, directory, file_glob, case_insensitive, max_results
    )


@coding_agent.tool
async def read_file(
    ctx: RunContext[AgentDeps],
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    Read a file with optional line range.

    Args:
        file_path: Path relative to workspace root.
        start_line: First line to include (1-indexed, inclusive).
        end_line: Last line to include (1-indexed, inclusive).
    """
    return await _read_file_impl(ctx.deps.workspace, file_path, start_line, end_line)


@coding_agent.tool
async def list_directory(
    ctx: RunContext[AgentDeps],
    directory: str = ".",
    recursive: bool = False,
    file_glob: str = "*",
) -> str:
    """
    List files and directories inside *directory*.

    Args:
        directory: Directory to list (default: workspace root).
        recursive: Recurse into sub-directories when True.
        file_glob: Filename filter (e.g. "*.py").
    """
    return await _list_directory_impl(ctx.deps.workspace, directory, recursive, file_glob)


# --- Write tools (executor only) ---

@coding_agent.tool
async def write_file(
    ctx: RunContext[AgentDeps],
    file_path: str,
    content: str,
    overwrite: bool = False,
) -> str:
    """
    Write *content* to a file. Creates parent directories automatically.

    Args:
        file_path: Target path relative to workspace root.
        content: Full text content to write.
        overwrite: Must be True to replace an existing file.
    """
    workspace = ctx.deps.workspace
    resolved = _resolve_path(workspace, file_path)
    if resolved.exists() and not overwrite:
        return (
            f"ERROR: '{file_path}' already exists. "
            "Set overwrite=True to replace it."
        )
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        return f"SUCCESS: Wrote {lines} lines ({len(content):,} bytes) to '{file_path}'."
    except Exception as exc:
        return f"ERROR: Could not write '{file_path}': {exc}"


@coding_agent.tool
async def replace_in_file(
    ctx: RunContext[AgentDeps],
    file_path: str,
    old_content: str,
    new_content: str,
    occurrence: int = 1,
) -> str:
    """
    Surgically replace an exact block of text inside an existing file.

    Args:
        file_path: Target path relative to workspace root.
        old_content: Exact text to find and replace (must match verbatim).
        new_content: Replacement text.
        occurrence: Which match to replace (1=first, -1=last, 0=all).
    """
    workspace = ctx.deps.workspace
    resolved = _resolve_path(workspace, file_path)
    if not resolved.exists():
        return f"ERROR: File '{file_path}' does not exist."
    try:
        original = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"ERROR: Could not read '{file_path}': {exc}"
    count = original.count(old_content)
    if count == 0:
        return (
            f"ERROR: Snippet not found in '{file_path}'.\n"
            "Tip: old_content must match exactly — same whitespace, indentation, line endings."
        )
    if occurrence == 0:
        updated = original.replace(old_content, new_content)
        replaced = count
    elif occurrence > 0:
        idx = -1
        for _ in range(occurrence):
            idx = original.find(old_content, idx + 1)
            if idx == -1:
                return f"ERROR: Only {count} occurrence(s) found; requested #{occurrence}."
        updated = original[:idx] + new_content + original[idx + len(old_content):]
        replaced = 1
    else:
        idx = original.rfind(old_content)
        updated = original[:idx] + new_content + original[idx + len(old_content):]
        replaced = 1
    try:
        resolved.write_text(updated, encoding="utf-8")
    except Exception as exc:
        return f"ERROR: Could not write '{file_path}': {exc}"
    old_lines = old_content.count("\n") + 1
    new_lines = new_content.count("\n") + 1
    return (
        f"SUCCESS: Replaced {replaced} occurrence(s) in '{file_path}'.\n"
        f"  Removed {old_lines} line(s), inserted {new_lines} line(s)."
    )


@coding_agent.tool
async def run_shell(
    ctx: RunContext[AgentDeps],
    command: str,
    cwd: str = ".",
    timeout: int = 30,
) -> str:
    """
    Execute a shell command inside the workspace.

    DISABLED by default — set allow_shell=True in AgentDeps to enable.

    Args:
        command: Shell command (e.g. "python -m pytest tests/").
        cwd: Working directory relative to workspace root.
        timeout: Max seconds to wait.
    """
    if not ctx.deps.allow_shell:
        return (
            "ERROR: Shell execution is disabled. "
            "Pass allow_shell=True to enable this tool."
        )
    workspace = ctx.deps.workspace
    work_dir = _resolve_path(workspace, cwd)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        if len(output) > MAX_READ_CHARS:
            output = output[:MAX_READ_CHARS] + "\n... (truncated)"
        return f"Exit code: {result.returncode}\n\n{output}"
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s."
    except Exception as exc:
        return f"ERROR: {exc}"


# Public API

def run_planner(
    prompt: str,
    workspace: str | None = None,
    allow_shell: bool = False,
) -> Plan:
    """
    Phase 1 — Analyse the request and return a structured Plan.

    The planner only reads files; it never modifies anything.

    Args:
        prompt: Natural-language description of the desired change.
        workspace: Absolute path to the project root.
        allow_shell: Passed to deps (not used in plan phase, but forwarded for context).

    Returns:
        A structured Plan ready for user review.
    """
    deps = AgentDeps(
        workspace=workspace or str(DEFAULT_WORKSPACE),
        allow_shell=allow_shell,
        mode="plan",
    )
    with logfire.span("planner_agent.run", prompt=prompt[:200]):
        result = planner_agent.run_sync(prompt, deps=deps)
    return result.output


def run_coding_agent(
    prompt: str,
    workspace: str | None = None,
    allow_shell: bool = False,
    approved_plan: Plan | None = None,
) -> str:
    """
    Phase 2 — Execute changes using all available tools.

    Should be called only after the user has reviewed and approved the Plan
    returned by run_planner().

    Args:
        prompt: The original user request (for context).
        workspace: Absolute path to the project root.
        allow_shell: Allow shell command execution when True.
        approved_plan: The Plan returned by run_planner() that the user approved.
                       When provided, it is injected as execution context.

    Returns:
        The agent's final response as a plain string (includes success/failure summary).
    """
    deps = AgentDeps(
        workspace=workspace or str(DEFAULT_WORKSPACE),
        allow_shell=allow_shell,
        mode="execute",
    )

    if approved_plan is not None:
        plan_json = approved_plan.model_dump_json(indent=2)
        full_prompt = (
            f"USER REQUEST:\n{prompt}\n\n"
            f"APPROVED PLAN — execute these steps exactly:\n{plan_json}"
        )
    else:
        full_prompt = prompt

    with logfire.span("coding_agent.run", prompt=prompt[:200]):
        result = coding_agent.run_sync(full_prompt, deps=deps)
    return result.output
