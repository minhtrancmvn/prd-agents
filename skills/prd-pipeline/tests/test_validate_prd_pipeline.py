from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


VALIDATOR_PATH = Path(__file__).parents[1] / "scripts" / "validate-prd-pipeline.py"
CONTRACT_PATH = Path(__file__).parents[1] / "references" / "prd-pipeline-contract.md"
ARTIFACT_FORMAT_PATH = Path(__file__).parents[1] / "references" / "prd-artifact-format.md"

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

SKILL_PATH = Path(__file__).parents[1] / "SKILL.md"
SKILL_REQUIRED_FRONTMATTER = {
    "name: prd-pipeline",
    "version: 1.0.0",
    "user-invocable: true",
    "  - Agent",
    "  - Task",
}
SKILL_REQUIRED_PHASES = (
    "### Phase 0: LOAD",
    "### Phase 1: PLAN",
    "### Phase 2: CONTEXT AND ROLES",
    "### Phase 3: FIGMA",
    "### Phase 4: AUTHOR",
    "### Phase 5: QA",
    "### Phase 6: REPAIR AND RECHECK",
    "### Phase 7: REPORT",
)
SKILL_REQUIRED_AGENTS = {
    "prd-planner",
    "prd-context-role-analyzer",
    "prd-figma-reader",
    "prd-author",
    "prd-noti-req-author",
    "prd-email-req-author",
    "prd-consistency-checker",
}
SKILL_REQUIRED_REFERENCES = {
    "references/prd-pipeline-contract.md",
    "references/prd-artifact-format.md",
    "validate-prd-pipeline.py run --run-dir",
}

REPOSITORY_ROOT = Path(__file__).parents[3]
ORCHESTRATOR_PATH = REPOSITORY_ROOT / "agents" / "prd-orchestrator.md"
FIGMA_READER_PATH = REPOSITORY_ROOT / "agents" / "prd-figma-reader.md"
CHECKER_PATH = REPOSITORY_ROOT / "agents" / "prd-consistency-checker.md"
CHECKER_FIRST_LINE_STATUSES = {
    "CHECKLIST_PASSED",
    "CHECKLIST_FAILED",
    "INPUT_INVALID",
    "DOCUMENT_NOT_FOUND",
    "ROLES_FILE_NOT_FOUND",
}


