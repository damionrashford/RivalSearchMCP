<!--
PR title format: <type>(<scope>): <short summary>
  type:  feat | fix | chore | refactor | docs | test | ci
  scope: optional, e.g. social, scientific, web, infra
Examples:
  fix(social): retry Reddit when Cloudflare blocks the JSON path
  feat(content_operations): add bulk URL liveness check
-->

## Summary

<!-- 1-3 sentences. Lead with what changed and why. Skip the implementation
     details — those live in the diff. -->

## Linked issue(s)

<!-- "Fixes #N" auto-closes the issue on merge. Use "Relates to #N" for
     looser links. If this PR has no linked issue, delete the line below
     instead of leaving the placeholder. -->

Fixes #<!-- replace with issue number, or delete this entire line -->

## How I tested

<!-- Be specific. "Ran the test suite" is fine for trivial changes; for
     anything that touches a tool, mention the actual command + the result.

     - [ ] `uv run pytest tests/tools/test_<area>.py` — passes
     - [ ] Manually invoked `<tool>` from the MCP client and confirmed
           <expected behavior>
     - [ ] Checked logs for regressions in <related area>
-->

## Anything reviewers should look at first?

<!-- e.g. "the retry logic in reddit.py — easy to get the tier ordering
     wrong" or "the new schema field — does this break existing callers?".
     If nothing, delete this section. -->

---

<sub>🤖 Made with [Claude Code](https://claude.com/claude-code)? Mention it in your commit trailer with `Co-Authored-By: Claude <noreply@anthropic.com>` — it shows up in `git log` and won't go stale as model versions advance.</sub>
