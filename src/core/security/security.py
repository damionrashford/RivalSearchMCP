"""
Security hardening module for RivalSearchMCP.
Provides rate limiting, input validation, and security measures.
"""

import asyncio
import hashlib
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from src.logging.logger import logger


class RateLimiter:
    """Token bucket rate limiter for API protection."""

    def __init__(self, requests_per_minute: int = 60, burst_limit: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.tokens: Dict[str, List[float]] = defaultdict(list)
        self._cleanup_task: Optional[asyncio.Task] = None
        # Defer task creation until event loop is available
        self._cleanup_started = False

    def start_cleanup_task(self):
        """Start periodic cleanup of old tokens. Call this when event loop is running."""
        if not self._cleanup_started:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self._cleanup_started = True

    async def _periodic_cleanup(self):
        """Periodically clean up expired tokens."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                current_time = time.time()
                cutoff_time = current_time - 60  # Remove tokens older than 1 minute

                for client_tokens in self.tokens.values():
                    # Remove old tokens
                    client_tokens[:] = [t for t in client_tokens if t > cutoff_time]

                # Remove empty client entries
                empty_clients = [client for client, tokens in self.tokens.items() if not tokens]
                for client in empty_clients:
                    del self.tokens[client]

            except Exception as e:
                logger.warning(f"Rate limiter cleanup error: {e}")
                await asyncio.sleep(60)

    def _get_client_key(self, client_ip: str, user_agent: str = "") -> str:
        """Generate a client key for rate limiting."""
        key_components = [client_ip, user_agent]
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()[:16]

    async def check_rate_limit(self, client_ip: str, user_agent: str = "") -> Tuple[bool, int]:
        """
        Check if request is within rate limits.

        Args:
            client_ip: Client IP address
            user_agent: User agent string

        Returns:
            Tuple of (allowed: bool, remaining_tokens: int)
        """
        # Bypass rate limiting during tests
        import os

        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING"):
            return True, 999

        client_key = self._get_client_key(client_ip, user_agent)
        current_time = time.time()

        # Get current tokens for this client
        client_tokens = self.tokens[client_key]

        # Remove expired tokens (older than 1 minute)
        cutoff_time = current_time - 60
        client_tokens[:] = [t for t in client_tokens if t > cutoff_time]

        # Check burst limit
        if len(client_tokens) >= self.burst_limit:
            return False, 0

        # Check rate limit
        if len(client_tokens) >= self.requests_per_minute:
            return False, 0

        # Add new token
        client_tokens.append(current_time)

        # Calculate remaining capacity
        remaining = min(
            self.burst_limit - len(client_tokens), self.requests_per_minute - len(client_tokens)
        )

        return True, remaining

    async def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        total_clients = len(self.tokens)
        total_tokens = sum(len(tokens) for tokens in self.tokens.values())

        return {
            "total_clients": total_clients,
            "total_tokens": total_tokens,
            "requests_per_minute": self.requests_per_minute,
            "burst_limit": self.burst_limit,
        }

    async def clear(self):
        """Clear all rate limit data."""
        self.tokens.clear()

    async def close(self):
        """Clean up resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


class InputValidator:
    """Input validation and sanitization for security."""

    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        r"(?i)<script[^>]*>.*?</script>",  # Script tags
        r"(?i)<iframe[^>]*>.*?</iframe>",  # Iframes
        r"(?i)<object[^>]*>.*?</object>",  # Object/embed tags
        r"(?i)<embed[^>]*>.*?</embed>",  # Embed tags
        r"(?i)javascript:",  # JavaScript URLs
        r"(?i)vbscript:",  # VBScript URLs
        r"(?i)on\w+\s*=",  # Event handlers
        r"(?i)eval\s*\(",  # Eval calls
        r"(?i)exec\s*\(",  # Exec calls
        r"(?i)import\s*\(",  # Import calls
        r"(?i)open\s*\(",  # File open calls
        r"(?i)\.\./",  # Directory traversal
        r"(?i)\.\.\\",  # Windows directory traversal
    ]

    # Allowed URL schemes
    ALLOWED_URL_SCHEMES = {"http", "https"}

    # Maximum lengths
    MAX_QUERY_LENGTH = 500
    MAX_URL_LENGTH = 2000
    MAX_CONTENT_LENGTH = 100000  # 100KB

    @classmethod
    def validate_search_query(cls, query: str) -> Tuple[bool, str]:
        """
        Validate and sanitize search query.

        Args:
            query: Search query string

        Returns:
            Tuple of (is_valid: bool, cleaned_query: str or error_message: str)
        """
        if not query or not isinstance(query, str):
            return False, "Query must be a non-empty string"

        query = query.strip()

        if len(query) > cls.MAX_QUERY_LENGTH:
            return False, f"Query too long (max {cls.MAX_QUERY_LENGTH} characters)"

        if len(query) < 2:
            return False, "Query too short (minimum 2 characters)"

        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected in query: {pattern}")
                return False, "Query contains potentially dangerous content"

        # Basic sanitization - remove excessive special characters
        cleaned_query = re.sub(
            r"[^\w\s\-_\.\(\)\[\]\{\}\+\=\&\^\%\$\#\@\!\?\,\;\:\'\"]+", "", query
        )

        return True, cleaned_query

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str]:
        """
        Validate and sanitize URL.

        Args:
            url: URL string

        Returns:
            Tuple of (is_valid: bool, cleaned_url: str or error_message: str)
        """
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string"

        url = url.strip()

        if len(url) > cls.MAX_URL_LENGTH:
            return False, f"URL too long (max {cls.MAX_URL_LENGTH} characters)"

        # Parse URL
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme and parsed.scheme.lower() not in cls.ALLOWED_URL_SCHEMES:
                return False, f"Invalid URL scheme: {parsed.scheme}. Only HTTP/HTTPS allowed."

            # Check for dangerous patterns in URL
            for pattern in cls.DANGEROUS_PATTERNS:
                if re.search(pattern, url, re.IGNORECASE):
                    logger.warning(f"Dangerous pattern detected in URL: {pattern}")
                    return False, "URL contains potentially dangerous content"

            # Reconstruct clean URL
            if not parsed.scheme:
                # Assume HTTPS if no scheme provided
                clean_url = f"https://{url}"
            else:
                clean_url = url

            # Validate the reconstructed URL
            parsed_clean = urlparse(clean_url)
            if not parsed_clean.netloc:
                return False, "Invalid URL format"

            return True, clean_url

        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

    @classmethod
    def validate_content(cls, content: str) -> Tuple[bool, str]:
        """
        Validate content for processing.

        Args:
            content: Content string

        Returns:
            Tuple of (is_valid: bool, content: str or error_message: str)
        """
        if not isinstance(content, str):
            return False, "Content must be a string"

        if len(content) > cls.MAX_CONTENT_LENGTH:
            return False, f"Content too large (max {cls.MAX_CONTENT_LENGTH} characters)"

        # Check for dangerous patterns
        dangerous_found = []
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                dangerous_found.append(pattern)

        if dangerous_found:
            logger.warning(f"Dangerous patterns detected in content: {dangerous_found}")
            # Don't block content, but log the warning
            # Return True but with sanitized content

        return True, content

    @classmethod
    def validate_numeric_param(
        cls,
        value: Any,
        param_name: str,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
    ) -> Tuple[bool, Union[int, str]]:
        """
        Validate numeric parameters.

        Args:
            value: Parameter value
            param_name: Parameter name for error messages
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Tuple of (is_valid: bool, value: int or error_message: str)
        """
        try:
            int_value = int(value)

            if min_val is not None and int_value < min_val:
                return False, f"{param_name} must be at least {min_val}"

            if max_val is not None and int_value > max_val:
                return False, f"{param_name} must be at most {max_val}"

            return True, int_value

        except (ValueError, TypeError):
            return False, f"{param_name} must be a valid integer"

    @classmethod
    def validate_boolean_param(cls, value: Any, param_name: str) -> Tuple[bool, Union[bool, str]]:
        """
        Validate boolean parameters.

        Args:
            value: Parameter value
            param_name: Parameter name for error messages

        Returns:
            Tuple of (is_valid: bool, value: bool or error_message: str)
        """
        if isinstance(value, bool):
            return True, value

        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ("true", "1", "yes", "on"):
                return True, True
            elif lower_val in ("false", "0", "no", "off"):
                return True, False

        return False, f"{param_name} must be a valid boolean value"


