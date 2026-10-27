# Shared Authoring Standards

All authoring agents must read and apply every standard here alongside their document-type-specific rules.

---

## Reference Files

### Roles & Permissions File

The roles & permissions file is named exactly `roles-permissions.md` and lives somewhere in the active workspace. Its location varies per project, so never hardcode a path — resolve it at runtime:

1. **Explicit override**: if the request or Plan Document names a roles file path, use it verbatim.
2. **Discovery**: otherwise `Glob` the workspace for `**/roles-permissions.md`. Each workspace contains exactly one such file.
3. **Resolution**:
   - Exactly one match → use it.
   - No match → emit `ROLES_FILE_NOT_FOUND` as the first line of output, followed by the attempted glob pattern. Do not guess or invent role names.

Agents that consume roles (planner, context analyzer, consistency checker) all resolve the file this way. Refer to it as "the workspace roles file" rather than a literal path.

### PRD Root Directory

PRDs live under a single root directory whose name varies per workspace — either `business-requirements/` or `prd/`. Never hardcode one; resolve it at runtime:

1. **Explicit override**: if the request or Plan Document names a PRD root, use it verbatim.
2. **Discovery**: otherwise `Glob` for `business-requirements/` first, then `prd/`. Use whichever exists at the workspace.
3. **Resolution**:
   - One root found → use it for all PRD search and target-path proposals.
   - Neither found → treat the workspace root as the PRD root and follow existing folder conventions when proposing paths.

Refer to it as "the workspace PRD root" rather than a literal path.

---

## Metadata Section

Place this front-matter block before the document title:

