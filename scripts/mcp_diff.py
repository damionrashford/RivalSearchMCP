#!/usr/bin/env python3
"""Compare two FastMCP manifest JSON files and emit a markdown diff.

Usage:
    python scripts/mcp_diff.py BASE.json HEAD.json [--output diff.md]

Reads `fastmcp inspect --format mcp` output (the protocol-shaped manifest)
from both files and classifies each change to the tool surface as:

  ➕ Added          a new tool appeared
  ➖ Removed        a tool disappeared
  ⚠️ Breaking       required field added · type changed · enum value removed
                   · required→optional removed · output schema changed
  🔧 Compatible    optional field added · enum value added · default changed
  📝 Cosmetic      description / docstring changed only

Exit code is always 0 — the script's job is to describe the diff, not gate
the PR. A maintainer reads the comment and decides.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text())
    # `fastmcp inspect --format mcp` returns {"tools": [...], "resources": [...], ...}
    # but earlier versions and other formats may differ. Be lenient.
    if "tools" in raw and isinstance(raw["tools"], list):
        return raw
    if "capabilities" in raw and isinstance(raw.get("tools"), list):
        return raw
    raise SystemExit(f"{path}: doesn't look like a FastMCP manifest (no `tools` list)")


def tools_by_name(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["name"]: t for t in manifest.get("tools", []) if isinstance(t, dict) and "name" in t}


def schema_required(schema: dict[str, Any] | None) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    req = schema.get("required") or []
    return set(req) if isinstance(req, list) else set()


def schema_properties(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties") or {}
    return props if isinstance(props, dict) else {}


def property_type(prop: dict[str, Any]) -> str:
    if not isinstance(prop, dict):
        return "<unknown>"
    if "type" in prop:
        return str(prop["type"])
    if "anyOf" in prop or "oneOf" in prop:
        return "union"
    return "<unknown>"


def property_enum(prop: dict[str, Any]) -> set[str] | None:
    if not isinstance(prop, dict):
        return None
    enum = prop.get("enum")
    if isinstance(enum, list):
        return set(map(str, enum))
    return None


def classify_tool_change(
    base: dict[str, Any], head: dict[str, Any]
) -> tuple[str, list[str]]:
    """Return (category, bullet-lines)."""
    base_schema = base.get("inputSchema") or {}
    head_schema = head.get("inputSchema") or {}
    base_req = schema_required(base_schema)
    head_req = schema_required(head_schema)
    base_props = schema_properties(base_schema)
    head_props = schema_properties(head_schema)

    breaking: list[str] = []
    compatible: list[str] = []
    cosmetic: list[str] = []

    added_props = set(head_props) - set(base_props)
    removed_props = set(base_props) - set(head_props)
    common_props = set(base_props) & set(head_props)

    for name in sorted(removed_props):
        breaking.append(f"input field `{name}` removed")
    for name in sorted(added_props):
        if name in head_req:
            breaking.append(f"required input field `{name}` added")
        else:
            compatible.append(f"optional input field `{name}` added")

    for name in sorted(common_props):
        b = base_props[name]
        h = head_props[name]
        bt, ht = property_type(b), property_type(h)
        if bt != ht:
            breaking.append(f"input field `{name}` type changed: `{bt}` → `{ht}`")
        be, he = property_enum(b), property_enum(h)
        if be is not None and he is not None:
            removed_enum = be - he
            added_enum = he - be
            if removed_enum:
                breaking.append(
                    f"input field `{name}` removed enum value(s): {', '.join(f'`{v}`' for v in sorted(removed_enum))}"
                )
            if added_enum:
                compatible.append(
                    f"input field `{name}` added enum value(s): {', '.join(f'`{v}`' for v in sorted(added_enum))}"
                )

    newly_required = (head_req - base_req) & common_props
    for name in sorted(newly_required):
        breaking.append(f"input field `{name}` is now required (was optional)")

    newly_optional = (base_req - head_req) & common_props
    for name in sorted(newly_optional):
        compatible.append(f"input field `{name}` is now optional (was required)")

    if (base.get("description") or "") != (head.get("description") or ""):
        cosmetic.append("description changed")

    if breaking:
        return ("breaking", breaking + compatible + cosmetic)
    if compatible:
        return ("compatible", compatible + cosmetic)
    if cosmetic:
        return ("cosmetic", cosmetic)
    return ("unchanged", [])


def render_markdown(base: dict[str, Any], head: dict[str, Any]) -> str:
    base_tools = tools_by_name(base)
    head_tools = tools_by_name(head)

    added = sorted(set(head_tools) - set(base_tools))
    removed = sorted(set(base_tools) - set(head_tools))
    common = sorted(set(base_tools) & set(head_tools))

    breaking: list[tuple[str, list[str]]] = []
    compatible: list[tuple[str, list[str]]] = []
    cosmetic: list[tuple[str, list[str]]] = []

    for name in common:
        cat, lines = classify_tool_change(base_tools[name], head_tools[name])
        if cat == "breaking":
            breaking.append((name, lines))
        elif cat == "compatible":
            compatible.append((name, lines))
        elif cat == "cosmetic":
            cosmetic.append((name, lines))

    if not (added or removed or breaking or compatible or cosmetic):
        return ""  # no changes — caller should skip posting

    out: list[str] = ["## 🔧 MCP tool-surface diff", ""]

    out.append(
        f"**{len(head_tools)} tools** in head ({len(added)} added, {len(removed)} removed, "
        f"{len(breaking)} breaking, {len(compatible)} compatible, {len(cosmetic)} cosmetic)."
    )
    out.append("")

    if added:
        out.append("### ➕ Added")
        for name in added:
            desc = (head_tools[name].get("description") or "").split("\n", 1)[0]
            out.append(f"- **`{name}`** — {desc}" if desc else f"- **`{name}`**")
        out.append("")

    if removed:
        out.append("### ➖ Removed")
        for name in removed:
            out.append(f"- **`{name}`**")
        out.append("")

    if breaking:
        out.append("### ⚠️ Breaking schema changes")
        for name, lines in breaking:
            out.append(f"- **`{name}`**")
            for line in lines:
                out.append(f"  - {line}")
        out.append("")

    if compatible:
        out.append("### 🔧 Compatible schema changes")
        for name, lines in compatible:
            out.append(f"- **`{name}`**")
            for line in lines:
                out.append(f"  - {line}")
        out.append("")

    if cosmetic:
        out.append("### 📝 Cosmetic changes")
        for name, lines in cosmetic:
            out.append(f"- **`{name}`** — {', '.join(lines)}")
        out.append("")

    out.append("<sub>Generated by `scripts/mcp_diff.py` from `fastmcp inspect` output.</sub>")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="base manifest JSON")
    parser.add_argument("head", type=Path, help="head manifest JSON")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="write markdown to this file. If omitted, write to stdout.",
    )
    args = parser.parse_args()

    base = load_manifest(args.base)
    head = load_manifest(args.head)
    md = render_markdown(base, head)

    if args.output:
        args.output.write_text(md)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
