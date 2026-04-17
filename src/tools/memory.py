"""
Research memory — a single MCP tool that wraps all workspace CRUD.

The old version exposed five tools (start/add/get/list/delete). That's
noise in the tool list for agents. This version is one tool with a
`Literal` `operation` enum the MCP schema surfaces explicitly, so an
agent sees a single primitive with a clear enumeration of what it can
do.

Semantics match the previous tools exactly; only the surface changed.
Persistence is pluggable via src.core.memory.get_store (MemoryStore
by default; FileTreeStore when RESEARCH_MEMORY_DIR is set).
"""

from typing import Annotated, Any, Dict, List, Literal, Optional

from fastmcp import FastMCP
from pydantic import Field

from src.core.memory import research_session_add as _add
from src.core.memory import research_session_delete as _delete
from src.core.memory import research_session_get as _get
from src.core.memory import research_session_list as _list
from src.core.memory import research_session_start as _start
from src.logging.logger import logger

MemoryOperation = Literal["start", "add", "get", "list", "delete"]


def register_memory_tools(mcp: FastMCP) -> None:
    """Register the single research_memory tool."""

    @mcp.tool(
        annotations={
            "title": "Research Memory",
            # NOT read-only: `delete`/`add`/`start` mutate local workspace state.
            "readOnlyHint": False,
            # Closed world: operates on a local key/value store, no external APIs.
            "openWorldHint": False,
            # `delete` permanently removes a session.
            "destructiveHint": True,
            # `add` appends on each call; `start` creates new ids. Not idempotent.
            "idempotentHint": False,
        },
        # Local key/value store -- fast unless the backend is a remote
        # filesystem. Tight timeout flags a stuck store quickly.
        timeout=15.0,
    )
    async def research_memory(
        operation: Annotated[
            MemoryOperation,
            Field(
                description=(
                    "start  - create a new workspace. Requires `topic`. "
                    "Returns a session_id the caller uses for every "
                    "subsequent call.\n"
                    "add    - append `findings` and/or a `note` to an "
                    "existing workspace. Requires `session_id`. Duplicate "
                    "URLs are silently collapsed.\n"
                    "get    - read the full state (topic, tags, findings, "
                    "notes) of a workspace. Requires `session_id`.\n"
                    "list   - enumerate workspaces (most-recently-updated "
                    "first). Optionally filter by `tag`.\n"
                    "delete - remove a workspace permanently. Requires "
                    "`session_id`."
                ),
            ),
        ],
        session_id: Annotated[
            Optional[str],
            Field(
                description=(
                    "Workspace id. Required for add / get / delete. "
                    "Returned by start. Ignored for list."
                ),
                default=None,
            ),
        ] = None,
        topic: Annotated[
            Optional[str],
            Field(
                description=(
                    "start only: human-readable subject of this workspace "
                    "(e.g. 'OpenAI funding history', 'postgres vs mysql "
                    "for OLAP at 10TB')."
                ),
                default=None,
                min_length=2,
                max_length=300,
            ),
        ] = None,
        tags: Annotated[
            Optional[List[str]],
            Field(
                description=(
                    "start: tags for grouping/filtering (e.g. "
                    "['vendor-eval', 'q2-2026']). list: filter to one tag."
                ),
                default=None,
            ),
        ] = None,
        tag: Annotated[
            Optional[str],
            Field(
                description="list only: return workspaces that carry this tag.",
                default=None,
            ),
        ] = None,
        findings: Annotated[
            Optional[List[Dict[str, Any]]],
            Field(
                description=(
                    "add only: list of findings to append. Each entry is "
                    "an arbitrary dict; typical keys are `url`, `title`, "
                    "`quality` (from content_operations score), `source`, "
                    "`published`. URLs already in the workspace are deduped."
                ),
                default=None,
            ),
        ] = None,
        note: Annotated[
            Optional[str],
            Field(
                description=(
                    "add only: free-text note to append alongside findings "
                    "(hypotheses, follow-up items, caller's synthesis)."
                ),
                default=None,
                max_length=4000,
            ),
        ] = None,
    ) -> Dict[str, Any]:
        """
        Persistent research workspaces for iterative work.

        Append-only: findings are never overwritten; duplicate URLs are
        silently collapsed. Each entry gets a monotonic `index` and an
        `added_at` timestamp. Workspaces survive MCP session reconnects
        and, when RESEARCH_MEMORY_DIR is set, server restarts.
        """
        logger.info("research_memory: %s", operation)

        if operation == "start":
            if not topic:
                return {
                    "status": "error",
                    "error": "`topic` is required for operation='start'.",
                }
            s = await _start(topic=topic, tags=tags)
            return {"status": "success", **s.as_dict()}

        if operation == "add":
            if not session_id:
                return {
                    "status": "error",
                    "error": "`session_id` is required for operation='add'.",
                }
            if not findings and not note:
                return {
                    "status": "error",
                    "error": "Provide at least one of `findings` or `note` for add.",
                }
            updated = await _add(session_id, findings=findings, note=note)
            if updated is None:
                return {
                    "status": "error",
                    "error": f"No research session with id {session_id!r}.",
                }
            return {"status": "success", **updated.as_dict()}

        if operation == "get":
            if not session_id:
                return {
                    "status": "error",
                    "error": "`session_id` is required for operation='get'.",
                }
            s = await _get(session_id)
            if s is None:
                return {
                    "status": "error",
                    "error": f"No research session with id {session_id!r}.",
                }
            return {"status": "success", **s.as_dict()}

        if operation == "list":
            entries = await _list(tag=tag)
            return {
                "status": "success",
                "count": len(entries),
                "sessions": entries,
            }

        if operation == "delete":
            if not session_id:
                return {
                    "status": "error",
                    "error": "`session_id` is required for operation='delete'.",
                }
            removed = await _delete(session_id)
            return {
                "status": "success" if removed else "not_found",
                "deleted": removed,
                "session_id": session_id,
            }

        return {
            "status": "error",
            "error": f"Unknown operation: {operation}",
        }