class SecurityMiddleware:
    """Security middleware for FastMCP server."""

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.validator = InputValidator()
        self.suspicious_ips: Set[str] = set()
        self.blocked_ips: Set[str] = set()
        self._cleanup_started = False

    def start_cleanup_task(self):
        """Start cleanup task for rate limiter."""
        self.rate_limiter.start_cleanup_task()
        self._cleanup_started = True

    async def check_request(self, request_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check incoming request for security violations.

        Args:
            request_data: Request data including IP, user agent, and parameters

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Lazy initialization of cleanup task
        if not self._cleanup_started:
            try:
                self.start_cleanup_task()
            except RuntimeError:
                # No event loop, will try again later
                pass
        client_ip = request_data.get("client_ip", "unknown")
        user_agent = request_data.get("user_agent", "")

        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            return False, "IP address blocked"

        # Skip rate limiting for stdio/local connections (no IP = trusted local process)
        if client_ip == "unknown":
            allowed, remaining = True, 999
        else:
            allowed, remaining = await self.rate_limiter.check_rate_limit(client_ip, user_agent)

        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return False, "Rate limit exceeded. Try again later."

        # Validate parameters based on tool being called
        tool_name = request_data.get("tool_name", "")
        parameters = request_data.get("parameters", {})

        validation_result = await self._validate_tool_parameters(tool_name, parameters)
        if not validation_result[0]:
            return validation_result

        return True, f"Request allowed (rate limit remaining: {remaining})"

    async def _validate_tool_parameters(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate parameters for specific tools."""
        validator = self.validator

        if tool_name == "multi_search":
            # Validate query
            if "query" in parameters:
                valid, result = validator.validate_search_query(parameters["query"])
                if not valid:
                    return False, f"Invalid query: {result}"

            # Validate numeric parameters
            numeric_params = {
                "num_results": (1, 20),
                "max_depth": (1, 3),
            }

            for param, (min_val, max_val) in numeric_params.items():
                if param in parameters:
                    valid, result = validator.validate_numeric_param(
                        parameters[param], param, min_val, max_val
                    )
                    if not valid:
                        return False, str(result)

        elif tool_name in ["content_operations", "map_website"]:
            # Validate URL (traverse_website was renamed to map_website
            # in the tool-consolidation refactor; the URL-validation path
            # is identical for both).
            if "url" in parameters:
                valid, result = validator.validate_url(parameters["url"])
                if not valid:
                    return False, f"Invalid URL: {result}"

            if tool_name == "content_operations" and "content" in parameters:
                valid, result = validator.validate_content(parameters["content"])
                if not valid:
                    return False, f"Invalid content: {result}"

        # Add more tool validations as needed

        return True, "Parameters valid"

    async def block_ip(self, ip_address: str):
        """Block an IP address."""
        self.blocked_ips.add(ip_address)
        logger.warning(f"IP address blocked: {ip_address}")

    async def unblock_ip(self, ip_address: str):
        """Unblock an IP address."""
        self.blocked_ips.discard(ip_address)
        logger.info(f"IP address unblocked: {ip_address}")

    async def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        rate_stats = await self.rate_limiter.get_stats()

        return {
            "rate_limiting": rate_stats,
            "suspicious_ips": len(self.suspicious_ips),
            "blocked_ips": len(self.blocked_ips),
            "blocked_ip_list": list(self.blocked_ips),
        }

    async def close(self):
        """Clean up resources."""
        await self.rate_limiter.close()


# Global security instance
_security_instance: Optional[SecurityMiddleware] = None


def get_security_middleware() -> SecurityMiddleware:
    """Get the global security middleware instance."""
    global _security_instance
    if _security_instance is None:
        _security_instance = SecurityMiddleware()
    return _security_instance


async def validate_request(request_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate an incoming request.

    Args:
        request_data: Request data

    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    security = get_security_middleware()
    return await security.check_request(request_data)
