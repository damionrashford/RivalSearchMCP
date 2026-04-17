"""
Middleware module for RivalSearchMCP.
Provides production-ready middleware for monitoring, security, and performance.
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict

from fastmcp.exceptions import PromptError, ResourceError, ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

# Global reference to security middleware for startup tasks
_security_middleware = None


class TimingMiddleware(Middleware):
    """Middleware for timing MCP operations."""

    def __init__(self, log_slow_operations: bool = True, slow_threshold_ms: float = 1000.0):
        self.log_slow_operations = log_slow_operations
        self.slow_threshold_ms = slow_threshold_ms
        self.logger = logging.getLogger("timing")

    async def on_request(self, context: MiddlewareContext, call_next):
        start_time = time.perf_counter()

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000

            if self.log_slow_operations and duration_ms > self.slow_threshold_ms:
                self.logger.warning(
                    f"Slow operation detected: {context.method} took {duration_ms:.2f}ms"
                )
            else:
                self.logger.info(f"Operation completed: {context.method} in {duration_ms:.2f}ms")

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(f"Operation failed: {context.method} after {duration_ms:.2f}ms: {e}")
            raise


class LoggingMiddleware(Middleware):
    """Middleware for comprehensive request/response logging."""

    def __init__(self, include_payloads: bool = False, max_payload_length: int = 1000):
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length
        self.logger = logging.getLogger("mcp_requests")

    async def on_message(self, context: MiddlewareContext, call_next):
        # Log incoming message
        self.logger.info(
            f"Processing {context.method} from {context.source} " f"(type: {context.type})"
        )

        if self.include_payloads:
            payload_str = str(context.message)[: self.max_payload_length]
            if len(str(context.message)) > self.max_payload_length:
                payload_str += "... [truncated]"
            self.logger.debug(f"Message payload: {payload_str}")

        try:
            result = await call_next(context)
            self.logger.info(f"Completed {context.method} successfully")
            return result

        except Exception as e:
            self.logger.error(f"Failed {context.method}: {type(e).__name__}: {e}")
            raise


class RateLimitingMiddleware(Middleware):
    """Middleware for rate limiting MCP operations."""

    def __init__(self, max_requests_per_minute: int = 60, per_client: bool = True):
        self.max_requests_per_minute = max_requests_per_minute
        self.per_client = per_client
        self.client_requests = defaultdict(list)
        self.logger = logging.getLogger("rate_limiting")

    def _get_client_id(self, context: MiddlewareContext) -> str:
        """Extract client identifier from context."""
        if self.per_client and context.fastmcp_context:
            return context.fastmcp_context.client_id or "unknown"
        return "global"

    async def on_request(self, context: MiddlewareContext, call_next):
        client_id = self._get_client_id(context)
        current_time = time.time()

        # Clean old requests
        cutoff_time = current_time - 60
        self.client_requests[client_id] = [
            req_time for req_time in self.client_requests[client_id] if req_time > cutoff_time
        ]

        # Check rate limit
        if len(self.client_requests[client_id]) >= self.max_requests_per_minute:
            self.logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise ToolError(
                f"Rate limit exceeded. Maximum {self.max_requests_per_minute} "
                f"requests per minute allowed."
            )

        # Add current request
        self.client_requests[client_id].append(current_time)

        return await call_next(context)


class ErrorHandlingMiddleware(Middleware):
    """Middleware for consistent error handling and logging."""

    def __init__(self, include_traceback: bool = False, transform_errors: bool = True):
        self.include_traceback = include_traceback
        self.transform_errors = transform_errors
        self.logger = logging.getLogger("error_handling")
        self.error_counts = defaultdict(int)

    async def on_message(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)

        except Exception as error:
            # Track error statistics
            error_key = f"{type(error).__name__}:{context.method}"
            self.error_counts[error_key] += 1

            # Log error details
            self.logger.error(
                f"Error in {context.method}: {type(error).__name__}: {error}",
                exc_info=self.include_traceback,
            )

            # Transform errors if enabled
            if self.transform_errors:
                if isinstance(error, (ToolError, ResourceError, PromptError)):
                    # FastMCP errors are already properly formatted
                    raise
                else:
                    # Transform generic errors to FastMCP errors
                    method = context.method or ""
                    if method.startswith("tools/"):
                        raise ToolError(f"Tool execution failed: {str(error)}")
                    elif method.startswith("resources/"):
                        raise ResourceError(f"Resource access failed: {str(error)}")
                    elif method.startswith("prompts/"):
                        raise PromptError(f"Prompt execution failed: {str(error)}")
                    else:
                        raise ToolError(f"Operation failed: {str(error)}")
            else:
                raise


class PerformanceMonitoringMiddleware(Middleware):
    """Middleware for performance monitoring and metrics collection."""

    def __init__(self):
        self.operation_times = defaultdict(list)
        self.operation_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.logger = logging.getLogger("performance")

    async def on_request(self, context: MiddlewareContext, call_next):
        start_time = time.perf_counter()
        operation = context.method

        try:
            result = await call_next(context)
            duration = time.perf_counter() - start_time

            # Record successful operation
            self.operation_times[operation].append(duration)
            self.operation_counts[operation] += 1

            # Keep only recent measurements (last 100)
            if len(self.operation_times[operation]) > 100:
                self.operation_times[operation] = self.operation_times[operation][-100:]

            return result

        except Exception:
            duration = time.perf_counter() - start_time
            self.error_counts[operation] += 1

            # Record failed operation timing
            self.operation_times[operation].append(duration)
            self.operation_counts[operation] += 1

            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        metrics = {}

        for operation in self.operation_counts:
            times = self.operation_times[operation]
            if times:
                metrics[operation] = {
                    "count": self.operation_counts[operation],
                    "error_count": self.error_counts[operation],
                    "avg_time_ms": (sum(times) / len(times)) * 1000,
                    "min_time_ms": min(times) * 1000,
                    "max_time_ms": max(times) * 1000,
                    "success_rate": 1
                    - (self.error_counts[operation] / self.operation_counts[operation]),
                }

        return metrics


class SecurityMiddleware(Middleware):
    """Enhanced middleware for security monitoring and validation."""

    def __init__(self, block_suspicious_requests: bool = True):
        self.block_suspicious_requests = block_suspicious_requests
        self.logger = logging.getLogger("security")
        # Import our enhanced security module
        from src.core.security.security import get_security_middleware

        self.security = get_security_middleware()

    def start_cleanup_task(self):
        """Start cleanup task for rate limiter."""
        if hasattr(self.security, "start_cleanup_task"):
            self.security.start_cleanup_task()

    def _is_suspicious(self, context: MiddlewareContext) -> bool:
        """Check if request contains suspicious patterns."""
        message_str = str(context.message).lower()
        # Only block actual dangerous patterns, not benign mentions
        suspicious_patterns = [
            "<script",
            "<iframe",
            "<object",
            "<embed",  # HTML injection
            "vbscript:",
            "data:text/html",
            "file://",  # Protocol injection
            "rm -rf",
            "drop table",
            "union select",  # Command/SQL injection
            "eval(",
            "exec(",
            "system(",  # Code execution
            "'; drop",
            '"; drop',
            "' or '1'='1",  # SQL injection patterns
        ]
        return any(pattern in message_str for pattern in suspicious_patterns)

    async def on_request(self, context: MiddlewareContext, call_next):
        # Enhanced security check using our security module
        request_data = {
            "client_ip": getattr(context, "client_ip", "unknown"),
            "user_agent": getattr(context, "user_agent", ""),
            "tool_name": context.method.replace("tools/", "") if context.method else "",
            "parameters": (
                getattr(context.message, "params", {}) if hasattr(context.message, "params") else {}
            ),
        }

        # Use our security middleware for comprehensive validation
        allowed, reason = await self.security.check_request(request_data)

        if not allowed:
            self.logger.warning(f"Request blocked: {reason}")
            raise ToolError(f"Request blocked: {reason}")

        # Additional basic suspicious pattern check
        if self._is_suspicious(context):
            self.logger.warning(f"Suspicious pattern detected in request: {context.method}")
            if self.block_suspicious_requests:
                raise ToolError("Request blocked due to suspicious content")

        return await call_next(context)


def register_middleware(mcp) -> None:
    """Register the full middleware stack.

    Order (added first runs first on the way in, last on the way out):

      1.  ErrorHandlingMiddleware        — outermost, catches exceptions
                                           from every middleware below
      2.  SecurityMiddleware             — rejects malformed / malicious
                                           requests before doing real work
      3.  SlidingWindowRateLimitingMiddleware
                                         — rejects excess traffic before
                                           it pollutes caches or metrics
      4.  ResponseCachingMiddleware      — short-circuits repeated work;
                                           scoped to exclude stateful tools
      5.  PerformanceMonitoringMiddleware
                                         — aggregates per-operation metrics
                                           for the /metrics endpoint
      6.  TimingMiddleware (built-in)    — logs per-request duration
      7.  LoggingMiddleware (built-in)   — structured request/response log
      8.  ResponseLimitingMiddleware     — innermost on the way out; caps
                                           oversized tool responses
      9.  PingMiddleware                 — separate: 30s keepalive for
                                           long-lived streaming connections

    This ordering is intentional: error handling is outermost so it
    catches everything; rate-limiting runs before caching so cache hits
    don't bypass it; caching runs before performance/timing so metrics
    reflect actual handler work, not cache-hit speed; response-limiting
    is innermost so it sees the final response just before it leaves.
    """
    from pathlib import Path

    from fastmcp.server.middleware.caching import (
        CallToolSettings,
        GetPromptSettings,
        ListPromptsSettings,
        ListResourcesSettings,
        ListToolsSettings,
        ReadResourceSettings,
        ResponseCachingMiddleware,
    )
    from fastmcp.server.middleware.error_handling import (
        ErrorHandlingMiddleware as BuiltinErrorHandlingMiddleware,
    )
    from fastmcp.server.middleware.logging import LoggingMiddleware as BuiltinLoggingMiddleware
    from fastmcp.server.middleware.ping import PingMiddleware
    from fastmcp.server.middleware.rate_limiting import (
        SlidingWindowRateLimitingMiddleware,
    )
    from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
    from fastmcp.server.middleware.timing import TimingMiddleware as BuiltinTimingMiddleware

    security_middleware = SecurityMiddleware(block_suspicious_requests=True)

    # 1. Error handling -- outermost
    mcp.add_middleware(
        BuiltinErrorHandlingMiddleware(
            include_traceback=False,  # don't leak internal paths to clients
            transform_errors=False,  # preserve ToolError / ResourceError types
        )
    )

    # 2. Security (our custom) -- reject bad content early
    mcp.add_middleware(security_middleware)

    # 3. Rate limiting: 100 req/min per MCP session. Sliding window
    # because token-bucket bursts can mask abuse. Uses session id as
    # client key when available (behind CloudFront every request looks
    # the same by IP, so session id is the cleanest per-caller signal).
    mcp.add_middleware(
        SlidingWindowRateLimitingMiddleware(
            max_requests=100,
            window_minutes=1,
        )
    )

    # 4. Response caching: FileTreeStore under /tmp so cache survives
    # within the container's lifetime but costs nothing when the
    # container is recycled. Stateful tools are excluded so session_id
    # auto-save side-effects still fire.
    try:
        from key_value.aio.stores.filetree import (
            FileTreeStore,
            FileTreeV1CollectionSanitizationStrategy,
            FileTreeV1KeySanitizationStrategy,
        )

        cache_dir = Path("/tmp/fastmcp-cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_store = FileTreeStore(
            data_directory=cache_dir,
            key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(cache_dir),
            collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(cache_dir),
        )
        caching_kwargs = {"cache_storage": cache_store}
    except ImportError:
        # aiofile unavailable -> fall back to in-memory caching.
        caching_kwargs = {}

    # Use an include-list, not an exclude-list. Most tools are live
    # queries against the internet -- caching them serves stale results
    # and silently papers over transient source flakes (a 0-result
    # Reddit response gets cached for 5 minutes and every retry looks
    # broken). Only cache tools whose output is a near-pure function of
    # the URL they're given.
    # Disable caching for every list/read/get surface. Caching tools/list
    # (the default) freezes tool schemas against the client -- when we
    # edit annotations, timeouts, or params, clients still see the old
    # schema until the TTL expires. Same goes for prompts/list and the
    # resource lookups. Only call_tool is safe to cache, and only for
    # the URL-fetching tools whose output is a pure function of the URL.
    _disabled = {"enabled": False}
    mcp.add_middleware(
        ResponseCachingMiddleware(
            list_tools_settings=ListToolsSettings(**_disabled),
            list_resources_settings=ListResourcesSettings(**_disabled),
            list_prompts_settings=ListPromptsSettings(**_disabled),
            read_resource_settings=ReadResourceSettings(**_disabled),
            get_prompt_settings=GetPromptSettings(**_disabled),
            call_tool_settings=CallToolSettings(
                ttl=300,
                included_tools=[
                    # URL -> content. Target page can change, but not
                    # on a 5-minute timescale for the pages agents fetch.
                    "content_operations",
                    "document_analysis",
                ],
            ),
            **caching_kwargs,
        )
    )

    # 5. Performance monitoring -- our custom metrics exposed via /metrics.
    mcp.add_middleware(PerformanceMonitoringMiddleware())

    # 6 + 7. Built-in timing + logging (replace our own narrower impls).
    mcp.add_middleware(BuiltinTimingMiddleware())
    mcp.add_middleware(
        BuiltinLoggingMiddleware(
            include_payloads=True,
            max_payload_length=500,
        )
    )

    # 8. Response size cap -- only on tools that can produce very large
    # payloads. Leaves compact search/memory tools alone so their
    # structured output schemas aren't broken by truncation.
    mcp.add_middleware(
        ResponseLimitingMiddleware(
            max_size=1_000_000,  # 1MB safety net
            tools=["content_operations", "map_website", "document_analysis"],
        )
    )

    # 9. Keepalive ping for long streaming HTTP sessions.
    mcp.add_middleware(PingMiddleware(interval_ms=30_000))

    # Store reference to security middleware for later startup
    global _security_middleware
    _security_middleware = security_middleware

    logging.getLogger("middleware").info(
        "Middleware stack registered: error, security, rate-limit, cache, "
        "perf, timing, logging, response-limit, ping"
    )


def start_background_tasks():
    """Start background tasks that require an event loop."""
    global _security_middleware
    if _security_middleware:
        try:
            # Only start if there's a running event loop
            import asyncio

            if asyncio.get_running_loop():
                _security_middleware.start_cleanup_task()
                logging.getLogger("middleware").info("Security middleware background tasks started")
            else:
                logging.getLogger("middleware").info(
                    "No running event loop, background tasks will start on first request"
                )
        except RuntimeError:
            logging.getLogger("middleware").info(
                "No running event loop, background tasks will start on first request"
            )
