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
ALLOWED_COMPLEXITIES = {"Simple", "Complex", "UNKNOWN"}

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
    "DOCUMENT_NOT_FOUND",
}

CONTRACT_REQUIRED_TERMS = {
    "STATUS:",
    "DOCUMENT_TYPE:",
    "MODE:",
    "TARGET_PATH:",
    "ERROR_CODE:",
    "CHECKLIST_PASSED",
    "QA_RETRY_EXHAUSTED",
    "CONSOLIDATION_REGRESSION",
}

ARTIFACT_REQUIRED_TERMS = {
    "manifest.json",
    "content.md",
    "schema_version",
    "retry_count",
    "consolidation_attempts",
    "qa_verdict",
    "07-summary",
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
    "complexity",
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

REQUIRED_PHASE_DIRS = {
    "00-load",
    "01-plan",
    "02-context",
    "03-figma",
    "04-author",
    "07-summary",
}

HANDOFF_FIELDS = (
    ("STATUS", "status"),
    ("AGENT", "agent"),
    ("PHASE", "phase"),
    ("DOCUMENT_TYPE", "document_type"),
    ("MODE", "mode"),
    ("TARGET_PATH", "target_path"),
    ("ARTIFACT_DIR", "artifact_dir"),
    ("COMPLETED_CHECKS", "completed_checks"),
    ("UNRESOLVED_ITEMS", "unresolved_items"),
    ("NEXT_AGENT", "next_agent"),
    ("ERROR_CODE", "error_code"),
    ("ERROR_DETAILS", "error_details"),
)

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

    reference_terms = {
        "references/prd-pipeline-contract.md": ("invalid_contract", CONTRACT_REQUIRED_TERMS),
        "references/prd-artifact-format.md": ("invalid_artifact_format", ARTIFACT_REQUIRED_TERMS),
    }
    for relative_path, (code, terms) in reference_terms.items():
        path = skill_root / relative_path
        if path.is_file():
            reference_text = path.read_text(encoding="utf-8")
            for term in sorted(terms):
                if term not in reference_text:
                    errors.append(_error(path, code, f"missing required term: {term}"))
    return _sorted(errors)


def _contains_template(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _TEMPLATE_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_template(key) or _contains_template(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_template(item) for item in value)
    return False


def _format_handoff_value(value: Any) -> str:
    if isinstance(value, list):
        return ";".join(str(item) for item in value) if value else "NONE"
    return str(value)


def _validate_handoff(content_path: Path, manifest: dict[str, Any], errors: list[ValidationError]) -> str:
    if not content_path.is_file():
        return ""
    content_lines = content_path.read_text(encoding="utf-8").splitlines()
    handoff_lines = content_lines[:len(HANDOFF_FIELDS)]
    if len(handoff_lines) < len(HANDOFF_FIELDS):
        errors.append(_error(content_path, "missing_handoff_field", "handoff envelope must contain all required fields"))
    for index, (field, manifest_key) in enumerate(HANDOFF_FIELDS):
        if index >= len(handoff_lines):
            errors.append(_error(content_path, "missing_handoff_field", f"missing handoff field: {field}"))
            continue
        prefix = f"{field}:"
        line = handoff_lines[index]
        if not line.startswith(prefix):
            errors.append(_error(content_path, "invalid_handoff_order", f"expected handoff field {field} at line {index + 1}"))
            continue
        value = line[len(prefix):].strip()
        if value != _format_handoff_value(manifest.get(manifest_key)):
            errors.append(_error(content_path, "handoff_mismatch", f"{field} does not match manifest {manifest_key}"))
    return "\n".join(content_lines[len(HANDOFF_FIELDS):]).strip()


def _validate_artifacts(phase_dir: Path, manifest: dict[str, Any], errors: list[ValidationError]) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append(_error(phase_dir / "manifest.json", "invalid_artifacts", "artifacts must be a list"))
        return
    content_entries = [artifact for artifact in artifacts if isinstance(artifact, dict) and artifact.get("path") == "content.md"]
    if len(content_entries) != 1:
        errors.append(_error(phase_dir / "manifest.json", "invalid_content_artifact", "artifacts must contain exactly one content.md entry"))
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


def _is_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _validate_manifest(
    phase_dir: Path,
    manifest: dict[str, Any],
    run_dir: Path,
    errors: list[ValidationError],
) -> None:
    path = phase_dir / "manifest.json"
    status = manifest.get("status")
    if status not in ALLOWED_PHASE_STATUSES:
        errors.append(_error(path, "unknown_status", f"status must be one of {sorted(ALLOWED_PHASE_STATUSES)}"))
    if manifest.get("document_type") not in ALLOWED_DOCUMENT_TYPES:
        errors.append(_error(path, "unknown_document_type", "document_type is not allowed"))
    if manifest.get("mode") not in ALLOWED_MODES:
        errors.append(_error(path, "unknown_mode", "mode is not allowed"))
    if manifest.get("complexity") not in ALLOWED_COMPLEXITIES:
        errors.append(_error(path, "unknown_complexity", "complexity is not allowed"))
    if manifest.get("error_code") not in ALLOWED_ERROR_CODES:
        errors.append(_error(path, "unknown_error_code", "error_code is not allowed"))
    artifact_dir = manifest.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not Path(artifact_dir).is_absolute():
        errors.append(_error(path, "relative_artifact_dir", "artifact_dir must be absolute"))
    elif Path(artifact_dir).resolve() != run_dir:
        errors.append(_error(path, "artifact_dir_mismatch", "artifact_dir must equal resolved run directory"))
    target_path = manifest.get("target_path")
    if not isinstance(target_path, str):
        errors.append(_error(path, "invalid_target_path", "target_path must be a string or empty"))
    elif target_path and not Path(target_path).is_absolute():
        errors.append(_error(path, "relative_target_path", "target_path must be absolute"))

    retry_count = manifest.get("retry_count")
    retry_limit = manifest.get("retry_limit")
    consolidation_attempts = manifest.get("consolidation_attempts")
    if not _is_nonnegative_int(retry_count):
        errors.append(_error(path, "invalid_retry_count", "retry_count must be a non-negative integer"))
    if not _is_nonnegative_int(retry_limit):
        errors.append(_error(path, "invalid_retry_limit", "retry_limit must be a non-negative integer"))
    if not _is_nonnegative_int(consolidation_attempts):
        errors.append(_error(path, "invalid_consolidation_attempts", "consolidation_attempts must be a non-negative integer"))
    elif consolidation_attempts > 1:
        errors.append(_error(path, "consolidation_attempts_exceeded", "consolidation_attempts must not exceed one"))

    complexity = manifest.get("complexity")
    if complexity in {"Simple", "Complex"} and _is_nonnegative_int(retry_limit):
        expected_limit = 1 if complexity == "Simple" else 2
        if retry_limit != expected_limit:
            errors.append(_error(path, "invalid_retry_limit", f"retry_limit must be {expected_limit} for {complexity}"))
    if _is_nonnegative_int(retry_count) and _is_nonnegative_int(retry_limit) and retry_count > retry_limit:
        errors.append(_error(path, "retry_count_exceeded", "retry_count must not exceed retry_limit"))

    if manifest.get("terminal") is True:
        if status == "SUCCESS" and manifest.get("qa_verdict") != "CHECKLIST_PASSED":
            errors.append(_error(path, "terminal_success_without_checklist", "terminal success requires CHECKLIST_PASSED"))
        if status in {"BLOCKED", "FAILED"} and (
            manifest.get("error_code") == "NONE" or manifest.get("next_agent") != "STOP"
        ):
            errors.append(_error(path, "invalid_terminal_failure", "terminal blocked/failed result needs error code and STOP next_agent"))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_run(run_dir: Path, repository_root: Path | None = None) -> list[ValidationError]:
    """Validate phase manifests and paired content artifacts in a run directory."""
    errors: list[ValidationError] = []
    if not run_dir.is_dir():
        return [_error(run_dir, "missing_run", "run directory does not exist")]

    resolved_run_dir = run_dir.resolve()
    if repository_root is not None and _is_within(resolved_run_dir, repository_root.resolve()):
        return [_error(run_dir, "run_dir_inside_repository", "run directory must be outside repository root")]

    phase_dirs = sorted(path for path in resolved_run_dir.iterdir() if path.is_dir())
    phase_names = {path.name for path in phase_dirs}
    for required_phase in sorted(REQUIRED_PHASE_DIRS - phase_names):
        code = "missing_summary" if required_phase == "07-summary" else "missing_phase"
        errors.append(_error(resolved_run_dir / required_phase, code, "required phase directory is missing"))

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
        missing_keys = REQUIRED_MANIFEST_KEYS - manifest.keys()
        for key in sorted(missing_keys):
            errors.append(_error(manifest_path, "missing_manifest_key", f"missing required key: {key}"))
        if _contains_template(manifest):
            errors.append(_error(manifest_path, "unresolved_template", "manifest contains unresolved template token"))
        _validate_manifest(phase_dir, manifest, resolved_run_dir, errors)
        _validate_artifacts(phase_dir, manifest, errors)
        body = _validate_handoff(content_path, manifest, errors)
        if phase_dir.name == "03-figma" and manifest.get("status") == "SKIPPED" and not body:
            errors.append(_error(content_path, "missing_skipped_figma_reason", "skipped Figma content requires a non-empty reason"))
    return _sorted(errors)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate canonical PRD pipeline packages and runs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("--skill-root", required=True, type=Path)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--run-dir", required=True, type=Path)
    run_parser.add_argument("--repository-root", type=Path)
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
        errors = validate_run(path, args.repository_root)
    if not errors:
        print(f"PASS {path}")
        return 0
    for error in errors:
        print(f"ERROR {error.code} {error.path}: {error.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
