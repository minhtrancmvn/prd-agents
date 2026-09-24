# Canonical PRD Pipeline Design

## Status

Design approved in chat on 2026-09-24. Specification prepared for user review before implementation planning.

## Goal

Create one canonical `prd-pipeline` skill that coordinates existing PRD specialist agents through explicit phase gates, persisted handoff artifacts, bounded retries, and deterministic package validation.

## Context

This repository contains eight PRD specialist agents and shared authoring standards, but no executable coordination layer. `prd-orchestrator` documents the intended sequence but declares only `Read`, `Glob`, and `Grep`; it cannot dispatch specialist agents. The repository also denies new paths by default through `.gitignore`, so pipeline source and validation files need explicit tracking rules.

The pipeline must preserve specialist responsibilities rather than duplicate authoring logic:

```text
main Claude Code conversation
        |
        v
skills/prd-pipeline/SKILL.md
        |
        +--> prd-planner
        +--> prd-context-role-analyzer
        +--> prd-figma-reader (conditional)
        +--> prd-author | prd-noti-req-author | prd-email-req-author
        +--> prd-consistency-checker
```

## Non-goals

- Do not rewrite all eight specialist agents as part of initial pipeline creation.
- Do not add live ClickUp verification without an authorized external lookup capability.
- Do not commit generated per-run PRD artifacts, target workspace documents, credentials, or runtime state.
- Do not create a second runtime topology under `pipelines/`; canonical runtime discovery uses `skills/<name>/SKILL.md`.
- Do not make pipeline validation replace document-specific QA performed by `prd-consistency-checker`.

## Architecture

### Canonical skill

Create `skills/prd-pipeline/SKILL.md` with valid skill frontmatter and `Agent`/`Task` dispatch capability. The skill is the executable coordinator. It owns phase order, input normalization, gate evaluation, retry accounting, artifact paths, and final reporting.

The pipeline remains user-invocable for direct requests to create or update PRD, notification, or email-template requirements. Existing specialist agents remain independently discoverable for targeted work.

### Legacy orchestrator compatibility

Retain `agents/prd-orchestrator.md` as compatibility documentation for users who invoke it directly. Update it only enough to state that `prd-pipeline` owns dispatch and that the orchestrator's existing flow is a policy reference. Do not add nested dispatch claims unless its tool allowlist is changed and verified against runtime behavior.

### Shared contract reference

Create `skills/prd-pipeline/references/prd-pipeline-contract.md`. This is the source of truth for:

- phase inputs and outputs;
- status tokens;
- normalized handoff envelope;
- artifact naming and run directory rules;
- retry counters and limits;
- failure and non-blocking conditions;
- final summary schema.

### Artifact format reference

Create `skills/prd-pipeline/references/prd-artifact-format.md`. Define the human-readable `content.md` and machine-readable `manifest.json` layers for every phase. Generated artifacts live in a run directory outside the repository, selected from an explicit workspace/run path or a temporary directory. The pipeline reports their absolute locations but does not commit them.

### Deterministic validator

Create `skills/prd-pipeline/scripts/validate-prd-pipeline.py`. It validates the pipeline package itself and supplied run artifacts. It must not pretend to validate model judgment. It checks:

- skill file and frontmatter presence;
- required references and validator files;
- manifest/content pairing;
- required handoff fields;
- allowed status tokens;
- absolute target paths;
- retry counters within configured limits;
- terminal summary presence;
- unresolved template tokens in machine artifacts.

Use standard library only.

## Phase design

### Phase 0: LOAD

**Goal:** Normalize the user request, workspace root, optional explicit roles path, optional explicit PRD root, and run artifact directory.

**Artifact:** `00-load/manifest.json`, `00-load/content.md`.

**Gate:** Request is non-empty; workspace root resolves; run directory exists; document type is known or can be delegated to the planner; no generated target file is written.

**Failure:** `INPUT_INVALID` or `WORKSPACE_NOT_FOUND`; stop.

### Phase 1: PLAN

**Worker:** `prd-planner`.

**Input:** Full request, supplementary context, workspace root, and confirmed target-path policy.

**Artifact:** `01-plan/manifest.json`, `01-plan/content.md` containing the Plan Document.

