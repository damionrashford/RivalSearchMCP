# Triage Guide

How issues and PRs flow through RivalSearchMCP.

## Label taxonomy

Canonical source: [`.github/labels.yml`](../.github/labels.yml). Four namespaces.

| Namespace | Labels | Pick |
|---|---|---|
| **Type** | 🐛 Bug · ✨ Feature Request · ❓ Question · 💬 Feedback | one |
| **Priority** | 🔥 High · 🟡 Medium · 🟢 Low · 🔮 Roadmap | one |
| **Tool** | `tool:web_search`, `tool:social_search`, `tool:scientific_research`, `tool:news_aggregation`, `tool:github_search`, `tool:content_operations`, `tool:research_topic`, `tool:research_memory`, `tool:map_website`, `tool:document_analysis`, `tool:score_sources`, `tool:entity_research`, `tool:find_conflicts` | zero or more |
| **Status** | `status:in-progress` · `status:blocked` | zero or one (apply only when in motion) |

### Type

- **🐛 Bug** — Documented behavior doesn't match actual behavior.
- **✨ Feature Request** — New capability, or improvement to existing capability.
- **❓ Question** — Needs clarification or more information before it's actionable.
- **💬 Feedback** — User-experience observation. Often turns into one or more of the above after discussion.

### Priority

- **🔥 High** — Must fix this iteration. A default MCP tool is broken; a security/correctness issue; or a deal-breaker for adoption.
- **🟡 Medium** — Should fix soon. Workarounds exist or the impact is partial.
- **🟢 Low** — Nice to have. No clear timeline.
- **🔮 Roadmap** — Future direction we like but haven't committed to. Stays here until it earns a priority.

### Tool / area

One label per MCP tool the issue or PR touches. A PR that changes two tools gets both. The list lives in `.github/labels.yml`.

### Status

Apply **only when work is in motion**. An issue with no `status:*` label is implicitly in the backlog. The status label gets removed when the work merges or is parked.

- **`status:in-progress`** — Someone is actively working on it.
- **`status:blocked`** — Can't proceed until another issue resolves.

## Workflow

1. **Issue opened** → label with `Type`, `Tool` (if applicable), `Priority` (or 🔮 Roadmap if uncommitted).
2. **Work begins** → assignee added, `status:in-progress` applied.
3. **PR opened** → references the issue with `Fixes #N`.
4. **PR merged** → issue auto-closes; `status:*` labels are removed by the closer.

## Quick rules

- An MCP tool returning **zero results** when documented to work → 🐛 Bug + 🔥 High.
- A "would be cool if…" with no concrete user → 💬 Feedback + 🔮 Roadmap. Promote later if it sticks.
- A PR that touches `src/core/<area>/` should carry the matching `tool:<area>` label.

## Automation

Source-of-truth labels live in [`.github/labels.yml`](../.github/labels.yml). A
sync workflow keeps the live repo in agreement with that file: edit the YAML,
open a PR, and on merge the labels are reconciled automatically.

Coming in follow-up PRs (tracked in the management issues):

- Path-based PR auto-labeler — applies `tool:*` from changed file paths.
- `@claude` triage on issue open — applies `Type` / `tool:*` / priority on the way in.
- CODEOWNERS — auto-request reviewers per directory.
