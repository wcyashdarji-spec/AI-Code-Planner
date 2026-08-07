"""
CLI runner for the PydanticAI Coding Agent — Plan → Approve → Execute.

Usage examples:
  # Interactive REPL (plan + approve + execute)
  python agent_cli.py -w "D:\\Rank Tracker" --allow-shell

  # Single prompt  (plan displayed, then auto-executes)
  python agent_cli.py -w "D:\\Rank Tracker" -p "Add docstring to run_cron"

  # Plan-only (display plan but do NOT execute — useful for reviewing)
  python agent_cli.py -w "D:\\Rank Tracker" --plan-only -p "Refactor tracker_service"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make sure the project root is on sys.path when running standalone
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from code_agent import (
    Plan,
    PlanStep,
    run_planner,
    run_coding_agent,
    DEFAULT_WORKSPACE,
)

# ANSI colour helpers (degrade gracefully on Windows without VT support)

try:
    import colorama
    colorama.init(autoreset=True)
    _GREEN  = "\033[92m"
    _YELLOW = "\033[93m"
    _RED    = "\033[91m"
    _CYAN   = "\033[96m"
    _BOLD   = "\033[1m"
    _RESET  = "\033[0m"
except ImportError:
    _GREEN = _YELLOW = _RED = _CYAN = _BOLD = _RESET = ""


def _c(text: str, colour: str) -> str:
    return f"{colour}{text}{_RESET}"


# Banner

BANNER = f"""{_BOLD}
╔══════════════════════════════════════════════════════════════╗
║        PydanticAI  Coding  Agent  —  Plan→Execute           ║
║                                                              ║
║  Phase 1  🔍  Planner reads & analyses your codebase        ║
║  Phase 2  ✅  You approve the plan                          ║
║  Phase 3  🚀  Executor makes the changes                     ║
║                                                              ║
║  REPL commands:  exit | quit | q                             ║
╚══════════════════════════════════════════════════════════════╝{_RESET}"""


# Plan display

_RISK_ICON = {
    "low":    ("🟢", _GREEN),
    "medium": ("🟡", _YELLOW),
    "high":   ("🔴", _RED),
}

_ACTION_ICON = {
    "read":    "📖",
    "grep":    "🔍",
    "list":    "📁",
    "write":   "✏️ ",
    "replace": "✂️ ",
    "shell":   "⚡",
}


def _display_plan(plan: Plan) -> None:
    """Pretty-print the Plan for user review."""
    icon, colour = _RISK_ICON.get(plan.risk_level, ("⚪", _RESET))
    sep = "─" * 64

    print(f"\n{sep}")
    print(f"  {_c('📋  PLAN:', _BOLD)} {_c(plan.title, _CYAN)}")
    print(f"  {_c('Risk:', _BOLD)} {icon} {_c(plan.risk_level.upper(), colour)}")
    print(sep)

    print(f"\n  {_c('💡 Reasoning:', _BOLD)}")
    for line in plan.reasoning.strip().splitlines():
        print(f"     {line}")

    print(f"\n  {_c('📂 Affected files:', _BOLD)}")
    for f in plan.affected_files:
        print(f"     • {f}")

    print(f"\n  {_c('🗒  Steps:', _BOLD)}")
    for step in plan.steps:
        a_icon = _ACTION_ICON.get(step.action, "•")
        print(f"\n   Step {step.step_number} [{_c(step.action.upper(), _CYAN)}] {a_icon}")
        print(f"   {step.description}")
        if step.file_path:
            print(f"   File    : {step.file_path}")
        if step.command:
            print(f"   Command : {step.command}")
        if step.old_snippet:
            snippet = step.old_snippet[:120].replace("\n", "↵")
            print(f"   Remove  : {_c(snippet + ('…' if len(step.old_snippet) > 120 else ''), _RED)}")
        if step.new_snippet:
            snippet = step.new_snippet[:120].replace("\n", "↵")
            print(f"   Insert  : {_c(snippet + ('…' if len(step.new_snippet) > 120 else ''), _GREEN)}")

    if plan.risk_notes:
        print(f"\n  {_c('⚠️  Risk notes:', _BOLD)} {plan.risk_notes}")

    print(f"\n{sep}")


# Core two-phase flow

def _run_with_approval(
    initial_prompt: str,
    workspace: str,
    allow_shell: bool,
    auto_execute: bool = False,
) -> None:
    """
    Run the full Plan → Approve → Execute cycle.

    Args:
        initial_prompt: The user's natural-language request.
        workspace: Absolute workspace path.
        allow_shell: Enable shell execution in the executor.
        auto_execute: If True, skip the approval prompt and execute automatically
                      (used in non-interactive --prompt mode).
    """
    prompt = initial_prompt

    while True:
        # ── Phase 1: Plan ──────────────────────────────────────────────────
        print(f"\n{_c('🔍  Planning...', _CYAN)} (reading files, this may take a moment)")
        try:
            plan = run_planner(prompt, workspace=workspace, allow_shell=allow_shell)
        except Exception as exc:
            print(f"{_c('❌  Planner failed:', _RED)} {exc}", file=sys.stderr)
            return

        _display_plan(plan)

        # ── Phase 2: Approval ──────────────────────────────────────────────
        if auto_execute:
            print(f"{_c('⚡  Auto-executing (non-interactive mode)...', _YELLOW)}")
            decision = "yes"
        else:
            try:
                decision = input(
                    f"  {_c('Approve?', _BOLD)} "
                    f"[{_c('yes', _GREEN)} / {_c('no', _RED)} / {_c('edit', _YELLOW)}] > "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{_c('⚠️  Aborted.', _YELLOW)}")
                return

        if decision in {"yes", "y", "approve", "ok"}:
            # ── Phase 3: Execute ───────────────────────────────────────────
            print(f"\n{_c('🚀  Executing...', _GREEN)}")
            print("─" * 64)
            try:
                result = run_coding_agent(
                    prompt=initial_prompt,
                    workspace=workspace,
                    allow_shell=allow_shell,
                    approved_plan=plan,
                )
                print(result)
            except Exception as exc:
                print(f"{_c('❌  Executor failed:', _RED)} {exc}", file=sys.stderr)
            print("─" * 64)
            return

        elif decision in {"no", "n", "cancel", "abort"}:
            print(f"{_c('⚠️  Cancelled — no files were changed.', _YELLOW)}")
            return

        elif decision in {"edit", "e", "revise"}:
            # Let the user refine the prompt and re-plan
            try:
                new_prompt = input(
                    f"  {_c('Revised prompt', _BOLD)} (or Enter to keep original) > "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{_c('⚠️  Aborted.', _YELLOW)}")
                return
            if new_prompt:
                prompt = new_prompt
            print(f"{_c('↩  Re-planning with updated prompt...', _CYAN)}")
            # loop back to Phase 1

        else:
            print(
                f"  {_c('Unknown response.', _YELLOW)} "
                f"Please type {_c('yes', _GREEN)}, {_c('no', _RED)}, or {_c('edit', _YELLOW)}."
            )
            # loop back to approval prompt


# Argument parsing

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "PydanticAI Coding Agent CLI — Plan → Approve → Execute.\n"
            "The agent first analyses your codebase and proposes a plan.\n"
            "You review and approve before any file is modified."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default=None,
        help="Single prompt (non-interactive). Plan is displayed then auto-executed.",
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        default=str(DEFAULT_WORKSPACE),
        help=f"Absolute path to the workspace root. Default: {DEFAULT_WORKSPACE}",
    )
    parser.add_argument(
        "--allow-shell",
        action="store_true",
        default=False,
        help="Allow the executor to run shell commands.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        default=False,
        help="Display the plan but do NOT execute (even with --prompt).",
    )
    return parser.parse_args()


# REPL

def _repl(workspace: str, allow_shell: bool) -> None:
    """Interactive Plan → Approve → Execute REPL."""
    print(BANNER)
    print(f"  {_c('📁 Workspace', _BOLD)} : {workspace}")
    print(f"  {_c('🔧 Shell    ', _BOLD)} : {'enabled' if allow_shell else 'disabled'}")
    print(f"  {_c('💡 Tip      ', _BOLD)} : Type a change request to start planning.\n")

    while True:
        try:
            prompt = input(f"{_c('You', _BOLD)} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{_c('👋  Goodbye!', _CYAN)}")
            break

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", "q"}:
            print(f"{_c('👋  Goodbye!', _CYAN)}")
            break

        _run_with_approval(prompt, workspace=workspace, allow_shell=allow_shell)


# Entry point

def main() -> None:
    args = _parse_args()

    if args.prompt:
        if args.plan_only:
            # Just show the plan, do not execute
            print(f"\n{_c('🔍  Planning...', _CYAN)}")
            try:
                plan = run_planner(args.prompt, workspace=args.workspace, allow_shell=args.allow_shell)
                _display_plan(plan)
                print(f"{_c('ℹ️  --plan-only mode: nothing was executed.', _YELLOW)}")
            except Exception as exc:
                print(f"{_c('❌  Planner failed:', _RED)} {exc}", file=sys.stderr)
        else:
            # Non-interactive: plan then auto-execute
            _run_with_approval(
                args.prompt,
                workspace=args.workspace,
                allow_shell=args.allow_shell,
                auto_execute=True,
            )
    else:
        # Interactive REPL
        _repl(workspace=args.workspace, allow_shell=args.allow_shell)


if __name__ == "__main__":
    main()
