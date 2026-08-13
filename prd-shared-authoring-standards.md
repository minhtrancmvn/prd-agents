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

**New document**: version 1.0, today's date, "Initial document creation".

**Updating an existing document**:
- Check whether a version table exists before adding one.
- **Default**: update the existing version row in place — do not add a new row unless the user explicitly says to.
- **New version (explicit only)**: add a row, increment minor (1.1 → 1.2) or major (1.1 → 2.0) for significant changes.
- **No table exists**: create one at 1.0, then update in place unless instructed otherwise.
- Each entry: one concise line summarising the change — no sub-items or detailed changelogs.

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

After writing, signal the orchestrator to invoke `prd-consistency-checker` with the document's absolute path, Document Type, and any Figma URLs used. The task is not complete until the checker has run and all findings are resolved.

---

## Success Criteria

The completed document must:
- Contain no fabricated URLs, placeholder links, or empty headings.
- Pass all verification checklist items for its document type.
- Be implementable by developers without additional clarification.
- Follow all formatting, structural, and writing guidelines in this file and in the author agent's own rules.