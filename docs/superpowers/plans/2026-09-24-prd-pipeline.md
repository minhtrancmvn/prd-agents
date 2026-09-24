# Canonical PRD Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and Git-track a user-invocable `prd-pipeline` skill that coordinates existing PRD agents through persisted handoffs, explicit gates, bounded repair cycles, and deterministic artifact validation.

**Architecture:** `skills/prd-pipeline/SKILL.md` owns orchestration and dispatches existing specialist agents in sequence. Two reference documents define phase contracts and dual-layer artifacts; one standard-library Python validator checks package structure and run manifests without replacing semantic QA from `prd-consistency-checker`. Existing agents remain specialists, with narrow compatibility fixes to the legacy orchestrator, Figma failure classification, and checker external-link behavior.

**Tech Stack:** Claude Code skill Markdown/YAML, Claude Code `Agent`/`Task` dispatch, Python 3 standard library (`argparse`, `json`, `pathlib`, `unittest`), Git.

**Spec:** `docs/superpowers/specs/2026-09-24-prd-pipeline-design.md`

## Global Constraints

- Canonical runtime location is exactly `skills/prd-pipeline/SKILL.md`; do not create a second `pipelines/` topology.
- Existing specialist agents retain their authoring responsibilities; pipeline coordinates rather than duplicates them.
- Pipeline must remain user-invocable for PRD, notification requirement, and email-template requirement creation or update.
- Generated run artifacts must live outside repository source and must never be committed.
- Plan text may use `TODO` and `TBD` only when naming prohibited unresolved markers that the validator must detect; implementation output must contain none.
- Validator uses Python standard library only and checks structural facts, not model judgment.
- `prd-consistency-checker` remains source of document-specific QA truth.
- Live ClickUp validity must be `NOT_CHECKED` unless authorized lookup evidence is supplied.
- Figma auth, timeout, malformed response, and unavailable required source block; valid sparse data does not.
- Simple QA allows one correction retry; Complex QA allows two; consolidation gets one separate pass.
- Every phase has paired `manifest.json` and `content.md`, including skipped Figma.
- No credentials, settings, histories, caches, target PRDs, or runtime state enter Git.
- All code changes remain on `feature/add-prd-pipeline`.
- Commit messages use conventional format and contain no generated attribution.

## Review Focus

1. **Relative target path in a run manifest:** validator must reject it with a precise `target_path must be absolute` error when target path is required.
2. **Skipped Figma phase without human artifact:** validator must still require both `manifest.json` and `content.md`; skipped is a status, not an absent artifact.
3. **Retry count above complexity limit:** validator must reject `retry_count=2` for Simple and `retry_count=3` for Complex while allowing separate `consolidation_attempts=1`.
4. **Unknown or contradictory status values:** validator must reject unknown phase statuses and reject terminal success when QA verdict is not `CHECKLIST_PASSED`.
5. **ClickUp URL without verification evidence:** checker and pipeline must report syntax-only validation plus live state `NOT_CHECKED`, never infer validity.

## File Structure

### Create

- `skills/prd-pipeline/SKILL.md` — executable phase sequence, dispatch prompts, gates, retries, final response.
- `skills/prd-pipeline/references/prd-pipeline-contract.md` — normalized status, phase, failure, retry, and final-summary contract.
- `skills/prd-pipeline/references/prd-artifact-format.md` — exact run-directory and JSON/Markdown artifact schema.
- `skills/prd-pipeline/scripts/validate-prd-pipeline.py` — package and run-artifact validator CLI.
- `skills/prd-pipeline/tests/test_validate_prd_pipeline.py` — dependency-free validator unit tests using temporary fixture trees.

### Modify

- `.gitignore` — track implementation plan and only `skills/prd-pipeline/**`; continue ignoring run artifacts and other runtime state.
- `agents/prd-orchestrator.md` — identify `prd-pipeline` as executable coordinator; retain legacy policy role without false nested-dispatch claim.
- `agents/prd-figma-reader.md` — distinguish transport/tool failure from valid sparse output and include traceability fields.
- `agents/prd-consistency-checker.md` — add workspace root/external verification inputs, truthful ClickUp behavior, and mutually exclusive status protocol.
- `README.md` — install skill plus agents, invoke pipeline, explain artifacts/gates, and replace obsolete orchestration limitation.
- `task_plan.md` — mark implementation and verification phases while work proceeds; file remains local because root ignore policy excludes it.