**Gate:** Seven mandatory Plan Document fields are populated: Document Type, Scope Summary, User Roles Involved, Files & Documents to Read, Target File Path, Document Section Outline, Complexity Assessment. Target path is resolved and recorded. Figma links section appears only when links exist.

**Failure:** `PLAN_INCOMPLETE`; stop and report missing fields.

### Phase 2: CONTEXT AND ROLES

**Worker:** `prd-context-role-analyzer`.

**Input:** Plan Document, confirmed target path, workspace root, explicit roles path if supplied.

**Artifact:** `02-context/manifest.json`, `02-context/content.md` containing Context Report.

**Gate:** Roles source is readable; canonical role resolution is complete, or explicit unresolved-role approval is recorded. Search depth follows complexity: Simple uses feature folder; Complex searches all relevant PRDs.

**Failure:** `ROLES_FILE_NOT_FOUND` stops. `RISK_ITEMS_FOUND` stops for user resolution unless explicit proceed-with-markers instruction exists. Missing related PRDs is a successful empty result, not an automatic failure.

### Phase 3: FIGMA, conditional

**Worker:** `prd-figma-reader`.

**Condition:** Plan Document contains Figma links to analyze.

**Input:** Figma URLs/node IDs and Scope Summary verbatim, plus run context.

**Artifact:** `03-figma/manifest.json`, `03-figma/content.md` when executed; `03-figma/manifest.json` with `status: skipped` when no links exist.

**Gate:** Every required design source is analyzed, or a structured warning identifies skipped/ambiguous sources. Valid sparse data is not treated as transport failure.

**Failure:** Auth, timeout, malformed response, or unavailable required source produces `FIGMA_READ_FAILURE` and stops. A valid node with no relevant functional requirements produces success with an empty findings list.

### Phase 4: AUTHOR

**Worker:** Select exactly one of `prd-author`, `prd-noti-req-author`, or `prd-email-req-author` from Document Type.

**Input:** Plan Document, Context Report, optional Figma analysis, confirmed absolute target path, shared standards path, and any approved unresolved-role instruction.

**Artifact:** `04-author/manifest.json`, `04-author/content.md` containing write result and self-checks. Target requirements document is written at the confirmed target path.

**Gate:** Target file exists after write; document type and mode match plan; section order and type-specific variable rules pass author self-check; unrelated update content remains preserved; output explicitly requests `prd-consistency-checker` next.

**Failure:** Missing prerequisite, invalid update target, write failure, or self-check failure produces a typed failure and stops before accidental fallback file creation.

### Phase 5: QA

**Worker:** `prd-consistency-checker`.

**Input:** Absolute target path, Document Type, workspace root, optional Figma analysis, and optional externally supplied ClickUp verification result.

**Artifact:** `05-qa-attempt-N/manifest.json`, `05-qa-attempt-N/content.md` containing checker output and normalized findings.

**Gate:** `CHECKLIST_PASSED` with no blocking findings. Informational Figma-skipped notes are surfaced but do not block. `CHECKLIST_FAILED` enters repair if retry budget remains.

**External validation rule:** Without supplied live verification evidence or an authorized lookup tool, ClickUp links are checked only for presence/syntax and reported as `NOT_CHECKED` for live validity.

### Phase 6: REPAIR AND RECHECK

**Worker:** Applicable author, then checker.

**Input:** Full normalized QA findings, original inputs, and current target document.

**Retry limits:** Simple requests: one correction retry. Complex requests: two correction retries. Consolidation cleanup is one separate pass after an initial clean checklist and does not consume the normal failure budget.

**Gate:** Recheck passes, or retry budget is exhausted with complete unresolved findings. Consolidation cleanup must pass its separate recheck; regression stops the pipeline.

**Failure:** `QA_RETRY_EXHAUSTED` or `CONSOLIDATION_REGRESSION`; stop with target path and all findings.

### Phase 7: REPORT

**Goal:** Produce terminal summary and validate run artifacts.

**Artifact:** `07-summary/manifest.json`, `07-summary/content.md`.

**Gate:** Summary includes final status, target path, document type, mode, completed phases, QA verdict, retry counts, unresolved items, artifact directory, and Figma skipped/analysis note. `validate-prd-pipeline.py` passes.

## Handoff envelope

Every phase returns this envelope before any phase-specific payload:

