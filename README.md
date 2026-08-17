# PRD Agents

PRD Agents is a Claude Code subagent pack for creating and updating product requirements documents. It defines a staged business-analysis workflow for use cases, notifications, and email templates, with canonical role resolution, optional read-only Figma analysis, type-specific authoring rules, and final consistency checks.

This repository versions only eight PRD agent definitions and their shared authoring standards. Other files in a local `~/.claude` directory, such as settings, credentials, histories, caches, hooks, and databases, are runtime state and are intentionally outside this repository.

## Supported documents

| Document type | Author agent | Main output |
|---|---|---|
| Use Case | `prd-author` | User workflow, access, core functionality, grouped business rules, and optional flows/designs |
| Notification | `prd-noti-req-author` | Trigger, recipients, delivery channel, exact notification content, and content parameters |
| Email Template | `prd-email-req-author` | Trigger, recipients, delivery behavior, exact email content, and dynamic variables |

## Intended workflow

```text
prd-planner
    |
    v
prd-context-role-analyzer
    |
    +--> prd-figma-reader (only when Figma URLs are provided)
    |
    v
prd-author | prd-noti-req-author | prd-email-req-author
    |
    v
prd-consistency-checker
```

1. `prd-planner` classifies the document type, mode, scope, roles, target path, and complexity.
2. `prd-context-role-analyzer` resolves canonical roles and gathers related requirements context.
3. `prd-figma-reader` extracts functional UI details when the request contains Figma links.
4. One type-specific author writes or updates the target document.
5. `prd-consistency-checker` reports structural, role, terminology, language, business-rule, visual, and Figma consistency findings.

Simple requests allow one correction retry after the first QA run. Complex requests allow two correction retries. Author agents can write and edit target requirements files; planner, context, Figma, orchestrator, and checker agents are read-only.

> [!IMPORTANT]
> The current `prd-orchestrator` frontmatter allows only `Read`, `Glob`, and `Grep`. Current Claude Code requires the `Agent` tool for a subagent to spawn other subagents, so `prd-orchestrator` cannot execute the full nested pipeline by itself as currently defined. Until its tool allowlist includes `Agent`, have the main Claude Code conversation coordinate the specialist agents in sequence.

## Repository contents

| Path | Agent or resource | Responsibility |
|---|---|---|
| `agents/prd-orchestrator.md` | `prd-orchestrator` | Defines stage ordering, retries, and stop conditions |
| `agents/prd-planner.md` | `prd-planner` | Produces the seven-field Plan Document |
| `agents/prd-context-role-analyzer.md` | `prd-context-role-analyzer` | Resolves exact role names and related PRD context |
| `agents/prd-figma-reader.md` | `prd-figma-reader` | Reads functional UI details from Figma through read-only MCP tools |
| `agents/prd-author.md` | `prd-author` | Writes or updates use-case PRDs |
| `agents/prd-noti-req-author.md` | `prd-noti-req-author` | Writes or updates notification requirements |
| `agents/prd-email-req-author.md` | `prd-email-req-author` | Writes or updates email template requirements |
| `agents/prd-consistency-checker.md` | `prd-consistency-checker` | Reports checklist failures and consolidation recommendations |
| `prd-shared-authoring-standards.md` | Shared standards | Defines workspace discovery, metadata, versioning, references, diagrams, language, and verification rules |

Subagent files use Markdown with YAML frontmatter. Claude Code requires unique `name` and `description` fields; each file in this repository also declares an explicit tool allowlist.

## Prerequisites

