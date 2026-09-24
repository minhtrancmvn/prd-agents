---
name: prd-orchestrator
description: |
  Legacy compatibility policy for routing, retry, and stop conditions in PRD workflows.
  Use `prd-pipeline` for complete workflows or a named specialist agent for one prepared stage.
  Does not dispatch nested agents.
tools: Read, Glob, Grep
---

# BA Orchestrator Compatibility Policy

`prd-pipeline` is the executable coordinator for complete PRD workflows.
This legacy agent documents routing, retry, and stop policy for compatibility.
It does not dispatch nested agents with its current tool allowlist. For a full
run, invoke `prd-pipeline`. For one prepared stage, invoke the specialist agent.

## Legacy Pipeline Policy Reference

This table is legacy reference material, preserved for readers of the old orchestrator flow. It is not authoritative. The canonical contract is `skills/prd-pipeline/references/prd-pipeline-contract.md`, which governs inputs, handoffs, retry rules, and terminal responses.

| # | Subagent | Purpose | When |
|---|---|---|---|
| 1 | `prd-planner` | Produces Plan Document (scope, roles, outline, type, mode, complexity, target path). | Always first. |
| 2 | `prd-context-role-analyzer` | Resolves role names, surfaces reusable patterns, flags consistency risks. | Always after planner. |
| 3 | `prd-figma-reader` | Extracts structured UI info from Figma designs/flows. | Only when Figma URL provided. |
| 4a | `prd-author` | Writes/updates use-case requirements. | Type = **Use Case** |
| 4b | `prd-noti-req-author` | Writes/updates notification requirements. | Type = **Notification** |
| 4c | `prd-email-req-author` | Writes/updates email template requirements. | Type = **Email Template** |
| 5 | `prd-consistency-checker` | Validates final document against standards and checklist. | Always last. |

## Routing and Retry Policy

### Plan
The pipeline invokes `prd-planner` with full request and supplementary context. Mandatory Plan Document fields: Document Type, Scope Summary, User Roles Involved, Files & Documents to Read, Target File Path, Document Section Outline, Complexity Assessment. If any is missing, apply Failure Handling (Incomplete Plan Document).

The pipeline resolves the planner's proposed Target File Path against the workspace PRD root and records the normalized absolute path for all later stages. For an `UPDATE`, it retains the supplied existing path after normalization and never substitutes a different path.

### Resolve Context & Roles
The pipeline invokes `prd-context-role-analyzer` with Plan Document, confirmed Target File Path, and workspace root. Search depth: **Simple** = same feature folder only; **Complex** = all PRDs.

If response begins with `ROLES_FILE_NOT_FOUND` or `RISK_ITEMS_FOUND`, apply Failure Handling.

If user instructs proceed despite unresolved roles, pipeline resumes from Figma or authoring with Context Report as-is. Authoring specialist uses unresolved role names exactly as written in Plan Document and marks each with `<!-- UNRESOLVED ROLE -->`. Checker reports those roles in findings.

### Figma Analysis
When Plan Document includes Figma Links to Analyse, pipeline invokes `prd-figma-reader` with URLs and Scope Summary verbatim. If response is `FIGMA_READ_FAILURE`, apply Failure Handling.

### Author
Pipeline selects specialist by Document Type. It passes Plan Document, Context Report, Figma analysis if any, and confirmed Target File Path.

Pipeline requires authoring specialist to use ClickUp `clickup-page` URLs for all cross-document references. It never uses `.md` filename references unless source document has no `clickup-page` URL.

### QA and Fix Cycle
Pipeline invokes `prd-consistency-checker` with absolute document path, Document Type, Workspace root, Figma analysis if collected, and external ClickUp verification evidence if available.

If response begins with `ROLES_FILE_NOT_FOUND`, apply Failure Handling. If findings include **Figma Verification Skipped**, surface note to user.

**`CHECKLIST_PASSED`**: If consolidation recommendations exist, pipeline passes them to authoring specialist for one clean-up pass, then re-invokes checker once. A second `CHECKLIST_PASSED` completes workflow. `CHECKLIST_FAILED` stops workflow and reports regression. It does not count against normal retry budget. Without consolidation recommendations, workflow completes.

**`CHECKLIST_FAILED`**: Pipeline passes full findings to authoring specialist, then re-invokes checker. Retry budget: **Simple** = 1 retry (2 QA runs); **Complex** = 2 retries (3 QA runs). When exhausted, pipeline stops and reports unresolved issues.

## Failure Handling

This table is the authoritative registry of all stop and non-blocking conditions. Steps reference it rather than restating actions.

| Condition | Action |
|---|---|
| Any subagent error/empty output | **Stop**. Report subagent name, step, and error. Wait for user. |
| Incomplete Plan Document | **Stop**. Report missing fields. |
| `ROLES_FILE_NOT_FOUND` from context analyzer | **Stop**. Report to user. Do not allow invented role names. |
| `ROLES_FILE_NOT_FOUND` from consistency checker | **Stop**. Report anomaly (file was resolvable at Step 2, not at Step 5). Do not feed into QA retry loop. |
| `RISK_ITEMS_FOUND` from context analyzer | **Stop**. Report unresolved roles. Wait for user instruction (resolve or proceed with markers). |
| `FIGMA_READ_FAILURE` | **Stop**. Report verbatim. Do not author without Figma data. |
| QA failures persist after retry budget | **Stop**. Report all unresolved issues. |
| Consolidation cleanup causes QA regression | **Stop**. Report regression to user. Do not count against retry budget. |
| No Figma Links section in Plan Document | **Non-blocking** — skip Step 3. |
| Checker passes with informational notes only | **Non-blocking** — continue. |
| Consolidation recommendations only (no failures) | **Non-blocking** — one clean-up pass, then re-validate once. |
| Figma Verification Skipped note in checker output | **Non-blocking** — surface note to user; continue normal result handling. |
