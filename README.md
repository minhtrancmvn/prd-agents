# PRD Agents

PRD Agents provides eight specialists, one canonical pipeline skill, and shared authoring standards for creating and updating use-case product requirements documents (PRDs), notification requirements, and email-template requirements. `prd-pipeline` is sole executable entry point for full end-to-end runs. `prd-orchestrator` is legacy compatibility policy only; it does not execute or coordinate a full run.

Repository tracks source definitions and validation tooling only. Generated requirements, run artifacts, Claude Code settings, credentials, histories, caches, hooks, and databases are runtime state and remain outside version control.

## Supported documents

| Document type | Author agent | Main output |
|---|---|---|
| Use Case | `prd-author` | User workflow, access, core functionality, grouped business rules, and optional flows or designs |
| Notification | `prd-noti-req-author` | Trigger, recipients, delivery channel, exact notification content, and content parameters |
| Email Template | `prd-email-req-author` | Trigger, recipients, delivery behavior, exact email content, and dynamic variables |

## Workflow

```text
/prd-pipeline
    |
    v
LOAD -> PLAN -> CONTEXT -> FIGMA -> AUTHOR -> QA -> REPAIR/RECHECK -> REPORT
           |          |        |                  |
           |          |        +--> SKIPPED when no planned Figma links
           |          +--> blocks on unreadable roles or unapproved role risks
           +--> selects document type, target path, and retry budget
```

`prd-pipeline` persists phase artifacts, dispatches specialists, applies gates, and validates completed runs. It invokes these workers in pipeline-controlled order: `prd-planner`, `prd-context-role-analyzer`, optional `prd-figma-reader`, one type-specific author, and `prd-consistency-checker`. Run a named specialist only for one prepared stage with required inputs already available. Full runs use `/prd-pipeline`; legacy `prd-orchestrator` remains policy-only.

## Repository contents

| Path | Resource | Responsibility |
|---|---|---|
| `skills/prd-pipeline/SKILL.md` | `prd-pipeline` | Canonical executable full-run coordinator |
| `skills/prd-pipeline/references/prd-pipeline-contract.md` | Pipeline contract | Defines inputs, handoffs, retry rules, and terminal responses |
| `skills/prd-pipeline/references/prd-artifact-format.md` | Artifact format | Defines phase artifact pairs and manifest schema |
| `skills/prd-pipeline/scripts/validate-prd-pipeline.py` | Validator | Validates installed package structure and completed run artifacts |
| `skills/prd-pipeline/tests/test_validate_prd_pipeline.py` | Contract tests | Tests package, run, specialist, and README contracts |
| `agents/prd-orchestrator.md` | `prd-orchestrator` | Legacy compatibility policy; directs full runs to `prd-pipeline` |
| `agents/prd-planner.md` | `prd-planner` | Produces seven-field Plan Document |
| `agents/prd-context-role-analyzer.md` | `prd-context-role-analyzer` | Resolves exact role names and related PRD context |
| `agents/prd-figma-reader.md` | `prd-figma-reader` | Reads functional Figma details through read-only tools |
| `agents/prd-author.md` | `prd-author` | Writes or updates use-case PRDs |
| `agents/prd-noti-req-author.md` | `prd-noti-req-author` | Writes or updates notification requirements |
| `agents/prd-email-req-author.md` | `prd-email-req-author` | Writes or updates email-template requirements |
| `agents/prd-consistency-checker.md` | `prd-consistency-checker` | Reports exclusive QA verdicts and normalized findings |
| `prd-shared-authoring-standards.md` | Shared standards | Defines workspace discovery, metadata, versioning, references, diagrams, language, and verification rules |

Subagent files use Markdown with YAML frontmatter. Each definition declares explicit tool allowlist.

## Prerequisites