\```markdown
---
clickup-page: 
---
\```

Leave `clickup-page` empty if no ClickUp page exists. Do not fabricate URLs.

---

## Version History

Never omit. Always use today's date in YYYY-MM-DD format — never copy placeholder dates.

\```markdown
## Version History

| Version | Date       | Changes                          |
|---------|------------|----------------------------------|
| 1.0     | YYYY-MM-DD | Initial document creation        |
\```

Exactly three columns: `Version`, `Date`, `Changes`. No `Author` or other columns.

### Session-scoped version policy

Keep **one working version per document per conversation/thread/session**, for Use Case, Notification, and Email Template documents alike. A fresh run_id does not start a new session. Follow-up requests, resumed runs, QA repairs, and consolidation edit the same working row; they never independently increment it. Different target documents have independent decisions.

Before the first write for each target, read its existing Version History and resolve a **Session Version Decision** from the user's request, conversation history, and prior run artifacts for this same target and session:

- `CREATE_INITIAL`: new document, or an existing document with no version table. Create 1.0 once, with today's date and "Initial document creation". Later session edits stay at 1.0.
- `ADD_NEW`: user clearly requests a new version. Select the requested version, or increment minor once (1.1 → 1.2); use a major increment only when requested, not inferred from scope size. Add that row once, then reuse it throughout the session.
- `EDIT_LATEST`: user clearly requests edits to the latest version, or is continuing/correcting an already selected working version. Keep its version number and edit that row in place.
- If an existing document's initial request leaves add-new versus edit-latest unclear, **ask before writing**: "For <target_path>, add a new version or edit the latest version?" An unqualified "update" identifies document mode, not version intent. Do not silently choose a bump or edit-latest. Non-interactive workers return the question to their caller without writing; the caller asks it and resumes with the answer.

Record target path, `working_version`, action, `baseline_history` (the complete pre-session table or explicit absence), and `decision_source` (user instruction or prior artifact/history reference) before authoring. Reuse a decision only when its target and session provenance match. The calling conversation carries its prior decision/artifact references on routine follow-ups; users do not construct state. If prior context cannot be recovered or conflicts with current history, ask rather than infer ownership of rows. An old session's artifact is historical evidence, not authority to continue that session's version.

Preserve all pre-session history rows verbatim except the selected latest row under `EDIT_LATEST`. Never delete, rewrite, or merge historical entries to make the table look session-scoped. Only consolidate duplicate rows proven to have been produced in the current session, into its selected working row. If a follow-up appears to request another bump after a working version was selected, explain that this session already uses that version and clarify whether the user intends a separate versioning session before writing; do not automatically create a second row.

Use today's date for the working row when edited; leave untouched historical dates unchanged. Each working entry is one concise line summarising all session changes — no sub-items or per-turn changelogs. Before reporting success, compare the actual table to `baseline_history`: exactly one row for `working_version`, no extra session versions, no unexpected changes to pre-session history.

---

## Visual Appearance Restrictions

- Prioritise functional state/behaviour over appearance (e.g., "button becomes non-interactive", not "button turns grey").
- Document functional meaning (e.g., "badge indicates unread state"), element types, states, and statuses.
- **Do not document** position, layout, spacing, alignment, colours, fonts, or styling.
- Reference design mockups for visual specifications.

---

## Writing Guidelines

- Simple, direct, active-voice language.
- Bullet points and numbered lists for clarity.
- Precise, testable language — no "may", "might", "should", "could".
- For notification/email content: specify exact text and variable placeholders — do not paraphrase.

---

## Content Organization

- Group related actions to reduce redundancy.
- Do not split related concepts across sections.
- Balance completeness with conciseness.
- Cross-reference rather than duplicate.

---

## Cross-Document References

- Always use the document's `clickup-page` URL when referencing another requirements document.
- Never use `.md` filename references in body text if a `clickup-page` URL exists.
- Extract the ClickUp URL from the `clickup-page` field in the referenced file's metadata.
- Only use the exact filename (e.g., `password-rules.md`) as a fallback if the referenced document does not have a `clickup-page` value.
- Never fabricate ClickUp URLs or create markdown file links.

---

## Diagrams

- If a document includes an agent-authored diagram, represent it as ASCII inside a plain `text` code block.
- Do not generate Mermaid diagrams for requirement documents.
- Do not add image references for agent-authored diagrams.
- Keep diagram labels concise so the layout remains readable in monospace.
- If an existing Mermaid or image-based diagram is being updated per user request, replace it with an ASCII diagram unless the user explicitly asks to preserve Mermaid.

---

## No Additional Sections

Never add sections beyond those defined in the document-type structure. Cross-references to related PRDs go inside body text (Overview or relevant content section), not in a separate section.

---

## Dynamic Variables Table

\```markdown
| Variable | Source | Example | Fallback | Validation |
|----------|--------|---------|----------|------------|
| `{variable_name}` | Data source | "Sample value" | "Fallback value or behaviour" | Format constraint |
\```

All five columns must be populated for every row. Every `{variable_name}` used in content sections must have a row; no unreferenced variables may appear.

---

## Flows Section

Header: `## Flows`. If no flow URLs were provided, omit entirely. Use a `###` heading per flow with the link directly under it — no bullets. Never use placeholder URLs.

\```markdown
## Flows

### [Flow Name]
https://www.figma.com/proto/example-link
\```

---

## Designs Section

Header: `## Designs`. If no design URLs were provided, omit entirely. Use a `###` heading per asset with the link directly under it — no bullets. Always include the actual URL provided.

\```markdown
## Designs

### [Asset Name]
https://www.figma.com/design/example-link
\```

---

## Verification

After writing, signal the caller to invoke `prd-consistency-checker` with the document's absolute path, Document Type, and any Figma URLs used. For a full run, `prd-pipeline` invokes `prd-consistency-checker`; standalone authors provide the same handoff to their caller. The task is not complete until the checker has run and all findings are resolved.

---

## Success Criteria

The completed document must:
- Contain no fabricated URLs, placeholder links, or empty headings.
- Pass all verification checklist items for its document type.
- Be implementable by developers without additional clarification.
- Follow all formatting, structural, and writing guidelines in this file and in the author agent's own rules.