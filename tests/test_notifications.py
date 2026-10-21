"""Tests for persistent notifications and follow-up reminders (P3-B).

Covers: creation/persistence/retrieval, idempotent duplicate suppression,
restart recovery of pending reminders, dismissal and status transitions,
bounded retry fields, cleanup of stale notifications, and safe handling of
malformed persisted records. No real emails or external submissions are
invoked anywhere.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from career_agent.notifications import (
    FollowupState,
    NotificationManager,
    NotificationType,
)
from career_agent.store import (
    CareerStore,
    NotificationRecord,
    NotificationStatus,
    StoredRecordError,
)

UTC = timezone.utc


@pytest.fixture
def store(tmp_path: Path) -> CareerStore:
    return CareerStore(str(tmp_path / "notifications.db"))


def make_record(
    record_id: str = "n1",
    *,
    dedup_key: str = "k1",
    status: NotificationStatus = NotificationStatus.PENDING,
    timestamp: str | None = None,
) -> NotificationRecord:
    ts = timestamp or datetime.now(UTC).isoformat()
    return NotificationRecord(
        id=record_id,
        type=NotificationType.FOLLOWUP_REMINDER.value,
        title="Follow-up Reminder",
        message="Your eligibility status may have changed.",
        timestamp=ts,
        scheduled_time=ts,
        status=status,
        dedup_key=dedup_key,
        retry_count=0,
        max_retries=3,
        created_by="test",
    )


class TestPersistence:
    def test_save_get_roundtrip(self, store: CareerStore) -> None:
        record = make_record()
        store.save_notification(record)
        fetched = store.get_notification("n1")
        assert fetched is not None
        assert fetched.id == "n1"
        assert fetched.dedup_key == "k1"
        assert fetched.status is NotificationStatus.PENDING
        assert fetched.retry_count == 0
        assert fetched.max_retries == 3
        assert fetched.created_by == "test"

    def test_get_missing_returns_none(self, store: CareerStore) -> None:
        assert store.get_notification("nope") is None

    def test_list_filter_by_status(
        self, store: CareerStore
    ) -> None:
        store.save_notification(make_record("a", status=NotificationStatus.PENDING))
        store.save_notification(make_record("b", status=NotificationStatus.SHOWN))
        pending = store.list_notifications(status="pending")
        assert [n.id for n in pending] == ["a"]

    def test_update_status_and_retry_count(self, store: CareerStore) -> None:
        store.save_notification(make_record())
        store.update_notification_status("n1", "shown", retry_count=1)
        fetched = store.get_notification("n1")
        assert fetched.status is NotificationStatus.SHOWN
        assert fetched.retry_count == 1

    def test_pending_notifications(self, store: CareerStore) -> None:
        store.save_notification(make_record("p1", status=NotificationStatus.PENDING))
        store.save_notification(
            make_record("p2", status=NotificationStatus.DISMISSED)
        )
        pending = store.get_pending_notifications()
        assert [n.id for n in pending] == ["p1"]

    def test_clear_notifications_by_dedup_key(self, store: CareerStore) -> None:
        store.save_notification(make_record("c1", dedup_key="same"))
        store.save_notification(make_record("c2", dedup_key="same"))
        store.save_notification(make_record("c3", dedup_key="other"))
        store.clear_notifications(dedup_keys=("same",))
        assert store.list_notifications() == store.list_notifications()
        ids = {n.id for n in store.list_notifications()}
        assert ids == {"c3"}

    def test_save_is_idempotent_by_id(self, store: CareerStore) -> None:
        record = make_record()
        store.save_notification(record)
        record.status = NotificationStatus.SHOWN
        store.save_notification(record)
        records = store.list_notifications()
        assert len([r for r in records if r.id == "n1"]) == 1
        assert records[0].status is NotificationStatus.SHOWN


class TestRestartRecovery:
    def test_pending_notifications_survive_restart(
        self, tmp_path: Path, store: CareerStore
    ) -> None:
        """A fresh NotificationManager over the same store sees pending
        reminders created before the app exited."""
        manager = NotificationManager(store)
        manager.check_followup_reminder("profile_change")
        # Simulate restart: new manager over the same store
        fresh = NotificationManager(store)
        pending = store.list_notifications(status="pending")
        assert len(pending) == 1
        assert pending[0].dedup_key == "profile_change"
        # The second manager sees the pending reminder and does not
        # duplicate it (no notification storm after restart).
        result = fresh.check_followup_reminder("profile_change")
        assert result is None
        assert len(store.list_notifications(status="pending")) == 1


class TestDuplicateSuppression:
    def test_pending_reminder_suppresses_repeated_calls(
        self, store: CareerStore
    ) -> None:
        manager = NotificationManager(store)
        first = manager.check_followup_reminder("key1")
        assert first is not None
        second = manager.check_followup_reminder("key1")
        assert second is None
        assert len(store.list_notifications()) == 1

    def test_in_memory_interval_guard(self) -> None:
        """Without a store, the in-memory interval guard prevents repeats
        and never persists anything (store stays None)."""
        manager = NotificationManager(None)
        assert manager.check_followup_reminder("k") is not None
        assert manager.check_followup_reminder("k") is None

    def test_interval_check_does_not_persist_spurious_records(
        self, store: CareerStore
    ) -> None:
        """Calls made inside the quiet period must not create pending
        records just because the in-memory state lost its last_shown."""
        manager = NotificationManager(store)
        first = manager.check_followup_reminder("early", min_interval_hours=24)
        assert first is not None
        # Wipe the in-memory state, mimicking a separate manager that has
        # not shown anything yet, but keep the store: pending dedup check
        # must return None without persisting a second record.
        second_manager = NotificationManager(store)
        assert second_manager.check_followup_reminder("early") is None
        assert len(store.list_notifications()) == 1


class TestStatusTransitions:
    def test_dismissal_persists(self, store: CareerStore) -> None:
        manager = NotificationManager(store)
        notification = manager.check_followup_reminder("dismissable")
        assert notification is not None
        manager.dismiss_notification(notification.id)
        fetched = store.get_notification(notification.id)
        assert fetched is not None
        assert fetched.status is NotificationStatus.DISMISSED
        # should_show now returns False (dismissed in store)
        assert manager.should_show_notification(notification.id) is False

    def test_shown_state_persists(self, store: CareerStore) -> None:
        manager = NotificationManager(store)
        notification = manager.check_followup_reminder("showable")
        assert notification is not None
        manager.mark_notification_shown(notification.id)
        fetched = store.get_notification(notification.id)
        assert fetched.status is NotificationStatus.SHOWN

    def test_get_notification_returns_pending_record(
        self, store: CareerStore
    ) -> None:
        manager = NotificationManager(store)
        notification = manager.check_followup_reminder("visible")
        assert notification is not None
        # A NEW manager (post-restart) can view the pending record
        fresh = NotificationManager(store)
        view = fresh.get_notification(notification.id)
        assert view is not None
        assert view.id == notification.id
        assert view.type is NotificationType.FOLLOWUP_REMINDER

    def test_unknown_notification_type_gets_safe_default(
        self, store: CareerStore
    ) -> None:
        """Malformed/persisted type strings must not crash the manager."""
        store.save_notification(
            NotificationRecord(
                id="weird",
                type="not-a-real-type",
                title="Weird",
                message="Weird",
                timestamp=datetime.now(UTC).isoformat(),
                scheduled_time=datetime.now(UTC).isoformat(),
                status=NotificationStatus.PENDING,
                dedup_key="w",
                retry_count=0,
                max_retries=3,
                created_by="test",
            )
        )
        manager = NotificationManager(store)
        view = manager.get_notification("weird")
        assert view is not None
        assert view.type is NotificationType.REQUIREMENT_MISSING

    def test_malformed_stored_status_raises_structured_error(
        self, store: CareerStore
    ) -> None:
        store._connection.execute(
            "INSERT INTO notifications(id, type, title, message, timestamp,"
            " scheduled_time, status, dedup_key, retry_count, max_retries, created_by)"
            " VALUES ('bad', 'followup_reminder', 't', 'm', '2026-01-01', '2026-01-01',"
            " 'not-a-status', 'b', 0, 3, 'test')"
        )
        with pytest.raises(StoredRecordError):
            store.list_notifications()


class TestCleanup:
    def test_clear_old_notifications_removes_stale_only(
        self, store: CareerStore
    ) -> None:
        now = datetime.now(UTC)
        old_ts = (now - timedelta(hours=200)).isoformat()
        fresh_ts = (now - timedelta(hours=1)).isoformat()
        store.save_notification(make_record("old", timestamp=old_ts))
        store.save_notification(make_record("fresh", timestamp=fresh_ts))
        manager = NotificationManager(store)
        manager.clear_old_notifications(older_than_hours=168)
        ids = {n.id for n in store.list_notifications()}
        assert ids == {"fresh"}


class TestFollowupStateTracking:
    def test_times_shown_counts_increments_when_interval_elapsed(
        self, store: CareerStore
    ) -> None:
        manager = NotificationManager(store)
        first = manager.check_followup_reminder("counter")
        assert first is not None
        # Dismiss and clear so a new reminder can be created
        manager.dismiss_notification(first.id)
        store.clear_notifications(("counter",))
        # Age the in-memory last_shown past the 24h quiet period
        manager._followup_states["counter"] = FollowupState(
            last_shown=(datetime.now(UTC) - timedelta(hours=25)).isoformat(),
            times_shown=1,
            should_remind=True,
        )
        second = manager.check_followup_reminder("counter")
        assert second is not None
        state = manager._followup_states["counter"]
        assert state.times_shown == 2
        assert state.should_remind is True
        parsed = datetime.fromisoformat(state.last_shown)
        assert parsed.tzinfo is UTC  # timezone-aware timestamps
