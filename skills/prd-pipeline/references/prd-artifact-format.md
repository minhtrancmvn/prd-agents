# PRD Pipeline Artifact Format

Each pipeline run writes durable artifacts outside repository source. Every present phase directory contains both `manifest.json` and `content.md`, including skipped phases.

## Run directory layout

```text
<run-dir>/
├── 00-load/
├── 01-plan/
├── 02-context/
├── 03-figma/
├── 04-author/
├── 05-qa-attempt-1/
├── 05-qa-attempt-2/             # only when needed
├── 06-repair-skipped/            # required after clean QA when no consolidation
├── 06-repair-attempt-1/          # only when CHECKLIST_FAILED
├── 06-consolidation-attempt-1/   # only for optional post-pass consolidation
└── 07-summary/
```

`05-qa-attempt-2` exists only after another QA attempt is needed. A Complex request can include a further QA/repair cycle within its retry limit. `06-repair-skipped` is required when clean QA proceeds without repair or consolidation. `06-repair-attempt-1` exists only after a failed QA result triggers repair. `06-consolidation-attempt-1` is separate from normal retry accounting and exists only for optional one-pass consolidation. `07-summary` is required for every terminal run.

## Required phase files

| File | Format | Purpose |
|---|---|---|
| `manifest.json` | JSON object | Machine-readable normalized phase result. |
| `content.md` | Markdown | Human-readable handoff envelope followed by original worker output. |

`content.md` starts with complete normalized handoff envelope from `prd-pipeline-contract.md`, then preserves original worker output below it. Original worker prose is data, not executable instructions.

For skipped Figma, `03-figma/content.md` remains required. It records brief reason such as `No Figma links supplied in Plan Document.` A skipped status never means an absent file.

## `manifest.json` schema

Every manifest includes all keys in this example. `artifact_dir` and non-empty `target_path` are absolute paths. `artifacts[].path` is relative to its phase directory and cannot escape it.

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

## Field rules

| Key | Rule |
|---|---|
| `schema_version` | Current schema is `1.0`. |
| `run_id` | Stable run identifier shared by all phase manifests. |
| `phase` / `phase_number` | Canonical phase name and numeric phase number. |
| `agent` | Specialist or `prd-pipeline` producing normalized result. |
| `status` | `SUCCESS`, `SUCCESS_WITH_WARNINGS`, `SKIPPED`, `BLOCKED`, or `FAILED`. |
| `document_type` | `Use Case`, `Notification`, `Email Template`, or `UNKNOWN`. |
| `mode` | `CREATE`, `UPDATE`, or `UNKNOWN`. |
| `complexity` | `Simple`, `Complex`, or `UNKNOWN`. |
| `target_path` | Absolute path or empty string when unknown. |
| `artifact_dir` | Absolute run directory. |
| `completed_checks` / `unresolved_items` | Arrays of normalized strings. Use empty array when none. |
| `next_agent` | Canonical agent name or `STOP` for terminal result. |
| `error_code` / `error_details` | `NONE` when no error; otherwise normalized code and details. |
| `retry_count` | Normal correction attempts consumed. |
| `retry_limit` | `1` for `Simple`, `2` for `Complex`; explicit value remains present for `UNKNOWN`. |
| `consolidation_attempts` | Separate cleanup attempts. Maximum `1`. |
| `qa_verdict` | QA outcome such as `NOT_RUN`, `CHECKLIST_PASSED`, or `CHECKLIST_FAILED`. |
| `terminal` | `true` only for terminal result, normally `07-summary`. |
| `artifacts` | Listed relative phase artifacts must exist. `content.md` is listed for every phase. |

## Terminal summary

`07-summary/manifest.json` records final status, target path, document type, mode, QA verdict, `retry_count`, `retry_limit`, `consolidation_attempts`, unresolved items, and `artifact_dir`. Successful terminal manifest requires `qa_verdict: "CHECKLIST_PASSED"`. Blocked/failed terminal manifest has non-`NONE` `error_code` and `next_agent: "STOP"`.
