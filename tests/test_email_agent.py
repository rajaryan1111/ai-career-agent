"""Tests for the email agent's approval boundary (mock-only).

No test sends real email, touches network code paths, or uses real
credentials. The real provider is exercised only in its fail-closed states
(unauthenticated reads, unauthenticated send, and the boundary that refuses
to report a send that never happened).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from career_agent.email_agent import (
    EmailApproval,
    EmailDraft,
    EmailMessage,
    EmailPermission,
    EmailProvider,
    MockEmailProvider,
    RealEmailProvider,
    SendResult,
    make_email_provider,
)

RECIPIENT = "hiring@example-company.example"
SUBJECT = "Application: AI Intern (job 1)"
BODY = "A short, truthful application note with no fabricated facts."


def make_approval(
    draft: EmailDraft,
    approval_id: str = "appr-1",
    *,
    granted: bool = True,
    expires_at: str | None = None,
) -> EmailApproval:
    """Build an approval bound to the exact draft content."""
    return EmailApproval(
        approval_id=approval_id,
        recipient=draft.recipient,
        subject=draft.subject,
        approved_at=datetime.now(timezone.utc).isoformat(),
        expires_at=expires_at,
        granted=granted,
        content_hash=MockEmailProvider._content_hash(draft),
    )


class TestMockMailbox:
    def test_list_and_get_messages(self) -> None:
        provider = MockEmailProvider()
        message = EmailMessage(
            message_id="m1",
            thread_id="t1",
            subject="Re: your application",
            from_="recruiter@example.com",
            to="me@example.com",
            body_preview="Thanks for applying",
            received_at=datetime.now(timezone.utc).isoformat(),
            labels=("INBOX", "UNREAD"),
        )
        provider._messages["m1"] = message

        listed = provider.list_messages()
        assert listed == (message,)
        assert provider.get_message("m1") is message
        assert provider.get_message("missing") is None

    def test_label_filter(self) -> None:
        provider = MockEmailProvider()
        read_message = EmailMessage("m1", None, "s", None, None, None, None, ("INBOX",), True)
        unread_message = EmailMessage("m2", None, "s2", None, None, None, None, ("INBOX", "UNREAD"))
        provider._messages["m1"] = read_message
        provider._messages["m2"] = unread_message

        unread = provider.list_messages(label="UNREAD")
        assert [m.message_id for m in unread] == ["m2"]
        everything = provider.list_messages()
        assert len(everything) == 2

    def test_max_results_bound(self) -> None:
        provider = MockEmailProvider()
        for index in range(5):
            provider._messages[f"m{index}"] = EmailMessage(
                f"m{index}", None, "s", None, None, None, None
            )
        assert len(provider.list_messages(max_results=2)) == 2


class TestDraftCreation:
    def test_create_draft_is_never_sent(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        assert draft.recipient == RECIPIENT
        assert draft.subject == SUBJECT
        assert draft.body == BODY
        # timezone-aware ISO timestamp
        parsed = datetime.fromisoformat(draft.created_at)
        assert parsed.tzinfo is not None
        # The draft is stored, nothing is delivered
        assert any(d.recipient == RECIPIENT for d in provider._drafts.values())
        assert provider.send_attempts == []


class TestApprovalBoundary:
    def test_matching_approval_is_required_for_mock_send(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        approval = make_approval(draft)
        assert provider.send_email(draft, approval) is SendResult.SENT
        # The audit trail records exactly what the boundary allowed
        assert len(provider.send_attempts) == 1
        attempt = provider.send_attempts[0]
        assert attempt.recipient == RECIPIENT
        assert attempt.approval_id == "appr-1"
        assert attempt.result is SendResult.SENT

    def test_altered_content_rejected(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        approval = make_approval(draft)
        altered = EmailDraft(
            recipient=RECIPIENT,
            subject=SUBJECT,
            body=BODY + " (a change made after approval)",
            created_at=draft.created_at,
        )
        assert provider.send_email(altered, approval) is SendResult.PERMISSION_DENIED
        assert provider.send_attempts == []

    def test_ungranted_approval_rejected(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        approval = make_approval(draft, granted=False)
        assert provider.send_email(draft, approval) is SendResult.PERMISSION_DENIED
        assert provider.send_attempts == []

    def test_expired_approval_rejected(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        approval = make_approval(
            draft,
            expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        )
        assert provider.send_email(draft, approval) is SendResult.EXPIRED
        assert provider.send_attempts == []

    def test_fresh_expiry_allowed(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        approval = make_approval(
            draft,
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        assert provider.send_email(draft, approval) is SendResult.SENT

    def test_approval_is_not_reusable_for_changed_content(self) -> None:
        provider = MockEmailProvider()
        draft = provider.create_draft(RECIPIENT, SUBJECT, BODY)
        approval = make_approval(draft, approval_id="appr-once")
        assert provider.send_email(draft, approval) is SendResult.SENT
        # A different body needs its own approval
        changed = EmailDraft(
            recipient=RECIPIENT, subject=SUBJECT, body=BODY + " v2",
            created_at=draft.created_at,
        )
        assert provider.send_email(changed, approval) is SendResult.PERMISSION_DENIED


class TestProviderAuth_states:
    def test_mock_reports_auth_valid_and_revoke_is_noop(self) -> None:
        provider = MockEmailProvider()
        assert provider.check_auth() is True
        provider.revoke_auth()
        assert provider.check_auth() is True  # mock semantics, documented no-op

    def test_real_provider_is_unauthenticated_by_default(self) -> None:
        provider = RealEmailProvider(EmailProvider.GMAIL)
        assert provider.check_auth() is False
        assert provider.permission is EmailPermission.SEND
        assert provider.provider is EmailProvider.GMAIL

    def test_real_provider_reads_fail_closed(self) -> None:
        provider = RealEmailProvider(EmailProvider.GMAIL)
        with pytest.raises(PermissionError):
            provider.list_messages()
        with pytest.raises(PermissionError):
            provider.get_message("m1")
        with pytest.raises(PermissionError):
            provider.create_draft(RECIPIENT, SUBJECT, BODY)

    def test_real_provider_send_requires_auth_before_any_claim(self) -> None:
        provider = RealEmailProvider(EmailProvider.GMAIL)
        approval_stub = EmailApproval(
            approval_id="a",
            recipient=RECIPIENT,
            subject=SUBJECT,
            approved_at=datetime.now(timezone.utc).isoformat(),
            expires_at=None,
            granted=True,
            content_hash="irrelevant",
        )
        from career_agent.email_agent import EmailDraft as _D

        unauthenticated_draft = _D(RECIPIENT, SUBJECT, BODY, created_at="2026-01-01T00:00:00+00:00")
        assert provider.send_email(unauthenticated_draft, approval_stub) is SendResult.AUTH_REQUIRED

    def test_real_provider_never_claims_a_send_without_implementation(self) -> None:
        """Even with auth and a valid approval, without a real provider
        implementation nothing may be reported as SENT."""
        provider = RealEmailProvider(EmailProvider.GMAIL)
        provider._auth_valid = True  # white-box: simulate valid credentials
        draft = EmailDraft(RECIPIENT, SUBJECT, BODY, created_at="2026-01-01T00:00:00+00:00")
        approval = make_approval(draft)
        with pytest.raises(NotImplementedError):
            provider.send_email(draft, approval)


class TestFactory:
    def test_mock_factory(self) -> None:
        provider = make_email_provider("mock")
        assert isinstance(provider, MockEmailProvider)
        assert provider.permission is EmailPermission.SEND

    def test_real_factory_requires_provider_and_credentials(self) -> None:
        with pytest.raises(ValueError):
            make_email_provider("real")
        with pytest.raises(ValueError):
            make_email_provider("real", provider=EmailProvider.GMAIL)
        with pytest.raises(ValueError):
            make_email_provider("real", credentials_path="/tmp/creds.json")
        real = make_email_provider("real", provider=EmailProvider.GMAIL, credentials_path="/tmp/creds.json")
        assert isinstance(real, RealEmailProvider)
        assert real.check_auth() is False

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_email_provider("carrier-pigeon")