```text
STATUS: SUCCESS | SUCCESS_WITH_WARNINGS | SKIPPED | BLOCKED | FAILED
AGENT: <agent-name-or-pipeline>
PHASE: <phase-name>
DOCUMENT_TYPE: Use Case | Notification | Email Template | UNKNOWN
MODE: CREATE | UPDATE | UNKNOWN
TARGET_PATH: <absolute-path-or-empty>
ARTIFACT_DIR: <absolute-run-directory>
COMPLETED_CHECKS: <semicolon-separated checks>
UNRESOLVED_ITEMS: <semicolon-separated items or NONE>
NEXT_AGENT: <agent-name or STOP>
ERROR_CODE: <code or NONE>
ERROR_DETAILS: <details or NONE>
```

The machine manifest mirrors these values as JSON. Human content may include the original specialist output after the envelope.

Allowed terminal status codes:

- `SUCCESS`
- `SUCCESS_WITH_WARNINGS`
- `SKIPPED`
- `BLOCKED`
- `FAILED`
- `INPUT_INVALID`
- `WORKSPACE_NOT_FOUND`
- `PLAN_INCOMPLETE`
- `ROLES_FILE_NOT_FOUND`
- `RISK_ITEMS_FOUND`
- `FIGMA_READ_FAILURE`
- `AUTHOR_INPUT_INVALID`
- `AUTHOR_WRITE_FAILURE`
- `CHECKLIST_PASSED`
- `CHECKLIST_FAILED`
- `QA_RETRY_EXHAUSTED`
- `CONSOLIDATION_REGRESSION`
- `VALIDATION_FAILED`

## Final output

Successful final response must report:

```text
PRD_PIPELINE_COMPLETE
Target: <absolute path>
Document type: <type>
Mode: <CREATE|UPDATE>
Stages: <completed stage list>
QA: CHECKLIST_PASSED
Retries: <normal retries>/<limit>; consolidation=<none|passed>
Artifacts: <absolute run artifact directory>
Notes: <Figma and informational notes, or NONE>
```

Blocked/failed response must report the corresponding status, failed phase, error code, target path if known, remediation, and artifact directory. It must not claim a document was written unless the target exists and the author handoff confirms success.

## Validation and test strategy

Use a dependency-free validator plus fixture manifests. Minimum fixture scenarios:

- successful Use Case create;
- Notification create;
- Email Template update;
- skipped Figma branch;
- missing roles file;
- unresolved roles;
- malformed Plan Document;
- QA failure followed by successful repair;
- QA retry exhaustion;
- consolidation regression;
- missing artifact or mismatched manifest/content;
- unsupported ClickUp live verification reported as `NOT_CHECKED`.

Run static repository validation, pipeline validator tests, catalog generation/check, pairing validation, relevant hook tests, `git diff --check`, and a final diff review.

## Git and installation

Work on branch `feature/add-prd-pipeline`.

Tracked source:

- `skills/prd-pipeline/SKILL.md`
- `skills/prd-pipeline/references/*.md`
- `skills/prd-pipeline/scripts/*.py`
- focused fixtures/tests if added;
- updated README and narrow `.gitignore` exceptions;
- updated legacy orchestrator contract if changed;
- regenerated catalogs only when this repository owns the canonical catalog.

Do not track generated run directories, target workspace PRDs, credentials, local settings, or runtime state.

Commit sequence:

1. Commit this design specification before implementation planning.
2. After user approves the committed specification, create implementation plan.
3. Implement and validate.
4. Review diff and commit implementation with conventional commit message.

## Alternatives considered

### Upgrade `prd-orchestrator`

Rejected as primary architecture. It keeps coordination in an agent that currently lacks dispatch capability and mixes policy with execution. It remains useful as compatibility documentation.

### Pipeline skill plus second orchestration wrapper

Deferred. Two executable entry points would create drift. Add a wrapper later only if existing users require direct orchestrator compatibility after the canonical skill ships.

## Open implementation details

- Confirm whether the PRD repository itself or a separate canonical toolkit repository owns `skills/prd-pipeline`. This design assumes current repository ownership based on the active workspace and existing branch.
- Confirm catalog generation scope during implementation; regenerate only catalogs that are tracked and owned by this repository.
- Use existing sync behavior rather than changing installer code unless validation proves the new skill is not copied.
