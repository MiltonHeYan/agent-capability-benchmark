from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from agent_capability_benchmark import __version__
from agent_capability_benchmark.evidence import load_evidence
from agent_capability_benchmark.fixture_server import start_fixture_server
from agent_capability_benchmark.validation import (
    discover_task_files,
    validate_task_file,
    validate_task_suite,
)
from agent_capability_benchmark.verifier import verify_task_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capability-bench",
        description="Validate and run vendor-neutral capability benchmark assets.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate task JSON files")
    validate.add_argument("paths", nargs="+", type=Path)

    verify = subparsers.add_parser("verify", help="verify normalized evidence for one task")
    verify.add_argument("task", type=Path)
    verify.add_argument("evidence", type=Path)

    serve = subparsers.add_parser(
        "serve-fixtures",
        help="run the loopback-only reference fixture session server",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8765, type=int)
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

    for path in paths:
        if path.is_dir() and (path / "MANIFEST.json").exists():
            errors = validate_task_suite(path)
            if errors:
                failures += 1
                print(f"FAIL {path / 'MANIFEST.json'}")
                for error in errors:
                    print(f"  - {error}")
            else:
                print(f"PASS {path / 'MANIFEST.json'}")

    print(f"Validated {len(task_files)} task file(s); {failures} failed.")
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return _validate(args.paths)
    if args.command == "verify":
        task_errors = validate_task_file(args.task)
        if task_errors:
            for error in task_errors:
                print(f"FAIL {error}")
            return 1
        task = json.loads(args.task.read_text(encoding="utf-8"))
        try:
            evidence = load_evidence(args.evidence)
            result = verify_task_evidence(task, evidence)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"FAIL {error}")
            return 1
        for check in result.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"{status} {check.subject} {check.operator}: {check.detail}")
        print(f"Verified {result.passed_checks}/{len(result.checks)} checks.")
        return 0 if result.passed else 1
    if args.command == "serve-fixtures":
        handle = start_fixture_server(args.host, args.port)
        print(f"Reference fixture server listening at {handle.base_url}")
        try:
            handle.thread.join()
        except KeyboardInterrupt:
            handle.close()
        return 0
    raise AssertionError(f"unhandled command: {args.command}")
