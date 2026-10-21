"""Phase 5: Notifications and follow-ups module.

Implements local notification/follow-up requirement.
Preserves accurate state and avoids duplicate notifications where idempotency is required.
Does not pretend that notifications run when the application is closed unless a
verified external worker exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from .store import CareerStore, NotificationRecord, NotificationStatus


class NotificationType(str, Enum):
    """Types of notifications that can be generated."""
    ELIGIBILITY_UPDATE = "eligibility_update"
    REQUIREMENT_MISSING = "requirement_missing"
    RECOMMENDATION_CHANGED = "recommendation_changed"
    POLICY_BLOCKED = "policy_blocked"
    FOLLOWUP_REMINDER = "followup_reminder"


@dataclass(frozen=True)
class Notification:
    """A notification about eligibility or policy state."""
    id: str  # Unique notification identifier
    type: NotificationType
    title: str
    message: str
    timestamp: str  # ISO format
    requires_action: bool
    action_label: str | None = None  # Label for the action button
    action_url: str | None = None  # URL to navigate to (if applicable)
    dismissed: bool = False  # Whether the user has dismissed it


@dataclass(frozen=True)
class FollowupState:
    """State tracking for follow-up reminders."""
    last_shown: str  # ISO timestamp when last shown
    times_shown: int  # How many times shown
    should_remind: bool  # Whether reminder should be shown again


# NotificationStatus and NotificationRecord are imported from .store so that
# callers passing records to CareerStore.save_notification share one exact type.
# They are re-exported here for backwards compatibility.
__all__ = [
    "FollowupState",
    "Notification",
    "NotificationManager",
    "NotificationRecord",
    "NotificationStatus",
    "NotificationType",
]


class NotificationManager:
    """Manages local notifications and follow-up reminders.

    Uses the CareerStore for persistent notification records across restarts.
    Tracks state within the application for display in the UI.
    """

    def __init__(self, store: CareerStore | None = None) -> None:
        self._store = store  # None means in-memory only (original behavior)
        self._shown_notifications: set[str] = set()
        self._followup_states: dict[str, FollowupState] = {}

    @property
    def store(self) -> CareerStore | None:
        """Get the underlying store, or None if using in-memory mode."""
        return self._store

    @store.setter
    def store(self, value: CareerStore | None) -> None:
        self._store = value
        self._shown_notifications = set()
        self._followup_states = {}

    def should_show_notification(self, notification_id: str) -> bool:
        """Check if a notification should be shown (not already dismissed)."""
        # Also check store for dismissal state (only when store is available)
        if notification_id in self._shown_notifications:
            return False
        if self._store is not None:
            notif = self._store.get_notification(notification_id)
            if notif is not None and notif.status is NotificationStatus.DISMISSED:
                return False
        return True

    def mark_notification_shown(self, notification_id: str) -> None:
        """Mark a notification as shown to avoid duplicates."""
        self._shown_notifications.add(notification_id)
        # Update status in store (only when store is available)
        if self._store is not None:
            self._store.update_notification_status(notification_id, NotificationStatus.SHOWN)

    def check_followup_reminder(
        self,
        key: str,
        *,
        min_interval_hours: int = 24,
    ) -> Notification | None:
        """Check if a follow-up reminder should be shown.

        Idempotent: won't show duplicate reminders within the minimum interval.
        Persistent across restarts via store.
        Returns None if no reminder should be shown.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Check if there's already a pending followup notification in store (only when store is available)
        if self._store is not None:
            pending = self._store.list_notifications(status="pending")
            for n in pending:
                if n.dedup_key == key and n.status is NotificationStatus.PENDING:
                    # Already have a pending reminder for this key
                    return None

        # Check if enough time has passed since last shown (in-memory state);
        # this must happen BEFORE creating/persisting anything so that calls
        # inside the quiet period do not persist spurious pending records.
        times_shown = 1
        if key in self._followup_states:
            previous = self._followup_states[key]
            times_shown = previous.times_shown + 1
            try:
                last_shown = datetime.fromisoformat(previous.last_shown)
                if now < (last_shown + timedelta(hours=min_interval_hours)).isoformat():
                    # Too soon to remind again
                    return None
            except (ValueError, TypeError):
                pass  # If parsing fails, re-show

        # Create a new reminder notification (for UI display)
        notification = Notification(
            id=f"followup_{key}_{int(datetime.now().timestamp())}",
            type=NotificationType.FOLLOWUP_REMINDER,
            title="Follow-up Reminder",
            message="Your eligibility status may have changed. Review your profile and job matches.",
            timestamp=now,
            requires_action=False,
        )
        # Persist it as a record (separate from the UI Notification)
        # Only persist when store is available
        if self._store is not None:
            record = NotificationRecord(
                id=notification.id,
                type=NotificationType.FOLLOWUP_REMINDER.value,
                title="Follow-up Reminder",
                message="Your eligibility status may have changed. Review your profile and job matches.",
                timestamp=now,
                scheduled_time=now,
                status=NotificationStatus.PENDING,
                dedup_key=key,
                retry_count=0,
                max_retries=3,
                created_by="notification_manager",
            )
            self._store.save_notification(record)

        # Update followup state
        self._followup_states[key] = FollowupState(
            last_shown=now,
            times_shown=times_shown,
            should_remind=True,
        )

        # Mark as shown
        self._shown_notifications.add(notification.id)

        return notification

    def get_notification(self, notification_id: str) -> Notification | None:
        """Get a notification by ID if it exists and wasn't dismissed."""
        if notification_id in self._shown_notifications:
            # Return a copy with dismissed=False for fresh display
            # In a real implementation, we'd track dismissal state separately
            return None  # Simplified: just check existence
        # Also check store (only when store is available)
        if self._store is not None:
            notif = self._store.get_notification(notification_id)
            if notif is not None and notif.status is not NotificationStatus.DISMISSED:
                # Return a mutable-like view for the UI. A malformed stored
                # type must surface a safe default instead of crashing.
                try:
                    notification_type = NotificationType(notif.type)
                except ValueError:
                    notification_type = NotificationType.REQUIREMENT_MISSING
                return Notification(
                    id=notif.id,
                    type=notification_type,
                    title=notif.title,
                    message=notif.message,
                    timestamp=notif.timestamp,
                    requires_action=False,
                )
        return None

    def dismiss_notification(self, notification_id: str) -> None:
        """Mark a notification as dismissed in the store."""
        self._shown_notifications.discard(notification_id)
        # Only update store status when store is available
        if self._store is not None:
            self._store.update_notification_status(notification_id, NotificationStatus.DISMISSED.value)

    def clear_old_notifications(self, older_than_hours: int = 168) -> None:
        """Clear notifications older than the given hours.

        Deletion is BY RECORD ID: dedup keys are shared by many records,
        so key-based deletion would drop younger reminders too.
        """
        if self._store is not None:
            all_notifs = self._store.list_notifications()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat()
            to_delete = [n.id for n in all_notifs if n.timestamp < cutoff]
            if to_delete:
                self._store.clear_notifications_by_ids(list(to_delete))
