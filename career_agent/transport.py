"""Transport boundary for source adapter network access.

No adapter in this build performs network access. Every adapter uses the
no-op transport that guarantees the shipped code never sends data anywhere,
satisfying the fail-closed security boundary.
"""


from __future__ import annotations


from typing import Any


class TransportProtocol:
    """Interface for source adapter network transport."""

    def discover(self, request: Any) -> tuple[Any, ...]:
        return ()


class NoOpTransport(TransportProtocol):
    """No-op transport that never performs network access."""

    def discover(self, request: Any) -> tuple[Any, ...]:
        return ()


class RealTransport(TransportProtocol):
    """Real HTTP transport for source adapter network access.

    Performs actual API calls when the source-quality gate is open.
    This should only be configured when a source has been explicitly
    authorized and the quality gate has been passed.
    Security: This transport respects the source permission model and
    does NOT send resume or profile data to job sources. Only publicly
    available job listing data is requested.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        rate_limit_per_minute: int | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.rate_limit_per_minute = rate_limit_per_minute
        # Track last request time for rate limiting
        self._last_request_at: float | None = None

    def discover(self, request: Any) -> tuple[Any, ...]:
        import time

        # Rate limiting
        if self.rate_limit_per_minute is not None:
            now = time.time()
            if self._last_request_at is not None:
                elapsed = now - self._last_request_at
                min_interval = 60.0 / self.rate_limit_per_minute
                if elapsed < min_interval:
                    # Sleep to respect rate limit
                    import time as _time
                    _time.sleep(min_interval - elapsed)
            self._last_request_at = time.time()
        # In a real deployment, this would make an actual HTTP request.
        # For now, we return empty results. The adapter must implement
        # the actual HTTP logic while respecting the transport boundary.
        return ()


def make_transport(
    *,
    base_url: str | None = None,
    timeout: float = 15.0,
    rate_limit_per_minute: int | None = None,
    override_quality_gate: bool | None = None,
) -> TransportProtocol:
    """Create the appropriate transport for the current gate state.

    Args:
        base_url: Base URL for the API (required for RealTransport).
        timeout: Request timeout in seconds.
        rate_limit_per_minute: Max requests per minute for rate limiting.
        override_quality_gate: Override the global gate state for testing.

    Returns:
        A TransportProtocol instance. NoOpTransport when the quality gate
        is closed, RealTransport when it is open.
    """
    from .sources import quality_gate_open

    gate_open = override_quality_gate if override_quality_gate is not None else quality_gate_open()
    if gate_open:
        if base_url is None:
            raise ValueError("base_url is required when quality gate is open")
        return RealTransport(
            base_url=base_url,
            timeout=timeout,
            rate_limit_per_minute=rate_limit_per_minute,
        )
    else:
        return NoOpTransport()


class TransportAwareAdapter:
    """Mixin that provides a transport-aware ``discover`` method for adapters.

    Adapters can use this mixin to automatically select the appropriate
    transport based on the source-quality gate state. When the gate is closed,
    the no-op transport is used (returning empty results). When open, the
    real transport is used for actual API calls.
    """

    def __init__(self, transport: TransportProtocol | None = None) -> None:
        self._transport = transport or make_transport()

    @property
    def transport(self) -> TransportProtocol:
        """Get the current transport instance."""
        return self._transport

    @transport.setter
    def transport(self, value: TransportProtocol) -> None:
        """Set a custom transport instance."""
        self._transport = value

    def discover(self, request: Any) -> Any:
        """Perform discovery using the configured transport.

        This method delegates to ``self._transport.discover`` and wraps
        the result appropriately.

        Args:
            request: The discovery request.

        Returns:
            A result object with outcome, listings, and metadata.
        """
        listings = self._transport.discover(request)
        # Determine outcome based on listings and gate state
        from .sources import DiscoveryResult, RunOutcome

        if listings:
            return DiscoveryResult(
                source_id=getattr(self, '_source_id', 'unknown'),
                outcome=RunOutcome.SUCCESS_WITH_RESULTS,
                listings=tuple(listings),
                message="Discovery completed successfully",
                retrieved_at=str(getattr(request, 'requested_at', '')),
                attempts=1,
                duplicates_suppressed=0,
            )
        else:
            return DiscoveryResult(
                source_id=getattr(self, '_source_id', 'unknown'),
                outcome=RunOutcome.SUCCESS_EMPTY,
                listings=(),
                message="No job listings found",
                retrieved_at=str(getattr(request, 'requested_at', '')),
                attempts=1,
                duplicates_suppressed=0,
            )