### Do not modify unless validation proves necessary

- `prd-shared-authoring-standards.md` — pipeline mechanics do not belong in document authoring rules.
- `agents/prd-planner.md`, `agents/prd-context-role-analyzer.md`, and three author agents — pipeline wraps their existing outputs and supplies explicit prompts.
- Toolkit-wide `skills/INDEX.json` or `agents/INDEX.json` — not tracked by this PRD repository; run external catalog checks only when available, never import unrelated runtime files.
- Sync hooks — README installation copies this package explicitly; no installer change in this repository.

---

### Task 1: Lock Artifact Contract with Failing Validator Tests

**Files:**
- Create: `skills/prd-pipeline/tests/test_validate_prd_pipeline.py`
- Create: `skills/prd-pipeline/scripts/validate-prd-pipeline.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `Path` values for a package root or run directory.
- Produces:
  - `ValidationError = dataclass(frozen=True)` with `path: str`, `code: str`, `message: str`.
  - `validate_package(skill_root: Path) -> list[ValidationError]`.
  - `validate_run(run_dir: Path) -> list[ValidationError]`.
  - `main(argv: list[str] | None = None) -> int`.
  - CLI: `python3 validate-prd-pipeline.py package --skill-root PATH`.
  - CLI: `python3 validate-prd-pipeline.py run --run-dir PATH`.

- [ ] **Step 1: Extend `.gitignore` for exact plan and pipeline paths**

Keep current deny-by-default policy. Add only these plan and pipeline rules; preserve existing spec rule:

```gitignore
!/docs/superpowers/plans/
/docs/superpowers/plans/*
!/docs/superpowers/plans/2026-09-24-prd-pipeline.md
!/skills/
/skills/*
!/skills/prd-pipeline/
!/skills/prd-pipeline/**
```

Verify tracked candidates:

```bash
git check-ignore -v docs/superpowers/plans/2026-09-24-prd-pipeline.md skills/prd-pipeline/tests/test_validate_prd_pipeline.py || true
git ls-files --others --exclude-standard
```

Expected: plan and future pipeline paths are not excluded; unrelated `~/.claude` runtime files remain excluded.

- [ ] **Step 2: Write tests for package validation**

Create `skills/prd-pipeline/tests/test_validate_prd_pipeline.py` using `unittest`, `tempfile.TemporaryDirectory`, `importlib.util.spec_from_file_location`, and `Path`. Load the hyphenated validator filename dynamically.

Add these concrete tests:

```python
class PackageValidationTests(unittest.TestCase):
    def test_package_requires_skill_references_script_and_tests(self):
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

    def test_complete_package_passes(self):
        root = self.make_complete_skill_root()
        self.assertEqual(validator.validate_package(root), [])
```

`make_complete_skill_root()` must write:

- `SKILL.md` with frontmatter containing `name: prd-pipeline`, `description`, `version`, `user-invocable: true`, `allowed-tools`, and all phase headings from `Phase 0: LOAD` through `Phase 7: REPORT`;
- both required references;
- validator script and test file placeholders containing non-empty text.

- [ ] **Step 3: Write tests for run validation happy paths**

Add helpers:

```python
def write_phase(
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
    ...
```

The helper writes both `manifest.json` and non-empty `content.md`. Manifest uses exact fields from Task 2's artifact schema.

Add tests:

```python
def test_successful_use_case_create_passes(self): ...
def test_successful_notification_create_passes(self): ...
def test_successful_email_update_passes(self): ...
def test_skipped_figma_with_both_artifacts_passes(self): ...
def test_qa_failure_then_successful_repair_passes(self): ...
```

Each successful tree includes `00-load`, `01-plan`, `02-context`, `03-figma`, `04-author`, at least one `05-qa-attempt-*`, and `07-summary`. Final summary uses `qa_verdict: CHECKLIST_PASSED` and `terminal: true`.

- [ ] **Step 4: Write tests for structural and retry failures**

Add:

```python
def test_relative_target_path_is_rejected(self): ...
def test_skipped_figma_without_content_is_rejected(self): ...
def test_unknown_status_is_rejected(self): ...
def test_simple_retry_count_above_one_is_rejected(self): ...
def test_complex_retry_count_above_two_is_rejected(self): ...
def test_two_consolidation_attempts_are_rejected(self): ...
def test_terminal_success_requires_checklist_passed(self): ...
def test_missing_summary_is_rejected(self): ...
def test_unresolved_template_token_is_rejected(self): ...
def test_missing_roles_file_blocked_run_is_valid_terminal_state(self): ...
def test_unresolved_roles_blocked_run_is_valid_terminal_state(self): ...
def test_qa_retry_exhausted_run_is_valid_terminal_state(self): ...
def test_consolidation_regression_run_is_valid_terminal_state(self): ...
```

For blocking terminal states, summary must be present with `STATUS: BLOCKED` or `FAILED`, matching `error_code`, and `next_agent: STOP`.

- [ ] **Step 5: Run tests and verify expected import failure**

Run:

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
```

Expected: FAIL because `validate-prd-pipeline.py` lacks exported `ValidationError`, `validate_package`, and `validate_run` behavior.

- [ ] **Step 6: Implement minimum validator skeleton and constants**

Implement:

```python
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
```

Implement package required-path checks and deterministic sorted error output.

- [ ] **Step 7: Implement run-manifest validation**

Use exact required keys:

```python
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
```

Rules:

- every phase directory has both files;
- JSON parses to object;
- values belong to allowed sets;
- `artifact_dir` is absolute;
- `target_path` is absolute when non-empty;
- `retry_limit` equals `1` for Simple and `2` for Complex once `complexity` exists in plan/summary manifests;
- `retry_count <= retry_limit`;
- `consolidation_attempts <= 1`;
- final success requires `qa_verdict == "CHECKLIST_PASSED"`;
- terminal blocked/failed result requires non-`NONE` `error_code` and `next_agent == "STOP"`;
- `07-summary` exists;
- strings matching `<[^>]+>`, `TBD`, `TODO`, `[PLACEHOLDER]`, or `[INSERT]` in manifest values fail as `unresolved_template`;
- artifacts listed in manifest exist and match relative paths inside the phase directory.

- [ ] **Step 8: Implement CLI and JSON/text output**

CLI behavior:

```text
PASS <validated-path>
```

or one line per error:

```text
ERROR <code> <path>: <message>
```

Return `0` on pass, `1` on validation findings, and `2` on invalid CLI usage.

- [ ] **Step 9: Run focused tests**

Run:

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit validator foundation**

```bash
git add .gitignore docs/superpowers/plans/2026-09-24-prd-pipeline.md skills/prd-pipeline/scripts/validate-prd-pipeline.py skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git commit -m "test: define PRD pipeline artifact validation"
```

---

### Task 2: Define Handoff and Artifact References

**Files:**
- Create: `skills/prd-pipeline/references/prd-pipeline-contract.md`
- Create: `skills/prd-pipeline/references/prd-artifact-format.md`
- Test: `skills/prd-pipeline/tests/test_validate_prd_pipeline.py`

**Interfaces:**
- Consumes: status and manifest constants implemented in Task 1.
- Produces: exact contract consumed by `SKILL.md`, agent dispatch prompts, run artifacts, validator fixtures, and README examples.

- [ ] **Step 1: Add failing contract-content tests**

Add package validator tests requiring contract reference to contain:

```python
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
```

Require artifact-format reference to contain:

```python
ARTIFACT_REQUIRED_TERMS = {
    "manifest.json",
    "content.md",
    "schema_version",
    "retry_count",
    "consolidation_attempts",
    "qa_verdict",
    "07-summary",
}
```

Run tests. Expected: FAIL because references do not exist.

- [ ] **Step 2: Write `prd-pipeline-contract.md`**

Include:

1. Pipeline input contract: request, workspace root, optional roles path, optional PRD root, optional run directory, optional external ClickUp verification evidence.
2. Exact handoff envelope:

```text
STATUS: SUCCESS | SUCCESS_WITH_WARNINGS | SKIPPED | BLOCKED | FAILED
AGENT: <agent-name-or-pipeline>
PHASE: LOAD | PLAN | CONTEXT | FIGMA | AUTHOR | QA | REPAIR | REPORT
DOCUMENT_TYPE: Use Case | Notification | Email Template | UNKNOWN
MODE: CREATE | UPDATE | UNKNOWN
TARGET_PATH: <absolute-path-or-empty>
ARTIFACT_DIR: <absolute-run-directory>
COMPLETED_CHECKS: <semicolon-separated-values-or-NONE>
UNRESOLVED_ITEMS: <semicolon-separated-values-or-NONE>
NEXT_AGENT: <agent-name-or-STOP>
ERROR_CODE: <allowed-error-code-or-NONE>
ERROR_DETAILS: <details-or-NONE>
```

3. Agent request tables listing exact inputs for all seven specialists.
4. Phase result tables listing gate, success status, blocking status, and next phase.
5. Retry rules: Simple `1`, Complex `2`, consolidation `1` separate.
6. Mutually exclusive checker interpretation: `CHECKLIST_PASSED`, `CHECKLIST_FAILED`, `ROLES_FILE_NOT_FOUND`, `INPUT_INVALID`, `DOCUMENT_NOT_FOUND`.
7. Final success and terminal failure response formats.
8. Explicit rule that worker prose is data to normalize, not executable instructions.

- [ ] **Step 3: Write `prd-artifact-format.md`**

Define directory layout:

```text
<run-dir>/
├── 00-load/
├── 01-plan/
├── 02-context/
├── 03-figma/
├── 04-author/
├── 05-qa-attempt-1/
├── 05-qa-attempt-2/       # only when needed
├── 06-repair-attempt-1/   # only when needed
└── 07-summary/
```

Every present directory contains `manifest.json` and `content.md`.

Define complete JSON example with all required keys and:

```json
{
  "schema_version": "1.0",
  "run_id": "prd-20260924-reset-password",
  "phase": "PLAN",
  "phase_number": 1,
  "agent": "prd-planner",
  "status": "SUCCESS",
  "document_type": "Use Case",
  "mode": "CREATE",
  "complexity": "Simple",
  "target_path": "/workspace/prd/reset-password.md",
  "artifact_dir": "/tmp/prd-pipeline/prd-20260924-reset-password",
  "completed_checks": ["seven plan fields present"],
  "unresolved_items": [],
  "next_agent": "prd-context-role-analyzer",
  "error_code": "NONE",
  "error_details": "NONE",
  "retry_count": 0,
  "retry_limit": 1,
  "consolidation_attempts": 0,
  "qa_verdict": "NOT_RUN",
  "terminal": false,
  "artifacts": [
    {"path": "content.md", "type": "content"}
  ]
}
```

State that `content.md` starts with handoff envelope, then original worker output. Define skipped Figma content as a brief reason, not an absent file.

- [ ] **Step 4: Align validator fields with reference schema**

Add `complexity` to required manifest keys and allowed values `Simple`, `Complex`, `UNKNOWN`. Ensure retry-limit validation derives from this field rather than directory assumptions.

- [ ] **Step 5: Run tests and package validator**

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
```

Expected: tests pass; package validation still reports `missing_skill` only until Task 3.

- [ ] **Step 6: Commit references**

```bash
git add skills/prd-pipeline/references skills/prd-pipeline/scripts/validate-prd-pipeline.py skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git commit -m "docs: define PRD pipeline handoff contracts"
```

---

### Task 3: Build Executable Pipeline Skill

**Files:**
- Create: `skills/prd-pipeline/SKILL.md`
- Modify: `skills/prd-pipeline/tests/test_validate_prd_pipeline.py`

**Interfaces:**
- Consumes: handoff and artifact contracts from Task 2; specialist agent names and current outputs.
- Produces: user-invocable orchestration skill with phases `LOAD`, `PLAN`, `CONTEXT AND ROLES`, `FIGMA`, `AUTHOR`, `QA`, `REPAIR AND RECHECK`, `REPORT`.

- [ ] **Step 1: Add failing skill-structure tests**

Add tests requiring:

```python
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
```

Also require references to both contract files and validator command.

Run tests. Expected: FAIL with `missing_skill` and missing term errors.

- [ ] **Step 2: Create frontmatter and operator boundaries**

Use:

```yaml
---
name: prd-pipeline
description: |
  Coordinate creation or update of use-case PRDs, notification requirements,
  and email-template requirements through planning, canonical role resolution,
  optional read-only Figma analysis, type-specific authoring, QA, and bounded
  repair. Use for end-to-end PRD requests. Do NOT use for a single specialist
  stage when its prepared inputs already exist.
version: 1.0.0
user-invocable: true
context: fork
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Agent
  - Task
routing:
  triggers:
    - "create prd"
    - "update prd"
    - "notification requirement"
    - "email template requirement"
    - "prd pipeline"
  pairs_with:
    - prd-planner
    - prd-context-role-analyzer
    - prd-figma-reader
    - prd-author
    - prd-noti-req-author
    - prd-email-req-author
    - prd-consistency-checker
  complexity: Complex
  category: domain
---
```

Add hardcoded behaviors:

- read project instructions first;
- create run artifacts before dispatch;
- never invent roles, URLs, or evidence;
- never continue through blocking gates;
- never claim success before checker pass and validator pass;
- never commit run artifacts;
- ask only for decisions that cannot be derived safely.

Add CAN/CANNOT and anti-pattern sections.

- [ ] **Step 3: Implement LOAD through FIGMA phases in skill instructions**

For each phase include Goal, Actions, Artifact, Gate, and Failure.

Dispatch prompt for planner must say:

```text
Return your complete Plan Document. Do not write the target requirement.
The caller will persist and normalize your output. Populate all seven mandatory
fields and include Figma Links to Analyse only when the request contains links.
```

Context prompt must include absolute workspace root and target path. Figma phase must write a skipped artifact when no links exist. Agent errors and empty outputs stop.

- [ ] **Step 4: Implement AUTHOR routing and gate**

Route exact document types:

```text
Use Case -> prd-author
Notification -> prd-noti-req-author
Email Template -> prd-email-req-author
```

Pass full Plan Document, Context Report, Figma analysis or explicit skip, absolute target path, shared standards path, and unresolved-role approval if any.

After worker returns:

1. verify target path exists with `Read`;
2. persist worker output;
3. record self-check claims in manifest;
4. do not substitute a new path when Update target is missing;
5. proceed only to checker.

- [ ] **Step 5: Implement QA and repair state machine**

Interpret checker first token using exclusive branches:

```text
CHECKLIST_PASSED -> success or optional one-pass consolidation
CHECKLIST_FAILED -> repair if retry_count < retry_limit
ROLES_FILE_NOT_FOUND -> terminal BLOCKED
INPUT_INVALID -> terminal FAILED
DOCUMENT_NOT_FOUND -> terminal FAILED
anything else -> terminal VALIDATION_FAILED
```

For repair, send full checker body plus original author inputs to same author. Increment normal retry only after an author correction. Re-run checker. Keep consolidation count separate and capped at one.

- [ ] **Step 6: Implement REPORT phase and validator gate**

Run:

```bash
python3 ~/.claude/skills/prd-pipeline/scripts/validate-prd-pipeline.py run --run-dir <absolute-run-dir>
```

If source-local project installation is active, resolve validator relative to loaded skill before user-level fallback.

Emit success only with exact fields:

```text
PRD_PIPELINE_COMPLETE
Target: /absolute/path
Document type: Use Case | Notification | Email Template
Mode: CREATE | UPDATE
Stages: LOAD, PLAN, CONTEXT, FIGMA|FIGMA_SKIPPED, AUTHOR, QA, REPORT
QA: CHECKLIST_PASSED
Retries: <count>/<limit>; consolidation=<none|passed>
Artifacts: /absolute/run-directory
Notes: <notes-or-NONE>
```

- [ ] **Step 7: Run tests and package validation**

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
```

Expected: PASS.

- [ ] **Step 8: Run repository skill validator when available**

```bash
if test -f scripts/skill_eval/quick_validate.py; then
  python3 scripts/skill_eval/quick_validate.py skills/prd-pipeline
else
  echo "SKIP: repository does not track toolkit skill_eval validator"
fi
```

Record skip honestly; do not copy runtime toolkit scripts into this repository.

- [ ] **Step 9: Commit executable skill**

```bash
git add skills/prd-pipeline/SKILL.md skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git commit -m "feat: add canonical PRD pipeline"
```

---

### Task 4: Align Narrow Specialist Interfaces

**Files:**
- Modify: `agents/prd-orchestrator.md`
- Modify: `agents/prd-figma-reader.md`
- Modify: `agents/prd-consistency-checker.md`
- Modify: `skills/prd-pipeline/tests/test_validate_prd_pipeline.py`

**Interfaces:**
- Consumes: pipeline contract from Task 2.
- Produces: truthful worker outputs compatible with pipeline interpretation, without changing authoring ownership.

- [ ] **Step 1: Add failing source-contract tests**

Add tests reading repository-relative agent files. Require:

```python
def test_legacy_orchestrator_routes_full_runs_to_prd_pipeline(): ...
def test_figma_reader_distinguishes_sparse_data_from_tool_failure(): ...
def test_figma_reader_reports_source_traceability(): ...
def test_checker_accepts_workspace_root_and_external_verification(): ...
def test_checker_reports_not_checked_without_live_evidence(): ...
def test_checker_declares_exclusive_first_line_statuses(): ...
```

Assertions must look for exact durable phrases, not entire prompt snapshots:

- orchestrator contains `` `prd-pipeline` is the executable coordinator ``;
- Figma reader contains `valid sparse result` and fields `Source URL`, `Node ID`, `Screens Analysed`, `Unresolved Ambiguities`;
- checker inputs contain `Workspace root` and `External ClickUp verification evidence`;
- checker contains `NOT_CHECKED` and all allowed first-line statuses.

Run tests. Expected: FAIL.

- [ ] **Step 2: Narrow `prd-orchestrator` to compatibility policy**

Change description and opening section to:

```text
`prd-pipeline` is the executable coordinator for complete PRD workflows.
This legacy agent documents routing, retry, and stop policy for compatibility.
It does not dispatch nested agents with its current tool allowlist. For a full
run, invoke `prd-pipeline`. For one prepared stage, invoke the specialist agent.
```

Keep existing tables as policy reference. Replace imperative `Invoke` wording with `The pipeline invokes` where needed. Do not add `Agent` or `Task` to this agent.

- [ ] **Step 3: Fix Figma failure classification and traceability**

Update failure rules:

- hard fail on MCP auth, timeout, transport, malformed response, missing requested node, or inaccessible required source;
- do not fail solely because a successful structured response has no relevant functional elements;
- return a valid sparse result with empty elements and explanatory note;
- tag failure fence as `text`.

Add output header fields:

```markdown
- **Source URL:** ...
- **File Key:** ...
- **Node ID:** ...
- **Screens Analysed:** ...
- **Screens Skipped:** ...
- **Unresolved Ambiguities:** ...
```

- [ ] **Step 4: Fix checker inputs and external-link truthfulness**

Add inputs:

```markdown
- Absolute workspace root
- Optional external ClickUp verification evidence keyed by URL
```

Replace `Verify any ClickUp links in metadata are real` with:

```text
Check ClickUp URL presence and syntax locally. Verify live validity only when
external verification evidence is provided or an authorized ClickUp lookup tool
is available. Otherwise report live validity as NOT_CHECKED; this is
informational, not a checklist failure by itself.
```

- [ ] **Step 5: Make checker status protocol exclusive**

Define allowed first lines:

```text
CHECKLIST_PASSED
CHECKLIST_FAILED
INPUT_INVALID
DOCUMENT_NOT_FOUND
ROLES_FILE_NOT_FOUND
```

State:

- exactly one appears;
- `CHECKLIST_*` only after document and roles source are readable;
- input/document/roles errors do not include checklist verdict;
- each error status includes attempted path and remediation.

Keep checker read-only.

- [ ] **Step 6: Run agent-contract and validator tests**

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
```

Expected: PASS.

- [ ] **Step 7: Run existing PRD inventory check**

```bash
python3 - <<'PY'
from pathlib import Path
import re

expected = {
    "prd-orchestrator",
    "prd-planner",
    "prd-context-role-analyzer",
    "prd-figma-reader",
    "prd-author",
    "prd-noti-req-author",
    "prd-email-req-author",
    "prd-consistency-checker",
}
files = sorted(Path("agents").glob("prd-*.md"))
assert len(files) == 8
names = set()
for path in files:
    match = re.search(r"^name:\s*([^\s]+)\s*$", path.read_text(), re.MULTILINE)
    assert match, path
    names.add(match.group(1))
assert names == expected
assert Path("prd-shared-authoring-standards.md").is_file()
print("validated PRD agent inventory")
PY
```

Expected: `validated PRD agent inventory`.

- [ ] **Step 8: Commit agent alignment**

```bash
git add agents/prd-orchestrator.md agents/prd-figma-reader.md agents/prd-consistency-checker.md skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git commit -m "fix: align PRD agents with pipeline contracts"
```

---

### Task 5: Document Installation, Invocation, and Development Validation

**Files:**
- Modify: `README.md`
- Modify: `skills/prd-pipeline/tests/test_validate_prd_pipeline.py`

**Interfaces:**
- Consumes: final paths, status names, and commands from Tasks 1–4.
- Produces: installation and operation documentation matching tracked source.

- [ ] **Step 1: Add failing README contract tests**

Add tests requiring README contains:

```python
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
```

Also assert obsolete text `Until its tool allowlist includes Agent` is absent.

Run tests. Expected: FAIL.

- [ ] **Step 2: Update repository purpose and contents**

Change opening from “only eight PRD agent definitions” to “eight specialists, one canonical pipeline skill, and shared authoring standards.” Add rows for `skills/prd-pipeline/SKILL.md`, references, validator, and tests.

- [ ] **Step 3: Replace intended workflow and limitation note**

Show `prd-pipeline` above workers. Explain `prd-orchestrator` is compatibility policy only. Remove recommendation that main conversation manually coordinates stages.

- [ ] **Step 4: Update installation commands**

User-level:

```bash
mkdir -p ~/.claude/agents ~/.claude/skills
cp agents/prd-*.md ~/.claude/agents/
cp prd-shared-authoring-standards.md ~/.claude/
rm -rf ~/.claude/skills/prd-pipeline
cp -R skills/prd-pipeline ~/.claude/skills/
```

Warn that `rm -rf` removes only same-named installed pipeline after user inspects/backups; do not run it as part of implementation.

Project-level:

```bash
PROJECT_ROOT=/path/to/your/project
mkdir -p "$PROJECT_ROOT/.claude/agents" "$PROJECT_ROOT/.claude/skills"
cp agents/prd-*.md "$PROJECT_ROOT/.claude/agents/"
rm -rf "$PROJECT_ROOT/.claude/skills/prd-pipeline"
cp -R skills/prd-pipeline "$PROJECT_ROOT/.claude/skills/"
cp prd-shared-authoring-standards.md ~/.claude/
```

- [ ] **Step 5: Update quick start and operational sections**

Use:

```text
/prd-pipeline Create a use-case PRD for resetting a password as a Generic User.
```

Document:

- run artifact location is reported at completion;
- artifacts are not source-controlled;
- every phase has manifest/content pair;
- status/error signals;
- retry budgets;
- ClickUp live state `NOT_CHECKED` without evidence;
- Figma skipped versus failed behavior.

- [ ] **Step 6: Replace development validation section**

Document commands:

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py run --run-dir /absolute/path/to/run
python3 -m py_compile skills/prd-pipeline/scripts/validate-prd-pipeline.py skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git diff --check
```

Retain agent inventory check, updated to assert pipeline files exist and orchestrator names all workers.

- [ ] **Step 7: Run tests and documentation command checks**

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
python3 -m py_compile skills/prd-pipeline/scripts/validate-prd-pipeline.py skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git diff --check
```

Expected: PASS.

- [ ] **Step 8: Commit documentation**

```bash
git add README.md skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git commit -m "docs: document PRD pipeline usage"
```

---

### Task 6: Full Verification and Branch Review

**Files:**
- Modify only if verification reveals a defect in files from Tasks 1–5.
- Update local-only: `task_plan.md`.

**Interfaces:**
- Consumes: complete branch implementation.
- Produces: verified branch with no unstaged implementation changes and recorded evidence.

- [ ] **Step 1: Re-read spec and compare every requirement**

Read:

```text
docs/superpowers/specs/2026-09-24-prd-pipeline-design.md
docs/superpowers/plans/2026-09-24-prd-pipeline.md
```

Create a temporary checklist mapping every spec heading to implemented path. Delete temporary checklist after review.

- [ ] **Step 2: Run validator tests**

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
```

Expected: all tests pass, including five Review Focus cases.

- [ ] **Step 3: Run package and syntax validation**

```bash
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
python3 -m py_compile skills/prd-pipeline/scripts/validate-prd-pipeline.py skills/prd-pipeline/tests/test_validate_prd_pipeline.py
```

Expected: package `PASS`; compilation silent success.

- [ ] **Step 4: Run PRD repository inventory validation**

Run README's updated dependency-free inventory block. Expected: eight agents, shared standards, pipeline skill, references, script, and tests validated.

- [ ] **Step 5: Run external toolkit checks only if scripts exist**

```bash
if test -f scripts/generate-index.py; then
  python3 scripts/generate-index.py --check
else
  echo "SKIP: generate-index.py not tracked by PRD repository"
fi

if test -f scripts/validate-pairs-with.py; then
  python3 scripts/validate-pairs-with.py
else
  echo "SKIP: validate-pairs-with.py not tracked by PRD repository"
fi

if test -f scripts/list-capabilities.py; then
  python3 scripts/list-capabilities.py summary
else
  echo "SKIP: list-capabilities.py not tracked by PRD repository"
fi
```

Do not claim skipped checks passed.

- [ ] **Step 6: Run Git validation**

```bash
git diff main...HEAD --check
git status --short --branch
git ls-files
```

Verify tracked files include only intended PRD package source/docs. Confirm no run artifact directory, generated PRD, credential, settings file, or `task_plan.md` is tracked.

- [ ] **Step 7: Request whole-branch review**

Use a fresh reviewer agent against `main...HEAD`. Review focus:

- executable dispatch instructions;
- gate contradictions;
- validator false positives/negatives;
- retry accounting;
- ClickUp and Figma truthfulness;
- README/install correctness;
- scope creep beyond approved spec.

Apply only confirmed findings. Re-run Steps 2–6 after any fix.

- [ ] **Step 8: Update task plan status**

Mark implementation and verification complete in local `task_plan.md`. Record exact test counts, skipped external checks, and any fixed reviewer findings.

- [ ] **Step 9: Verify commit history and clean tree**

```bash
git log --oneline main..HEAD
git status --porcelain
```

Expected: design plus implementation commits present; working tree clean except intentionally ignored local `task_plan.md`.

- [ ] **Step 10: Create final fix commit only when needed**

If verification or review produced tracked fixes:

```bash
git add <explicit-fixed-files>
git commit -m "fix: address PRD pipeline validation findings"
```

If no tracked fixes exist, do not create an empty commit.

- [ ] **Step 11: Report evidence**

Report:

- branch and commit hashes;
- created/modified files;
- unit test count and result;
- package validator result;
- syntax check result;
- inventory result;
- external checks run versus skipped;
- whole-branch review result;
- clean-tree status;
- no push or PR unless separately requested.
