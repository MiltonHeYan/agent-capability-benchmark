from __future__ import annotations

from agent_capability_benchmark.runners.base import RunnerFingerprint


def _fingerprint(**overrides) -> RunnerFingerprint:
    values = {
        "runner": "reference",
        "runner_version": "1.0.0",
        "engine": "example-cli",
        "engine_version": "2.0.0",
        "runtime_image_sha256": "a" * 64,
        "model": "example-model",
        "system_prompt": "fixed prompt",
        "inference_config": {"temperature": 0},
        **overrides,
    }
    return RunnerFingerprint.from_system_prompt(**values)


def test_runner_fingerprint_is_stable() -> None:
    assert _fingerprint().digest == _fingerprint().digest


def test_runner_fingerprint_changes_with_controlled_variables() -> None:
    baseline = _fingerprint().digest

    assert _fingerprint(model="other-model").digest != baseline
    assert _fingerprint(runtime_image_sha256="b" * 64).digest != baseline
    assert _fingerprint(system_prompt="other prompt").digest != baseline
    assert _fingerprint(inference_config={"temperature": 0.2}).digest != baseline
