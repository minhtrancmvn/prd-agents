from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ValidationError:
    path: str
    code: str
    message: str


ALLOWED_PHASE_STATUSES = {
    "SUCCESS",
    "SUCCESS_WITH_WARNINGS",
    "SKIPPED",
    "BLOCKED",
    "FAILED",
}

ALLOWED_DOCUMENT_TYPES = {
    "Use Case",
    "Notification",
    "Email Template",
    "UNKNOWN",
}

ALLOWED_MODES = {"CREATE", "UPDATE", "UNKNOWN"}

ALLOWED_ERROR_CODES = {
    "NONE",
    "INPUT_INVALID",
    "WORKSPACE_NOT_FOUND",
    "PLAN_INCOMPLETE",
    "ROLES_FILE_NOT_FOUND",
    "RISK_ITEMS_FOUND",
    "FIGMA_READ_FAILURE",
    "AUTHOR_INPUT_INVALID",
    "AUTHOR_WRITE_FAILURE",
    "CHECKLIST_FAILED",
    "QA_RETRY_EXHAUSTED",
    "CONSOLIDATION_REGRESSION",
    "VALIDATION_FAILED",
}

REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "run_id",
    "phase",
    "phase_number",
    "agent",
    "status",
    "document_type",
    "mode",
    "target_path",
    "artifact_dir",
    "completed_checks",
    "unresolved_items",
    "next_agent",
    "error_code",
    "error_details",
    "retry_count",
    "retry_limit",
    "consolidation_attempts",
    "qa_verdict",
    "terminal",
    "artifacts",
}

_TEMPLATE_PATTERNS = (
    re.compile(r"<[^>]+>"),
    re.compile(r"TBD"),
    re.compile(r"TODO"),
    re.compile(r"\[PLACEHOLDER\]"),
    re.compile(r"\[INSERT\]"),
)


def _error(path: Path, code: str, message: str) -> ValidationError:
    return ValidationError(str(path), code, message)


def _sorted(errors: list[ValidationError]) -> list[ValidationError]:
    return sorted(errors, key=lambda item: (item.path, item.code, item.message))


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def validate_package(skill_root: Path) -> list[ValidationError]:
    """Validate required files and structural terms in a pipeline package."""
    errors: list[ValidationError] = []
    required_files = {
        "SKILL.md": "missing_skill",
        "references/prd-pipeline-contract.md": "missing_contract",
        "references/prd-artifact-format.md": "missing_artifact_format",
        "scripts/validate-prd-pipeline.py": "missing_validator",
        "tests/test_validate_prd_pipeline.py": "missing_tests",
    }
    for relative_path, code in required_files.items():
        path = skill_root / relative_path
        if not _non_empty_file(path):
            errors.append(_error(path, code, "required non-empty file is missing"))

    skill_path = skill_root / "SKILL.md"
    if skill_path.is_file():
        skill_text = skill_path.read_text(encoding="utf-8")
        for term in (
            "name: prd-pipeline",
            "description:",
            "version:",
            "user-invocable: true",
            "allowed-tools:",
            "### Phase 0: LOAD",
            "### Phase 1: PLAN",
            "### Phase 2: CONTEXT AND ROLES",
            "### Phase 3: FIGMA",
            "### Phase 4: AUTHOR",
            "### Phase 5: QA",
            "### Phase 6: REPAIR AND RECHECK",
            "### Phase 7: REPORT",
        ):
            if term not in skill_text:
                errors.append(_error(skill_path, "invalid_skill", f"missing required term: {term}"))
    return _sorted(errors)