- [Claude Code](https://code.claude.com/docs/en/overview) with custom subagent support.
- A target workspace containing exactly one discoverable `roles-permissions.md`, or an explicit roles-file path in the request.
- Product context sufficient to identify scope, involved roles, source documents, and target requirements path.
- Optional: a configured `figma-console` MCP server and valid Figma access when requests contain Figma URLs. See [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp).

No package manager, build system, application runtime, or test framework is required by the tracked repository files.

## Installation

### User-level installation

User-level subagents are available across all projects. Clone the repository, then copy its agent definitions and shared standards into `~/.claude`:

```bash
git clone https://github.com/minhtrancmvn/prd-agents.git
cd prd-agents
mkdir -p ~/.claude/agents
cp agents/prd-*.md ~/.claude/agents/
cp prd-shared-authoring-standards.md ~/.claude/
```

These `cp` commands overwrite same-named files. Back up local customizations before reinstalling or updating.

Claude Code watches an existing `~/.claude/agents/` directory and normally detects additions or edits within a few seconds. Restart Claude Code if this installation created the first `agents` directory during an already-running session.

### Project-level installation

Claude Code also discovers project-scoped definitions under `.claude/agents/`:

```bash
PROJECT_ROOT=/path/to/your/project
mkdir -p "$PROJECT_ROOT/.claude/agents"
cp agents/prd-*.md "$PROJECT_ROOT/.claude/agents/"
mkdir -p ~/.claude
cp prd-shared-authoring-standards.md ~/.claude/
```

The shared standards remain user-level because the current agent prompts reference `~/.claude/prd-shared-authoring-standards.md`. If you move that file into a project, update every reference consistently.

See [Create custom subagents](https://code.claude.com/docs/en/sub-agents) for current scope, precedence, frontmatter, and invocation behavior.

## Quick start

Start Claude Code from the workspace where the requirements documents live. Ask the main conversation to coordinate the specialists explicitly:

```text
Create a use-case PRD for resetting a password as a Generic User.
Coordinate the PRD agents in this order: prd-planner, prd-context-role-analyzer,
the applicable author, then prd-consistency-checker. Confirm the target path before writing.
```

Figma-backed example:

```text
Create an email template requirement from this Figma design: <figma-url>.
Use prd-planner, prd-context-role-analyzer, prd-figma-reader,
prd-email-req-author, and prd-consistency-checker in sequence.
```

Update example:

```text
Update <path-to-notification-requirement> with the new delivery rule.
Preserve content outside the requested scope and use the PRD agent workflow.
```

Claude Code can delegate based on agent descriptions, or you can explicitly name or `@`-mention a specialist. Keep orchestration in the main conversation until the `prd-orchestrator` tool allowlist includes `Agent`.

## Workspace conventions

### Roles and permissions

Role-consuming agents resolve the workspace roles file in this order:

1. Use an explicit path from the request or Plan Document.
2. Search the workspace with `**/roles-permissions.md`.
3. Stop with `ROLES_FILE_NOT_FOUND` if no file can be read.

Role names in requirements must match the canonical file exactly. The User Access section wraps role names in backticks; body text uses “user” or “users” instead of repeating role names.

### PRD root

Target and search paths resolve in this order:

1. Explicit PRD root from the request or Plan Document.
2. `business-requirements/`.
3. `prd/`.
4. Workspace root, following existing folder conventions.

### Metadata and references

Every generated document starts with:

```yaml
---
clickup-page:
---
```

Agents leave `clickup-page` empty when no ClickUp page exists and never fabricate URLs. Cross-document references use the source document's `clickup-page` URL when present; the exact filename is the fallback.

### Updates and version history

Every document includes a three-column `Version`, `Date`, and `Changes` table. For an update, the default behavior is to edit the existing version row in place. A new version row is added only when the user explicitly asks for one.

### Figma boundary

`prd-figma-reader` is read-only. It extracts exact labels, element types, states, statuses, behavior, validation hints, visibility, navigation, and literal content. It does not report colors, fonts, dimensions, spacing, alignment, shadows, styling, or asset filenames, and it does not call Figma write, comment, annotation, FigJam edit, or Slides edit tools.

### Diagrams and visual details

Agent-authored diagrams use ASCII inside plain `text` code blocks unless the user explicitly requests Mermaid. Requirements describe functional state and behavior rather than appearance or implementation details.

## Pipeline signals

| Signal | Meaning | Next action |
|---|---|---|
| `ROLES_FILE_NOT_FOUND` | Canonical roles file is missing or unreadable | Add or identify `roles-permissions.md`, then rerun |
| `RISK_ITEMS_FOUND` | One or more requested roles do not resolve | Correct roles or explicitly accept unresolved-role markers |
| `FIGMA_READ_FAILURE` | Figma MCP call failed, timed out, or returned empty data | Verify MCP availability and Figma access, then retry |
| `CHECKLIST_PASSED` | Final QA found no blocking checklist issue | Complete, or perform one requested consolidation pass and recheck |
| `CHECKLIST_FAILED` | Final QA found one or more issues | Send findings to the applicable author and rerun QA within retry budget |

The consistency checker always reports findings; it never edits the target document.

## Authoring guarantees

The shared standards and final checker enforce these requirements:

- Canonical roles come from the workspace roles file rather than invention.
- URLs and design links come from source material rather than placeholders.
- Requirements use direct, active, testable language and avoid vague quality adjectives.
- Use-case business rules are grouped by functional area or state and cover happy, edge, and error paths.
- Notification and email variables each have `Variable`, `Source`, `Example`, `Fallback`, and `Validation` values.
- Static notification and email content preserves exact source wording.
- Functional requirements exclude colors, fonts, spacing, layout, and styling.
- Authoring is not complete until `prd-consistency-checker` has run and its findings are resolved.

## Development and validation

Keep agent names unique, preserve YAML frontmatter, and maintain the orchestrator's stage contracts when editing definitions. Read-only agents should not gain write tools without a concrete workflow need. Author agents require `Write` and `Edit` because they create or update target requirements files.

Run this dependency-free static check from the repository root:

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
    text = path.read_text()
    match = re.search(r"^name:\s*([^\s]+)\s*$", text, re.MULTILINE)
    assert match, f"missing name in {path}"
    names.add(match.group(1))

assert names == expected, f"agent mismatch: {sorted(names ^ expected)}"
assert Path("prd-shared-authoring-standards.md").is_file()

orchestrator = Path("agents/prd-orchestrator.md").read_text()
for name in expected - {"prd-orchestrator"}:
    assert f"`{name}`" in orchestrator, f"orchestrator does not reference {name}"

print("validated 8 PRD agents, shared standards, and orchestrator references")
PY

git diff --check
```

The repository does not currently include an automated test suite. The validation above checks inventory and orchestration references; review prompt behavior and tool boundaries manually when changing workflow semantics.

## Privacy and repository scope

The root `.gitignore` denies all files by default and includes only `.gitignore`, `agents/prd-*.md`, `prd-shared-authoring-standards.md`, and this README. Keep local Claude Code settings, tokens, MCP credentials, histories, caches, sessions, and generated requirements documents out of version control.

<!-- Verification Report
- Agent definitions: 8/8 parsed
- Orchestrator references: verified against source
- Installation steps: executed in an isolated temporary HOME
- Documented paths and signals: verified against tracked files
- Generated: 2026-08-13
-->
