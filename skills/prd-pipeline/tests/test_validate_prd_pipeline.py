from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


VALIDATOR_PATH = Path(__file__).parents[1] / "scripts" / "validate-prd-pipeline.py"


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
        (root / "references" / "prd-pipeline-contract.md").write_text("contract", encoding="utf-8")
        (root / "references" / "prd-artifact-format.md").write_text("artifact format", encoding="utf-8")
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
        target_path: str = "/workspace/prd/reset-password.md",
        document_type: str = "Use Case",
        mode: str = "CREATE",
        retry_count: int = 0,
        retry_limit: int = 1,
        consolidation_attempts: int = 0,
        qa_verdict: str = "NOT_RUN",
    ) -> None:
        phase_dir = run_dir / directory
        phase_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": "1.0",
            "run_id": "prd-test-run",
            "phase": phase,
            "phase_number": int(directory.split("-")[0]),
            "agent": "prd-pipeline",
            "status": status,
            "document_type": document_type,
            "mode": mode,
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
        (phase_dir / "content.md").write_text(f"STATUS: {status}\n", encoding="utf-8")

    def make_successful_run(
        self,
        *,
        document_type: str = "Use Case",
        mode: str = "CREATE",
        qa_attempts: int = 1,
    ) -> Path:
        self.write_phase(self.run_dir, "00-load", phase="LOAD", document_type=document_type, mode=mode)
        self.write_phase(self.run_dir, "01-plan", phase="PLAN", document_type=document_type, mode=mode)
        self.write_phase(self.run_dir, "02-context", phase="CONTEXT", document_type=document_type, mode=mode)
        self.write_phase(self.run_dir, "03-figma", phase="FIGMA", status="SKIPPED", document_type=document_type, mode=mode)
        self.write_phase(self.run_dir, "04-author", phase="AUTHOR", document_type=document_type, mode=mode)
        for attempt in range(1, qa_attempts + 1):
            self.write_phase(
                self.run_dir,
                f"05-qa-attempt-{attempt}",
                phase="QA",
                document_type=document_type,
                mode=mode,
                qa_verdict="CHECKLIST_PASSED",
            )
        self.write_phase(
            self.run_dir,
            "07-summary",
            phase="REPORT",
            document_type=document_type,
            mode=mode,
            qa_verdict="CHECKLIST_PASSED",
        )
        return self.run_dir

    def read_manifest(self, directory: str) -> dict[str, object]:
        return json.loads((self.run_dir / directory / "manifest.json").read_text(encoding="utf-8"))

    def update_manifest(self, directory: str, **updates: object) -> None:
        manifest = self.read_manifest(directory)
        manifest.update(updates)
        (self.run_dir / directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def assert_error_code(self, code: str) -> None:
        errors = validator.validate_run(self.run_dir)
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
        self.update_manifest("05-qa-attempt-1", status="FAILED", error_code="CHECKLIST_FAILED", qa_verdict="CHECKLIST_FAILED")
        self.write_phase(self.run_dir, "06-repair-attempt-1", phase="REPAIR", retry_count=1)
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_relative_target_path_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", target_path="relative/target.md")
        self.assert_error_code("relative_target_path")

    def test_skipped_figma_without_content_is_rejected(self) -> None:
        self.make_successful_run()
        (self.run_dir / "03-figma" / "content.md").unlink()
        self.assert_error_code("missing_content")

    def test_unknown_status_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", status="UNKNOWN")
        self.assert_error_code("unknown_status")

    def test_simple_retry_count_above_one_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("05-qa-attempt-1", retry_count=2)
        self.assert_error_code("retry_count_exceeded")

    def test_complex_retry_count_above_two_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("01-plan", complexity="Complex")
        self.update_manifest("05-qa-attempt-1", retry_count=3, retry_limit=2)
        self.assert_error_code("retry_count_exceeded")

    def test_two_consolidation_attempts_are_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("07-summary", consolidation_attempts=2)
        self.assert_error_code("consolidation_attempts_exceeded")

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

    def test_qa_retry_exhausted_run_is_valid_terminal_state(self) -> None:
        self.assert_valid_terminal_failure("QA_RETRY_EXHAUSTED", status="FAILED")

    def test_consolidation_regression_run_is_valid_terminal_state(self) -> None:
        self.assert_valid_terminal_failure("CONSOLIDATION_REGRESSION", status="FAILED")


if __name__ == "__main__":
    unittest.main()
