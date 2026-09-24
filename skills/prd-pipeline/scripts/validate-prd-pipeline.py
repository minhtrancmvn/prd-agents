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
    "Early terminal layout",
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

BASE_PHASES = (
    ("00-load", "LOAD"),
    ("01-plan", "PLAN"),
    ("02-context", "CONTEXT"),
    ("03-figma", "FIGMA"),
    ("04-author", "AUTHOR"),
)
SUMMARY_DIRECTORY = "07-summary"
EARLY_TERMINAL_ERRORS = {
    "LOAD": {"INPUT_INVALID", "WORKSPACE_NOT_FOUND"},
    "PLAN": {"PLAN_INCOMPLETE"},
    "CONTEXT": {"ROLES_FILE_NOT_FOUND", "RISK_ITEMS_FOUND"},
    "FIGMA": {"FIGMA_READ_FAILURE"},
    "AUTHOR": {"AUTHOR_INPUT_INVALID", "AUTHOR_WRITE_FAILURE"},
}

QA_DIRECTORY_PATTERN = re.compile(r"05-qa-attempt-([1-9]\d*)")
REPAIR_DIRECTORY_PATTERN = re.compile(r"06-repair-attempt-([1-9]\d*)")
CONSOLIDATION_DIRECTORY = "06-consolidation-attempt-1"
REPAIR_SKIPPED_DIRECTORY = "06-repair-skipped"

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
    if complexity in {"Simple", "Complex", "UNKNOWN"} and _is_nonnegative_int(retry_limit):
        expected_limit = 1 if complexity == "Simple" else 2 if complexity == "Complex" else 0
        if retry_limit != expected_limit:
            errors.append(_error(path, "invalid_retry_limit", f"retry_limit must be {expected_limit} for {complexity}"))
    if _is_nonnegative_int(retry_count) and _is_nonnegative_int(retry_limit) and retry_count > retry_limit:
        errors.append(_error(path, "retry_count_exceeded", "retry_count must not exceed retry_limit"))

    if manifest.get("phase") == "QA" and manifest.get("qa_verdict") == "CHECKLIST_FAILED":
        expected_author = {
            "Use Case": "prd-author",
            "Notification": "prd-noti-req-author",
            "Email Template": "prd-email-req-author",
        }.get(manifest.get("document_type"))
        if not (
            status == "SUCCESS"
            and manifest.get("error_code") == "CHECKLIST_FAILED"
            and manifest.get("terminal") is False
            and manifest.get("next_agent") == expected_author
        ):
            errors.append(_error(path, "invalid_qa_repair_mapping", "CHECKLIST_FAILED QA must map to its document-type author"))
    if manifest.get("terminal") is True:
        if status == "SUCCESS" and manifest.get("qa_verdict") != "CHECKLIST_PASSED":
            errors.append(_error(path, "terminal_success_without_checklist", "terminal success requires CHECKLIST_PASSED"))
        if status in {"BLOCKED", "FAILED"} and (
            manifest.get("error_code") == "NONE" or manifest.get("next_agent") != "STOP"
        ):
            errors.append(_error(path, "invalid_terminal_failure", "terminal blocked/failed result needs error code and STOP next_agent"))


def _validate_base_phase_topology(
    run_dir: Path,
    phase_names: set[str],
    manifests: dict[str, dict[str, Any]],
    errors: list[ValidationError],
) -> bool:
    """Validate contiguous pre-QA phases and allow an early terminal summary."""
    names = set(phase_names)
    summary = manifests.get(SUMMARY_DIRECTORY)
    if summary is None:
        return False

    present_indices = [index for index, (directory, _) in enumerate(BASE_PHASES) if directory in names]
    expected_indices = list(range(len(present_indices)))
    if present_indices != expected_indices:
        errors.append(_error(run_dir, "invalid_phase_topology", "base phases must form a contiguous prefix from LOAD"))
        return False
    if not present_indices:
        errors.append(_error(run_dir, "invalid_phase_topology", "run requires LOAD before summary"))
        return False

    for directory, phase in BASE_PHASES:
        manifest = manifests.get(directory)
        if manifest is not None and manifest.get("phase") != phase:
            errors.append(_error(run_dir / directory / "manifest.json", "invalid_phase_topology", f"{directory} must declare phase {phase}"))

    reached_qa = any(name.startswith("05-qa-attempt-") for name in names)
    if summary.get("status") == "SUCCESS":
        if len(present_indices) != len(BASE_PHASES) or not reached_qa:
            errors.append(_error(run_dir / SUMMARY_DIRECTORY / "manifest.json", "invalid_success_terminal_topology", "successful summary requires all base phases and QA"))
        return reached_qa

    if summary.get("status") not in {"BLOCKED", "FAILED"}:
        return reached_qa

    if reached_qa:
        if len(present_indices) != len(BASE_PHASES):
            errors.append(_error(run_dir, "invalid_phase_topology", "QA requires all base phases"))
        return True

    terminal_index = present_indices[-1]
    terminal_directory, terminal_phase = BASE_PHASES[terminal_index]
    terminal_manifest = manifests[terminal_directory]
    allowed_directories = {directory for directory, _ in BASE_PHASES[:terminal_index + 1]} | {SUMMARY_DIRECTORY}
    unexpected_directories = names - allowed_directories
    if unexpected_directories:
        errors.append(_error(run_dir, "invalid_phase_topology", "early terminal run contains unapproved phase directories"))

    preceding_manifests = (manifests[directory] for directory, _ in BASE_PHASES[:terminal_index])
    if any(
        manifest.get("status") != "SUCCESS"
        or manifest.get("terminal") is not False
        or manifest.get("error_code") != "NONE"
        for manifest in preceding_manifests
    ):
        errors.append(_error(run_dir, "invalid_terminal_topology", "early terminal preceding base phases must be successful non-terminal results"))

    allowed_errors = EARLY_TERMINAL_ERRORS[terminal_phase]
    if not (
        terminal_manifest.get("status") in {"BLOCKED", "FAILED"}
        and terminal_manifest.get("terminal") is False
        and terminal_manifest.get("error_code") in allowed_errors
        and summary.get("terminal") is True
        and summary.get("status") == terminal_manifest.get("status")
        and summary.get("error_code") == terminal_manifest.get("error_code")
    ):
        errors.append(_error(run_dir / SUMMARY_DIRECTORY / "manifest.json", "invalid_terminal_topology", "early terminal summary must match valid failed or blocked final phase"))
    return False


