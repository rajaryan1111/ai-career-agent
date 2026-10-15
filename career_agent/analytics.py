"""What the recorded activity adds up to: counts a person can check, and rates with named denominators.

A job search is long enough that memory is a bad instrument: after forty applications nobody remembers how
many answered. This module turns the records already stored here into that answer. It is written to be
useful without becoming a horoscope, which sets the rules it follows:

* **A rate always names its denominator.** "3 of 12 applications you recorded as sent" - never "25%
  response rate" with the 12 hidden somewhere.
* **A denominator that is too small produces no rate at all.** Below :data:`MIN_RATE_DENOMINATOR` the
  counts are printed and the rate is withheld with the reason, because a percentage over three applications
  moves by thirty points on one email and reads as a trend.
* **Unavailable is not zero.** An offer is the clearest example: no column, field or status in this
  application can hold one, so no offer count is reported, and the report says *why* rather than printing
  `0`, which would read as "you received none".
* **Zero is reported as zero.** Twenty applications and no recorded reply is a real, useful, painful fact,
  and it is printed as `0 of 20`.
* **Nothing here claims causation or judges the person.** The caveats are part of the report, not an
  appendix: these are counts of what was written down here, not a measure of anyone's worth or of what
  caused what.

The module is pure: it takes records and a ``today`` the caller supplies, and returns a report. No clock, no
database, no network - so the same records always produce the same report and the edge cases are testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from .core import (
    ActivityKind, ApplicationActivity, ApplicationStatus, ApplicationTracker, InterviewRound,
)

#: The smallest number of applications a rate may be computed over. Chosen so that one event moves the
#: figure by at most twenty percentage points: below that, a rate is mostly a description of its own noise
#: and reads as a trend where there is none. The counts are still reported at any size.
MIN_RATE_DENOMINATOR = 5

#: The window each half of the period comparison covers, in days.
TREND_WINDOW_DAYS = 90

#: How many recorded pairs a median needs before it is reported. A median of two numbers is their average,
#: which is not what "typical" means, so it is withheld with the reason instead.
MIN_MEDIAN_SAMPLES = 3

#: Statuses that could only be reached after something was actually sent to an employer. Deliberately
#: conservative: ``shortlisted`` and ``prepared`` are the candidate's own plans, ``submission_attempted``
#: and ``failed`` are attempts that did not complete, and ``unknown_status`` means the record does not say.
#: ``rejected_by_employer`` and beyond require a confirmed employer response (the domain refuses to store
#: them without evidence), so they belong here.
SENT_STATUSES = frozenset({
    ApplicationStatus.SUBMITTED_UNVERIFIED,
    ApplicationStatus.CONFIRMED,
    ApplicationStatus.RESPONSE_RECEIVED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.REJECTED_BY_EMPLOYER,
    ApplicationStatus.WITHDRAWN,
})

#: Statuses that could only be reached after an employer replied. Every one of them requires either a
#: candidate-confirmed record or an activity the person wrote; none is derived from silence.
REPLIED_STATUSES = frozenset({
    ApplicationStatus.RESPONSE_RECEIVED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.REJECTED_BY_EMPLOYER,
})

#: What this application cannot know, with the reason. Printed by every report, because the absence of a
#: number is information and must not be filled in with a plausible-looking one.
UNAVAILABLE_METRICS: tuple[tuple[str, str], ...] = (
    ("Offers",
     "no field, status or record in this application can hold an offer, so no offer count or offer rate is "
     "reported at all. This is missing data, not a zero, and it is why you will not see '0 offers' below."),
    ("How many applications were seen, screened or rejected without a reply",
     "an employer's silence is not a record: nothing here can observe a decision you were not told about."),
    ("Any rate of 'success'",
     "no outcome is defined here as success. An offer would be a fact about one employer on one day, and "
     "this application has nowhere to store one."),
)


@dataclass(frozen=True)
class Count:
    """One measured thing, and whether this application can measure it at all."""

    label: str
    count: int
    #: The evidence sentence: where the number comes from, in the person's own words.
    source: str

    def describe(self) -> str:
        return f"{self.label}: {self.count} ({self.source})"


@dataclass(frozen=True)
class Rate:
    """A count over an explicitly named denominator, withheld when the denominator is too small."""

    label: str
    numerator: int
    denominator: int
    #: What the denominator counts, printed in every line that uses it.
    denominator_label: str
    #: Why the rate is not being shown, when it is not. ``None`` when the rate is shown.
    withheld_because: str | None

    @property
    def available(self) -> bool:
        return self.withheld_because is None

    @property
    def percent(self) -> float | None:
        """The rate as a percentage, or ``None`` when it is withheld or the denominator is zero.

        A zero denominator is not a rate of zero: nothing was measured, and ``None`` says so.
        """
        if self.withheld_because is not None or self.denominator == 0:
            return None
        return self.numerator * 100 / self.denominator

    def describe(self) -> str:
        base = f"{self.label}: {self.numerator} of {self.denominator} {self.denominator_label}"
        if self.withheld_because is not None:
            return f"{base}. No rate is shown: {self.withheld_because}"
        if self.denominator == 0:
            return f"{base}. No rate is shown: nothing was measured yet."
        return f"{base} ({self.percent:.0f}%)"


@dataclass(frozen=True)
class PeriodComparison:
    """One figure measured over two windows, or the reason the two windows cannot be compared."""

    label: str
    window_days: int
    recent: tuple[int, int]
    earlier: tuple[int, int]
    withheld_because: str | None

    @property
    def available(self) -> bool:
        return self.withheld_because is None

    def describe(self) -> tuple[str, ...]:
        recent_numerator, recent_denominator = self.recent
        earlier_numerator, earlier_denominator = self.earlier
        lines = [
            f"{self.label}: the last {self.window_days} days hold {recent_numerator} of "
            f"{recent_denominator} recorded application(s); the {self.window_days} days before that hold "
            f"{earlier_numerator} of {earlier_denominator}."
        ]
        if self.withheld_because is not None:
            lines.append(f"  The two periods are not compared: {self.withheld_because}")
            return tuple(lines)
        lines.append(
            f"  {recent_numerator * 100 / recent_denominator:.0f}% against "
            f"{earlier_numerator * 100 / earlier_denominator:.0f}% - two counts of what was written down "
            "here, and not evidence that anything you changed caused the difference."
        )
        return tuple(lines)


@dataclass(frozen=True)
class Median:
    """A middle value over the pairs that could be measured, or why it is withheld."""

    label: str
    value: float | None
    samples: int
    unit: str
    withheld_because: str | None

    @property
    def available(self) -> bool:
        return self.withheld_because is None and self.value is not None

    def describe(self) -> str:
        if self.withheld_because is not None:
            return f"{self.label}: not reported. {self.withheld_because}"
        if self.value is None or self.samples == 0:
            return f"{self.label}: not reported. No pair of dates could be measured."
        shown = f"{self.value:g}"
        return f"{self.label}: {shown} {self.unit} (the middle of {self.samples} pair(s) you recorded)"


@dataclass(frozen=True)
class AnalyticsReport:
    """Everything this application can honestly say about the recorded search, and nothing it cannot."""

    generated_on: date
    applications_recorded: int
    counts: tuple[Count, ...]
    rates: tuple[Rate, ...]
    medians: tuple[Median, ...]
    periods: tuple[PeriodComparison, ...]
    unavailable: tuple[tuple[str, str], ...]
    caveats: tuple[str, ...]

    @property
    def anything_recorded(self) -> bool:
        return self.applications_recorded > 0

    def headline(self) -> str:
        """One line for a status bar or a summary label: the counts, never a bare percentage."""
        if not self.anything_recorded:
            return ("No application has been recorded as sent here yet, so nothing can be summarised. "
                    "The counts start from what you write down.")
        for rate in self.rates:
            if rate.label == "Applications with a recorded reply" and rate.available:
                return (f"{self.applications_recorded} application(s) recorded as sent; "
                        f"{rate.numerator} with a recorded reply ({rate.percent:.0f}%).")
        replies = next((count.count for count in self.counts
                        if count.label == "Applications with a recorded reply"), 0)
        return (f"{self.applications_recorded} application(s) recorded as sent; {replies} with a recorded "
                "reply - too few to report a rate.")

    def describe(self) -> tuple[str, ...]:
        """The whole report as lines, in the order a person reads it: what happened, then how often."""
        lines: list[str] = [f"Progress from the records in this database ({self.generated_on.isoformat()})"]
        if not self.anything_recorded:
            lines.append("")
            lines.append("Nothing is recorded as sent yet, so there is nothing to add up. The counts below "
                         "start as soon as you write down an application or move a record past the plan "
                         "stages.")
        lines.append("")
        lines.append("What the records hold")
        lines.extend(f"  {count.describe()}" for count in self.counts)
        lines.append("")
        lines.append("How often, against a named denominator")
        lines.extend(f"  {rate.describe()}" for rate in self.rates)
        lines.append("")
        lines.append("Timing")
        lines.extend(f"  {entry.describe()}" for entry in self.medians)
        lines.append("")
        lines.append("This period against the one before")
        for comparison in self.periods:
            lines.extend(f"  {line}" for line in comparison.describe())
        if not self.periods:
            lines.append("  Nothing to compare: no application has a recorded date yet.")
        lines.append("")
        lines.append("What cannot be measured here")
        for label, reason in self.unavailable:
            lines.append(f"  {label}: {reason}")
        lines.append("")
        lines.append("How to read this")
        lines.extend(f"  - {caveat}" for caveat in self.caveats)
        return tuple(lines)


def _sent_listing_ids(jobs: Sequence[Any], trackers: Mapping[str, ApplicationTracker],
                      activities: Mapping[str, Sequence[ApplicationActivity]]) -> tuple[str, ...]:
    """The listings that count as "recorded as sent", in the order the jobs are stored.

    Two independent routes, because both are real records the person made: an activity entry saying they
    applied, and a tracker status that could only be reached after something was sent. A listing that has
    both is counted once.
    """
    sent: list[str] = []
    for job in jobs:
        listing_id = job.listing_id
        applied_entry = any(entry.kind is ActivityKind.APPLIED for entry in activities.get(listing_id, ()))
        tracker = trackers.get(listing_id)
        status_says_sent = tracker is not None and tracker.status in SENT_STATUSES
        if applied_entry or status_says_sent:
            sent.append(listing_id)
    return tuple(sent)


def _replied_listing_ids(trackers: Mapping[str, ApplicationTracker],
                         activities: Mapping[str, Sequence[ApplicationActivity]]) -> tuple[str, ...]:
    """Listings with a reply *recorded*: a response entry written by the person, or a status that needs one.

    "Recorded" is the whole point. An application nobody answered has no entry and no status here, so it is
    absent from this list - which is why every rate built on it names its denominator as the applications
    recorded as sent rather than claiming to count the ones that were ignored.
    """
    replied = []
    for listing_id, entries in activities.items():
        if any(entry.kind is ActivityKind.RESPONSE for entry in entries):
            replied.append(listing_id)
    for listing_id, tracker in trackers.items():
        if tracker.status in REPLIED_STATUSES and listing_id not in replied:
            replied.append(listing_id)
    return tuple(replied)


def _first_date(entries: Iterable[ApplicationActivity], kind: ActivityKind) -> date | None:
    """The earliest date recorded for one kind of entry, or ``None`` when the person recorded none."""
    dates = [entry.occurred_on for entry in entries if entry.kind is kind]
    return min(dates) if dates else None


def _rate(label: str, numerator: int, denominator: int, denominator_label: str,
          *, minimum: int = MIN_RATE_DENOMINATOR) -> Rate:
    """Build a rate, withholding it when the denominator cannot support one.

    The denominators are counted, never estimated: an application that was never written down cannot be
    counted anywhere, and the report says so in its caveats rather than inflating a figure to look complete.
    """
    if denominator == 0:
        # Not "0%": nothing was measured, and a rate of zero would read as "none of them replied" when the
        # truth is that none of them were written down yet.
        return Rate(label, numerator, denominator, denominator_label,
                    withheld_because="nothing has been measured yet, because no application is recorded as "
                                     "sent in this database")
    if denominator < minimum:
        return Rate(label, numerator, denominator, denominator_label,
                    withheld_because=(f"the floor of {minimum} application(s) is not reached "
                                      f"(the denominator is {denominator})"))
    return Rate(label, numerator, denominator, denominator_label, withheld_because=None)


def _in_window(day: date, today: date, *, days: int, offset: int) -> bool:
    """Whether ``day`` falls in one of two adjacent windows, the most recent one ending on ``today``."""
    start = today - timedelta(days=days * (offset + 1) - 1)
    end = today - timedelta(days=days * offset)
    return start <= day <= end


def build_report(
    *,
    jobs: Sequence[Any],
    trackers: Mapping[str, ApplicationTracker],
    activities: Mapping[str, Sequence[ApplicationActivity]],
    rounds: Sequence[InterviewRound],
    today: date,
) -> AnalyticsReport:
    """Add up the stored records. Pure: the same records and the same day always give the same report."""
    sent = _sent_listing_ids(jobs, trackers, activities)
    replied = tuple(listing_id for listing_id in _replied_listing_ids(trackers, activities)
                    if listing_id in set(sent))

    interviewed = tuple(listing_id for listing_id in sent
                       if any(round_record.listing_id == listing_id for round_record in rounds))
    rejected = tuple(listing_id for listing_id in sent
                     if trackers.get(listing_id) is not None
                     and trackers[listing_id].status is ApplicationStatus.REJECTED_BY_EMPLOYER)
    withdrawn = tuple(listing_id for listing_id in sent
                      if trackers.get(listing_id) is not None
                      and trackers[listing_id].status is ApplicationStatus.WITHDRAWN)
    planned = tuple(job.listing_id for job in jobs
                    if trackers.get(job.listing_id) is not None
                    and trackers[job.listing_id].status in (ApplicationStatus.SHORTLISTED,
                                                           ApplicationStatus.PREPARED))

    activity_counts: dict[ActivityKind, int] = {kind: 0 for kind in ActivityKind}
    for entries in activities.values():
        for entry in entries:
            activity_counts[entry.kind] = activity_counts.get(entry.kind, 0) + 1

    counts = (
        Count("Applications recorded as sent", len(sent),
              "a listing with an 'applied' entry you wrote, or a status that could only be reached after "
              "something was sent"),
        Count("Applications with a recorded reply", len(replied),
              "a 'response' entry you wrote, or a status that requires a confirmed employer reply"),
        Count("Applications with an interview round recorded", len(interviewed),
              "at least one round saved against that application"),
        Count("Interview rounds recorded", len(rounds),
              "every round you saved, whether or not its day has come"),
        Count("Rounds whose day is today or earlier", sum(1 for record in rounds if record.scheduled_on <= today),
              "the planned day has arrived; nothing here claims the interview took place"),
        Count("Rounds where you recorded how it went",
              sum(1 for record in rounds if record.outcome is not None),
              "your own reading of the round, saved after it happened"),
        Count("Rejections recorded with evidence", len(rejected),
              "a status the app refuses to store without a confirmed employer response"),
        Count("Applications you withdrew", len(withdrawn),
              "your own decision, recorded as a status change"),
        Count("Applications still being planned", len(planned),
              "shortlisted or prepared, with nothing sent yet"),
        Count("Follow-up entries you wrote", activity_counts[ActivityKind.FOLLOW_UP],
              "an entry saying you chased somebody"),
        Count("Notes you wrote", activity_counts[ActivityKind.NOTE],
              "an entry recording something that happened"),
    )

    rates = (
        _rate("Applications with a recorded reply", len(replied), len(sent), "recorded as sent"),
        _rate("Applications with an interview round", len(interviewed), len(sent), "recorded as sent"),
        _rate("Rejections recorded with evidence", len(rejected), len(sent), "recorded as sent"),
        _rate("Applications you withdrew", len(withdrawn), len(sent), "recorded as sent"),
    )

    medians = _medians(jobs, activities, sent, trackers)
    periods = _periods(sent, replied, activities, today)
    return AnalyticsReport(
        generated_on=today, applications_recorded=len(sent), counts=counts, rates=rates, medians=medians,
        periods=periods, unavailable=UNAVAILABLE_METRICS, caveats=_CAVEATS,
    )


#: The sentences that keep the numbers above from being read as more than they are. Kept as data so a test
#: can assert each one is present rather than trusting the prose to survive an edit.
_CAVEATS = (
    "Every figure here counts what was written down in this database. Applications you sent and never "
    "recorded are not in any denominator, so these rates describe this database, not your job hunt.",
    "A rate is not your ability and not your worth. It moves when the market moves, when a season changes, "
    "and when one person happens to read one email.",
    "Nothing here says what caused anything. A rate that changed did not change *because* you changed your "
    "résumé, and a rate that held steady is not evidence that anything is working.",
    "An employer's silence is invisible to this application: a listing with no reply is not recorded as a "
    "rejection, because nobody rejected you - and that is why the reply rate and the rejection rate do not "
    "add up to one.",
)


def _medians(
    jobs: Sequence[Any],
    activities: Mapping[str, Sequence[ApplicationActivity]],
    sent: Sequence[str],
    trackers: Mapping[str, ApplicationTracker],
) -> tuple[Median, ...]:
    """The two timings the stored dates can support, and the reason for each one that is refused.

    Only dates the person recorded are used, and only pairs where the reply came on or after the day they
    say they applied: a response dated before the application is a data-entry mistake, not a negative gap,
    so it is excluded from the median instead of pulling it below zero. The count of excluded pairs is not
    hidden - it is part of the withheld reason when nothing is left.
    """
    sent_set = set(sent)
    gaps: list[int] = []
    unpaired = 0
    for listing_id in sent_set:
        entries = activities.get(listing_id, ())
        applied_on = _first_date(entries, ActivityKind.APPLIED)
        replied_on = _first_date(entries, ActivityKind.RESPONSE)
        if replied_on is None:
            tracker = trackers.get(listing_id)
            if tracker is None or tracker.status not in REPLIED_STATUSES:
                continue
            # A reply recorded as a status change has no day of its own here: the tracker stores the moment
            # the status was saved, not the day the employer replied, so it cannot be used as a date.
            unpaired += 1
            continue
        if applied_on is None or replied_on < applied_on:
            unpaired += 1
            continue
        gaps.append((replied_on - applied_on).days)

    if len(gaps) < MIN_MEDIAN_SAMPLES:
        if not gaps and not unpaired:
            reason = ("no application has both an application date and a reply date written down yet, so "
                      "there is no gap to measure")
            return (
                Median("Days from application to first recorded reply", None, 0, "day(s)", reason),
                Median("Interview rounds between the day they were planned for and now", None, 0, "day(s)",
                       "nothing here tracks how long a round lasted: it is a meeting, not a state"),
            )
        reason = (f"only {len(gaps)} application(s) have both an application date and a reply date written "
                  f"down ({MIN_MEDIAN_SAMPLES} are needed to call anything typical)")
        if unpaired:
            reason += (f"; {unpaired} more have a recorded reply with no reply date, because a status change "
                       "records when it was saved here rather than the day the employer replied")
        return (
            Median("Days from application to first recorded reply", None, len(gaps), "day(s)", reason),
            Median("Interview rounds between the day they were planned for and now", None, 0, "day(s)",
                   "nothing here tracks how long a round lasted: it is a meeting, not a state"),
        )
    return (
        Median("Days from application to first recorded reply", float(median(gaps)), len(gaps), "day(s)",
               None),
        Median("Interview rounds between the day they were planned for and now", None, 0, "day(s)",
               "nothing here tracks how long a round lasted: it is a meeting, not a state"),
    )


def _periods(
    sent: Sequence[str],
    replied: Sequence[str],
    activities: Mapping[str, Sequence[ApplicationActivity]],
    today: date,
) -> tuple[PeriodComparison, ...]:
    """This window against the one before, or the reason the two cannot be compared.

    An application is placed in a window by the day *it* was written down as sent; a listing with no
    ``applied`` entry cannot be placed at all, so it is excluded from both windows and the comparison says
    how many were left out rather than quietly shrinking the denominator.
    """
    if not sent:
        # Nothing was written down as sent, so there is no period to describe. A "0 of 0 against 0 of 0"
        # comparison would be a sentence about nothing, and the report says nothing is comparable instead.
        return ()
    replied_set = set(replied)
    recent_sent = recent_replied = earlier_sent = earlier_replied = 0
    unplaced = 0
    for listing_id in sent:
        applied_on = _first_date(activities.get(listing_id, ()), ActivityKind.APPLIED)
        if applied_on is None:
            unplaced += 1
            continue
        if _in_window(applied_on, today, days=TREND_WINDOW_DAYS, offset=0):
            recent_sent += 1
            recent_replied += 1 if listing_id in replied_set else 0
        elif _in_window(applied_on, today, days=TREND_WINDOW_DAYS, offset=1):
            earlier_sent += 1
            earlier_replied += 1 if listing_id in replied_set else 0

    withheld = None
    if recent_sent < MIN_RATE_DENOMINATOR or earlier_sent < MIN_RATE_DENOMINATOR:
        withheld = (
            f"both periods need at least {MIN_RATE_DENOMINATOR} recorded application(s) to compare; this "
            f"database has {recent_sent} in the recent one and {earlier_sent} in the one before"
        )
        if unplaced:
            withheld += (f", and {unplaced} application(s) have no application date recorded, so they "
                         "cannot be placed in either")
    comparison = PeriodComparison(
        "Replies recorded, by period", TREND_WINDOW_DAYS, (recent_replied, recent_sent),
        (earlier_replied, earlier_sent), withheld_because=withheld,
    )
    return (comparison,)


def report_from_store(store: Any, *, today: date) -> AnalyticsReport:
    """Gather what the report needs from a store, then compute it.

    The store is used through its public methods only, and only to read. ``jobs``, ``trackers`` and the
    per-listing activity are gathered in one pass each so a database with hundreds of applications still
    costs a handful of queries rather than one per figure.
    """
    jobs = store.list_jobs()
    trackers = {tracker.listing_id: tracker for tracker in store.list_trackers()}
    activities = {job.listing_id: store.list_activity(job.listing_id) for job in jobs}
    return build_report(jobs=jobs, trackers=trackers, activities=activities,
                        rounds=store.list_interviews(), today=today)
