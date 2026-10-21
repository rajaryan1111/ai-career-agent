"""Email integration for AI Career Agent.

Provides mailbox reading, drafting, and sending capabilities with explicit
approval enforcement at the external-submission boundary.

This module deliberately separates:
- Mocked provider interactions (testable without credentials)
- Real provider access (requires explicit authorization)
- Approval binding to specific recipient/subject/content

Never logs credentials, access tokens, or private message contents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class EmailProvider(str, Enum):
    """Supported email providers."""

    GMAIL = "gmail"
    OUTLOOK = "outlook"
    PROVIDER_SPECIFIC = "provider_specific"


class EmailPermission(str, Enum):
    """Permission levels for email provider access."""

    READ_ONLY = "read_only"
    DRAFT = "draft"
    SEND = "send"


@dataclass(frozen=True)
class EmailMessage:
    """Represents an email message with minimal, redacted fields."""

    message_id: str
    thread_id: str | None
    subject: str
    from_: str | None  # renamed from 'from' to avoid keyword
    to: str | None
    body_preview: str | None
    received_at: str | None
    labels: tuple[str, ...] = ()
    is_read: bool = False
    importance: str | None = None


@dataclass(frozen=True)
class EmailDraft:
    """A draft email ready for review and approval."""

    recipient: str
    subject: str
    body: str
    created_at: str  # ISO format
    # Evidence that this draft was prepared from reviewed data
    evidence_ref: str | None = None


class SendResult(str, Enum):
    """Outcome of attempting to send an email."""

    SENT = "sent"
    DEFERRED = "deferred"
    PERMISSION_DENIED = "permission_denied"
    AUTH_REQUIRED = "auth_required"
    TRANSIENT_FAILURE = "transient_failure"
    RATE_LIMITED = "rate_limited"
    UNKNOWN_ERROR = "unknown_error"
    EXPIRED = "expired"


@dataclass(frozen=True)
class SendAttempt:
    """Records a send attempt with full audit trail."""

    recipient: str
    subject: str
    body: str
    result: SendResult
    error_message: str | None
    attempted_at: str  # ISO format
    approval_id: str | None = None  # Bind to specific approval record


class ApprovalStatus(str, Enum):
    """Status of an email send approval."""

    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class EmailApproval:
    """An explicit approval record for sending an email."""

    approval_id: str
    recipient: str
    subject: str
    approved_at: str  # ISO format
    expires_at: str | None  # ISO format or None = never expires
    granted: bool
    # What was approved - bind to specific content hash
    content_hash: str  # hash of recipient+subject+body
    # Bound to specific application context if applicable
    application_id: str | None = None
    # Scope of approval
    permission_level: EmailPermission = EmailPermission.SEND
    # Who granted it (user or system)
    granted_by: str = "user"  # "user" or "system"


class EmailProviderInterface(ABC):
    """Abstract interface for email providers.

    Implementations must provide read, draft, and send capabilities.
    The interface distinguishes between mock (testable) and real (authorized)
    provider access.
    """

    @property
    @abstractmethod
    def provider(self) -> EmailProvider:
        """Return the email provider name."""

    @property
    @abstractmethod
    def permission(self) -> EmailPermission:
        """Return the permission level this instance has."""

    @abstractmethod
    def list_messages(
        self, max_results: int = 50, label: str | None = None
    ) -> tuple[EmailMessage, ...]:
        """List messages from the mailbox.

        Args:
            max_results: Maximum number of messages to return.
            label: Optional label filter (e.g., "UNREAD").

        Returns:
            Tuple of EmailMessage objects. Never includes private keys,
            tokens, or passwords in the returned data.
        """

    @abstractmethod
    def get_message(self, message_id: str) -> EmailMessage | None:
        """Get a specific message by ID.

        Returns only headers and body preview; full credentials and tokens
        are never returned in message data.
        """

    @abstractmethod
    def create_draft(
        self, recipient: str, subject: str, body: str
    ) -> EmailDraft:
        """Create a draft email.

        The draft is not sent; it requires explicit approval before sending.
        """

    @abstractmethod
    def send_email(self, draft: EmailDraft, approval: EmailApproval) -> SendResult:
        """Send a draft email with explicit approval.

        This is the external-submission boundary. The method must:
        - Bind approval to the specific recipient, subject, and body content
        - Not reuse approval for another application or changed content
        - Return appropriate result status
        - Never log credentials or private message contents
        """

    @abstractmethod
    def check_auth(self) -> bool:
        """Check if the provider has valid authentication.

        Returns True if credentials are valid and current, False if
        re-authorization is needed.
        """

    @abstractmethod
    def revoke_auth(self) -> None:
        """Revoke current authentication credentials.

        Called when the user wants to reset access. After this, check_auth
        returns False and all real provider operations are blocked until
        re-authorization.
        """


class MockEmailProvider(EmailProviderInterface):
    """Mock email provider for testing without real credentials.

    This provider simulates a mailbox for unit and integration tests.
    It does not perform real network access and is safe to use in any
    test environment.
    """

    def __init__(self, name: str = "mock") -> None:
        self._name = name
        # In-memory store of messages for this session
        self._messages: dict[str, EmailMessage] = {}
        self._drafts: dict[str, EmailDraft] = {}
        self._next_message_id = 1
        # Audit trail of boundary decisions made through this provider
        self.send_attempts: list[SendAttempt] = []

    @property
    def provider(self) -> EmailProvider:
        return EmailProvider.PROVIDER_SPECIFIC

    @property
    def permission(self) -> EmailPermission:
        return EmailPermission.SEND

    def list_messages(
        self, max_results: int = 50, label: str | None = None
    ) -> tuple[EmailMessage, ...]:
        """Return stored messages, optionally filtered by label."""
        messages = tuple(self._messages.values())
        if label is not None:
            messages = tuple(m for m in messages if label in m.labels)
        return messages[:max_results]

    def get_message(self, message_id: str) -> EmailMessage | None:
        return self._messages.get(message_id)

    def create_draft(
        self, recipient: str, subject: str, body: str
    ) -> EmailDraft:
        """Create a draft (stored in-memory, not sent)."""
        draft = EmailDraft(
            recipient=recipient,
            subject=subject,
            body=body,
            created_at=self._now_iso(),
        )
        draft_id = f"draft_{self._next_message_id}_"
        self._next_message_id += 1
        self._drafts[draft_id] = draft
        return draft

    def send_email(self, draft: EmailDraft, approval: EmailApproval) -> SendResult:
        """Mock send: enforce the same approval boundary as a real provider.

        The approval must match the exact draft content, must not be
        rejected or expired, and every attempt (success or rejection) is
        recorded in ``self.send_attempts`` for audit. No real network
        access ever happens in mock mode.
        """
        # Verify approval binds to this specific draft content
        expected_hash = self._content_hash(draft)
        if approval.content_hash != expected_hash:
            return SendResult.PERMISSION_DENIED
        if not approval.granted:
            return SendResult.PERMISSION_DENIED
        if approval.expires_at is not None:
            from datetime import datetime, timezone
            try:
                expires = datetime.fromisoformat(approval.expires_at)
                if datetime.now(timezone.utc) > expires:
                    return SendResult.EXPIRED
            except (ValueError, TypeError):
                return SendResult.UNKNOWN_ERROR

        # Record the send attempt as the mock's audit trail
        self.send_attempts.append(
            SendAttempt(
                recipient=draft.recipient,
                subject=draft.subject,
                body=draft.body,
                result=SendResult.SENT,
                error_message=None,
                attempted_at=self._now_iso(),
                approval_id=approval.approval_id,
            )
        )
        # In mock mode, nothing leaves the machine and nothing is marked
        # as externally delivered; the result only reflects the boundary
        # decision.
        return SendResult.SENT

    def check_auth(self) -> bool:
        """Mock auth: always valid for mock provider."""
        return True

    def revoke_auth(self) -> None:
        """Mock revoke: no-op for mock provider."""
        pass

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _content_hash(draft: EmailDraft) -> str:
        """Create a hash binding approval to specific draft content."""
        import hashlib
        content = f"{draft.recipient}:{draft.subject}:{draft.body}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class RealEmailProvider(EmailProviderInterface):
    """Real email provider that requires explicit authorization.

    This provider performs actual network access to a mailbox provider
    (Gmail, Outlook, etc.). It must only be used when the user has
    explicitly authorized credentials and approved real email operations.
    """

    def __init__(
        self,
        provider: EmailProvider,
        credentials_path: str | None = None,
        *,
        scope: EmailPermission = EmailPermission.SEND,
    ) -> None:
        self._provider = provider
        self._scope = scope
        self._credentials_path = credentials_path
        self._auth_valid = False
        self._initialized = False

        # Only attempt initialization if credentials path is provided
        if credentials_path is not None:
            self._initialize()

    @property
    def provider(self) -> EmailProvider:
        return self._provider

    @property
    def permission(self) -> EmailPermission:
        return self._scope

    def _initialize(self) -> None:
        """Initialize connection to the email provider.

        Must be called before any real operations. Sets _auth_valid based
        on whether credentials are valid.
        """
        # In a real implementation, this would load OAuth credentials,
        # refresh tokens, etc. from the credentials path.
        # For now, mark as not initialized to prevent accidental use.
        self._auth_valid = False
        self._initialized = True

    def check_auth(self) -> bool:
        """Check if real authentication is valid.

        Returns True if credentials are valid and current.
        Returns False if re-authorization is needed.
        """
        return self._auth_valid

    def revoke_auth(self) -> None:
        """Revoke current authentication credentials."""
        self._auth_valid = False
        self._initialized = False

    def list_messages(
        self, max_results: int = 50, label: str | None = None
    ) -> tuple[EmailMessage, ...]:
        """List messages from the mailbox.

        Requires valid authentication. Never returns private keys, tokens,
        or password data in message previews.
        """
        if not self._auth_valid:
            raise PermissionError("Email provider not authenticated")

        # In a real implementation, this would query the provider's API
        # returning only safe fields (subject, from, preview, etc.)
        # Full body, headers with tokens, and credentials are never exposed
        raise NotImplementedError(
            "Real email provider API access not implemented; "
            "use MockEmailProvider for testing or authorize real credentials"
        )

    def get_message(self, message_id: str) -> EmailMessage | None:
        """Get a specific message by ID.

        Requires valid authentication. Returns only headers and body preview.
        """
        if not self._auth_valid:
            raise PermissionError("Email provider not authenticated")
        raise NotImplementedError(
            "Real email provider API access not implemented; "
            "use MockEmailProvider for testing or authorize real credentials"
        )

    def create_draft(
        self, recipient: str, subject: str, body: str
    ) -> EmailDraft:
        """Create a draft email.

        Requires valid authentication. The draft is stored locally and
        requires explicit approval before sending.
        """
        if not self._auth_valid:
            raise PermissionError("Email provider not authenticated")
        draft = EmailDraft(
            recipient=recipient,
            subject=subject,
            body=body,
            created_at=self._now_iso(),
        )
        return draft

    def send_email(self, draft: EmailDraft, approval: EmailApproval) -> SendResult:
        """Send a draft email with explicit approval.

        This is the external-submission boundary. Must:
        - Bind approval to the specific recipient, subject, and body content
        - Not reuse approval for another application or materially changed answers
        - Perform actual sending only when all checks pass
        - Return appropriate result status
        - Never log credentials or private message contents
        """
        if not self._auth_valid:
            return SendResult.AUTH_REQUIRED

        # Verify approval binds to this specific draft content
        expected_hash = self._content_hash(draft)
        if approval.content_hash != expected_hash:
            return SendResult.PERMISSION_DENIED

        # Verify approval is not expired
        if approval.expires_at is not None:
            from datetime import datetime, timezone
            try:
                expires = datetime.fromisoformat(approval.expires_at)
                now = datetime.now(timezone.utc)
                if now > expires:
                    return SendResult.EXPIRED
            except (ValueError, TypeError):
                pass  # If parsing fails, proceed but may be unsafe

        # There is no real provider implementation behind this class yet.
        # Reporting SENT here would claim a delivery that never happened,
        # so the boundary fails closed until a genuine authorized provider
        # is integrated and the send is confirmed by that provider.
        raise NotImplementedError(
            "Real email delivery is not implemented; "
            "use MockEmailProvider for testing or integrate an authorized "
            "provider with real send confirmation"
        )

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _content_hash(draft: EmailDraft) -> str:
        """Create a hash binding approval to specific draft content."""
        import hashlib
        content = f"{draft.recipient}:{draft.subject}:{draft.body}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


def make_email_provider(
    kind: str = "mock",
    *,
    provider: EmailProvider | None = None,
    credentials_path: str | None = None,
    scope: EmailPermission = EmailPermission.SEND,
) -> EmailProviderInterface:
    """Factory function to create an email provider instance.

    Args:
        kind: "mock" for testable mock, "real" for authorized provider
        provider: Email provider name (GMAIL, OUTLOOK) — required for real
        credentials_path: Path to OAuth credentials JSON — required for real
        scope: Permission level (READ_ONLY, DRAFT, SEND)

    Returns:
        An EmailProviderInterface instance.

    Raises:
        ValueError: If required parameters are missing for the chosen kind.
    """
    if kind == "mock":
        name = credentials_path or "mock"
        return MockEmailProvider(name=name)
    elif kind == "real":
        if provider is None:
            raise ValueError("provider is required for real email provider")
        if credentials_path is None:
            raise ValueError("credentials_path is required for real email provider")
        return RealEmailProvider(
            provider=provider,
            credentials_path=credentials_path,
            scope=scope,
        )
    else:
        raise ValueError(f"Unknown email provider kind: {kind}")
