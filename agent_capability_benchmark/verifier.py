from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MISSING = object()


@dataclass(frozen=True)
class CheckResult:
    subject: str
    operator: str
    passed: bool
    actual: Any
    expected: Any
    detail: str


@dataclass(frozen=True)
class VerificationResult:
    task_id: str
    run_id: str
    passed: bool
    checks: tuple[CheckResult, ...]

    @property
    def passed_checks(self) -> int:
        return sum(check.passed for check in self.checks)


def verify_task_evidence(
    task: dict[str, Any],
    evidence: dict[str, Any],
) -> VerificationResult:
    task_id = task.get("id", "")
    if evidence.get("task_id") != task_id:
        raise ValueError(
            f"evidence task_id {evidence.get('task_id')!r} does not match task {task_id!r}"
        )

    observations = evidence.get("observations", {})
    baseline = evidence.get("baseline", {})
    references = evidence.get("references", {})
    results = tuple(
        _evaluate_check(
            check,
            observations=observations,
            baseline=baseline,
            references=references,
        )
        for check in task["verifier"]["checks"]
    )
    return VerificationResult(
        task_id=task_id,
        run_id=evidence["run_id"],
        passed=all(result.passed for result in results),
        checks=results,
    )


def _evaluate_check(
    check: dict[str, Any],
    *,
    observations: dict[str, Any],
    baseline: dict[str, Any],
    references: dict[str, Any],
) -> CheckResult:
    subject = check["subject"]
    operator = check["operator"]
    actual = _resolve_path(observations, subject)
    expected = _resolve_expected(check, references)

    if operator == "equals":
        passed = actual is not _MISSING and actual == expected
    elif operator == "contains":
        passed = actual is not _MISSING and _contains(actual, expected)
    elif operator == "count-equals":
        count = (
            len(actual) if hasattr(actual, "__len__") and not isinstance(actual, int) else actual
        )
        passed = actual is not _MISSING and count == expected
    elif operator == "exists":
        passed = actual is not _MISSING
    elif operator == "not-exists":
        passed = actual is _MISSING
    elif operator == "unchanged":
        baseline_value = _resolve_path(baseline, subject)
        expected = baseline_value
        passed = (
            actual is not _MISSING and baseline_value is not _MISSING and actual == baseline_value
        )
    elif operator == "less-than-or-equal":
        passed = (
            actual is not _MISSING
            and isinstance(actual, int | float)
            and isinstance(expected, int | float)
            and actual <= expected
        )
    else:
        raise ValueError(f"unsupported verifier operator: {operator}")

    display_actual = None if actual is _MISSING else actual
    display_expected = None if expected is _MISSING else expected
    detail = "passed" if passed else f"expected {display_expected!r}, observed {display_actual!r}"
    return CheckResult(
        subject=subject,
        operator=operator,
        passed=passed,
        actual=display_actual,
        expected=display_expected,
        detail=detail,
    )


def _resolve_expected(check: dict[str, Any], references: dict[str, Any]) -> Any:
    if "expected_ref" in check:
        return references.get(check["expected_ref"], _MISSING)
    return check.get("expected", _MISSING)


def _resolve_path(root: Any, path: str) -> Any:
    current = root
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < len(current):
                current = current[index]
                continue
        else:
            return _MISSING
        return _MISSING
    return current


def _contains(actual: Any, expected: Any) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return expected.casefold() in actual.casefold()
    if isinstance(actual, dict):
        return expected in actual
    if isinstance(actual, list | tuple | set):
        return expected in actual
    return False
