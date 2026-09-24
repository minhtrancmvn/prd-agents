from __future__ import annotations

import contextlib
import importlib.util
import io
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
    "Early terminal layout",
}

PACKAGE_VALIDATOR_STUB = (
    "from __future__ import annotations\n"
    "\n"
    "\n"
    "def main() -> int:\n"
    "    return 0\n"
)

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
README_PATH = REPOSITORY_ROOT / "README.md"
README_REQUIRED_TERMS = {
    "skills/prd-pipeline/SKILL.md",
    "cp -R skills/prd-pipeline ~/.claude/skills/",
    "/prd-pipeline",
    "manifest.json",
    "content.md",
    "QA_RETRY_EXHAUSTED",
    "NOT_CHECKED",
    "validate-prd-pipeline.py package",
    "validate-prd-pipeline.py run",
}
README_USER_INSTALL_COMMANDS = (
    "mkdir -p ~/.claude/agents ~/.claude/skills",
    "cp agents/prd-*.md ~/.claude/agents/",
    "cp prd-shared-authoring-standards.md ~/.claude/",
    "rm -rf ~/.claude/skills/prd-pipeline",
    "cp -R skills/prd-pipeline ~/.claude/skills/",
)
README_PROJECT_INSTALL_COMMANDS = (
    "PROJECT_ROOT=/path/to/your/project",
    "CLONE_ROOT=/absolute/path/to/prd-agents",
    '[ -n "$PROJECT_ROOT" ] && [ "$PROJECT_ROOT" != "/" ] || { echo "PROJECT_ROOT must be a real project directory"; exit 1; }',
    'mkdir -p "$PROJECT_ROOT/.claude/agents" "$PROJECT_ROOT/.claude/skills"',
    'cp "$CLONE_ROOT"/agents/prd-*.md "$PROJECT_ROOT/.claude/agents/"',
    'rm -rf "$PROJECT_ROOT/.claude/skills/prd-pipeline"',
    'cp -R "$CLONE_ROOT"/skills/prd-pipeline "$PROJECT_ROOT/.claude/skills/"',
    'cp "$CLONE_ROOT"/prd-shared-authoring-standards.md ~/.claude/',
)
README_VALIDATOR_COMMANDS = (
    "python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline",
    "python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py run --run-dir /absolute/path/to/run --repository-root /absolute/path/to/workspace",
)
README_REQUIRED_STATUS_SIGNALS = {
    "INPUT_INVALID",
    "WORKSPACE_NOT_FOUND",
    "AUTHOR_INPUT_INVALID",
    "DOCUMENT_NOT_FOUND",
}
ORCHESTRATOR_PATH = REPOSITORY_ROOT / "agents" / "prd-orchestrator.md"
FIGMA_READER_PATH = REPOSITORY_ROOT / "agents" / "prd-figma-reader.md"
CHECKER_PATH = REPOSITORY_ROOT / "agents" / "prd-consistency-checker.md"
SHARED_STANDARDS_PATH = REPOSITORY_ROOT / "prd-shared-authoring-standards.md"
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