def _validate_qa_repair_sequence(
    run_dir: Path,
    manifests: dict[str, dict[str, Any]],
    errors: list[ValidationError],
) -> None:
    names = set(manifests)
    qa_numbers: list[int] = []
    repair_numbers: list[int] = []
    malformed = []
    for name in names:
        if name.startswith("05-qa-attempt-"):
            match = QA_DIRECTORY_PATTERN.fullmatch(name)
            if match is None:
                malformed.append(name)
            else:
                qa_numbers.append(int(match.group(1)))
        if name.startswith("06-repair-attempt-"):
            match = REPAIR_DIRECTORY_PATTERN.fullmatch(name)
            if match is None:
                malformed.append(name)
            else:
                repair_numbers.append(int(match.group(1)))
    for name in malformed:
        errors.append(_error(run_dir / name, "invalid_phase_topology", "phase directory name is malformed"))
    qa_numbers.sort()
    repair_numbers.sort()
    if qa_numbers != list(range(1, len(qa_numbers) + 1)):
        errors.append(_error(run_dir, "invalid_phase_topology", "QA attempts must be contiguous and start at one"))
    if repair_numbers != list(range(1, len(repair_numbers) + 1)):
        errors.append(_error(run_dir, "invalid_phase_topology", "repair attempts must be contiguous and start at one"))
    if not qa_numbers:
        return
    if any(f"05-qa-attempt-{number}" not in manifests for number in qa_numbers):
        return
    has_skipped = REPAIR_SKIPPED_DIRECTORY in names
    has_consolidation = CONSOLIDATION_DIRECTORY in names
    other_phase6 = [
        name for name in names if name.startswith("06-") and name not in {
            REPAIR_SKIPPED_DIRECTORY,
            CONSOLIDATION_DIRECTORY,
            *(f"06-repair-attempt-{number}" for number in repair_numbers),
        }
    ]
    for name in other_phase6:
        errors.append(_error(run_dir / name, "invalid_phase_topology", "unknown Phase 6 directory"))
    if has_skipped and repair_numbers:
        errors.append(_error(run_dir, "invalid_phase_topology", "repair-skipped cannot coexist with repair attempts"))
    if has_skipped and manifests[REPAIR_SKIPPED_DIRECTORY].get("status") != "SKIPPED":
        errors.append(_error(run_dir / REPAIR_SKIPPED_DIRECTORY / "manifest.json", "invalid_phase_topology", "repair-skipped must have SKIPPED status"))
    expected_repairs = len(qa_numbers) - 1 - int(has_consolidation)
    if len(repair_numbers) != expected_repairs:
        errors.append(_error(run_dir, "invalid_phase_topology", "repair count must equal failed QA attempts"))
    retry_limit = manifests[f"05-qa-attempt-{qa_numbers[-1]}"].get("retry_limit")
    if _is_nonnegative_int(retry_limit) and repair_numbers and repair_numbers[-1] > retry_limit:
        errors.append(_error(run_dir, "retry_count_exceeded", "highest repair attempt exceeds retry_limit"))
    for repair_number in repair_numbers:
        repair_manifest = manifests.get(f"06-repair-attempt-{repair_number}")
        if repair_manifest is None:
            continue
        if repair_manifest.get("retry_count") != repair_number:
            errors.append(_error(run_dir / f"06-repair-attempt-{repair_number}" / "manifest.json", "invalid_retry_count", "repair retry_count must equal repair attempt number"))
    if not repair_numbers and expected_repairs == 0 and not has_skipped and not has_consolidation:
        errors.append(_error(run_dir, "invalid_phase_topology", "clean QA requires repair-skipped or consolidation artifact"))
    summary = manifests.get("07-summary")
    for index, qa_number in enumerate(qa_numbers, start=1):
        qa_manifest = manifests[f"05-qa-attempt-{qa_number}"]
        verdict = qa_manifest.get("qa_verdict")
        is_consolidation_pass = has_consolidation and index == len(qa_numbers) - 1
        if index < len(qa_numbers) and verdict != ("CHECKLIST_PASSED" if is_consolidation_pass else "CHECKLIST_FAILED"):
            errors.append(_error(run_dir / f"05-qa-attempt-{qa_number}" / "manifest.json", "invalid_qa_sequence", "QA sequence has invalid verdict"))
        if index < len(qa_numbers) and not is_consolidation_pass and f"06-repair-attempt-{index}" not in names:
            errors.append(_error(run_dir, "invalid_phase_topology", "failed QA requires matching repair attempt"))
        expected_retry_count = index - 1 if index < len(qa_numbers) and not is_consolidation_pass else len(repair_numbers)
        if qa_manifest.get("retry_count") != expected_retry_count:
            errors.append(_error(run_dir / f"05-qa-attempt-{qa_number}" / "manifest.json", "invalid_retry_count", "QA retry_count must retain consumed repairs"))
    final_qa = manifests[f"05-qa-attempt-{qa_numbers[-1]}"]
    if summary and summary.get("status") == "SUCCESS":
        if not (
            final_qa.get("status") == "SUCCESS"
            and final_qa.get("terminal") is False
            and final_qa.get("qa_verdict") == "CHECKLIST_PASSED"
            and final_qa.get("error_code") == "NONE"
            and summary.get("qa_verdict") == "CHECKLIST_PASSED"
        ):
            errors.append(_error(run_dir / "07-summary" / "manifest.json", "invalid_success_terminal_topology", "successful summary requires passing non-terminal final QA"))
    elif summary and summary.get("error_code") == "QA_RETRY_EXHAUSTED":
        retry_limit = final_qa.get("retry_limit")
        consumed_retries = len(repair_numbers)
        if not (
            final_qa.get("qa_verdict") == "CHECKLIST_FAILED"
            and _is_nonnegative_int(retry_limit)
            and consumed_retries == retry_limit
            and len(qa_numbers) == retry_limit + 1
            and final_qa.get("retry_count") == consumed_retries
            and summary.get("retry_count") == final_qa.get("retry_count")
        ):
            errors.append(
                _error(
                    run_dir / "07-summary" / "manifest.json",
                    "invalid_failed_terminal_topology",
                    "retry exhaustion requires every retry to have a repair and QA recheck with matching final counts",
                )
            )
    elif summary and summary.get("error_code") == "CONSOLIDATION_REGRESSION":
        penultimate_qa = manifests.get(f"05-qa-attempt-{qa_numbers[-2]}") if len(qa_numbers) > 1 else None
        if not (
            has_consolidation
            and penultimate_qa is not None
            and penultimate_qa.get("qa_verdict") == "CHECKLIST_PASSED"
            and final_qa.get("qa_verdict") == "CHECKLIST_FAILED"
        ):
            errors.append(_error(run_dir / "07-summary" / "manifest.json", "invalid_failed_terminal_topology", "consolidation regression requires pass, consolidation, then failed QA"))
    if has_consolidation:
        consolidation = manifests[CONSOLIDATION_DIRECTORY]
        if consolidation.get("consolidation_attempts") != 1:
            errors.append(_error(run_dir / CONSOLIDATION_DIRECTORY / "manifest.json", "invalid_phase_topology", "consolidation attempt must record count one"))
        if qa_numbers[-1] < 2:
            errors.append(_error(run_dir / CONSOLIDATION_DIRECTORY / "manifest.json", "invalid_phase_topology", "consolidation requires following QA recheck"))


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
    if SUMMARY_DIRECTORY not in phase_names:
        errors.append(_error(resolved_run_dir / SUMMARY_DIRECTORY, "missing_summary", "required phase directory is missing"))

    manifests: dict[str, dict[str, Any]] = {}
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
        manifests[phase_dir.name] = manifest
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
        if phase_dir.name == "06-repair-skipped" and manifest.get("status") == "SKIPPED" and not body:
            errors.append(_error(content_path, "missing_skipped_repair_reason", "skipped repair content requires a non-empty reason"))
    reaches_qa = _validate_base_phase_topology(resolved_run_dir, phase_names, manifests, errors)
    if reaches_qa:
        _validate_qa_repair_sequence(resolved_run_dir, manifests, errors)
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
