from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from agent_capability_benchmark import __version__
from agent_capability_benchmark.validation import discover_task_files, validate_task_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capability-bench",
        description="Validate and run vendor-neutral capability benchmark assets.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate task JSON files")
    validate.add_argument("paths", nargs="+", type=Path)
    return parser


def _validate(paths: Sequence[Path]) -> int:
    task_files = discover_task_files(paths)
    if not task_files:
        print("No task JSON files found.")
        return 1

    failures = 0
    for task_file in task_files:
        errors = validate_task_file(task_file)
        if errors:
            failures += 1
            print(f"FAIL {task_file}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {task_file}")

    print(f"Validated {len(task_files)} task file(s); {failures} failed.")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args.paths)
    raise AssertionError(f"unhandled command: {args.command}")