class ReadmeContractTests(unittest.TestCase):
    def test_readme_documents_canonical_pipeline_contract(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            {term for term in README_REQUIRED_TERMS if term not in readme_text},
            set(),
        )

    def test_readme_documents_exact_install_commands_for_both_scopes(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        for command in (*README_USER_INSTALL_COMMANDS, *README_PROJECT_INSTALL_COMMANDS):
            with self.subTest(command=command):
                self.assertIn(command, readme_text)

    def test_readme_documents_exact_validator_commands(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        for command in README_VALIDATOR_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, readme_text)

    def test_readme_requires_artifacts_outside_repository(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("outside repository source", readme_text)
        self.assertIn("outside that root", readme_text)

    def test_readme_documents_required_terminal_statuses(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            {signal for signal in README_REQUIRED_STATUS_SIGNALS if signal not in readme_text},
            set(),
        )

    def test_readme_limits_phase_six_artifacts_to_clean_qa_runs(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("Every terminal run has `07-summary`.", readme_text)
        self.assertIn("only a run whose final QA verdict is `CHECKLIST_PASSED` needs a Phase 6", readme_text)
        self.assertIn("LOAD, PLAN, CONTEXT, FIGMA, or AUTHOR", readme_text)
        self.assertIn("do not create Phase 6 artifact", readme_text)
        self.assertIn("A blocking QA terminal stopped before a passing verdict also carries no Phase 6 artifact.", readme_text)

    def test_readme_documents_python_floor(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("Python 3.10 or newer", readme_text)

    def test_readme_gitignore_inventory_lists_tracked_design_and_plan_docs(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("docs/superpowers/specs/2026-09-24-prd-pipeline-design.md", readme_text)
        self.assertIn("docs/superpowers/plans/2026-09-24-prd-pipeline.md", readme_text)

    def test_readme_project_install_commands_are_workspace_safe(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("CLONE_ROOT=/absolute/path/to/prd-agents", readme_text)
        self.assertIn('[ -n "$PROJECT_ROOT" ] && [ "$PROJECT_ROOT" != "/" ]', readme_text)
        self.assertIn("Run these commands from the target workspace", readme_text)

    def test_readme_figma_failure_wording_distinguishes_empty_from_sparse(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("no output at all", readme_text)
        self.assertIn("valid analysis is evidence", readme_text)
        self.assertIn("`figma-console-mcp` MCP server", readme_text)

    def test_readme_routes_unresolved_roles_to_caller_reinvocation(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("cannot prompt mid-run", readme_text)
        self.assertIn("re-invoke `/prd-pipeline` with explicit approval", readme_text)

    def test_readme_defines_validation_failed_for_artifacts_and_worker_output(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        for term in (
            "Package or run-artifact validation failed",
            "unsupported, mixed, empty, malformed, or an agent error",
        ):
            with self.subTest(term=term):
                self.assertIn(term, readme_text)

    def test_readme_removes_obsolete_manual_orchestration_guidance(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Until its tool allowlist includes Agent", readme_text)
        for obsolete in (
            "main Claude Code conversation",
            "main conversation",
            "manually coordinate",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, readme_text)

    def test_readme_states_canonical_pipeline_routing_sentence(self) -> None:
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("`prd-pipeline` is sole executable entry point for full end-to-end runs.", readme_text)
        self.assertIn("Full runs use `/prd-pipeline`", readme_text)


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
        (root / "scripts" / "validate-prd-pipeline.py").write_text(PACKAGE_VALIDATOR_STUB, encoding="utf-8")
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

    def test_package_validator_fixture_is_parseable_python(self) -> None:
        compile(PACKAGE_VALIDATOR_STUB, "validate-prd-pipeline.py", "exec")

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

    def test_shared_standards_use_pipeline_compatible_checker_handoff(self) -> None:
        text = SHARED_STANDARDS_PATH.read_text(encoding="utf-8")
        self.assertIn("signal the caller", text)
        self.assertIn("`prd-pipeline` invokes `prd-consistency-checker`", text)
        self.assertIn("standalone authors provide the same handoff to their caller", text)
        self.assertNotIn("signal the orchestrator", text)

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

    def test_skill_delegates_relative_target_resolution_to_shared_standards(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("prd-shared-authoring-standards.md", text)
        self.assertIn("`PRD Root Directory`", text)
        for term in ("explicit PRD root", "`business-requirements/`", "`prd/`", "workspace root"):
            with self.subTest(term=term):
                self.assertIn(term, text)
        self.assertNotIn("<workspace_root>/prd", text)

    def test_skill_report_validator_command_passes_repository_root(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        commands = [line for line in text.splitlines() if "validate-prd-pipeline.py run" in line]
        self.assertTrue(commands, "missing REPORT validator command")
        for command in commands:
            with self.subTest(command=command):
                self.assertIn("--repository-root", command)

    def test_skill_places_validator_evidence_record_inside_summary(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("as a file inside `07-summary`", text)
        self.assertIn("list that record as a relative artifact entry in `07-summary/manifest.json`", text)

    def test_skill_figma_failure_wording_distinguishes_empty_from_sparse(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("no output at all", text)
        self.assertIn("valid analysis is evidence", text)

    def test_skill_terminates_for_role_approval_instead_of_prompting(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("context: fork", text)
        self.assertIn("do not prompt the user mid-run", text)
        self.assertIn("instruct the caller to re-invoke with explicit approval", text)
        self.assertNotIn("ask user only whether to approve", text)

    def test_qa_validation_failed_artifact_shape_matches_across_contract_surfaces(self) -> None:
        expected = (
            "QA-stage VALIDATION_FAILED: QA manifest status FAILED, error_code VALIDATION_FAILED, "
            "terminal false, next_agent STOP; 07-summary status FAILED, error_code VALIDATION_FAILED, "
            "terminal true, next_agent STOP. Pipeline is terminal through 07-summary, not QA manifest. "
            "REPORT-stage VALIDATION_FAILED shape remains unchanged."
        )
        for label, path in (
            ("SKILL", SKILL_PATH),
            ("contract", CONTRACT_PATH),
            ("README", README_PATH),
        ):
            with self.subTest(document=label):
                self.assertIn(expected, path.read_text(encoding="utf-8"))

    def test_skill_contract_and_readme_share_one_phase_six_rule(self) -> None:
        skill_text = SKILL_PATH.read_text(encoding="utf-8")
        contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        readme_text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("When the final QA verdict is `CHECKLIST_PASSED`, a Phase 6 artifact exists", skill_text)
        self.assertIn("only when the final QA verdict is `CHECKLIST_PASSED`", contract_text)
        self.assertIn("only a run whose final QA verdict is `CHECKLIST_PASSED` needs a Phase 6", readme_text)
        for label, text in (("SKILL", skill_text), ("contract", contract_text), ("README", readme_text)):
            with self.subTest(document=label):
                self.assertIn("06-repair-attempt-N", text)
                self.assertIn("06-consolidation-attempt-1", text)

    def test_artifact_format_documents_repair_attempt_range(self) -> None:
        text = ARTIFACT_FORMAT_PATH.read_text(encoding="utf-8")
        self.assertIn("06-repair-attempt-N/", text)
        self.assertIn("N up to the retry limit", text)

    def test_figma_reader_declares_matching_mcp_server_name(self) -> None:
        text = FIGMA_READER_PATH.read_text(encoding="utf-8")
        self.assertIn("mcp__figma-console-mcp__", text)
        self.assertIn("figma-console-mcp MCP server", text)
        self.assertNotIn("configured as `figma-console`", text)

    def test_legacy_orchestrator_defers_to_authoritative_contract(self) -> None:
        text = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        self.assertIn("references/prd-pipeline-contract.md", text)
        self.assertIn("not authoritative", text)
        self.assertNotIn("confirms or overrides proposed Target File Path", text)


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
            "next_agent": "prd-pipeline" if not directory.startswith("07-") else "STOP",
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
                f"NEXT_AGENT: {'prd-pipeline' if not directory.startswith('07-') else 'STOP'}",
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

    def make_early_terminal_run(
        self,
        failure_directory: str,
        *,
        phase: str,
        error_code: str,
        status: str = "FAILED",
    ) -> Path:
        phases = (
            ("00-load", "LOAD", "UNKNOWN"),
            ("01-plan", "PLAN", "Simple"),
            ("02-context", "CONTEXT", "Simple"),
            ("03-figma", "FIGMA", "Simple"),
            ("04-author", "AUTHOR", "Simple"),
        )
        for directory, phase_name, complexity in phases:
            is_failure = directory == failure_directory
            self.write_phase(
                self.run_dir,
                directory,
                phase=phase_name,
                status=status if is_failure else "SUCCESS",
                error_code=error_code if is_failure else "NONE",
                complexity=complexity,
                retry_limit=0 if complexity == "UNKNOWN" else 1,
            )
            if is_failure:
                break
        self.write_phase(
            self.run_dir,
            "07-summary",
            phase="REPORT",
            status=status,
            error_code=error_code,
            complexity="UNKNOWN" if failure_directory == "00-load" else "Simple",
            retry_limit=0 if failure_directory == "00-load" else 1,
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

    def test_early_terminal_failures_accept_contiguous_prefix_and_summary(self) -> None:
        cases = (
            ("00-load", "LOAD", "INPUT_INVALID", "BLOCKED"),
            ("01-plan", "PLAN", "PLAN_INCOMPLETE", "BLOCKED"),
            ("02-context", "CONTEXT", "ROLES_FILE_NOT_FOUND", "BLOCKED"),
            ("03-figma", "FIGMA", "FIGMA_READ_FAILURE", "FAILED"),
            ("04-author", "AUTHOR", "AUTHOR_WRITE_FAILURE", "FAILED"),
        )
        for directory, phase, error_code, status in cases:
            with self.subTest(phase=phase):
                self.make_early_terminal_run(directory, phase=phase, error_code=error_code, status=status)
                self.assertEqual(validator.validate_run(self.run_dir), [])
                self.run_dir = Path(self.temp_dir.name) / f"run-{directory}"

    def test_author_document_not_found_terminal_run_validates(self) -> None:
        self.make_early_terminal_run("04-author", phase="AUTHOR", error_code="DOCUMENT_NOT_FOUND", status="FAILED")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_early_terminal_failure_rejects_missing_prefix_phase(self) -> None:
        self.make_early_terminal_run("03-figma", phase="FIGMA", error_code="FIGMA_READ_FAILURE")
        for path in (self.run_dir / "02-context").iterdir():
            path.unlink()
        (self.run_dir / "02-context").rmdir()
        self.assert_error_code("invalid_phase_topology")

    def test_early_terminal_failure_rejects_later_phase(self) -> None:
        self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
        self.write_phase(self.run_dir, "03-figma", phase="FIGMA", status="SKIPPED", complexity="Simple")
        self.assert_error_code("invalid_phase_topology")

    def test_early_terminal_failure_rejects_summary_with_wrong_error_phase(self) -> None:
        self.make_early_terminal_run("02-context", phase="CONTEXT", error_code="ROLES_FILE_NOT_FOUND", status="BLOCKED")
        self.update_manifest("07-summary", error_code="PLAN_INCOMPLETE")
        self.assert_error_code("invalid_terminal_topology")

    def test_early_terminal_failure_rejects_qa_phase_six_and_unapproved_directories(self) -> None:
        cases = (
            ("05-qa-attempt-1", "QA", "SUCCESS", "NONE"),
            ("06-repair-skipped", "REPAIR", "SKIPPED", "NONE"),
            ("08-unapproved", "REPORT", "SUCCESS", "NONE"),
            ("05-qa-attempt-01", "QA", "SUCCESS", "NONE"),
        )
        for directory, phase, status, error_code in cases:
            with self.subTest(directory=directory):
                self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
                self.write_phase(self.run_dir, directory, phase=phase, status=status, error_code=error_code, complexity="Simple")
                self.assert_error_code("invalid_phase_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-{directory}"

    def test_early_terminal_failure_rejects_unapproved_directory_without_manifest(self) -> None:
        self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
        (self.run_dir / "08-unapproved").mkdir()
        self.assert_error_code("invalid_phase_topology")

    def test_early_terminal_failure_rejects_non_successful_preceding_base_phase(self) -> None:
        self.make_early_terminal_run("03-figma", phase="FIGMA", error_code="FIGMA_READ_FAILURE")
        self.update_manifest("01-plan", status="BLOCKED", error_code="PLAN_INCOMPLETE")
        self.assert_error_code("invalid_terminal_topology")

    def test_early_terminal_failure_rejects_terminal_preceding_base_phase(self) -> None:
        self.make_early_terminal_run("03-figma", phase="FIGMA", error_code="FIGMA_READ_FAILURE")
        self.update_manifest("01-plan", terminal=True)
        self.assert_error_code("invalid_terminal_topology")

    def test_early_terminal_failure_rejects_error_on_preceding_base_phase(self) -> None:
        self.make_early_terminal_run("03-figma", phase="FIGMA", error_code="FIGMA_READ_FAILURE")
        self.update_manifest("01-plan", error_code="PLAN_INCOMPLETE")
        self.assert_error_code("invalid_terminal_topology")

    def test_early_terminal_failure_rejects_summary_status_mismatch(self) -> None:
        self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
        self.update_manifest("07-summary", status="FAILED")
        self.assert_error_code("invalid_terminal_topology")

    def test_early_terminal_failure_requires_terminal_summary(self) -> None:
        self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
        self.update_manifest("07-summary", terminal=False)
        self.assert_error_code("invalid_terminal_topology")

    def test_early_terminal_failure_rejects_wrong_phase_error_pairs(self) -> None:
        cases = (
            ("00-load", "LOAD", "PLAN_INCOMPLETE", "FAILED"),
            ("01-plan", "PLAN", "INPUT_INVALID", "BLOCKED"),
            ("02-context", "CONTEXT", "FIGMA_READ_FAILURE", "BLOCKED"),
            ("03-figma", "FIGMA", "AUTHOR_WRITE_FAILURE", "FAILED"),
            ("04-author", "AUTHOR", "RISK_ITEMS_FOUND", "FAILED"),
        )
        for directory, phase, error_code, status in cases:
            with self.subTest(phase=phase):
                self.make_early_terminal_run(directory, phase=phase, error_code=error_code, status=status)
                self.assert_error_code("invalid_terminal_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-{directory}"

    def test_early_terminal_failure_rejects_valid_error_with_wrong_phase_status(self) -> None:
        cases = (
            ("00-load", "LOAD", "INPUT_INVALID", "FAILED"),
            ("01-plan", "PLAN", "PLAN_INCOMPLETE", "FAILED"),
            ("02-context", "CONTEXT", "RISK_ITEMS_FOUND", "FAILED"),
            ("03-figma", "FIGMA", "FIGMA_READ_FAILURE", "BLOCKED"),
            ("04-author", "AUTHOR", "AUTHOR_INPUT_INVALID", "BLOCKED"),
        )
        for directory, phase, error_code, status in cases:
            with self.subTest(phase=phase):
                self.make_early_terminal_run(directory, phase=phase, error_code=error_code, status=status)
                self.assert_error_code("invalid_terminal_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-{directory}"

    def test_early_terminal_failure_rejects_nonterminal_summary_statuses(self) -> None:
        for status in ("SUCCESS", "SKIPPED", "SUCCESS_WITH_WARNINGS", "UNKNOWN"):
            with self.subTest(status=status):
                self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
                self.update_manifest("07-summary", status=status)
                self.assert_error_code("invalid_terminal_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-{status}"

    def test_early_terminal_failure_rejects_invalid_summary_status_with_extra_directory(self) -> None:
        for status in ("SUCCESS", "SKIPPED", "SUCCESS_WITH_WARNINGS", "UNKNOWN"):
            with self.subTest(status=status):
                self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
                self.update_manifest("07-summary", status=status)
                self.write_phase(self.run_dir, "08-unapproved", phase="REPORT", status="SUCCESS", complexity="Simple")
                self.assert_error_code("invalid_terminal_topology")
                self.assert_error_code("invalid_phase_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-extra-{status}"

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

    def test_passing_final_verdict_accepts_prior_repair_attempts_as_phase_six(self) -> None:
        """Locked rule: a Phase 6 artifact is repair-skipped, consolidation, or a prior repair attempt."""
        self.make_repair_record_run()
        self.assertFalse((self.run_dir / "06-repair-skipped").exists())
        self.assertEqual(validator.validate_run(self.run_dir), [])
        for path in (self.run_dir / "06-repair-attempt-1").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-attempt-1").rmdir()
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

    def test_clean_qa_topology_rejects_non_success_summary_statuses(self) -> None:
        for status in ("SKIPPED", "SUCCESS_WITH_WARNINGS", "BLOCKED", "FAILED"):
            with self.subTest(status=status):
                self.make_successful_run()
                self.update_manifest("07-summary", status=status)
                self.assert_error_code("invalid_success_terminal_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-{status}"

    def test_qa_path_rejects_unknown_and_malformed_phase_directories(self) -> None:
        for directory in ("08-unapproved", "05-qa-attempt-01", "06-repair-attempt-01"):
            with self.subTest(directory=directory):
                self.make_successful_run()
                self.write_phase(self.run_dir, directory, phase="QA", complexity="Simple")
                self.assert_error_code("invalid_phase_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-{directory}"

    def test_canonical_directories_require_matching_phase_and_number(self) -> None:
        self.make_successful_run()
        self.write_phase(self.run_dir, "06-repair-attempt-1", phase="REPAIR", retry_count=1, complexity="Simple")
        self.write_phase(
            self.run_dir,
            "06-consolidation-attempt-1",
            phase="REPAIR",
            consolidation_attempts=1,
            complexity="Simple",
        )
        expected_bindings = {
            "00-load": ("LOAD", 0),
            "01-plan": ("PLAN", 1),
            "02-context": ("CONTEXT", 2),
            "03-figma": ("FIGMA", 3),
            "04-author": ("AUTHOR", 4),
            "05-qa-attempt-1": ("QA", 5),
            "06-repair-skipped": ("REPAIR", 6),
            "06-repair-attempt-1": ("REPAIR", 6),
            "06-consolidation-attempt-1": ("REPAIR", 6),
            "07-summary": ("REPORT", 7),
        }
        for directory, (phase, phase_number) in expected_bindings.items():
            with self.subTest(directory=directory, field="phase"):
                self.update_manifest(directory, phase="WRONG")
                self.assert_error_code("invalid_phase_binding")
                self.update_manifest(directory, phase=phase)
            with self.subTest(directory=directory, field="phase_number"):
                self.update_manifest(directory, phase_number=phase_number + 1)
                self.assert_error_code("invalid_phase_binding")
                self.update_manifest(directory, phase_number=phase_number)

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

    def test_no_figma_early_terminal_run_validates(self) -> None:
        self.make_early_terminal_run("04-author", phase="AUTHOR", error_code="AUTHOR_INPUT_INVALID", status="FAILED")
        self.update_manifest("03-figma", status="SKIPPED")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_blocking_qa_terminal_without_phase_six_validates(self) -> None:
        cases = (
            ("BLOCKED", "ROLES_FILE_NOT_FOUND"),
            ("FAILED", "DOCUMENT_NOT_FOUND"),
            ("FAILED", "INPUT_INVALID"),
        )
        for index, (status, error_code) in enumerate(cases):
            with self.subTest(error_code=error_code):
                self.make_successful_run()
                for path in (self.run_dir / "06-repair-skipped").iterdir():
                    path.unlink()
                (self.run_dir / "06-repair-skipped").rmdir()
                self.update_manifest("05-qa-attempt-1", status=status, error_code=error_code, next_agent="STOP")
                self.update_manifest("07-summary", status=status, error_code=error_code, next_agent="STOP")
                self.assertEqual(validator.validate_run(self.run_dir), [])
                self.run_dir = Path(self.temp_dir.name) / f"run-blocking-qa-{index}"

    def test_report_validation_failure_after_clean_qa_validates(self) -> None:
        self.make_successful_run()
        self.update_manifest("07-summary", status="FAILED", error_code="VALIDATION_FAILED", next_agent="STOP")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_report_validation_failure_requires_clean_qa(self) -> None:
        self.make_successful_run()
        self.update_manifest("05-qa-attempt-1", status="FAILED", error_code="INPUT_INVALID", next_agent="STOP")
        self.update_manifest("07-summary", status="FAILED", error_code="VALIDATION_FAILED", next_agent="STOP")
        self.assert_error_code("invalid_failed_terminal_topology")

    def make_qa_validation_failure_run(self) -> Path:
        """Build a QA-stage VALIDATION_FAILED tree with no Phase 6 artifact."""
        self.make_successful_run()
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        self.update_manifest(
            "05-qa-attempt-1",
            status="FAILED",
            error_code="VALIDATION_FAILED",
            qa_verdict="NOT_RUN",
            terminal=False,
            next_agent="STOP",
        )
        self.update_manifest(
            "07-summary",
            status="FAILED",
            error_code="VALIDATION_FAILED",
            qa_verdict="NOT_RUN",
            terminal=True,
            next_agent="STOP",
        )
        return self.run_dir

    def test_qa_validation_failure_without_phase_six_validates(self) -> None:
        self.make_qa_validation_failure_run()
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_qa_validation_failure_requires_stop_summary(self) -> None:
        self.make_qa_validation_failure_run()
        self.update_manifest("07-summary", next_agent="prd-pipeline")
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_qa_validation_failure_requires_nonterminal_qa_manifest(self) -> None:
        self.make_qa_validation_failure_run()
        self.update_manifest("05-qa-attempt-1", terminal=True)
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_qa_validation_failure_requires_failed_qa_manifest(self) -> None:
        self.make_qa_validation_failure_run()
        self.update_manifest("05-qa-attempt-1", status="SUCCESS")
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_qa_validation_failure_with_phase_six_pair_is_rejected(self) -> None:
        self.make_qa_validation_failure_run()
        self.write_phase(self.run_dir, "06-repair-skipped", phase="REPAIR", status="SKIPPED")
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_qa_path_rejects_non_successful_base_phase(self) -> None:
        self.make_successful_run()
        self.update_manifest("02-context", status="BLOCKED", error_code="ROLES_FILE_NOT_FOUND")
        self.assert_error_code("invalid_terminal_topology")

    def test_qa_path_rejects_terminal_base_phase(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", terminal=True)
        self.assert_error_code("invalid_terminal_topology")

    def test_qa_path_accepts_warned_figma_phase(self) -> None:
        self.make_successful_run()
        self.update_manifest("03-figma", status="SUCCESS_WITH_WARNINGS")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_success_summary_requires_terminal_stop_and_no_error(self) -> None:
        cases = (
            {"terminal": False},
            {"error_code": "INPUT_INVALID"},
            {"next_agent": "prd-author"},
        )
        for index, updates in enumerate(cases):
            with self.subTest(updates=updates):
                self.make_successful_run()
                self.update_manifest("07-summary", **updates)
                self.assert_error_code("invalid_success_terminal_topology")
                self.run_dir = Path(self.temp_dir.name) / f"run-summary-{index}"

    def make_repair_record_run(self) -> None:
        self.make_successful_run(qa_attempts=2, complexity="Complex")
        self.update_manifest("05-qa-attempt-1", status="SUCCESS", error_code="CHECKLIST_FAILED", qa_verdict="CHECKLIST_FAILED", next_agent="prd-author")
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        self.write_phase(self.run_dir, "06-repair-attempt-1", phase="REPAIR", retry_count=1, complexity="Complex")

    def assert_body_required(self, directory: str) -> None:
        content = (self.run_dir / directory / "content.md").read_text(encoding="utf-8")
        self.update_content(directory, content.split("\n\n", 1)[0] + "\n\n")
        self.assert_error_code("missing_content_body")

    def test_repair_record_phases_require_content_body(self) -> None:
        directories = ("04-author", "05-qa-attempt-1", "06-repair-attempt-1", "07-summary")
        for index, directory in enumerate(directories):
            with self.subTest(directory=directory):
                self.make_repair_record_run()
                self.assert_body_required(directory)
                self.run_dir = Path(self.temp_dir.name) / f"run-repair-body-{index}"

    def test_consolidation_phase_requires_content_body(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest("06-repair-skipped", consolidation_attempts=1)
        self.update_manifest("05-qa-attempt-2", retry_count=0)
        self.write_phase(self.run_dir, "06-consolidation-attempt-1", phase="REPAIR", consolidation_attempts=1, qa_verdict="CHECKLIST_PASSED")
        self.assert_body_required("06-consolidation-attempt-1")

    def test_non_record_phases_allow_empty_body(self) -> None:
        self.make_successful_run()
        for directory in ("01-plan", "02-context"):
            content = (self.run_dir / directory / "content.md").read_text(encoding="utf-8")
            self.update_content(directory, content.split("\n\n", 1)[0] + "\n\n")
        self.assertNotIn("missing_content_body", {error.code for error in validator.validate_run(self.run_dir)})

    def test_artifact_symlink_escaping_phase_directory_is_rejected(self) -> None:
        self.make_successful_run()
        outside = Path(self.temp_dir.name) / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        (self.run_dir / "01-plan" / "linked.md").symlink_to(outside)
        self.update_manifest(
            "01-plan",
            artifacts=[{"path": "content.md", "type": "content"}, {"path": "linked.md", "type": "evidence"}],
        )
        self.assert_error_code("invalid_artifact_path")

    def test_artifact_inside_phase_directory_still_validates(self) -> None:
        self.make_successful_run()
        (self.run_dir / "01-plan" / "evidence.md").write_text("evidence", encoding="utf-8")
        self.update_manifest(
            "01-plan",
            artifacts=[{"path": "content.md", "type": "content"}, {"path": "evidence.md", "type": "evidence"}],
        )
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_missing_manifest_reports_error_without_crash(self) -> None:
        self.make_early_terminal_run("01-plan", phase="PLAN", error_code="PLAN_INCOMPLETE", status="BLOCKED")
        (self.run_dir / "01-plan" / "manifest.json").unlink()
        self.assert_error_code("missing_manifest")

    def test_unparseable_manifest_reports_error_without_crash(self) -> None:
        self.make_successful_run()
        (self.run_dir / "02-context" / "manifest.json").write_text("{not json", encoding="utf-8")
        self.assert_error_code("invalid_json")

    def test_non_utf8_content_reports_error_without_crash(self) -> None:
        self.make_successful_run()
        (self.run_dir / "04-author" / "content.md").write_bytes(b"\xff\xfe\x00\x01invalid")
        self.assert_error_code("invalid_content")

    def test_relative_target_path_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", target_path="relative/target.md")
        self.assert_error_code("relative_target_path")

    def test_cross_phase_binding_rejects_target_path_drift(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", target_path="/workspace/prd/other-target.md")
        self.assert_error_code("cross_phase_mismatch")

    def test_cross_phase_binding_rejects_document_type_drift(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", document_type="Notification")
        self.assert_error_code("cross_phase_mismatch")

    def test_cross_phase_binding_rejects_run_id_drift(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", run_id="other-run")
        self.assert_error_code("cross_phase_mismatch")

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
        self.assert_error_code("invalid_phase_topology")

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
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            exit_code = validator.main([
                "run",
                "--run-dir",
                str(self.run_dir),
                "--repository-root",
                str(self.run_dir.parent),
            ])
        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR run_dir_inside_repository", stream.getvalue())

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

    def test_empty_string_target_path_is_allowed_only_for_load(self) -> None:
        self.make_successful_run()
        self.update_manifest("00-load", target_path="")
        self.assertEqual(validator.validate_run(self.run_dir), [])

    def test_empty_string_target_path_is_rejected_from_plan_onward(self) -> None:
        phase_directories = (
            "01-plan",
            "02-context",
            "03-figma",
            "04-author",
            "05-qa-attempt-1",
            "06-repair-skipped",
            "07-summary",
        )
        for directory in phase_directories:
            with self.subTest(directory=directory):
                self.make_successful_run()
                self.update_manifest(directory, target_path="")
                self.assert_error_code("missing_target_path")
                self.run_dir = Path(self.temp_dir.name) / f"run-empty-target-{directory}"

    def test_unknown_status_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("04-author", status="UNKNOWN")
        self.assert_error_code("unknown_status")

    def test_manifest_schema_and_agent_names_are_canonical(self) -> None:
        cases = (
            ({"schema_version": "2.0"}, "invalid_schema_version"),
            ({"agent": "evil-agent"}, "unknown_agent"),
            ({"next_agent": "evil-agent"}, "unknown_next_agent"),
        )
        for index, (updates, code) in enumerate(cases):
            with self.subTest(updates=updates):
                self.make_successful_run()
                self.update_manifest("01-plan", **updates)
                self.assert_error_code(code)
                self.run_dir = Path(self.temp_dir.name) / f"run-canonical-{index}"

    def test_unknown_complexity_uses_zero_retry_limit(self) -> None:
        self.make_successful_run()
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.update_manifest("00-load", retry_limit=1)
        self.assert_error_code("invalid_retry_limit")

    def test_load_phase_requires_unknown_complexity_before_plan(self) -> None:
        self.make_successful_run()
        self.update_manifest("00-load", complexity="Simple", retry_limit=1)
        self.assert_error_code("invalid_load_complexity")

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

    def test_document_not_found_blocked_summary_rejects_clean_qa(self) -> None:
        self.assert_clean_qa_rejects_terminal_failure("DOCUMENT_NOT_FOUND")

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

    def test_missing_summary_does_not_suppress_topology_diagnostics(self) -> None:
        self.make_successful_run()
        self.update_manifest("02-context", status="BLOCKED", error_code="ROLES_FILE_NOT_FOUND")
        for path in (self.run_dir / "06-repair-skipped").iterdir():
            path.unlink()
        (self.run_dir / "06-repair-skipped").rmdir()
        for path in (self.run_dir / "07-summary").iterdir():
            path.unlink()
        (self.run_dir / "07-summary").rmdir()
        codes = {error.code for error in validator.validate_run(self.run_dir)}
        self.assertIn("missing_summary", codes)
        self.assertIn("invalid_terminal_topology", codes)
        self.assertIn("invalid_phase_topology", codes)

    def test_unresolved_template_token_is_rejected(self) -> None:
        self.make_successful_run()
        self.update_manifest("01-plan", error_details="TODO: fill target")
        self.assert_error_code("unresolved_template")

    def assert_clean_qa_rejects_terminal_failure(self, error_code: str, status: str = "BLOCKED") -> None:
        self.make_successful_run()
        self.update_manifest("07-summary", status=status, error_code=error_code, error_details="fixture terminal state")
        self.assert_error_code("invalid_success_terminal_topology")

    def test_missing_roles_file_blocked_summary_rejects_clean_qa(self) -> None:
        self.assert_clean_qa_rejects_terminal_failure("ROLES_FILE_NOT_FOUND")

    def test_unresolved_roles_blocked_summary_rejects_clean_qa(self) -> None:
        self.assert_clean_qa_rejects_terminal_failure("RISK_ITEMS_FOUND")

    def test_qa_retry_exhausted_run_requires_failed_final_qa_topology(self) -> None:
        self.make_exhausted_run("Simple")
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.update_manifest("05-qa-attempt-2", status="SUCCESS", error_code="NONE", qa_verdict="CHECKLIST_PASSED")
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_consolidation_regression_run_requires_failed_final_qa_topology(self) -> None:
        self.make_successful_run(qa_attempts=2)
        self.update_manifest("05-qa-attempt-1", retry_count=0)
        self.update_manifest("06-repair-skipped", consolidation_attempts=1)
        self.update_manifest("05-qa-attempt-2", status="SUCCESS", error_code="CHECKLIST_FAILED", qa_verdict="CHECKLIST_FAILED", next_agent="prd-author", retry_count=0)
        self.write_phase(self.run_dir, "06-consolidation-attempt-1", phase="REPAIR", status="SUCCESS", consolidation_attempts=1, qa_verdict="CHECKLIST_PASSED")
        self.update_manifest("07-summary", status="FAILED", error_code="CONSOLIDATION_REGRESSION", qa_verdict="CHECKLIST_FAILED")
        self.assertEqual(validator.validate_run(self.run_dir), [])
        self.update_manifest("05-qa-attempt-2", status="SUCCESS", error_code="NONE", qa_verdict="CHECKLIST_PASSED")
        self.assert_error_code("invalid_failed_terminal_topology")

    def test_terminal_summary_status_is_pinned_to_terminal_values(self) -> None:
        for status in ("SUCCESS_WITH_WARNINGS", "SKIPPED", "UNKNOWN"):
            with self.subTest(status=status):
                self.make_exhausted_run("Simple")
                self.update_manifest("07-summary", status=status)
                self.assert_error_code("invalid_terminal_summary_status")
                self.run_dir = Path(self.temp_dir.name) / f"run-terminal-status-{status}"

    def test_summary_qa_verdict_must_equal_final_qa_verdict(self) -> None:
        self.make_exhausted_run("Simple")
        self.update_manifest("07-summary", qa_verdict="CHECKLIST_PASSED")
        self.assert_error_code("invalid_summary_qa_verdict")

    def test_failed_final_qa_rejects_unrelated_terminal_error_code(self) -> None:
        self.make_exhausted_run("Simple")
        self.update_manifest("07-summary", error_code="AUTHOR_WRITE_FAILURE")
        self.assert_error_code("invalid_failed_terminal_topology")


if __name__ == "__main__":
    unittest.main()