spec = importlib.util.spec_from_file_location("validate_prd_pipeline", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load validator from {VALIDATOR_PATH}")
validator: ModuleType = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


class PackageValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def make_skill_root(self) -> Path:
        return Path(self.temp_dir.name) / "prd-pipeline"

    def make_complete_skill_root(self) -> Path:
        root = self.make_skill_root()
        (root / "references").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "tests").mkdir()
        phases = "\n".join(f"### Phase {number}: {name}" for number, name in enumerate(
            ("LOAD", "PLAN", "CONTEXT AND ROLES", "FIGMA", "AUTHOR", "QA", "REPAIR AND RECHECK", "REPORT")
        ))
        (root / "SKILL.md").write_text(
            "---\n"
            "name: prd-pipeline\n"
            "description: Coordinate PRD workflows.\n"
            "version: 1.0.0\n"
            "user-invocable: true\n"
            "allowed-tools:\n"
            "  - Read\n"
            "---\n"
            f"{phases}\n",
            encoding="utf-8",
        )
        (root / "references" / "prd-pipeline-contract.md").write_text(" ".join(CONTRACT_REQUIRED_TERMS), encoding="utf-8")
        (root / "references" / "prd-artifact-format.md").write_text(" ".join(ARTIFACT_REQUIRED_TERMS), encoding="utf-8")
        (root / "scripts" / "validate-prd-pipeline.py").write_text("validator", encoding="utf-8")
        (root / "tests" / "test_validate_prd_pipeline.py").write_text("tests", encoding="utf-8")
        return root

    def test_package_requires_skill_references_script_and_tests(self) -> None:
        root = self.make_skill_root()
        errors = validator.validate_package(root)
        self.assertEqual(
            {error.code for error in errors},
            {
                "missing_skill",
                "missing_contract",
                "missing_artifact_format",
                "missing_validator",
                "missing_tests",
            },
        )

    def test_complete_package_passes(self) -> None:
        root = self.make_complete_skill_root()
        self.assertEqual(validator.validate_package(root), [])

    def test_package_rejects_contract_missing_required_term(self) -> None:
        root = self.make_complete_skill_root()
        (root / "references" / "prd-pipeline-contract.md").write_text("STATUS:", encoding="utf-8")
        self.assertIn("invalid_contract", {error.code for error in validator.validate_package(root)})

    def test_package_rejects_artifact_format_missing_required_term(self) -> None:
        root = self.make_complete_skill_root()
        (root / "references" / "prd-artifact-format.md").write_text("manifest.json", encoding="utf-8")
        self.assertIn("invalid_artifact_format", {error.code for error in validator.validate_package(root)})

    def test_contract_reference_contains_required_terms(self) -> None:
        contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            {term for term in CONTRACT_REQUIRED_TERMS if term not in contract_text},
            set(),
        )

    def test_artifact_format_reference_contains_required_terms(self) -> None:
        artifact_format_text = ARTIFACT_FORMAT_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            {term for term in ARTIFACT_REQUIRED_TERMS if term not in artifact_format_text},
            set(),
        )

    def test_skill_structure_contains_required_frontmatter_phases_agents_and_references(self) -> None:
        self.assertTrue(SKILL_PATH.is_file(), "missing_skill")
        skill_text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            {term for term in SKILL_REQUIRED_FRONTMATTER if term not in skill_text},
            set(),
        )
        self.assertEqual(
            [phase for phase in SKILL_REQUIRED_PHASES if phase not in skill_text],
            [],
        )
        self.assertEqual(
            {agent for agent in SKILL_REQUIRED_AGENTS if agent not in skill_text},
            set(),
        )
        self.assertEqual(
            {term for term in SKILL_REQUIRED_REFERENCES if term not in skill_text},
            set(),
        )


class SpecialistAgentContractTests(unittest.TestCase):
    def test_legacy_orchestrator_routes_full_runs_to_prd_pipeline(self) -> None:
        text = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("`prd-pipeline` is the executable coordinator", text)

    def test_figma_reader_distinguishes_sparse_data_from_tool_failure(self) -> None:
        text = FIGMA_READER_PATH.read_text(encoding="utf-8")
        self.assertIn("valid sparse result", text)

    def test_figma_reader_reports_source_traceability(self) -> None:
        text = FIGMA_READER_PATH.read_text(encoding="utf-8")
        for field in ("Source URL", "Node ID", "Screens Analysed", "Unresolved Ambiguities"):
            with self.subTest(field=field):
                self.assertIn(field, text)

    def test_checker_accepts_workspace_root_and_external_verification(self) -> None:
        text = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn("Workspace root", text)
        self.assertIn("External ClickUp verification evidence", text)

    def test_checker_reports_not_checked_without_live_evidence(self) -> None:
        text = CHECKER_PATH.read_text(encoding="utf-8")
        self.assertIn("NOT_CHECKED", text)

    def test_checker_declares_exclusive_first_line_statuses(self) -> None:
        text = CHECKER_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"First line must be exactly one of:\n\n```text\n(?P<statuses>[^`]+)```",
            text,
        )
        self.assertIsNotNone(match, "missing checker first-line status fence")
        assert match is not None
        self.assertEqual(set(match.group("statuses").splitlines()), CHECKER_FIRST_LINE_STATUSES)
        self.assertIn(
            "Exactly one status appears as first line, with no preceding text.",
            text,
        )

    def test_pipeline_accepts_and_maps_all_checker_statuses(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"Require trimmed first line to equal exactly one documented status and full non-empty body:\n\n```text\n(?P<statuses>[^`]+)```",
            text,
        )
        self.assertIsNotNone(match, "missing pipeline checker-status fence")
        assert match is not None
        self.assertEqual(set(match.group("statuses").splitlines()), CHECKER_FIRST_LINE_STATUSES)
        for status, mapping in {
            "CHECKLIST_PASSED": "QA manifest SUCCESS, qa_verdict CHECKLIST_PASSED, error_code NONE",
            "CHECKLIST_FAILED": "QA manifest SUCCESS, qa_verdict CHECKLIST_FAILED, error_code CHECKLIST_FAILED",
            "ROLES_FILE_NOT_FOUND": "terminal BLOCKED, error_code ROLES_FILE_NOT_FOUND, next_agent STOP",
            "INPUT_INVALID": "terminal FAILED, error_code INPUT_INVALID, next_agent STOP",
            "DOCUMENT_NOT_FOUND": "terminal FAILED, error_code DOCUMENT_NOT_FOUND, next_agent STOP",
        }.items():
            with self.subTest(status=status):
                self.assertIn(f"{status} -> {mapping}", text)


class RunValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.run_dir = Path(self.temp_dir.name) / "run"

    def write_phase(
        self,
        run_dir: Path,
        directory: str,
        *,
        phase: str,
        status: str = "SUCCESS",
        error_code: str = "NONE",
        target_path: object = "/workspace/prd/reset-password.md",
        document_type: str = "Use Case",
        mode: str = "CREATE",
        retry_count: int = 0,
        retry_limit: int | None = None,
        consolidation_attempts: int = 0,
        qa_verdict: str = "NOT_RUN",
        complexity: str | None = None,
    ) -> None:
        phase_dir = run_dir / directory
        phase_dir.mkdir(parents=True, exist_ok=True)
        if retry_limit is None:
            retry_limit = 0 if complexity is None else 1 if complexity != "Complex" else 2
        manifest = {
            "schema_version": "1.0",
            "run_id": "prd-test-run",
            "phase": phase,
            "phase_number": int(directory.split("-")[0]),
            "agent": "prd-pipeline",
            "status": status,
            "document_type": document_type,
            "mode": mode,
            "complexity": complexity or "UNKNOWN",
            "target_path": target_path,
            "artifact_dir": str(run_dir.resolve()),
            "completed_checks": ["fixture check"],
            "unresolved_items": [],
            "next_agent": "prd-next-agent" if not directory.startswith("07-") else "STOP",
            "error_code": error_code,
            "error_details": "NONE" if error_code == "NONE" else "fixture failure",
            "retry_count": retry_count,
            "retry_limit": retry_limit,
            "consolidation_attempts": consolidation_attempts,
            "qa_verdict": qa_verdict,
            "terminal": directory.startswith("07-"),
            "artifacts": [{"path": "content.md", "type": "content"}],
        }
        (phase_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        handoff = "\n".join(
            (
                f"STATUS: {status}",
                "AGENT: prd-pipeline",
                f"PHASE: {phase}",
                f"DOCUMENT_TYPE: {document_type}",
                f"MODE: {mode}",
                f"TARGET_PATH: {target_path}",
                f"ARTIFACT_DIR: {run_dir.resolve()}",
                "COMPLETED_CHECKS: fixture check",
                "UNRESOLVED_ITEMS: NONE",
                f"NEXT_AGENT: {'prd-next-agent' if not directory.startswith('07-') else 'STOP'}",
                f"ERROR_CODE: {error_code}",
                f"ERROR_DETAILS: {'NONE' if error_code == 'NONE' else 'fixture failure'}",
            )
        )
        body = (
            "No Figma links supplied."
            if directory == "03-figma" and status == "SKIPPED"
            else "No repair required after QA pass."
            if directory == "06-repair-skipped" and status == "SKIPPED"
            else "Worker output."
        )
        (phase_dir / "content.md").write_text(f"{handoff}\n\n{body}\n", encoding="utf-8")

    def make_successful_run(
        self,
        *,
        document_type: str = "Use Case",
        mode: str = "CREATE",
        qa_attempts: int = 1,
        complexity: str | None = None,
    ) -> Path:
        resolved_complexity = complexity or "Simple"
        self.write_phase(self.run_dir, "00-load", phase="LOAD", document_type=document_type, mode=mode, complexity="UNKNOWN", retry_limit=0)
        self.write_phase(self.run_dir, "01-plan", phase="PLAN", document_type=document_type, mode=mode, complexity=resolved_complexity)
        self.write_phase(self.run_dir, "02-context", phase="CONTEXT", document_type=document_type, mode=mode, complexity=resolved_complexity)
        self.write_phase(self.run_dir, "03-figma", phase="FIGMA", status="SKIPPED", document_type=document_type, mode=mode, complexity=resolved_complexity)
        self.write_phase(self.run_dir, "04-author", phase="AUTHOR", document_type=document_type, mode=mode, complexity=resolved_complexity)
        for attempt in range(1, qa_attempts + 1):
            self.write_phase(
                self.run_dir,
                f"05-qa-attempt-{attempt}",
                phase="QA",
                document_type=document_type,
                mode=mode,
                qa_verdict="CHECKLIST_PASSED",
                retry_count=attempt - 1,
                complexity=resolved_complexity,
            )
        self.write_phase(
            self.run_dir,
            "06-repair-skipped",
            phase="REPAIR",
            status="SKIPPED",
            document_type=document_type,
            mode=mode,
            qa_verdict="CHECKLIST_PASSED",
            complexity=resolved_complexity,
        )
        self.write_phase(
            self.run_dir,
            "07-summary",
            phase="REPORT",
            document_type=document_type,
            mode=mode,
            qa_verdict="CHECKLIST_PASSED",
            complexity=resolved_complexity,
        )
        return self.run_dir

    def read_manifest(self, directory: str) -> dict[str, object]:
        return json.loads((self.run_dir / directory / "manifest.json").read_text(encoding="utf-8"))

    def update_manifest(self, directory: str, **updates: object) -> None:
        manifest = self.read_manifest(directory)
        manifest.update(updates)
        phase_dir = self.run_dir / directory
        (phase_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        content_path = phase_dir / "content.md"
        content_lines = content_path.read_text(encoding="utf-8").splitlines()
        handoff_keys = {
            "status": "STATUS",
            "agent": "AGENT",
            "phase": "PHASE",
            "document_type": "DOCUMENT_TYPE",
            "mode": "MODE",
            "target_path": "TARGET_PATH",
            "artifact_dir": "ARTIFACT_DIR",
            "completed_checks": "COMPLETED_CHECKS",
            "unresolved_items": "UNRESOLVED_ITEMS",
            "next_agent": "NEXT_AGENT",
            "error_code": "ERROR_CODE",
            "error_details": "ERROR_DETAILS",
        }
        for manifest_key, field in handoff_keys.items():
            if manifest_key not in updates:
                continue
            value = manifest[manifest_key]
            rendered = ";".join(str(item) for item in value) if isinstance(value, list) and value else ("NONE" if isinstance(value, list) else str(value))
            content_lines = [f"{field}: {rendered}" if line.startswith(f"{field}:") else line for line in content_lines]
        content_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")

    def update_content(self, directory: str, content: str) -> None:
        (self.run_dir / directory / "content.md").write_text(content, encoding="utf-8")

    def assert_error_code(self, code: str, repository_root: Path | None = None) -> None:
        errors = validator.validate_run(self.run_dir, repository_root)
        self.assertIn(code, {error.code for error in errors})

    def test_successful_use_case_create_passes(self) -> None:
        self.make_successful_run()
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_successful_notification_create_passes(self) -> None:
        self.make_successful_run(document_type="Notification")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_successful_email_update_passes(self) -> None:
        self.make_successful_run(document_type="Email Template", mode="UPDATE")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_skipped_figma_with_both_artifacts_passes(self) -> None:
        self.make_successful_run()
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.assertTrue((self.run_dir / "03-figma" / "content.md").read_text(encoding="utf-8"))

    def test_qa_failure_then_successful_repair_passes(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest(
            "05-qa-attempt-1",
            status="SUCCESS",
            error_code="CHECKLIST_FAILED",
            qa_verdict="CHECKLIST_FAILED",
            next_agent="prd-author",
        )
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        self.write_phase(self.run_dir, "06-repair-attempt-1", phase="REPAIR", retry_count=1, complexity="Simple")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_repair_skipped_phase_is_required(self) -> None:
        self.make_successful_run()
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        self.assert_error_code("invalid_phase_topology")

    def test_consolidation_attempt_has_separate_phase_path_and_count(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest("06-repair-skipped", consolidation_attempts=1)
        self.update_manifest("05-qa-attempt-2", retry_count=0)
        self.write_phase(
            self.run_dir,
            "06-consolidation-attempt-1",
            phase="REPAIR",
            status="SUCCESS",
            consolidation_attempts=1,
            qa_verdict="CHECKLIST_PASSED",
        )
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_checklist_failure_requires_repair_mapping(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest(
            "05-qa-attempt-1",
            status="SUCCESS",
            error_code="CHECKLIST_FAILED",
            qa_verdict="CHECKLIST_FAILED",
            next_agent="prd-noti-req-author",
        )
        self.assert_error_code("invalid_qa_repair_mapping")

    def test_two_repair_sequence_requires_contiguous_qa_and_repair_attempts(self) -> None:
        self.make_successful_run(qa_attempts=3, complexity="Complex")
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        for attempt in (1, 2):
            self.update_manifest(
                f"05-qa-attempt-{attempt}",
                status="SUCCESS",
                error_code="CHECKLIST_FAILED",
                qa_verdict="CHECKLIST_FAILED",
                next_agent="prd-author",
            )
            self.write_phase(self.run_dir, f"06-repair-attempt-{attempt}", phase="REPAIR", retry_count=attempt, complexity="Complex")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_qa_attempt_gap_is_rejected(self) -> None:
        self.make_successful_run(qa_attempts=2)
        (self.run_dir / "05-qa-attempt-2").rename(self.run_dir / "05-qa-attempt-3")
        self.assert_error_code("invalid_phase_topology")

    def test_leading_zero_qa_attempt_is_rejected_without_crash(self) -> None:
        self.make_successful_run()
        (self.run_dir / "05-qa-attempt-1").rename(self.run_dir / "05-qa-attempt-01")
        self.assert_error_code("invalid_phase_topology")

    def test_repair_retry_count_bypass_is_rejected(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest("05-qa-attempt-1", status="SUCCESS", error_code="CHECKLIST_FAILED", qa_verdict="CHECKLIST_FAILED", next_agent="prd-author")
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        self.write_phase(self.run_dir, "06-repair-attempt-1", phase="REPAIR", retry_count=0, complexity="Simple")
        self.assert_error_code("invalid_retry_count")

    def test_successful_terminal_requires_passing_final_qa_topology(self) -> None:
        self.make_successful_run()
        self.update_manifest("05-qa-attempt-1", error_code="CHECKLIST_FAILED", qa_verdict="CHECKLIST_FAILED", next_agent="prd-author")
        self.assert_error_code("invalid_success_terminal_topology")

    def make_exhausted_run(self, complexity: str) -> Path:
        retry_limit = 1 if complexity == "Simple" else 2
        self.make_successful_run(qa_attempts=retry_limit + 1, complexity=complexity)
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        for attempt in range(1, retry_limit + 1):
            self.update_manifest(
                f"05-qa-attempt-{attempt}",
                status="SUCCESS",
                error_code="CHECKLIST_FAILED",
                qa_verdict="CHECKLIST_FAILED",
                next_agent="prd-author",
            )
            self.write_phase(
                self.run_dir,
                f"06-repair-attempt-{attempt}",
                phase="REPAIR",
                retry_count=attempt,
                complexity=complexity,
            )
        self.update_manifest(
            f"05-qa-attempt-{retry_limit + 1}",
            status="SUCCESS",
            error_code="CHECKLIST_FAILED",
            qa_verdict="CHECKLIST_FAILED",
            next_agent="prd-author",
            retry_count=retry_limit,
        )
        self.update_manifest(
            "07-summary",
            status="FAILED",
            error_code="QA_RETRY_EXHAUSTED",
            qa_verdict="CHECKLIST_FAILED",
            retry_count=retry_limit,
        )
        return self.run_dir

    def test_simple_exhausted_terminal_allows_consumed_repair_topology(self) -> None:
        self.make_exhausted_run("Simple")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_complex_exhausted_terminal_allows_consumed_repair_topology(self) -> None:
        self.make_exhausted_run("Complex")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_exhausted_terminal_rejects_no_repair_with_fabricated_retry_count(self) -> None:
        self.make_successful_run()
        self.update_manifest(
            "05-qa-attempt-1",
            status="SUCCESS",
            error_code="CHECKLIST_FAILED",
            qa_verdict="CHECKLIST_FAILED",
            next_agent="prd-author",
            retry_count=1,
        )
        self.update_manifest(
            "07-summary",
            status="FAILED",
            error_code="QA_RETRY_EXHAUSTED",
            qa_verdict="CHECKLIST_FAILED",
            retry_count=1,
        )
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_exhausted_terminal_rejects_fabricated_summary_retry_count(self) -> None:
        self.make_exhausted_run("Simple")
        self.update_manifest("07-summary", retry_count=0)
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_consolidation_regression_terminal_allows_failed_final_qa_topology(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest("05-qa-attempt-1", retry_count=0)
        self.update_manifest("05-qa-attempt-2", status="SUCCESS", error_code="CHECKLIST_FAILED", qa_verdict="CHECKLIST_FAILED", next_agent="prd-author", retry_count=0)
        self.update_manifest("06-repair-skipped", consolidation_attempts=1)
        self.update_manifest("05-qa-attempt-2", retry_count=0)
        self.write_phase(self.run_dir, "06-consolidation-attempt-1", phase="REPAIR", status="SUCCESS", consolidation_attempts=1, qa_verdict="CHECKLIST_PASSED")
        self.update_manifest("07-summary", status="FAILED", error_code="CONSOLIDATION_REGRESSION", qa_verdict="CHECKLIST_FAILED")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_relative_target_path_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", target_path="relative/target.md")
        self.assert_error_code("relative_target_path")

    def test_skipped_figma_without_content_is_rejected(self) -> None:
        self.make_successful_run()
        (self.run_dir / "03-figma" / "content.md").unlink()
        self.assert_error_code("missing_content")

    def test_skipped_figma_requires_nonempty_reason(self) -> None:
        self.make_successful_run()
        content = (self.run_dir / "03-figma" / "content.md").read_text(encoding="utf-8")
        self.update_content("03-figma", content.split("\n\n", 1)[0] + "\n\n")
        self.assert_error_code("missing_skipped_figma_reason")

    def test_missing_base_phase_is_rejected(self) -> None:
        self.make_successful_run()
        (self.run_dir / "02-context").rename(self.run_dir / "02-context-removed")
        self.assert_error_code("missing_phase")

    def test_handoff_missing_field_is_rejected(self) -> None:
        self.make_successful_run()
        content = (self.run_dir / "01-plan" / "content.md").read_text(encoding="utf-8")
        self.update_content("01-plan", "\n".join(content.splitlines()[:11]))
        self.assert_error_code("missing_handoff_field")

    def test_handoff_manifest_mismatch_is_rejected(self) -> None:
        self.make_successful_run()
        content = (self.run_dir / "01-plan" / "content.md").read_text(encoding="utf-8")
        self.update_content("01-plan", content.replace("PHASE: PLAN", "PHASE: LOAD", 1))
        self.assert_error_code("handoff_mismatch")

    def test_artifact_dir_mismatch_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("01-plan", artifact_dir="/tmp/other-run")
        self.assert_error_code("artifact_dir_mismatch")

    def test_run_inside_repository_is_rejected(self) -> None:
        self.make_successful_run()
        self.assert_error_code("run_dir_inside_repository", self.run_dir.parent)

    def test_cli_accepts_repository_root_flag(self) -> None:
        self.make_successful_run()
        self.assertEqual(
            validator.main([
                "run",
                "--run-dir",
                str(self.run_dir),
                "--repository-root",
                str(self.run_dir.parent),
            ]),
            1,
        )

    def test_duplicate_content_artifact_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("01-plan", artifacts=[{"path": "content.md", "type": "content"}, {"path": "content.md", "type": "content"}])
        self.assert_error_code("invalid_content_artifact")

    def test_non_string_falsy_target_path_is_rejected(self) -> None:
        for value in (None, False, 0, [], {}):
            with self.subTest(value=value):
                self.make_successful_run()
                self.update_manifest("04-author", target_path=value)
                self.assert_error_code("invalid_target_path")
                self.run_dir = Path(self.temp_dir.name) / f"run-{len(list(Path(self.temp_dir.name).iterdir()))}"

    def test_empty_string_target_path_is_allowed(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", target_path="")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_unknown_status_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", status="UNKNOWN")
        self.assert_error_code("unknown_status")

    def test_unknown_complexity_uses_zero_retry_limit(self) -> None:
        self.make_successful_run()
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.update_manifest("00-load", retry_limit=1)
        self.assert_error_code("invalid_retry_limit")

    def test_simple_complexity_uses_one_retry_limit(self) -> None:
        self.make_successful_run(complexity="Simple")
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.update_manifest("05-qa-attempt-1", retry_limit=2)
        self.assert_error_code("invalid_retry_limit")

    def test_complex_complexity_uses_two_retry_limit(self) -> None:
        self.make_successful_run(complexity="Complex")
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.update_manifest("05-qa-attempt-1", retry_limit=1)
        self.assert_error_code("invalid_retry_limit")

    def test_simple_retry_count_above_one_is_rejected(self) -> None:
        self.make_successful_run(complexity="Simple")
        self.update_manifest("05-qa-attempt-1", retry_count=2)
        self.assert_error_code("retry_count_exceeded")

    def test_complex_retry_count_above_two_is_rejected(self) -> None:
        self.make_successful_run(complexity="Complex")
        self.update_manifest("05-qa-attempt-1", retry_count=3)
        self.assert_error_code("retry_count_exceeded")

    def test_two_consolidation_attempts_are_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("07-summary", consolidation_attempts=2)
        self.assert_error_code("consolidation_attempts_exceeded")

    def test_negative_and_boolean_retry_values_are_rejected(self) -> None:
        expected_codes = {
            "retry_count": "invalid_retry_count",
            "retry_limit": "invalid_retry_limit",
            "consolidation_attempts": "invalid_consolidation_attempts",
        }
        for field in ("retry_count", "retry_limit", "consolidation_attempts"):
            for value in (-1, True):
                with self.subTest(field=field, value=value):
                    self.make_successful_run()
                    self.update_manifest("01-plan", **{field: value})
                    self.assert_error_code(expected_codes[field])
                    self.run_dir = Path(self.temp_dir.name) / f"run-invalid-{field}-{value}"

    def test_document_not_found_blocked_run_is_valid_terminal_state(self) -> None:
        self.assert_valid_terminal_failure("DOCUMENT_NOT_FOUND")

    def test_terminal_success_requires_checklist_passed(self) -> None:
        self.make_successful_run()
        self.update_manifest("07-summary", qa_verdict="CHECKLIST_FAILED")
        self.assert_error_code("terminal_success_without_checklist")

    def test_missing_summary_is_rejected(self) -> None:
        self.make_successful_run()
        for path in (self.run_dir / "07-summary").iterdir():
            path.unlink()
        (self.run_dir / "07-summary").rmdir()
        self.assert_error_code("missing_summary")

    def test_unresolved_template_token_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("01-plan", error_details="TODO: fill target")
        self.assert_error_code("unresolved_template")

    def assert_valid_terminal_failure(self, error_code: str, status: str = "BLOCKED") -> None:
        self.make_successful_run()
        self.update_manifest("07-summary", status=status, error_code=error_code, error_details="fixture terminal state")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_missing_roles_file_blocked_run_is_valid_terminal_state(self) -> None:
        self.assert_valid_terminal_failure("ROLES_FILE_NOT_FOUND")

    def test_unresolved_roles_blocked_run_is_valid_terminal_state(self) -> None:
        self.assert_valid_terminal_failure("RISK_ITEMS_FOUND")

    def test_qa_retry_exhausted_run_requires_failed_final_qa_topology(self) -> None:
        self.test_simple_exhausted_terminal_allows_consumed_repair_topology()

    def test_consolidation_regression_run_requires_failed_final_qa_topology(self) -> None:
        self.test_consolidation_regression_terminal_allows_failed_final_qa_topology()


if __name__ == "__main__":
    unittest.main()