def _contains_template(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _TEMPLATE_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_template(key) or _contains_template(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_template(item) for item in value)
    return False


def _complexity_for_manifests(manifests: list[tuple[Path, dict[str, Any]]]) -> str | None:
    for _, manifest in manifests:
        complexity = manifest.get("complexity")
        if complexity in {"Simple", "Complex"}:
            return complexity
    return None


def _validate_artifacts(phase_dir: Path, manifest: dict[str, Any], errors: list[ValidationError]) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append(_error(phase_dir / "manifest.json", "invalid_artifacts", "artifacts must be a list"))
        return
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            errors.append(_error(phase_dir / "manifest.json", "invalid_artifact", "each artifact needs a relative path"))
            continue
        relative_path = Path(artifact["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(_error(phase_dir / "manifest.json", "invalid_artifact_path", "artifact path must stay inside phase directory"))
            continue
        artifact_path = phase_dir / relative_path
        if not artifact_path.is_file():
            errors.append(_error(artifact_path, "missing_artifact", "manifest artifact does not exist"))


def validate_run(run_dir: Path) -> list[ValidationError]:
    """Validate phase manifests and paired content artifacts in a run directory."""
    errors: list[ValidationError] = []
    if not run_dir.is_dir():
        return [_error(run_dir, "missing_run", "run directory does not exist")]

    phase_dirs = sorted(path for path in run_dir.iterdir() if path.is_dir())
    manifests: list[tuple[Path, dict[str, Any]]] = []
    for phase_dir in phase_dirs:
        manifest_path = phase_dir / "manifest.json"
        content_path = phase_dir / "content.md"
        if not manifest_path.is_file():
            errors.append(_error(manifest_path, "missing_manifest", "phase requires manifest.json"))
            continue
        if not content_path.is_file():
            errors.append(_error(content_path, "missing_content", "phase requires content.md"))
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(_error(manifest_path, "invalid_json", f"manifest must contain valid JSON: {exc}"))
            continue
        if not isinstance(parsed, dict):
            errors.append(_error(manifest_path, "manifest_not_object", "manifest JSON must be an object"))
            continue
        manifest = parsed
        manifests.append((phase_dir, manifest))
        missing_keys = REQUIRED_MANIFEST_KEYS - manifest.keys()
        for key in sorted(missing_keys):
            errors.append(_error(manifest_path, "missing_manifest_key", f"missing required key: {key}"))
        if _contains_template(manifest):
            errors.append(_error(manifest_path, "unresolved_template", "manifest contains unresolved template token"))
        _validate_manifest(phase_dir, manifest, errors)
        _validate_artifacts(phase_dir, manifest, errors)

    if not any(path.name == "07-summary" for path in phase_dirs):
        errors.append(_error(run_dir / "07-summary", "missing_summary", "run requires 07-summary phase"))

    complexity = _complexity_for_manifests(manifests)
    if complexity is not None:
        expected_limit = 1 if complexity == "Simple" else 2
        for phase_dir, manifest in manifests:
            retry_limit = manifest.get("retry_limit")
            if retry_limit != expected_limit:
                errors.append(_error(phase_dir / "manifest.json", "invalid_retry_limit", f"retry_limit must be {expected_limit} for {complexity}"))
    for phase_dir, manifest in manifests:
        retry_count = manifest.get("retry_count")
        retry_limit = manifest.get("retry_limit")
        if isinstance(retry_count, int) and isinstance(retry_limit, int) and retry_count > retry_limit:
            errors.append(_error(phase_dir / "manifest.json", "retry_count_exceeded", "retry_count must not exceed retry_limit"))
    return _sorted(errors)


def _validate_manifest(phase_dir: Path, manifest: dict[str, Any], errors: list[ValidationError]) -> None:
    path = phase_dir / "manifest.json"
    status = manifest.get("status")
    if status not in ALLOWED_PHASE_STATUSES:
        errors.append(_error(path, "unknown_status", f"status must be one of {sorted(ALLOWED_PHASE_STATUSES)}"))
    if manifest.get("document_type") not in ALLOWED_DOCUMENT_TYPES:
        errors.append(_error(path, "unknown_document_type", "document_type is not allowed"))
    if manifest.get("mode") not in ALLOWED_MODES:
        errors.append(_error(path, "unknown_mode", "mode is not allowed"))
    if manifest.get("error_code") not in ALLOWED_ERROR_CODES:
        errors.append(_error(path, "unknown_error_code", "error_code is not allowed"))
    artifact_dir = manifest.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not Path(artifact_dir).is_absolute():
        errors.append(_error(path, "relative_artifact_dir", "artifact_dir must be absolute"))
    target_path = manifest.get("target_path")
    if target_path and (not isinstance(target_path, str) or not Path(target_path).is_absolute()):
        errors.append(_error(path, "relative_target_path", "target_path must be absolute"))
    retry_count = manifest.get("retry_count")
    retry_limit = manifest.get("retry_limit")
    consolidation_attempts = manifest.get("consolidation_attempts")
    if not isinstance(retry_count, int) or not isinstance(retry_limit, int):
        errors.append(_error(path, "invalid_retry_count", "retry_count and retry_limit must be integers"))
    if not isinstance(consolidation_attempts, int):
        errors.append(_error(path, "invalid_consolidation_attempts", "consolidation_attempts must be an integer"))
    elif consolidation_attempts > 1:
        errors.append(_error(path, "consolidation_attempts_exceeded", "consolidation_attempts must not exceed one"))
    if manifest.get("terminal") is True:
        if status == "SUCCESS" and manifest.get("qa_verdict") != "CHECKLIST_PASSED":
            errors.append(_error(path, "terminal_success_without_checklist", "terminal success requires CHECKLIST_PASSED"))
        if status in {"BLOCKED", "FAILED"} and (
            manifest.get("error_code") == "NONE" or manifest.get("next_agent") != "STOP"
        ):
            errors.append(_error(path, "invalid_terminal_failure", "terminal blocked/failed result needs error code and STOP next_agent"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate canonical PRD pipeline packages and runs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("--skill-root", required=True, type=Path)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--run-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run package or run validation and print deterministic findings."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    if args.command == "package":
        path = args.skill_root
        errors = validate_package(path)
    else:
        path = args.run_dir
        errors = validate_run(path)
    if not errors:
        print(f"PASS {path}")
        return 0
    for error in errors:
        print(f"ERROR {error.code} {error.path}: {error.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
