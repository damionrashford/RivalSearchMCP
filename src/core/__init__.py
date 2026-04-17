"""
Core business logic for RivalSearchMCP.

Organized as subpackages (search, content, fetch, news, social, scientific,
traverse, quality, conflict, memory, cache, security, metrics, github_api,
pdf). Nothing is re-exported here -- callers import from the relevant
subpackage directly. Keeping this file empty avoids the kind of stale
`__all__` drift that accumulated in the previous version when modules
were renamed/removed.
"""