- [Claude Code](https://code.claude.com/docs/en/overview) with custom skills and subagent support.
- Python 3.10 or newer to run the pipeline validator and its tests (standard library only).
- Target workspace containing exactly one discoverable `roles-permissions.md`, or explicit roles-file path in request.
- Product context sufficient to identify scope, roles, source documents, and target requirements path.
- Optional: configured `figma-console-mcp` MCP server and Figma access when request contains Figma URLs. The server name must match the `mcp__figma-console-mcp__` tool allowlist prefix in `agents/prd-figma-reader.md`. See [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp).

No package manager, application runtime, or build system is required.

## Installation

Clone repository, then install agents, shared standards, and canonical skill.

### User-level installation

User-level components are available across projects.

```bash
git clone https://github.com/minhtrancmvn/prd-agents.git
cd prd-agents
mkdir -p ~/.claude/agents ~/.claude/skills
cp agents/prd-*.md ~/.claude/agents/
cp prd-shared-authoring-standards.md ~/.claude/
rm -rf ~/.claude/skills/prd-pipeline
cp -R skills/prd-pipeline ~/.claude/skills/
```

Inspect or back up `~/.claude/skills/prd-pipeline` before running `rm -rf`. It removes only existing installed pipeline with that same name. Do not use it to remove any other skill directory.

### Project-level installation

Project-scoped agents and skill are available only in selected project. Run these commands from the target workspace and set `CLONE_ROOT` to the absolute path of your cloned repository.

```bash
PROJECT_ROOT=/path/to/your/project
CLONE_ROOT=/absolute/path/to/prd-agents
[ -n "$PROJECT_ROOT" ] && [ "$PROJECT_ROOT" != "/" ] || { echo "PROJECT_ROOT must be a real project directory"; exit 1; }
mkdir -p "$PROJECT_ROOT/.claude/agents" "$PROJECT_ROOT/.claude/skills"
cp "$CLONE_ROOT"/agents/prd-*.md "$PROJECT_ROOT/.claude/agents/"
rm -rf "$PROJECT_ROOT/.claude/skills/prd-pipeline"
cp -R "$CLONE_ROOT"/skills/prd-pipeline "$PROJECT_ROOT/.claude/skills/"
cp "$CLONE_ROOT"/prd-shared-authoring-standards.md ~/.claude/
```

The `PROJECT_ROOT` guard aborts before `rm -rf` when `PROJECT_ROOT` is empty or `/`, so removal cannot act on the root filesystem.

Inspect or back up `$PROJECT_ROOT/.claude/skills/prd-pipeline` before removal. Shared standards stay at `~/.claude/prd-shared-authoring-standards.md` because tracked agent prompts reference that path.

Claude Code normally detects additions or edits in existing skill and agent directories within seconds. Restart Claude Code if installation created first such directory in active session.

## Quick start

Start Claude Code from target workspace, then invoke canonical pipeline.

```text
/prd-pipeline Create a use-case PRD for resetting a password as a Generic User.
```

For update or Figma-backed work, pass target path, relevant source context, and Figma URL in same `/prd-pipeline` request. Pipeline derives safe decisions from supplied context. It runs with `context: fork` and cannot prompt mid-run, so when it cannot derive a decision safely it stops with `BLOCKED` and returns the exact unresolved list. For unresolved roles, re-invoke `/prd-pipeline` with explicit approval for that exact list in the request.

### Invocation examples

Create notification requirements:

```text
/prd-pipeline Create notification requirements for notifying a Contractor when a job is assigned.

Workspace root: /absolute/path/to/project
Target path: /absolute/path/to/project/business-requirements/job-assigned-notification.md
```

Create email-template requirements:

```text
/prd-pipeline Create email-template requirements for password-reset confirmation.

Workspace root: /absolute/path/to/project
Target path: /absolute/path/to/project/business-requirements/password-reset-email.md
```

Update an existing document:

```text
/prd-pipeline Update this notification requirement with the new delivery rule.

Workspace root: /absolute/path/to/project
Target path: /absolute/path/to/project/business-requirements/job-assigned-notification.md
Preserve content outside the requested scope.
```

Use Figma-backed requirements by including explicit Figma URLs or node links:

```text
/prd-pipeline Create a use-case PRD from this design:
https://www.figma.com/design/<file-key>/<name>?node-id=<node-id>

Workspace root: /absolute/path/to/project
Target path: /absolute/path/to/project/business-requirements/example.md
```

Optional explicit inputs reduce blocked runs:

```text
Roles path: /absolute/path/to/project/roles-permissions.md
PRD root: /absolute/path/to/project/business-requirements
Mode: CREATE
```

Use `/prd-pipeline` for complete runs. Invoke a named specialist only when required inputs for that single stage already exist. Do not invoke `prd-orchestrator` for full runs; it is legacy routing and retry policy, not executable coordination.

## Run artifacts

Pipeline reports absolute run artifact location in terminal response under `Artifacts:`. Pipeline stores artifacts outside repository source and does not source-control them. Never add generated PRDs, credentials, runtime state, or run artifacts to Git.

Every phase directory has both `manifest.json` and `content.md`, including skipped phases. `manifest.json` stores normalized machine-readable state. `content.md` begins with normalized handoff envelope then preserves worker output or local evidence. Every terminal run has `07-summary`. Runs reaching QA include `05-qa-attempt-N`; only a run whose final QA verdict is `CHECKLIST_PASSED` needs a Phase 6 artifact — `06-repair-skipped`, `06-consolidation-attempt-1`, or the `06-repair-attempt-N` pairs already recorded for the run. Early terminal runs from LOAD, PLAN, CONTEXT, FIGMA, or AUTHOR stop with `07-summary` and do not create Phase 6 artifact. A blocking QA terminal stopped before a passing verdict also carries no Phase 6 artifact.

Successful terminal response has `PRD_PIPELINE_COMPLETE`, absolute target path, document type, mode, completed stages, `CHECKLIST_PASSED`, retry accounting, artifact directory, and notes. Blocked or failed terminal response has `PRD_PIPELINE_BLOCKED` or `PRD_PIPELINE_FAILED`, phase, error, target, remediation, artifacts, and unresolved items.

## Status, retry, ClickUp, and Figma behavior

### Status and error signals

| Signal | Meaning | Next action |
|---|---|---|
| `INPUT_INVALID` | Required request, workspace, target, or checker input is missing, malformed, or unsafe | Supply valid required input and rerun from a new pipeline invocation |
| `WORKSPACE_NOT_FOUND` | Supplied workspace root does not exist | Supply existing absolute workspace root and rerun |
| `ROLES_FILE_NOT_FOUND` | Roles source missing or unreadable | Add or specify readable `roles-permissions.md`, then rerun pipeline |
| `RISK_ITEMS_FOUND` | Requested roles do not resolve without approval | Correct roles or explicitly approve exact unresolved-role list |
| `PLAN_INCOMPLETE` | Planner result lacks required fields or safe target resolution | Supply missing scope, roles, documents, target, outline, or complexity facts |
| `FIGMA_READ_FAILURE` | Required Figma source failed, was inaccessible, or returned malformed output or no output at all (an empty response, not a sparse-but-valid analysis) | Verify MCP availability and Figma access, then rerun |
| `AUTHOR_INPUT_INVALID` | Selected author received invalid type, target, mode, or required handoff input | Correct planned input or target policy and rerun |
| `AUTHOR_WRITE_FAILURE` | Author did not produce planned exact target | Correct target inputs or workspace write access, then rerun |
| `DOCUMENT_NOT_FOUND` | Planned target cannot be read before QA or is absent after authoring | Restore or create exact planned target, then rerun |
| `CHECKLIST_FAILED` | QA found blocking findings with retry budget remaining | Pipeline supplies complete findings to selected author and reruns QA |
| `QA_RETRY_EXHAUSTED` | Normal correction budget consumed without clean QA | Resolve reported findings, then start new run |
| `CONSOLIDATION_REGRESSION` | Optional post-pass consolidation caused QA failure | Revert or correct consolidation changes, then start new run |
| `VALIDATION_FAILED` | Package or run-artifact validation failed, or worker/checker output was unsupported, mixed, empty, malformed, or an agent error | Repair reported artifact or contract issue; correct worker/checker input or availability; then start a new run or rerun validation as applicable |
| `CHECKLIST_PASSED` | QA found no blocking checklist issue | Pipeline validates run and reports completion |

`CHECKLIST_PASSED` and `CHECKLIST_FAILED` are mutually exclusive QA outcomes. QA-stage VALIDATION_FAILED: QA manifest status FAILED, error_code VALIDATION_FAILED, terminal false, next_agent STOP; 07-summary status FAILED, error_code VALIDATION_FAILED, terminal true, next_agent STOP. Pipeline is terminal through 07-summary, not QA manifest. REPORT-stage VALIDATION_FAILED shape remains unchanged. Pipeline does not claim success until final checker verdict passes and run validator succeeds.

### Retry budgets

Retry budget counts successful author correction attempts after a failed checklist. Initial QA does not consume a retry.

| Complexity | Correction retries | Maximum QA runs | Behavior |
|---|---:|---:|---|
| `UNKNOWN` | 0 | 0 | Planner must resolve complexity before author repair can start. |
| `Simple` | 1 | 2 | Initial QA plus at most one corrected-document recheck. |
| `Complex` | 2 | 3 | Initial QA plus at most two corrected-document rechecks. |

`retry_count` increments only after all three conditions pass:

1. Selected author returns non-empty correction output.
2. Exact planned target remains present and readable.
3. Pipeline persists complete `06-repair-attempt-N` artifact pair.

These events do not consume normal retry budget:

- initial checker run or later checker execution;
- failed or empty author dispatch;
- malformed, unsupported, or empty checker output;
- Figma analysis or Figma access failure;
- input, workspace, role, target, or artifact validation failures;
- optional consolidation pass after `CHECKLIST_PASSED`.

Simple timeline:

```text
QA1 CHECKLIST_FAILED
  -> repair1 succeeds; retry_count becomes 1
  -> QA2 CHECKLIST_PASSED: complete
     or
  -> QA2 CHECKLIST_FAILED: QA_RETRY_EXHAUSTED
```

Complex timeline:

```text
QA1 CHECKLIST_FAILED
  -> repair1 succeeds; retry_count becomes 1
  -> QA2 CHECKLIST_FAILED
  -> repair2 succeeds; retry_count becomes 2
  -> QA3 CHECKLIST_PASSED: complete
     or
  -> QA3 CHECKLIST_FAILED: QA_RETRY_EXHAUSTED
```

After `CHECKLIST_PASSED`, pipeline may perform one separate consolidation attempt. Consolidation does not change `retry_count` and cannot create another consolidation attempt. Pipeline reruns QA once after consolidation:

- pass -> record `consolidation=passed`;
- fail -> stop with `CONSOLIDATION_REGRESSION`; do not spend normal retry budget to repair that regression.

`QA_RETRY_EXHAUSTED` means all allowed successful correction attempts were consumed and final QA still failed. Start a new pipeline run after resolving remaining findings.

### ClickUp verification

Without supplied external evidence or authorized lookup, live ClickUp state is `NOT_CHECKED`. Pipeline may perform URL syntax checks but never treats syntax as live verification and never invents ClickUp URLs or validity claims.

### Figma behavior

Pipeline calls `prd-figma-reader` only for explicit Figma links in Plan Document. No planned links creates `03-figma` artifact pair with `SKIPPED` status and non-empty reason; skipped does not mean artifacts are absent. Required Figma source failure ends run with `FIGMA_READ_FAILURE`. An empty response means no output at all; sparse but valid analysis is evidence and does not become failure solely for being sparse.

## Workspace conventions

### Roles and permissions

Role-consuming phases resolve roles source in this order: explicit request or Plan Document path, workspace `**/roles-permissions.md` search, then terminal `ROLES_FILE_NOT_FOUND`. Role names in requirements must match canonical source exactly. User Access wraps role names in backticks; body text uses “user” or “users” instead of repeating names.

### PRD root

Target and search paths resolve in this order: explicit PRD root, `business-requirements/`, `prd/`, then workspace root following existing folder conventions. `UPDATE` retains supplied existing target after normalization; pipeline never substitutes a different path.

### Metadata, references, and updates

Every generated document starts with `clickup-page` YAML metadata. Agents leave it empty when no ClickUp page exists. Cross-document references use source `clickup-page` URL when present, otherwise exact filename. Every document has `Version`, `Date`, and `Changes` table. Updates edit existing row unless user explicitly requests new version row.

### Functional design boundary

`prd-figma-reader` is read-only. It records functional labels, element types, states, statuses, behavior, validation hints, visibility, navigation, literal content, source URL, node ID, screens analysed, and unresolved ambiguities. It does not report appearance or call Figma write, comment, annotation, FigJam edit, or Slides edit tools. Agent-authored diagrams use ASCII in plain `text` code blocks unless user asks for Mermaid.

## Development and validation

Keep agent names unique, preserve YAML frontmatter, and keep `prd-pipeline` contract aligned with specialist prompts. `prd-orchestrator` must name all worker agents and direct full runs to pipeline. Read-only agents must not gain write tools without concrete need. Author agents need `Write` and `Edit` for target requirement files.

Run commands from repository root.

```bash
python3 -m unittest discover -s skills/prd-pipeline/tests -p 'test_*.py' -v
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py package --skill-root skills/prd-pipeline
python3 skills/prd-pipeline/scripts/validate-prd-pipeline.py run --run-dir /absolute/path/to/run --repository-root /absolute/path/to/workspace
python3 -m py_compile skills/prd-pipeline/scripts/validate-prd-pipeline.py skills/prd-pipeline/tests/test_validate_prd_pipeline.py
git diff --check
```

The run validator receives `--repository-root` so it can reject accidental run artifacts inside target repository. Use an artifact directory outside that root.

Run inventory check after definition changes.

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
assert len(files) == 8, f"expected 8 PRD agents, found {len(files)}"
names = set()
for path in files:
    match = re.search(r"^name:\s*([^\s]+)\s*$", path.read_text(), re.MULTILINE)
    assert match, f"missing name in {path}"
    names.add(match.group(1))
assert names == expected, f"agent mismatch: {sorted(names ^ expected)}"
assert Path("prd-shared-authoring-standards.md").is_file()
for path in (
    Path("skills/prd-pipeline/SKILL.md"),
    Path("skills/prd-pipeline/references/prd-pipeline-contract.md"),
    Path("skills/prd-pipeline/references/prd-artifact-format.md"),
    Path("skills/prd-pipeline/scripts/validate-prd-pipeline.py"),
    Path("skills/prd-pipeline/tests/test_validate_prd_pipeline.py"),
):
    assert path.is_file(), f"missing pipeline file: {path}"
orchestrator = Path("agents/prd-orchestrator.md").read_text()
for name in expected - {"prd-orchestrator"}:
    assert f"`{name}`" in orchestrator, f"orchestrator does not reference {name}"
assert "`prd-pipeline` is the executable coordinator" in orchestrator
print("validated 8 PRD agents, pipeline package, shared standards, and orchestrator references")
PY
```

## Privacy and repository scope

Root `.gitignore` denies all files by default and includes only tracked agent sources, `skills/prd-pipeline/`, shared standards, README, and the tracked design and plan docs (`docs/superpowers/specs/2026-09-24-prd-pipeline-design.md` and `docs/superpowers/plans/2026-09-24-prd-pipeline.md`). Keep local Claude Code settings, tokens, MCP credentials, histories, caches, sessions, generated requirements, and run artifacts out of version control.
