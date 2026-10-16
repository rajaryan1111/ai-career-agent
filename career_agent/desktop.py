"""Offline-first Tkinter desktop workflow for AI Career Agent.

Launch with python -m career_agent. No network calls or external service dependencies.
Domain rules, validation, and form mapping live in ``core.py``, ``store.py``,
``validation.py``, and ``desktop_logic.py``; this module only wires them to widgets.
"""
from __future__ import annotations
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import BOTH, END, LEFT, W, X, filedialog, messagebox, ttk

from .backup import (
    BACKUP_SUFFIX, BackupError, create_backup, restore_backup, suggested_backup_name,
    validate_app_database,
)
from .core import (
    INITIAL_APPLICATION_STATUS, ApplicationStatus, ApplicationTracker, Availability,
    Decision, EducationEntry, EmploymentType, FactSource, InterviewMode, InterviewOutcome,
    InterviewStage, PreparationKind, PROFILE_FACTS, WorkHistoryEntry, evaluate_eligibility,
    missing_required_profile_facts, months_covered_by, profile_fact_values, score_relevance,
    selectable_tracker_statuses,
)
from . import __version__
from . import analytics
from . import contacts
from . import integrations
from .config import database_path_for_run
from .event_log import record_event
from .handlers import seed_default_tasks
from . import importer as import_export
from .followups import (
    FollowUpState, calendar_file_name, reminder_for, reminders, summary, to_calendar,
)
from .matching import DISCLAIMER as MATCHING_DISCLAIMER, FactorStatus, assess
from .preparation import (
    ActionKind, actions as next_actions, interview_summary, preparation_summary,
    summary as actions_summary,
)
from .store import PrivateWriteError, write_private_text_file
from .worker import worker_status
from .desktop_logic import (
    ACTIVITY_DATE_PATTERN, ACTIVITY_KIND_CHOICES, JobSaveMode, activity_form_values, build_activity,
    build_candidate_profile,
    fact_label, fact_review_summary, format_stored_timestamp, form_values, job_form_values,
    plan_job_save, profile_fact_review, profile_fields_not_matching, profile_form_values,
    required_fact_questions, required_facts_to_confirm,
)
from . import contact_export, resume
from .diagnostics import describe_startup_failure, record_startup_failure
from .store import (
    SCHEMA_VERSION,
    CareerStore,
    ContactConflictOrigin,
    PrivateWriteError,
    StoredRecordError,
    TrackerStatusError,
    UnavailableStore,
    write_private_text_file,
)
from .urls import redact_url_credentials


def stored_status_text(row: dict | None) -> str:
    """Status text for a list row, shown exactly as stored when this version does not know it.

    A legacy, hand-edited, or future value is displayed as it is rather than being hidden or
    rewritten: the row is the person's own data, and an unfamiliar value is information about what
    happened, not something for the interface to repair silently. ``row`` is what
    ``CareerStore.get_tracker_raw`` returns, or ``None`` when there is no record yet.
    """
    if row is None:
        # No record yet: the domain's initial status is what such a row would start at.
        return INITIAL_APPLICATION_STATUS.value
    try:
        return ApplicationStatus(row["status"]).value
    except ValueError:
        return f"{row['status']} (not recognised by this version)"


#: How wide text drawn right across a tab may wrap, in pixels.
#:
#: A label that wraps at more than the tab has room for asks for more width than the tab gives it, and Tk
#: draws the difference outside the tab rather than short of it. The number has to hold on every platform,
#: and the pages are not the same size: at this window's own declared minimum of 900x600 the notebook's page
#: measured 878x483 on the Linux leg of run 38820361412 (2026-10-16) and only 826x453 on its macOS legs -
#: where 832- and 828-pixel labels, wrapped at 830, reached 18 and 14 pixels past the page on run
#: 38822542797. A scrolling tab is the tighter case still, because its canvas gives up the scrollbar's width
#: to it: 826 - 24 of tab padding - 15 of scrollbar = 787, less a couple of pixels for Tk's own rounding of a
#: wrapped line. 780 is that number with a little room, and it is not a preference about line length: at the
#: smallest window this application permits, each platform's page must be able to hold what a tab asks for. A
#: label standing in a narrow row beside a control is not part of this policy - it is wrapped to the width of
#: the row it shares, which is smaller than any tab.
_TAB_TEXT_WRAP = 780

#: How many recorded disagreements the review panel lists at once. The table behind it is bounded only by how
#: many contradictory files a person imports, so the screen is not. The list keeps the store's own order
#: (oldest first) rather than re-sorting what the record holds, and the label under it says how many
#: disagreements are stored and that the ones past this cap are still there, which is what a rendering cap
#: has to say to stay honest. A paging control is deliberately not part of this increment.
_CONFLICT_ROWS_SHOWN = 40

#: How much of one value a *list cell* carries. A cell is one line and Tk clips it, so a 20 MB field would be
#: copied into a row for nothing. The detail panel below is where a value is read, and it is bounded by
#: ``_CONFLICT_VALUE_CHARACTERS`` instead.
_CONFLICT_CELL_CHARACTERS = 60

#: How much of one value the detail panel shows. Unlike a cell, this is shortened with the reason stated: the
#: person is told the value's real length and that only the beginning is shown, rather than being handed a
#: sentence that looks complete. A contact CSV is capped at 20 MB, so a field can genuinely be larger than any
#: screen, and "show it all" is not a policy this window can keep.
_CONFLICT_VALUE_CHARACTERS = 400


def _shorten(text: str, limit: int) -> str:
    """``text`` with its whitespace flattened and clipped to ``limit``: one line, never a wall of text."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "\u2026"


def _conflict_origins(origin) -> str:
    """Which two places disagree, in the words the person's own export makes sense in."""
    return {
        ContactConflictOrigin.FILE: "two rows of one file",
        ContactConflictOrigin.STORED: "your records vs the file",
    }[origin]


def _conflict_list_note(total: int) -> str:
    """What the list is showing, and what it is not: counts only, so the status line and the log agree."""
    if total == 0:
        return ("No disagreements are recorded: every import so far agreed with what this database holds "
                "and with itself.")
    shown = min(total, _CONFLICT_ROWS_SHOWN)
    if shown < total:
        return (f"{total} disagreement(s) recorded; the first {shown} are listed, oldest first, and the rest "
                f"are still stored - this build has no way to page to them yet.")
    return (f"{total} disagreement(s) recorded, oldest first. Nothing here is merged, and no disagreement "
            f"can be dismissed from this screen.")


def _describe_conflict(conflict) -> list[str]:
    """The two sides of one disagreement, with the provenance the schema actually holds.

    ``kept_value`` is described as what this database keeps and ``other_value`` as what the file said, in
    that order, because that is what the record holds; neither is called correct, and where the record does
    not say where a value came from, neither does this text.
    """
    if conflict.origin is ContactConflictOrigin.FILE:
        kept_side = ("  Kept: the first answer in that file's own row order. The row is not recorded, so "
                     "this screen does not claim which one it was.")
        other_side = (f"  Not kept: a later row in {conflict.source_file!r} said something different about "
                      f"the same address.")
    else:
        kept_side = ("  Kept: the value this database already held when the file was imported. The row is "
                     "not recorded, so this screen does not claim which file supplied it.")
        other_side = f"  Not kept: {conflict.source_file!r} said something different about the same address."
    lines = [
        f"Disagreement {conflict.conflict_id} about {conflict.email_key}",
        f"Field: {conflict.field}",
        "",
        f"Kept in this database:  {_conflict_value(conflict.kept_value)}",
        f"Recorded from the file: {_conflict_value(conflict.other_value)}",
        "",
        "Where each side comes from:",
        kept_side,
        other_side,
        f"  Recorded {conflict.observed_at} (UTC, by the import that saw it).",
        "",
        "Not merged, not resolved, and not something this screen can change: editing your own file and "
        "importing it again does not rewrite what your records state, and this build has no way to dismiss "
        "a recorded disagreement.",
    ]
    return lines


def _conflict_value(value: str) -> str:
    """One value for the detail panel: bounds stated, never silently cut."""
    text = str(value)
    if len(text) <= _CONFLICT_VALUE_CHARACTERS:
        return text
    return (f"{text[:_CONFLICT_VALUE_CHARACTERS]}\u2026\n"
            f"[this value is {len(text)} characters long; only the first {_CONFLICT_VALUE_CHARACTERS} are "
            f"shown here]")


def _conflict_cell(value: str) -> str:
    """One value for a list cell: flattened, and short enough that copying it costs nothing."""
    return _shorten(value, _CONFLICT_CELL_CHARACTERS)


@dataclass
class ProfileSetupWindow:
    """One open setup window: its widgets, the questions it is asking, and the answers it is holding.

    Kept as a small record rather than as loose attributes so that a rebuild is obviously a rebuild:
    ``_render_profile_setup`` empties ``body`` and fills it from storage again, which is what makes the
    questions after a save the facts the database still does not state. ``answer_vars`` and
    ``confirm_vars`` are recreated by that rebuild, so neither can outlive the state it was drawn from.
    """

    dialog: object
    body: object
    summary: object
    save_button: object
    questions: tuple = ()
    #: The required facts that are stored but not yet checked by the person, in the profile's own order.
    #: They are shown beside their stored values instead of being asked for again; this is the record of
    #: what is on screen, so what the window offers can be read without scraping the widgets.
    awaiting: tuple = ()
    answer_vars: dict = field(default_factory=dict)
    confirm_vars: dict = field(default_factory=dict)


class CareerAgentApp:
    """Small local UI over the tested domain logic and SQLite store."""
    def __init__(self, root: tk.Tk, database_path: str | Path | None = None):
        self.root = root
        self.root.title("AI Career Agent — Local Workspace")
        self.root.geometry("1120x760")
        self.root.minsize(900, 600)
        # One rule decides this file for the window, the command line and the doctor: an explicit
        # path, then CAREER_AGENT_DATABASE, then the platform's per-user folder. Keeping it in one
        # place is what stops the app from opening a different database than the doctor reports.
        self.db_path = database_path_for_run(database_path)
        self.store = CareerStore(self.db_path)
        # The log beside the database records the sequence of what this application did. It is not a
        # second database: it holds event names, identifiers and counts, never profile or document text.
        self._record("app.started", f"version={__version__}")
        self.selected_job_id = None
        self.job_save_mode = JobSaveMode.NEW
        self.job_edit_baseline = None
        #: The one open setup window, or ``None``. One at a time: a second window would hold answers the
        #: first one has already changed, and nothing it holds is written anywhere until it is saved.
        self.profile_setup = None
        #: The contact file currently being reviewed, as the parser returned it, or ``None``. Held in
        #: memory only: a preview that is never confirmed is written nowhere and copied nowhere.
        self.contacts_preview = None
        #: The email key of the stored contact the mark controls would act on, read from the database
        #: rather than from what the list shows: the mark is written against the stored record, and a
        #: screen row is text a person reads, never a value this window writes with.
        self.contact_selected_key: str | None = None
        #: The ``conflict_id`` the review panel is showing, or ``None``. Read-only: this identifier is never
        #: written anywhere, it only says which stored row the panel is describing.
        self.contact_conflict_selected_id: int | None = None
        #: How many disagreement rows the panel last drew, so a refresh can tell whether the view still
        #: matches the database before it decides the old selection is still on screen.
        self.contact_conflicts_shown = 0
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        header = ttk.Frame(root, padding=12)
        header.pack(fill=X)
        ttk.Label(header, text="AI Career Agent", font=("TkDefaultFont", 18, "bold")).pack(anchor=W)
        ttk.Label(header, text="Local workspace · source discovery and application submission are not enabled").pack(anchor=W)
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill=BOTH, expand=True, padx=10, pady=8)
        self.profile_tab = ttk.Frame(self.tabs, padding=12)
        self.jobs_tab = ttk.Frame(self.tabs, padding=12)
        self.tracker_tab = ttk.Frame(self.tabs, padding=12)
        self.data_tab = ttk.Frame(self.tabs, padding=12)
        self.scheduler_tab = ttk.Frame(self.tabs, padding=12)
        self.follow_up_tab = ttk.Frame(self.tabs, padding=12)
        self.actions_tab = ttk.Frame(self.tabs, padding=12)
        self.history_tab = ttk.Frame(self.tabs, padding=12)
        self.contacts_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.profile_tab, text="Candidate profile")
        self.tabs.add(self.jobs_tab, text="Jobs & eligibility")
        self.tabs.add(self.tracker_tab, text="Application tracker")
        self.tabs.add(self.history_tab, text="Work history & study")
        self.tabs.add(self.actions_tab, text="Next actions")
        self.tabs.add(self.follow_up_tab, text="Follow-ups")
        self.tabs.add(self.data_tab, text="Data safety")
        self.tabs.add(self.scheduler_tab, text="Background tasks")
        self.tabs.add(self.contacts_tab, text="HR contacts")
        # Whatever a person did in another tab, or a second window did to this database, the contacts tab
        # reads it again when it is shown rather than keeping what it drew an hour ago: an import that ran
        # somewhere else shows up here the moment the tab is looked at, and a screen that came back to life
        # never describes a database that has moved on. Read-only, like everything on this tab.
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.profile_vars = {}
        self.job_vars = {}
        self._build_profile()
        self._build_jobs()
        self._build_tracker()
        self._build_history()
        self._build_actions()
        self._build_follow_ups()
        self._build_data_safety()
        self._build_scheduler()
        self._build_contacts()
        self.status = tk.StringVar(value=f"Local database: {self.db_path}")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor=W, padding=5).pack(fill=X, side="bottom")
        self._load_profile()
        self._refresh_jobs()
        self._refresh_tracker()
        self._refresh_progress()
        self._refresh_follow_ups()
        self._refresh_history()
        self._refresh_actions()
        self._refresh_scheduler()
        self._refresh_contacts()

    def _entry(self, parent, label, key, row, col, variables, *, choices=None, width=26):
        ttk.Label(parent, text=label).grid(row=row, column=col * 2, sticky=W, padx=(0, 5), pady=4)
        var = tk.StringVar()
        variables[key] = var
        widget = ttk.Combobox(parent, textvariable=var, values=choices, width=width, state="readonly") if choices else ttk.Entry(parent, textvariable=var, width=width)
        widget.grid(row=row, column=col * 2 + 1, sticky="ew", padx=(0, 12), pady=4)
        return widget

    def _build_profile(self):
        """The candidate profile: the form, the import, and what is stored behind each fact.

        Inside a scrolling body, like the Work history and the HR contacts tabs: the facts table and the
        sentences that explain it make this tab taller than the smallest page it can be given, and content
        below the fold cannot be reached at all unless something scrolls it.
        """
        body = self._scrollable_body(self.profile_tab)
        for col in (1, 3):
            body.columnconfigure(col, weight=1)
        ttk.Label(body, text="Only enter verifiable facts. Blank fields remain unknown.", wraplength=_TAB_TEXT_WRAP).grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 8))
        fields = [
            ("Country", "country", 1, 0, None), ("Degree / discipline", "degree", 1, 1, None),
            ("Study status", "study_status", 2, 0, list(resume.study_status_choices())),
            ("Graduation year", "graduation_year", 2, 1, None), ("Experience years", "experience", 3, 0, None),
            ("Work authorization value (exact when required)", "work_authorization", 3, 1, None), ("Skills (comma-separated)", "skills", 4, 0, None),
            ("Preferred locations", "locations", 4, 1, None), ("Preferred work modes", "work_modes", 5, 0, None),
            ("Preferred role types", "role_types", 5, 1, None),
        ]
        for label, key, row, col, choices in fields:
            self._entry(body, label, key, row, col, self.profile_vars, choices=choices)
        actions = ttk.Frame(body)
        actions.grid(row=6, column=0, columnspan=4, sticky=W, pady=12)
        ttk.Button(actions, text="Save profile locally", command=self._save_profile).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Import resume (PDF/DOCX)", command=self._import_resume).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete saved profile", command=self._delete_profile).pack(side="left")
        ttk.Label(
            body,
            text=(
                "Resume import reads the chosen file on this device and proposes values for you to "
                "review: nothing is uploaded, nothing is saved until you confirm, and the extracted "
                "text is not kept. Privacy: no cloud sync, external AI API, or data transfer is "
                "performed. Data stays in the local application-data folder."
            ),
            wraplength=_TAB_TEXT_WRAP,
        ).grid(row=7, column=0, columnspan=4, sticky=W, pady=8)
        ttk.Label(
            body,
            text=(
                "A resume is untrusted input: the import reads text only, never runs macros, and refuses "
                "an encrypted or over-sized file. It is not a malware scanner."
            ),
            wraplength=_TAB_TEXT_WRAP,
        ).grid(row=8, column=0, columnspan=4, sticky=W)
        self._build_profile_facts(body, row=9)
        self._build_profile_setup_note(body, row=10)

    def _build_profile_facts(self, body, *, row: int) -> None:
        """What is stored, fact by fact: the value, where it came from, and whether the person confirmed it.

        The table is the honest half of the promise the import makes. A value read out of a document says so
        in its own row, a profile written before origins were recorded says *not recorded* rather than
        claiming the person typed it, and neither can be turned into a confirmation by reading a screen: the
        button below hands one selected fact to ``CareerStore.confirm_profile_fact``, which is the only path
        in this application to a confirmed fact.

        It is a tree rather than a set of labels because a fact is a row a person selects, and because the
        harness's own measurement work reads label text: the values a candidate typed belong in a control a
        person reads one line at a time, not in copy the window repeats about itself.
        """
        panel = ttk.LabelFrame(
            body, padding=8,
            text="Saved facts: the value, where it came from, and whether you confirmed it")
        panel.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        panel.columnconfigure(0, weight=1)
        ttk.Label(
            panel, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=(
                "Every fact your saved profile states is listed here. \"Where it came from\" records who "
                "supplied the value - you, a document you chose, or a file you imported - and it is a file "
                "name, never a folder. Confirming a fact only says you have checked it: it changes no value "
                "and rewrites no origin, it can be repeated without changing anything, and a fact with no "
                "value cannot be confirmed at all because there is nothing to check. Nothing on this row "
                "of controls sends anything anywhere."
            ),
        ).grid(row=0, column=0, sticky=W, pady=(0, 6))
        self.facts_summary = tk.StringVar(value="Reading the saved profile...")
        ttk.Label(panel, textvariable=self.facts_summary, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=1, column=0, sticky=W)
        self.facts_tree = ttk.Treeview(
            panel, columns=("fact", "value", "origin", "confirmation"), show="headings", height=6)
        for column, heading, width in (("fact", "Fact", 150), ("value", "Value stored", 260),
                                       ("origin", "Where it came from", 290),
                                       ("confirmation", "Confirmed by you", 210)):
            self.facts_tree.heading(column, text=heading)
            self.facts_tree.column(column, width=width, anchor=W)
        self.facts_tree.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
        # A row id is the fact's own name (``country``, ``work_authorization``), which is what the store's
        # confirmation call takes: the table cannot select something that is not a fact, and no value a
        # person typed is ever read back to decide which fact to confirm.
        self.facts_tree.bind("<<TreeviewSelect>>", self._on_fact_selection)
        controls = ttk.Frame(panel)
        controls.grid(row=3, column=0, sticky=W, pady=(6, 0))
        # Built disabled and enabled only while exactly one stored fact is selected, like the contact tab's
        # mark controls: a control that cannot do anything is better greyed out than offering something it
        # would refuse, and a disabled Tk button does not run its command when it is invoked.
        self.confirm_fact_button = ttk.Button(
            controls, text="This is correct — confirm it", state="disabled",
            command=self._confirm_selected_fact)
        self.confirm_fact_button.pack(side="left")
        ttk.Button(controls, text="Refresh the saved facts", command=self._refresh_fact_review).pack(
            side="left", padx=8)
        ttk.Button(controls, text="Set up missing required facts...", command=self._open_profile_setup).pack(
            side="left")

    def _build_profile_setup_note(self, body, *, row: int) -> None:
        """The sentence under the table about what this app will and will not ask a person for."""
        self.profile_setup_note = tk.StringVar(value=(
            "The setup window asks only for the facts a listing can require - country, degree, study "
            "status, graduation year, experience and work authorization - and only where your saved "
            "profile states nothing for them. A preference such as a location, a work mode or a role type "
            "is never asked as if a listing required it, and no answer is guessed from another: a fact you "
            "leave blank stays unknown, and the eligibility checks keep treating it as unknown."
        ))
        ttk.Label(body, textvariable=self.profile_setup_note, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=row, column=0, columnspan=4, sticky=W, pady=(10, 0))

    def _build_jobs(self):
        for col in (1, 3, 5):
            self.jobs_tab.columnconfigure(col, weight=1)
        ttk.Label(self.jobs_tab, text="Manual entry only. Leave unknown requirements blank; do not guess country eligibility or apply URLs.", wraplength=_TAB_TEXT_WRAP).grid(row=0, column=0, columnspan=6, sticky=W, pady=(0, 8))
        fields = [
            ("Employer", "employer", 1, 0, None), ("Role title", "title", 1, 1, None), ("Source name", "source_name", 1, 2, None),
            ("Source listing URL", "source_url", 2, 0, None), ("Employer apply URL (verified)", "apply_url", 2, 1, None), ("Requisition ID", "requisition", 2, 2, None),
            ("Availability", "availability", 3, 0, [x.value for x in Availability]), ("Eligibility scope", "scope", 3, 1, ["unknown", "restricted", "worldwide"]),
            ("Work mode", "work_mode", 3, 2, ["", "remote", "hybrid", "on-site"]),
            ("Role type", "role_type", 4, 0, None), ("Location", "location", 4, 1, None), ("Allowed countries", "countries", 4, 2, None),
            ("Allowed disciplines", "degrees", 5, 0, None), ("Allowed study statuses", "study_statuses", 5, 1, None), ("Allowed graduation years", "graduation_years", 5, 2, None),
            ("Allowed work-authorization values (exact)", "allowed_work_authorizations", 7, 0, None),
            ("Availability evidence / note", "provenance_note", 7, 1, None),
            ("Minimum experience", "min_exp", 6, 0, None), ("Maximum experience", "max_exp", 6, 1, None), ("Required skills", "required_skills", 6, 2, None),
        ]
        for label, key, row, col, choices in fields:
            self._entry(self.jobs_tab, label, key, row, col, self.job_vars, choices=choices, width=22)
        self.job_vars["availability"].set("unknown")
        self.job_vars["scope"].set("unknown")
        actions = ttk.Frame(self.jobs_tab)
        actions.grid(row=8, column=0, columnspan=6, sticky=W, pady=6)
        for text, callback in [
            ("Save job", self._save_job), ("Evaluate selected", self._evaluate),
            ("Shortlist if eligible", self._shortlist), ("Delete selected", self._delete_job), ("New job", self._begin_new_job),
        ]:
            ttk.Button(actions, text=text, command=callback).pack(side="left", padx=(0, 6))
        self.job_mode = tk.StringVar()
        ttk.Label(self.jobs_tab, textvariable=self.job_mode).grid(row=11, column=0, columnspan=6, sticky=W, pady=(4, 0))
        self._set_job_mode_display()
        self.jobs_tree = ttk.Treeview(self.jobs_tab, columns=("employer", "role", "availability", "status", "source", "observed"), show="headings", height=9)
        for col, label, width in [("employer", "Employer", 140), ("role", "Role", 170), ("availability", "Availability", 100), ("status", "Tracker status", 150), ("source", "Source", 190), ("observed", "Last saved here (this app, UTC)", 200)]:
            self.jobs_tree.heading(col, text=label)
            self.jobs_tree.column(col, width=width, anchor=W)
        self.jobs_tree.grid(row=9, column=0, columnspan=6, sticky="nsew", pady=(6, 0))
        self.jobs_tab.rowconfigure(9, weight=1)
        self.jobs_tree.bind("<<TreeviewSelect>>", self._select_job)
        self.report = tk.Text(self.jobs_tab, height=7, wrap="word", state="disabled")
        self.report.grid(row=10, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        self._report("Select a job and evaluate it. Only explicit PASS is eligible for shortlisting.")

    def _build_tracker(self):
        actions = ttk.Frame(self.tracker_tab)
        actions.pack(fill=X, pady=(0, 8))
        ttk.Button(actions, text="Refresh", command=self._refresh_tracker).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Update selected status", command=self._update_status).pack(side="left", padx=8)
        ttk.Button(actions, text="Export local data to JSON", command=self._export).pack(side="left", padx=8)
        ttk.Label(self.tracker_tab, text="A confirmed application requires evidence. An attempt or timeout is not proof.").pack(anchor=W, pady=(0, 8))
        self.tracker_tree = ttk.Treeview(self.tracker_tab, columns=("employer", "role", "status", "saved", "evidence"), show="headings")
        for col, label, width in [("employer", "Employer", 170), ("role", "Role", 200), ("status", "Status", 180), ("saved", "Status saved here (this app, UTC)", 200), ("evidence", "Evidence / note", 380)]:
            self.tracker_tree.heading(col, text=label)
            self.tracker_tree.column(col, width=width, anchor=W)
        self.tracker_tree.pack(fill=BOTH, expand=True)
        self.tracker_tree.bind("<<TreeviewSelect>>", self._select_tracker)
        self._build_activity_panel()

    def _build_activity_panel(self):
        """The dated history of what actually happened, kept beside the status it does not change."""
        ttk.Label(
            self.tracker_tab,
            text=(
                "Activity history — your own record of what happened, with dates. An entry never "
                "changes the status above and is never treated as proof that an employer replied."
            ),
            wraplength=_TAB_TEXT_WRAP,
        ).pack(anchor=W, pady=(10, 4))
        actions = ttk.Frame(self.tracker_tab)
        actions.pack(fill=X, pady=(0, 4))
        ttk.Button(actions, text="Add entry", command=self._add_activity).pack(side="right")
        ttk.Button(actions, text="Delete selected entry", command=self._delete_activity).pack(side="right", padx=8)
        self.activity_tree = ttk.Treeview(
            self.tracker_tab, columns=("occurred", "kind", "detail", "recorded"), show="headings", height=6,
        )
        for col, label, width in [("occurred", "Date", 110), ("kind", "What", 170),
                                  ("detail", "What happened", 430),
                                  ("recorded", "Recorded here (this app, UTC)", 210)]:
            self.activity_tree.heading(col, text=label)
            self.activity_tree.column(col, width=width, anchor=W)
        self.activity_tree.pack(fill=BOTH, expand=False)
        self._build_progress_panel()

    def _build_progress_panel(self):
        """One summary line and a read-only report, on the tab where the records they are counted from live.

        The line states counts and never a bare percentage, and the report it opens is the same report the
        command line prints - computed by ``career_agent.analytics`` from the records in this database, so
        the two surfaces cannot disagree about somebody's own numbers.
        """
        row = ttk.Frame(self.tracker_tab)
        row.pack(fill=X, pady=(10, 0))
        self.progress_summary = tk.StringVar()
        ttk.Label(
            self.tracker_tab, textvariable=self.progress_summary, wraplength=_TAB_TEXT_WRAP, justify="left",
        ).pack(anchor=W, pady=(6, 0))
        ttk.Button(row, text="Progress report", command=self._show_progress_report).pack(side="left")
        ttk.Label(
            row,
            text=("Counts of what is written down here, with the denominator named. A rate too small to mean "
                  "anything is withheld rather than shown, and what this app cannot measure is listed as "
                  "unmeasurable rather than as zero."),
            wraplength=760, justify="left",
        ).pack(side="left", padx=8)

    def _refresh_progress(self):
        """Recompute the summary line from the records. Read-only, and never fatal to the tab.

        A database that cannot be read here must not stop the tracker list itself from being drawn: the
        person's records are shown either way, and the summary says it could not be computed instead of
        showing a figure that is wrong.
        """
        if not hasattr(self, "progress_summary"):
            return
        try:
            report = analytics.report_from_store(self.store, today=datetime.now().date())
        except (StoredRecordError, TrackerStatusError, sqlite3.Error) as exc:
            self.progress_summary.set(f"The progress summary could not be computed: {exc}")
            return
        self.progress_summary.set(report.headline())

    def _open_read_only_dialog(self, *, title: str, heading: str, intro: str):
        """Open a fixed-size, read-only, scrollable dialog and return the frame to fill with lines.

        One surface for every "here is what this application would show you" text: the same size as the
        progress report, closed by Escape or Return, with a single Close button. The text is labels rather
        than an editable widget, so there is nothing here to type into or accidentally change; a caller
        that needs to produce an action still has to provide its own button, and no caller gets one from
        this helper.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.geometry("900x640")
        dialog.minsize(620, 400)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.bind("<Return>", lambda _event: dialog.destroy())

        footer = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        footer.pack(fill=X, side="bottom")
        ttk.Button(footer, text="Close", command=dialog.destroy).pack(side="right")

        header = ttk.Frame(dialog, padding=(12, 12, 12, 6))
        header.pack(fill=X)
        ttk.Label(header, text=heading, font=("TkDefaultFont", 11, "bold")).pack(anchor=W)
        ttk.Label(header, text=intro, wraplength=820, justify="left").pack(anchor=W, pady=(4, 0))

        body = ttk.Frame(dialog)
        body.pack(fill=BOTH, expand=True, padx=12, pady=(0, 4))
        return self._scrollable_body(body)

    def _scrollable_body(self, parent):
        """A scrollable area filling ``parent``, and the frame inside it to fill with content.

        One implementation for the read-only dialogs and for the tab that holds more than a small window
        can show. The inner frame is pinned to the canvas's own width, which is what stops a form wider
        than the window from pushing its right-hand columns outside the area it is drawn in: the grid
        inside shrinks its own columns instead. Measured by the display-backed harness on 2026-10-16,
        before this existed: at the window's own minimum size the employment and education forms reached
        174 pixels past the Work history and study tab's right edge, and at the size the window opens
        with, the education form's tree sat 18 pixels below the tab - packed content below the fold is
        drawn outside the window and, with nothing to scroll, could not be reached at all.
        """
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill=BOTH, expand=True)
        scrolled = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=scrolled, anchor="nw")

        def fit_scrollregion(_event=None):
            box = canvas.bbox("all")
            if box:
                canvas.configure(scrollregion=box)

        def fit_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        def scroll_units(event):
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        scrolled.bind("<Configure>", fit_scrollregion)
        canvas.bind("<Configure>", fit_width)
        canvas.bind("<MouseWheel>", scroll_units)
        scrolled.bind("<MouseWheel>", scroll_units)
        return scrolled

    def _add_read_only_lines(self, parent, lines) -> None:
        """Pack plain read-only lines into a dialog body, wrapping the long ones."""
        for line in lines:
            if not line:
                ttk.Label(parent, text="").pack(anchor=W)
            elif not line.startswith(" ") and line.count(":") <= 1:
                ttk.Label(parent, text=line, font=("TkDefaultFont", 10, "bold")).pack(anchor=W, pady=(6, 0))
            else:
                ttk.Label(parent, text=line, wraplength=830, justify="left").pack(anchor=W)

    def _show_progress_report(self):
        """Open the whole report in a read-only, scrollable dialog. Writes nothing."""
        try:
            report = analytics.report_from_store(self.store, today=datetime.now().date())
        except (StoredRecordError, TrackerStatusError) as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return

        scrolled = self._open_read_only_dialog(
            title="Progress from your records (read-only)",
            heading=f"Progress computed for {report.generated_on.isoformat()} (this machine's day)",
            intro=("Nothing here is read from anywhere but this database, and nothing here is sent "
                   "anywhere. Every figure is a count of what you recorded."),
        )

        self._add_read_only_lines(scrolled, report.describe())
        self.status.set("Progress report opened: read-only, computed from the records in this database.")


    # ------------------------------------------------------------------ the HR contact list
    #
    # The list is *imported*, never discovered: the person exports it themselves and chooses the file
    # here. The parser is the shipped one (``career_agent.contacts``) and the store owns the transaction
    # (``CareerStore.import_contacts``); this tab supplies the file chooser, shows what was read, and asks
    # once before anything is written. There is no sending here and no matching to jobs: this increment
    # stores a reviewed list and nothing else.

    def _build_contacts(self):
        """The tab about the contact list: what the chosen file holds, and what storing it would do.

        Inside a scrolling body, like the Work history and study tab and for the same reason: the preview,
        the rows worth a person's attention and the stored list together are taller than the smallest page
        this window can be given, and content below the fold cannot be reached at all unless something
        scrolls it. The contact values live in the two trees rather than in labels: a tree a person drags
        through is the right control for rows, and the text the acceptance harness reports measurements
        about is label text, which must never carry somebody's address.
        """
        body = self._scrollable_body(self.contacts_tab)
        ttk.Label(
            body, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=(
                "An HR contact list you exported is read from this machine, checked, and shown here before "
                "anything is stored. Nothing is sent, nothing is fetched and no address is contacted: the "
                "file is read from disk and the list is kept in this local database until you delete it. "
                "A mark of \"do not contact\" is never cleared by an import."
            ),
        ).grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 8))
        actions = ttk.Frame(body)
        actions.grid(row=1, column=0, columnspan=2, sticky=W, pady=(0, 4))
        ttk.Button(actions, text="Choose a contact CSV...",
                   command=self._choose_contact_csv).pack(side="left")
        ttk.Button(actions, text="Import these contacts",
                   command=self._store_contact_preview).pack(side="left", padx=8)
        ttk.Button(actions, text="Clear the preview",
                   command=self._clear_contact_preview).pack(side="left", padx=(0, 8))
        self.contacts_summary = tk.StringVar(value="Reading the stored contact list...")
        ttk.Label(body, textvariable=self.contacts_summary, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=2, column=0, columnspan=2, sticky=W, pady=(4, 8))
        ttk.Label(body, text="What the chosen file holds (nothing is stored until you confirm)").grid(
            row=3, column=0, columnspan=2, sticky=W, pady=(6, 2))
        self.contacts_preview_text = tk.Text(body, height=14, wrap="word", state="disabled")
        self.contacts_preview_text.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Label(body, text="Rows worth your attention, in the file's own order").grid(
            row=5, column=0, columnspan=2, sticky=W, pady=(10, 2))
        self.contact_rows_tree = ttk.Treeview(
            body, columns=("line", "contact", "name", "company", "why"), show="headings", height=7)
        for column, heading, width in (("line", "Line", 60), ("contact", "Address as written", 220),
                                       ("name", "Name as written", 150), ("company", "Company label", 150),
                                       ("why", "Why it needs a look", 220)):
            self.contact_rows_tree.heading(column, text=heading)
            self.contact_rows_tree.column(column, width=width, anchor=W)
        self.contact_rows_tree.grid(row=6, column=0, columnspan=2, sticky="nsew")
        ttk.Label(body, text="Stored contacts (what this database holds now)").grid(
            row=7, column=0, columnspan=2, sticky=W, pady=(10, 2))
        self.stored_contacts_tree = ttk.Treeview(
            body, columns=("contact", "name", "company", "source", "seen", "marked"),
            show="headings", height=7)
        for column, heading, width in (("contact", "Address as written", 220), ("name", "Name", 150),
                                       ("company", "Company label", 150), ("source", "From file", 140),
                                       ("seen", "Imports seen", 90), ("marked", "Flags or mark", 180)):
            self.stored_contacts_tree.heading(column, text=heading)
            self.stored_contacts_tree.column(column, width=width, anchor=W)
        self.stored_contacts_tree.grid(row=8, column=0, columnspan=2, sticky="nsew")
        # Selecting a row is what tells the controls below which contact they act on, and the line under
        # them says what that contact's mark is now: the two are read from the database, so a stale row
        # cannot be acted on as if it still existed.
        self.stored_contacts_tree.bind("<<TreeviewSelect>>", self._on_contact_selection)
        ttk.Button(body, text="Refresh", command=self._refresh_contacts).grid(row=9, column=0, sticky=W, pady=(8, 0))
        mark_controls = ttk.Frame(body)
        mark_controls.grid(row=10, column=0, columnspan=2, sticky=W, pady=(4, 0))
        # Both are built disabled and are enabled only for the action that would change the selected
        # contact's state. A control that cannot do anything here is better off greyed out than offering a
        # change it will refuse, and a disabled Tk button does not run its command when it is invoked.
        self.mark_contact_button = ttk.Button(
            mark_controls, text="Mark do not contact", state="disabled", command=self._mark_selected_contact)
        self.mark_contact_button.pack(side="left")
        self.clear_contact_button = ttk.Button(
            mark_controls, text="Remove do-not-contact mark", state="disabled",
            command=self._clear_selected_contact)
        self.clear_contact_button.pack(side="left", padx=8)
        # The reason sits on its own row rather than beside the buttons: two buttons with these labels
        # plus a labelled box on one line is wider than a tab can be at the window's own minimum size on
        # the platforms whose default font is not this one, and Tk clips rather than wrapping a row.
        note_row = ttk.Frame(body)
        note_row.grid(row=11, column=0, columnspan=2, sticky=W, pady=(4, 0))
        ttk.Label(note_row, text="Reason (optional):").pack(side="left")
        self.contact_note = tk.StringVar()
        self.contact_note_entry = ttk.Entry(note_row, textvariable=self.contact_note, width=24,
                                            state="disabled")
        self.contact_note_entry.pack(side="left", padx=(4, 0))
        self.contact_mark_state = tk.StringVar(value="No stored contact is selected.")
        ttk.Label(body, textvariable=self.contact_mark_state, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=12, column=0, columnspan=2, sticky=W, pady=(6, 0))
        # What a mark is, said in the place it is made: it is the person's own record, it survives an
        # import, and it cannot be mistaken for something that stops a message - because nothing in this
        # build sends anything.
        ttk.Label(
            body, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=(
                "A do-not-contact mark is a note you keep in your own database: no import can clear it, it "
                "travels with your backups and restores, and the reason you type is stored on the record "
                "alone - never in a log, a dialog or an activity event. Nothing in this build sends "
                "anything, so a mark records your decision; the state line above says whether a reason is "
                "already recorded with it."
            ),
        ).grid(row=13, column=0, columnspan=2, sticky=W, pady=(6, 0))
        # The one destructive action on this tab, on its own row and under its own sentence. It is not
        # beside the mark controls for two reasons: erasing a record is not another way of annotating one,
        # and a row holding these three labels plus this button is wider than the narrowest page this tab
        # can be given - Tk clips a row rather than wrapping it.
        delete_row = ttk.Frame(body)
        delete_row.grid(row=14, column=0, columnspan=2, sticky=W, pady=(10, 0))
        # Built disabled and enabled only while a stored row is selected, like the two mark controls: a
        # destructive button that cannot act is better off greyed out than offering something it will refuse.
        self.delete_contact_button = ttk.Button(
            delete_row, text="Delete selected contact", state="disabled",
            command=self._delete_selected_contact)
        self.delete_contact_button.pack(side="left")
        # The sentence sits in a text variable rather than in a literal, so what the window says about the
        # one action that cannot be undone is read back by a test rather than only drawn.
        self.contact_delete_note = tk.StringVar(value=(
            "Deleting removes one stored contact — the row you select above — and every "
            "disagreement recorded about it, in a single step. No other contact, mark or disagreement is "
            "touched. There is no undo in this application: nothing here can bring the record back. A "
            "backup you wrote earlier still holds it, and restoring that copy would bring it back, because "
            "a restore replaces this database with the copy you choose. Nothing is sent to anybody either "
            "way, and the delete key in this window never removes a contact file."
        ))
        ttk.Label(body, textvariable=self.contact_delete_note, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=15, column=0, columnspan=2, sticky=W, pady=(4, 0))
        ttk.Label(
            body, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=(
                "Checked: the shape of each address, which is a heuristic about text, and whether the "
                "columns agree with one another. Not checked, and not claimable from a file: whether a "
                "mailbox exists or is reachable, whether anybody agreed to be contacted, who still works "
                "where the file says, or whether this list may be used for outreach at all. A stored "
                "contact is never written to, and no send button exists in this build."
            ),
        ).grid(row=16, column=0, columnspan=2, sticky=W, pady=(10, 0))
        ttk.Label(body, text="Recorded disagreements (nothing here is merged or changed)").grid(
            row=17, column=0, columnspan=2, sticky=W, pady=(12, 2))
        # One disagreement per row, oldest first, in the store's own order. The columns carry the compact
        # facts and the panel below carries the two values in full: a list cell is one line and Tk clips it,
        # and a name that disagrees with another name is exactly the thing that must not be clipped.
        self.contact_conflicts_tree = ttk.Treeview(
            body,
            columns=("ref", "contact", "field", "origins", "recorded_from", "recorded_at"),
            show="headings", height=6)
        for column, heading, width in (
                ("ref", "#", 40), ("contact", "Contact", 200), ("field", "Field", 80),
                ("origins", "Which two sides", 170), ("recorded_from", "Recorded from", 160),
                ("recorded_at", "Recorded at", 150)):
            self.contact_conflicts_tree.heading(column, text=heading)
            self.contact_conflicts_tree.column(column, width=width, anchor=W)
        self.contact_conflicts_tree.grid(row=18, column=0, columnspan=2, sticky="nsew")
        self.contact_conflicts_tree.bind("<<TreeviewSelect>>", self._on_conflict_selection)
        self.contact_conflict_note = tk.StringVar(value="Reading the recorded disagreements...")
        ttk.Label(body, textvariable=self.contact_conflict_note, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=19, column=0, columnspan=2, sticky=W, pady=(6, 0))
        self.contact_conflict_text = tk.Text(body, height=8, wrap="word", state="disabled")
        self.contact_conflict_text.grid(row=20, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        # The sentence this panel exists to make unnecessary to guess at: what it does, what it refuses to
        # do, and why the database is the thing that decides which value it keeps.
        ttk.Label(
            body, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=(
                "A disagreement is two non-empty answers to one question about one address - the file's "
                "against your stored record, or one row of a file against another row of the same file. "
                "Both answers are kept, and this database keeps the one it already had rather than picking a "
                "winner: no import can rewrite the name or the company your records state. This screen only "
                "shows them, changes nothing, and cannot dismiss a disagreement. Select a row above to read "
                "both sides in full."
            ),
        ).grid(row=21, column=0, columnspan=2, sticky=W, pady=(6, 0))
        # The export lives at the bottom of this tab, under its own heading and its own sentence, because
        # it is the one control here that writes a file outside the database. The sentence is a variable
        # rather than a literal so what the window claims about the file - including the part it cannot do
        # - is read back by a test rather than only drawn, and the part about the mark comes from the
        # format module, so the window and the command line cannot describe it differently.
        ttk.Label(body, text="Take a copy of the stored list (a CSV file you choose)").grid(
            row=22, column=0, columnspan=2, sticky=W, pady=(12, 2))
        export_row = ttk.Frame(body)
        export_row.grid(row=23, column=0, columnspan=2, sticky=W)
        self.export_contacts_button = ttk.Button(export_row, text="Export the stored list...",
                                                 command=self._export_contacts)
        self.export_contacts_button.pack(side="left")
        self.contact_export_note = tk.StringVar(value=(
            "Exporting writes one CSV row per stored contact - the address, the name and the company "
            "label as they are stored, plus whether each one is marked do not contact - to a file you "
            "choose. It is a list to move between machines or read, not a backup of this application: "
            "marks, their reasons and the recorded disagreements stay in this database, no disagreement "
            "value is exported, and an existing file is only replaced if you confirm the overwrite in "
            "the save dialog. " + contact_export.MARK_COLUMN_LIMITATION + " Nothing is sent anywhere, and "
            "exporting changes nothing in this database."
        ))
        ttk.Label(body, textvariable=self.contact_export_note, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=24, column=0, columnspan=2, sticky=W, pady=(4, 0))
        body.columnconfigure(0, weight=1)

    def _choose_contact_csv(self):
        """Read one chosen contact CSV locally and show what it holds. Writes nothing at all."""
        chosen = filedialog.askopenfilename(
            parent=self.root, title="Choose a contact CSV to review",
            filetypes=[("Contact list (CSV)", "*.csv"), ("All files", "*.*")])
        if not chosen:
            self.status.set("Contact import cancelled; the database was not changed.")
            return
        try:
            parsed = contacts.read_contact_csv(chosen)
        except contacts.ContactImportError as exc:
            # The parser's sentence names the file and the problem and never a cell value, so it can be
            # shown as it stands; the second line is the promise this window keeps.
            messagebox.showerror("Nothing was imported", f"{exc}\n\nThe database was not changed.",
                                 parent=self.root)
            self.status.set("Contact file not read; the database was not changed.")
            self._record("import.refused", f"reason={type(exc).__name__}")
            return
        except Exception as exc:  # noqa: BLE001 - defensive: a Tk callback has no handler above it
            # The reader is written to refuse every unreadable file with its own error type, so this is the
            # last line of defence against a failure shape this build does not know about. Only the type is
            # reported: an unexpected message could quote a cell.
            messagebox.showerror(
                "Nothing was imported",
                "This file could not be read, so nothing was proposed and the database was not changed.\n\n"
                f"The reader reported {type(exc).__name__}; the file itself was not modified.",
                parent=self.root)
            self.status.set("Contact file not read; the database was not changed.")
            self._record("import.refused", f"reason={type(exc).__name__}")
            return
        # Counts only: the parsed values are shown in the panels below and are not events.
        self.contacts_preview = parsed
        self._render_contact_preview("")
        counts = parsed.counts()
        self.status.set(
            f"Contact file read: {counts['rows read']} row(s), {counts['unique email keys']} email "
            f"key(s), {counts['rows to review']} to review. Nothing has been stored yet.")

    def _render_contact_preview(self, note: str) -> None:
        """Fill the read-only panels from the previewed file. Shows values to the person, logs none."""
        parsed = self.contacts_preview
        lines = [note, ""] if note else []
        lines.extend(parsed.describe())
        self.contacts_preview_text.configure(state="normal")
        self.contacts_preview_text.delete("1.0", END)
        self.contacts_preview_text.insert("1.0", "\n".join(lines))
        self.contacts_preview_text.configure(state="disabled")
        self._clear_tree(self.contact_rows_tree)
        # The rows the parser flagged, plus the ones the file itself put in a review column: these are the
        # rows a person can still act on before confirming, and the values are theirs to read here only.
        for row in parsed.rows_to_review():
            # Both reasons are shown when both apply: the parser's own findings about the text, and any note
            # the person's export carried in its review column. This is the one place a row's values appear,
            # and it is the person's own file on their own screen.
            why = ", ".join(part for part in (row.describe_flags(), row.recorded_reasons.strip()) if part)
            self.contact_rows_tree.insert("", END, values=(
                row.line, row.email or "(no address)", row.name or "", row.company or "",
                why or "listed in the file's review column",
            ))

    def _store_contact_preview(self):
        """Store the previewed file, after showing what it would do and asking once.

        The plan is computed from the database first and shown in full, so an import into a list that
        already holds records is a decision the person makes with the consequences in front of them: how
        many contacts are added, how many are updated, how many disagreements will be kept for review, and
        how many rows cannot be stored at all because they have no address.
        """
        if self.contacts_preview is None:
            messagebox.showinfo(
                "Choose a file first",
                "No contact CSV has been read yet, so there is nothing to store. Use \"Choose a contact "
                "CSV...\" first; nothing was changed.",
                parent=self.root)
            return
        try:
            plan = self.store.plan_contact_import(self.contacts_preview)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if not messagebox.askyesno(
                "Import these contacts?",
                "\n".join(plan.describe()) + "\n\nStore them now?", parent=self.root):
            self.status.set("Contact import cancelled; nothing was written.")
            return
        try:
            outcome = self.store.import_contacts(self.contacts_preview)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        except ValueError as exc:
            # A refusal from the store itself, with its own sentence: nothing is claimed to have happened.
            messagebox.showerror("Nothing was imported", f"{exc}\n\nNo contact was stored.",
                                 parent=self.root)
            self._record("import.failed", "reason=a stored contact record was refused")
            return
        self._refresh_contacts()
        self._render_contact_preview(f"Imported: {outcome.describe()}.")
        self.status.set(f"Contact import complete: {outcome.describe()}.")
        messagebox.showinfo(
            "Contact import complete",
            f"{outcome.describe()}.\n\nNothing was contacted, no email was sent, and no address left this "
            "machine. The stored list is below; a do-not-contact mark survives every later import.",
            parent=self.root)

    def _clear_contact_preview(self):
        """Forget the previewed file. Nothing was ever stored for it, so there is nothing to undo."""
        self.contacts_preview = None
        self.contacts_preview_text.configure(state="normal")
        self.contacts_preview_text.delete("1.0", END)
        self.contacts_preview_text.insert(
            "1.0", "No contact file is being reviewed. Nothing has been stored by this panel.")
        self.contacts_preview_text.configure(state="disabled")
        self._clear_tree(self.contact_rows_tree)
        self.status.set("Contact preview cleared; nothing was stored or changed.")

    def _refresh_contacts(self):
        """Re-read the stored contact list and the counts beside it. Read-only."""
        try:
            records = self.store.list_contacts()
            counts = self.store.contact_record_counts()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._clear_tree(self.stored_contacts_tree)
        for record in records:
            marked = "do not contact" if record.suppressed else ", ".join(record.review_flags)
            self.stored_contacts_tree.insert("", END, iid=str(record.contact_id), values=(
                record.email, record.name or "", record.company or "", record.source_file,
                record.seen_count, marked,
            ))
        self.contacts_summary.set(
            f"Stored here: {counts['contacts']} contact(s) · {counts['do_not_contact']} marked "
            f"do-not-contact · {counts['with_review_flags']} carrying a review flag · "
            f"{counts['conflicts']} disagreement(s) kept for review. Nothing here has been contacted.")
        self._sync_contact_actions()
        # The disagreements are part of the same read: a screen that showed a new conflict count beside a
        # stale list of them would be the worse half of both.
        self._refresh_contact_conflicts()

    # ------------------------------------------------------------------ the do-not-contact mark
    #
    # The mark is the person's own decision about somebody on their list, and this is the only screen that
    # writes it: the store method it calls is the only writer of the column, and no import statement
    # mentions it at all, which is what makes the mark survive a re-import, a contradicting file, a backup,
    # a restore and a restart. Two rules the handlers below keep:
    #
    # * **A contact is described by where it sits, never by what it says.** A confirmation names the row's
    #   position in the list and the file it came from. The address, the name and the company are the
    #   person's own data on their own screen, and dialog text is what a screenshot or a bug report keeps.
    # * **Nothing is written unless the store call returns.** A declined confirmation, a refusal or an
    #   exception leaves the mark exactly as it was, and no message claims otherwise.

    def _selected_contact_id(self) -> int | None:
        """The stored contact id behind the list's selected row, or ``None`` when nothing usable is selected."""
        tree = getattr(self, "stored_contacts_tree", None)
        selection = tree.selection() if tree is not None else ()
        if not selection:
            return None
        try:
            return int(selection[0])
        except (TypeError, ValueError):
            return None

    def _on_contact_selection(self, _event=None):
        """Show what the newly selected contact's mark is, and enable the action that would change it."""
        self._sync_contact_actions()

    def _sync_contact_actions(self):
        """Read the selected contact and set the controls from what the database holds. Writes nothing.

        Called after every refresh, so a mark changed anywhere - here, by a restore, or by another window -
        is reflected rather than remembered: what a control offers is decided from the stored record at the
        moment it is shown, and a contact whose row has gone leaves both controls disabled.
        """
        if not hasattr(self, "stored_contacts_tree"):
            return
        try:
            records = self.store.list_contacts()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        selected_id = self._selected_contact_id()
        chosen = next((record for record in records if record.contact_id == selected_id), None)
        self.contact_selected_key = chosen.email_key if chosen is not None else None
        if chosen is None:
            self.mark_contact_button.state(["disabled"])
            self.clear_contact_button.state(["disabled"])
            self.contact_note_entry.state(["disabled"])
            self.delete_contact_button.state(["disabled"])
            self.contact_mark_state.set(
                "No stored contact is selected. Select a row in the list above to mark it, to clear the "
                "mark it already carries, or to delete it and the disagreements recorded about it."
            )
            return
        self.mark_contact_button.state(["disabled"] if chosen.suppressed else ["!disabled"])
        self.clear_contact_button.state(["!disabled"] if chosen.suppressed else ["disabled"])
        self.contact_note_entry.state(["disabled"] if chosen.suppressed else ["!disabled"])
        # Deleting applies to any selected record, marked or not: the mark is a reason to be careful about
        # contacting somebody, never a reason to keep their record, and this window does not decide which
        # records a person is allowed to remove from their own database.
        self.delete_contact_button.state(["!disabled"])
        position = [record.contact_id for record in records].index(chosen.contact_id) + 1
        if chosen.suppressed:
            reason = "a reason is recorded with it" if chosen.suppressed_note else "no reason is recorded with it"
            state = f"Marked do not contact, and {reason}."
        else:
            state = ("Not marked do not contact. A reason typed below is recorded with the mark when you "
                     "press the mark button.")
        self.contact_mark_state.set(
            f"Selected contact {position} of {len(records)} in the stored list: {state}")

    def _mark_selected_contact(self):
        """Mark the selected stored contact as do not contact, after one confirmation."""
        self._change_contact_mark(suppressed=True)

    def _clear_selected_contact(self):
        """Take the do-not-contact mark off the selected stored contact, after one confirmation."""
        self._change_contact_mark(suppressed=False)

    def _change_contact_mark(self, *, suppressed: bool):
        """Set or clear one stored contact's mark. Writes once, and only after the person confirms.

        The person is told which row they are acting on - its position in the list and the file it came
        from - and what the mark means. Nothing is claimed before the store call returns, and every refusal
        path leaves the stored mark untouched and says so.
        """
        try:
            records = self.store.list_contacts()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        selected_id = self._selected_contact_id()
        chosen = next((record for record in records if record.contact_id == selected_id), None)
        if chosen is None:
            if selected_id is None:
                messagebox.showinfo(
                    "Select a contact first",
                    "Select the stored contact you want to mark in the list above, then press the button "
                    "again; nothing was changed.",
                    parent=self.root,
                )
                self.status.set("Select a stored contact in the list first; nothing was changed.")
            else:
                # The row was deleted by another window, or by a restore that replaced this database: the
                # screen is showing a contact the database no longer holds, and it is not written to.
                messagebox.showinfo(
                    "That contact is no longer stored",
                    "The selected contact is no longer in this database, so nothing was changed. The list "
                    "has been refreshed; select a stored contact and try again.",
                    parent=self.root,
                )
                self.status.set("That contact is no longer stored; nothing was changed.")
                self._refresh_contacts()
            return
        if chosen.suppressed == suppressed:
            messagebox.showinfo(
                "Nothing to change",
                ("That contact is already marked do not contact; nothing was changed."
                 if suppressed else
                 "That contact does not carry a do-not-contact mark; nothing was changed."),
                parent=self.root,
            )
            self.status.set("That contact's mark is already what was asked for; nothing was changed.")
            self._refresh_contacts()
            return
        note = self.contact_note.get().strip() if suppressed else ""
        position = [record.contact_id for record in records].index(chosen.contact_id) + 1
        where = f"row {position} of {len(records)} in the stored list"
        origin = f"from {chosen.source_file!r}" if chosen.source_file else "whose source file is not recorded"
        if suppressed:
            title = "Mark this contact do not contact"
            question = (
                f"Mark {where} - the contact {origin} - as do not contact?\n\n"
                "The mark is stored in this database, travels with your backups and restores, and no "
                "import can clear it. Nothing is sent to this contact by anything in this build: the mark "
                "records your decision."
            )
            if note:
                question += "\n\nThe reason you typed is stored with the mark."
        else:
            title = "Remove this contact's do-not-contact mark"
            question = (
                f"Take the do-not-contact mark off {where} - the contact {origin}?\n\n"
                "The stored reason and the day the mark was made are removed with it, and the contact can "
                "be marked again later. Nothing is sent either way."
            )
        if not messagebox.askyesno(title, question + "\n\nDo this now?", parent=self.root):
            self.status.set("Cancelled; nothing was changed.")
            return
        try:
            stored = self.store.set_contact_suppression(chosen.email_key, suppressed, note=note or None)
        except ValueError as exc:
            # The store's own refusal, with its own sentence: the address it was asked about has no record
            # here, which is what happens when the list changed under this window. Nothing was written.
            messagebox.showerror("Nothing was changed", f"{exc}\n\nThe mark was left as it was.",
                                 parent=self.root)
            self.status.set("The do-not-contact mark was not changed; nothing was written.")
            return
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self.contact_note.set("")
        self._refresh_contacts()
        # Keep the row the person just acted on selected, so the line under the controls reads that
        # contact's new state rather than "nothing is selected" the moment the mark changed.
        self.stored_contacts_tree.selection_set(str(stored.contact_id))
        self._sync_contact_actions()
        said = "marked do not contact" if stored.suppressed else "no longer marked do not contact"
        self.status.set(f"The selected contact is now {said}; nothing was contacted.")
        messagebox.showinfo(
            "Do-not-contact mark updated",
            f"Row {position} of the stored list is now {said}.\n\n"
            + ("A later feature must respect this mark; nothing in this build contacts anybody."
               if stored.suppressed else
               "The contact stays in the list, with no reason recorded against it."),
            parent=self.root,
        )

    def _delete_selected_contact(self):
        """Delete the selected stored contact and its recorded disagreements, after one confirmation.

        The person is told which *row* they are acting on - its position in the list and the file it came
        from, the two references the mark confirmations already use - and how many disagreements go with it,
        counted from the same query the store's own deletion uses. The address, the name, the company, the
        reason a mark carries and every disagreement value stay out of the dialog: this is a question about a
        row the person is looking at, and the answer does not depend on seeing who it names.

        Every refusal path - nothing selected, a row this database no longer holds, a declined confirmation
        and a storage error - leaves the database exactly as it was and says so. The deletion itself is one
        store call, because a screen that issued the two deletes itself could leave the contact gone and its
        disagreements behind; the store owns the transaction and this handler owns only the question.
        """
        try:
            records = self.store.list_contacts()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        selected_id = self._selected_contact_id()
        chosen = next((record for record in records if record.contact_id == selected_id), None)
        if chosen is None:
            if selected_id is None:
                messagebox.showinfo(
                    "Select a contact first",
                    "Select the stored contact you want to delete in the list above, then press the button "
                    "again; nothing was deleted.",
                    parent=self.root,
                )
                self.status.set("Select a stored contact in the list first; nothing was deleted.")
            else:
                # A row another window deleted, or a database a restore replaced: the screen is showing a
                # contact the database no longer holds, and it is not deleted again from a stale row.
                messagebox.showinfo(
                    "That contact is no longer stored",
                    "The selected contact is no longer in this database, so nothing was deleted. The list "
                    "has been refreshed; select a stored contact and try again.",
                    parent=self.root,
                )
                self.status.set("That contact is no longer stored; nothing was deleted.")
                self._refresh_contacts()
            return
        position = [record.contact_id for record in records].index(chosen.contact_id) + 1
        where = f"row {position} of {len(records)} in the stored list"
        origin = f"from {chosen.source_file!r}" if chosen.source_file else "whose source file is not recorded"
        try:
            conflicts = len(self.store.list_contact_conflicts(email_key=chosen.email_key))
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if conflicts:
            goes_with = (f"{conflicts} recorded disagreement(s) about this contact - the two sides of each, "
                         "as shown below - are deleted with it")
        else:
            goes_with = "no disagreement is recorded about this contact, so nothing else goes with it"
        question = (
            f"Delete {where} - the contact {origin}?\n\n"
            f"The stored record is removed from this database, and {goes_with}. No other contact, mark or "
            "disagreement is touched.\n\n"
            "There is no undo in this application. A backup written before this still holds the record: "
            "restoring that copy would bring it back, because a restore replaces this database with the "
            "copy you choose. Nothing is sent to anybody either way."
        )
        if not messagebox.askyesno("Delete this stored contact",
                                   question + "\n\nDelete it now?", parent=self.root):
            self.status.set("Cancelled; nothing was deleted.")
            return
        try:
            outcome = self.store.delete_contact(chosen.email_key)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if not outcome.deleted:
            # The row went between the read above and the store's own check - another window, or a restore
            # that replaced this database. Nothing was deleted by this call, and that is what is reported.
            messagebox.showinfo(
                "That contact is no longer stored",
                "The selected contact was already not in this database, so nothing was deleted by this "
                "step. The list has been refreshed.",
                parent=self.root,
            )
            self.status.set("That contact was already not stored; nothing was deleted.")
            self._refresh_contacts()
            return
        # Both views read the database again here, in one call: the deleted contact's row goes, the
        # disagreements recorded about it go from the panel, and every other row stays where it was. The
        # rebuilt list holds no selection, which is the honest state after the row the person had chosen
        # stopped existing.
        self._refresh_contacts()
        self.status.set(f"{outcome.describe()}. Nothing was contacted.")
        # The report is built from the store's own outcome rather than from the count the question used: the
        # two are read at different moments, and what the person is told afterwards has to be what happened.
        if outcome.conflicts:
            removed = (f"{outcome.conflicts} recorded disagreement(s) about this contact - the two sides of "
                       "each, as shown below - were deleted with it")
        else:
            removed = "no disagreement is recorded about this contact, so nothing else went with it"
        messagebox.showinfo(
            "Contact deleted",
            f"Row {position} of the stored list is no longer in this database, and {removed}.\n\n"
            "Nothing was sent to anybody, and no other contact was touched. A backup written before this "
            "still holds the record; restoring that copy would bring it back.",
            parent=self.root,
        )

    # ------------------------------------------------------------------ the export of the stored list
    #
    # The other direction from the import above, and it keeps the same rules: everything is read from the
    # database, nothing is guessed, and the file is the person's own list rather than a backup. Three
    # things are deliberate here.
    #
    # * **The database is only read.** The export calls one read method and one store method that writes
    #   bytes to a file the person named; no statement of it changes a contact, a mark or a disagreement.
    # * **Success is claimed only for a file that was read back.** The writer compares the file's bytes
    #   with what it wrote before it returns, and every failure - a refused list, an unwritable folder, a
    #   link in the way - claims nothing and leaves the database as it was.
    # * **What the file is not is said where it is made.** The sentence beside the control says the mark
    #   column cannot be applied by an import, in the format module's own words; a person who takes the
    #   file to another machine has to know that before they rely on it, and a sentence buried in a
    #   document is not where they will read it.

    def _export_contacts(self):
        """Write the stored contact list to a file the person names. Read-only, and never a false claim."""
        destination = filedialog.asksaveasfilename(
            parent=self.root, title="Export the stored contact list", defaultextension=".csv",
            filetypes=[("Contact list (CSV)", "*.csv"), ("All files", "*.*")])
        if not destination:
            # A closed or cancelled dialog is not a failure and not a success: nothing was written and
            # nothing is said, exactly as the JSON export behaves when its dialog is dismissed.
            return
        dest_path = Path(destination)
        if dest_path.exists() and not messagebox.askyesno(
            "Replace the existing file?",
            f"{dest_path.name} already exists in the folder you chose.\n\n"
            "Replacing it writes a new contact export over it: whatever that file holds now is gone, and "
            "there is no undo in this application. Choose No and name another file to keep it.\n\n"
            "Replace it?",
            parent=self.root,
        ):
            self.status.set("Export cancelled; the existing file was left as it was.")
            return
        try:
            outcome = contact_export.write_export(self.store, dest_path)
        except contact_export.ContactExportRefused as exc:
            # A list this application could not read back: the sentence says what to use instead, and the
            # database - and the folder - are exactly as they were.
            messagebox.showerror("Nothing was exported", str(exc), parent=self.root)
            self.status.set("Contact export not written: the list is larger than the format reads back.")
            self._record("contacts.export.failed", "reason=the list is larger than the format's own limit")
            return
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            self.status.set("Contact export not written (a stored record could not be read).")
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        except PrivateWriteError as exc:
            # The writer's own refusal (the file could not be protected, or did not hold what was
            # written) already says what was left behind; the second line is the promise this window keeps.
            messagebox.showerror("Export not saved", f"{exc}\n\nNothing was saved; the database was not "
                                                     "changed.", parent=self.root)
            self.status.set("Export not saved (the file could not be written and kept).")
            self._record("contacts.export.failed", "reason=the file could not be written and kept")
            return
        except OSError as exc:
            messagebox.showerror("Export not saved", f"{exc}\n\nThe database was not changed.",
                                 parent=self.root)
            self.status.set("Export not saved (a local file error).")
            self._record("contacts.export.failed", f"reason={type(exc).__name__}")
            return
        # Counts only, and only after the file was read back: an event never carries an address, a name, a
        # company, a mark's reason or the name of the file the person chose.
        self._record("contacts.exported", f"contacts={outcome.contacts} marked={outcome.marked}")
        if outcome.contacts:
            self.status.set(f"Exported {outcome.contacts} contact(s) to a file you chose. Nothing was "
                            "contacted.")
        else:
            self.status.set("The contact export holds no rows: nothing is stored here yet.")
        messagebox.showinfo(
            "Contact list exported",
            f"{outcome.describe()}\n\n"
            "It holds the address, the name, the company label and the do-not-contact column of each "
            "stored contact, and nothing else: no reason for a mark, no recorded disagreement and no "
            "internal identifier.\n\n"
            f"{contact_export.MARK_COLUMN_LIMITATION}\n\n"
            "Nothing was sent to anybody, and the database was not changed.",
            parent=self.root,
        )

    # ------------------------------------------------------------------ recorded disagreements
    #
    # Disagreements are the evidence behind "nothing is merged silently", and until now only the count of
    # them was visible. This panel reads what the store already recorded and shows both sides of each one:
    #
    # * **Nothing here chooses.** The record keeps the value it already had, and the panel says so in those
    #   words rather than describing one side as right. There is no merge, no dismissal, no edit and no
    #   per-contact change on this screen, and the three assertions that matter - zero database writes, an
    #   unchanged do-not-contact mark, and no contact value in a log, a dialog or a status line - are what
    #   the tests are built around.
    # * **Provenance is shown where the schema has it, and nowhere else.** The conflict row records the
    #   file the disagreeing value arrived in and when the disagreement was seen. For a disagreement between
    #   two rows of one file that is the whole story. For a file against the stored record, the schema does
    #   *not* record which file supplied the stored value, and the panel says that instead of inventing it:
    #   the stored contact's own "first seen" file is a different fact and is not used as if it were this one.

    def _on_tab_changed(self, _event=None) -> None:
        """Re-read the contacts tab when it is shown. Read-only, and silent about every other tab.

        A person who leaves the tab open while a script imports into the same database, or who restores a
        backup from another tab, would otherwise be reading a screen that no longer describes their records.
        This is the same read the tab's own **Refresh** button performs, and it never opens a dialog.
        """
        try:
            shown = self.tabs.select()
            is_contacts = (shown == self.contacts_tab
                           or self.tabs.tab(shown, "text") == "HR contacts")
        except Exception:  # noqa: BLE001 - a notebook that cannot answer is not a reason to fail a switch
            return
        if is_contacts:
            self._refresh_contacts()

    def _refresh_contact_conflicts(self) -> None:
        """Re-read every recorded disagreement and redraw the panel. Read-only, and never a dialog."""
        try:
            conflicts = self.store.list_contact_conflicts()
            # One read of the stored contacts, so a row names its address the way the stored list does -
            # the text the person's own file wrote - instead of a second spelling of the same person.
            stored = {record.email_key: record for record in self.store.list_contacts()}
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._clear_tree(self.contact_conflicts_tree)
        for position, conflict in enumerate(conflicts[:_CONFLICT_ROWS_SHOWN], start=1):
            record = stored.get(conflict.email_key)
            reference = record.email if record is not None else conflict.email_key
            self.contact_conflicts_tree.insert(
                "", END, iid=str(conflict.conflict_id),
                values=(position, reference, conflict.field,
                        _conflict_origins(conflict.origin),
                        _conflict_cell(conflict.source_file), _conflict_cell(conflict.observed_at)))
        self.contact_conflicts_shown = min(len(conflicts), _CONFLICT_ROWS_SHOWN)
        self.contact_conflict_note.set(_conflict_list_note(len(conflicts)))
        # Everything the previous view was pointing at is gone from the list, so it is re-read rather than
        # described with what the screen last held.
        self.contact_conflict_selected_id = self._selected_conflict_id()
        self._show_selected_conflict()

    def _selected_conflict_id(self) -> int | None:
        """The stored disagreement id behind the selected row, or ``None`` when nothing usable is selected.

        Only an id that is still in the list counts: after a refresh the tree holds the rows that exist
        now, and a selection Tk dropped is the same thing as no selection at all.
        """
        tree = getattr(self, "contact_conflicts_tree", None)
        if tree is None:
            return None
        selection = tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except (TypeError, ValueError):
            return None

    def _on_conflict_selection(self, _event=None) -> None:
        """Describe the newly selected disagreement. Writes nothing and asks nothing."""
        self.contact_conflict_selected_id = self._selected_conflict_id()
        self._show_selected_conflict()

    def _show_selected_conflict(self) -> None:
        """Draw the selected disagreement's two sides, or say why there is nothing to draw."""
        chosen_id = self.contact_conflict_selected_id
        if chosen_id is None:
            lines = [self._no_conflict_selected_text()]
        else:
            try:
                conflict = next((item for item in self.store.list_contact_conflicts()
                                 if item.conflict_id == chosen_id), None)
            except StoredRecordError as exc:
                self._report_unreadable_record(exc)
                return
            except sqlite3.Error as exc:
                self._report_database_unavailable(exc)
                return
            if conflict is None:
                lines = [
                    "The disagreement this panel was showing is no longer recorded in this database, so "
                    "there is nothing to compare. The list above was refreshed: select a row to read one.",
                ]
            else:
                lines = _describe_conflict(conflict)
        self.contact_conflict_text.configure(state="normal")
        self.contact_conflict_text.delete("1.0", END)
        self.contact_conflict_text.insert("1.0", "\n".join(lines))
        self.contact_conflict_text.configure(state="disabled")
        # Deliberately no status line: like every other selection handler in this window, reading a row is
        # not an action and makes no claim. The status line is also this application's channel to the
        # activity log, and which disagreement a person is reading is not something to write there.

    def _no_conflict_selected_text(self) -> str:
        return ("No disagreement is selected. Select a row in the list above to read both sides of it; "
                "nothing on this screen changes what is stored.")

    @staticmethod
    def _clear_tree(tree) -> None:
        """Empty a list before refilling it, so it can never show a row the database no longer holds."""
        for item in tree.get_children():
            tree.delete(item)

    def _build_data_safety(self):
        ttk.Label(
            self.data_tab,
            text="Local only: no account, no cloud service, and no network access. Keep backups on storage you control.",
            wraplength=_TAB_TEXT_WRAP,
        ).grid(row=0, column=0, sticky=W, pady=(0, 8))
        ttk.Button(self.data_tab, text="Back up database", command=self._backup_database).grid(row=1, column=0, sticky=W, pady=4)
        ttk.Button(self.data_tab, text="Restore from backup", command=self._restore_database).grid(row=2, column=0, sticky=W, pady=4)
        ttk.Button(self.data_tab, text="Import an exported file (JSON)", command=self._import_data).grid(row=3, column=0, sticky=W, pady=4)
        ttk.Label(
            self.data_tab,
            text=(
                "Importing reads a JSON file this app exported, shows you what it would do, and only "
                "writes after you agree. It never replaces a listing or profile you already have: an "
                "entry that is already stored wins, an application record the file holds at a later "
                "status is imported without that status (with the reason shown), and a file that is not "
                "a valid export is refused before anything is read."
            ),
            wraplength=_TAB_TEXT_WRAP,
        ).grid(row=4, column=0, sticky=W, pady=(10, 0))
        ttk.Label(
            self.data_tab,
            text=(
                "A backup is one SQLite file holding the profile, listings and tracker history. It is "
                "written owner-only where the file system supports POSIX permissions, and the app reads it "
                "back and verifies it before reporting success. It is not encrypted, and a synced or shared "
                "folder can still expose it. Restoring validates the chosen file, copies the current "
                "database aside first, replaces the database in one step, then reopens and verifies it."
            ),
            wraplength=_TAB_TEXT_WRAP,
        ).grid(row=5, column=0, sticky=W, pady=(10, 0))

    # ------------------------------------------------------------------ background tasks
    #
    # The window is the control panel for the schedule; it is deliberately not the scheduler. Running a
    # task loop on the interface's thread would freeze the window for as long as a handler took, and a
    # person closing the window would then be closing a worker mid-attempt. The worker runs in its own
    # process (`python -m career_agent --worker`), and this tab shows what that process is doing and
    # lets the person change what is scheduled - reading the same tables the worker reads, through the
    # same module, so the two cannot disagree about what is due.

    def _build_scheduler(self):
        """The tab about what runs by itself: the labels, the controls and two lists of what it has done.

        Its content is taller than the smallest page this window can be given - two six-row lists of scheduled
        tasks and of recent attempts, each with its own heading, do not fit under the controls on a small
        screen - so it is built inside the same scrolling body the Work history and study tab uses. Measured
        by the display-backed harness on run 38820361412 (2026-10-16), before this existed: at the window's own
        minimum size the Tasks tree reached 65 pixels below the tab on Linux and Windows, and 38 pixels below
        it on macOS, where the notebook's page is shorter still. Content below the fold is drawn outside the
        tab and, with nothing to scroll, could not be reached at all.
        """
        body = self._scrollable_body(self.scheduler_tab)
        ttk.Label(
            body,
            text=(
                "Scheduled tasks run while the worker is running: python -m career_agent --worker "
                "(Ctrl-C stops it). Nothing here runs while the worker is stopped, and nothing runs "
                "while the computer is off or asleep. Every task runs locally; the source-quality gate "
                "is closed, so a scheduled discovery run is recorded as a refusal and fetches nothing."
            ),
            wraplength=_TAB_TEXT_WRAP, justify=LEFT,
        ).grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 8))
        self.scheduler_summary = tk.StringVar(value="Checking the schedule...")
        ttk.Label(body, textvariable=self.scheduler_summary, wraplength=_TAB_TEXT_WRAP,
                  justify=LEFT).grid(row=1, column=0, columnspan=4, sticky=W, pady=(0, 8))
        ttk.Button(body, text="Add the default tasks",
                   command=self._add_default_tasks).grid(row=2, column=0, sticky=W, pady=4)
        ttk.Button(body, text="Enable or disable the selected task",
                   command=self._toggle_scheduled_task).grid(row=2, column=1, sticky=W, padx=(8, 0), pady=4)
        ttk.Button(body, text="Refresh",
                   command=self._refresh_scheduler).grid(row=2, column=2, sticky=W, padx=(8, 0), pady=4)
        ttk.Label(body, text="Tasks").grid(row=3, column=0, columnspan=4, sticky=W, pady=(10, 2))
        task_columns = ("task", "name", "kind", "times", "zone", "next", "last")
        self.tasks_tree = ttk.Treeview(body, columns=task_columns, show="headings", height=6)
        for column, heading, width in (
            ("task", "Task", 150), ("name", "What it is", 190), ("kind", "Kind", 140),
            ("times", "Runs at", 110), ("zone", "Zone", 120), ("next", "Next run (local)", 190),
            ("last", "Last result", 200),
        ):
            self.tasks_tree.heading(column, text=heading)
            self.tasks_tree.column(column, width=width, anchor=W)
        self.tasks_tree.grid(row=4, column=0, columnspan=4, sticky="nsew")
        ttk.Label(body, text="Recent attempts").grid(row=5, column=0, columnspan=4,
                                                                  sticky=W, pady=(10, 2))
        run_columns = ("task", "attempt", "outcome", "when", "took", "note")
        self.task_runs_tree = ttk.Treeview(body, columns=run_columns, show="headings",
                                          height=6)
        for column, heading, width in (
            ("task", "Task", 150), ("attempt", "Attempt", 70), ("outcome", "Outcome", 110),
            ("when", "Scheduled for (local)", 190), ("took", "Took", 80), ("note", "What happened", 400),
        ):
            self.task_runs_tree.heading(column, text=heading)
            self.task_runs_tree.column(column, width=width, anchor=W)
        self.task_runs_tree.grid(row=6, column=0, columnspan=4, sticky="nsew")
        body.columnconfigure(0, weight=1)

    def _build_history(self):
        """The employment and study records behind the profile's summary fields.

        Two forms, two lists, on their own tab rather than inside the profile form: these are the records a
        person edits and reorders over years, and the profile form's ten fields are the summary they keep in
        mind. The buttons say what they do to the *selected row*, and a row has to be selected before an edit
        or a deletion can happen at all.
        """
        body = self._scrollable_body(self.history_tab)
        ttk.Label(
            body, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=("Your own record, in the order a CV reads: the current role first, then the most recent. "
                  "These are notes you keep, not verified facts, and nothing here is checked against any "
                  "employer or document. Blank fields stay unknown rather than being guessed."),
        ).pack(anchor=W, pady=(0, 8))

        work_form = ttk.LabelFrame(body, text="Employment", padding=8)
        work_form.pack(fill=X, pady=(0, 8))
        # The two field columns take the slack and absorb a shortfall, so a narrow window shortens the
        # fields instead of pushing them past the tab's right edge.
        work_form.columnconfigure(1, weight=1)
        work_form.columnconfigure(3, weight=1)
        self.work_vars = {}
        self._history_entry(work_form, "Employer", "employer", 0, 0, self.work_vars)
        self._history_entry(work_form, "Job title", "job_title", 0, 1, self.work_vars)
        self._history_entry(work_form, "Start date (YYYY-MM-DD)", "start_date", 1, 0, self.work_vars)
        self._history_entry(work_form, "End date (blank if not recorded)", "end_date", 1, 1, self.work_vars)
        ttk.Label(work_form, text="Employment type").grid(row=2, column=0, sticky=W, pady=4)
        self.work_type = tk.StringVar(value=EmploymentType.UNKNOWN.value)
        ttk.Combobox(work_form, textvariable=self.work_type, state="readonly", width=22,
                     values=[kind.value for kind in EmploymentType]).grid(row=2, column=1, sticky=W, pady=4)
        self.work_current = tk.BooleanVar(value=False)
        ttk.Checkbutton(work_form, text="This is my current role", variable=self.work_current
                        ).grid(row=2, column=2, columnspan=2, sticky=W, padx=(12, 0), pady=4)
        ttk.Label(work_form, text="What you did (optional)").grid(row=3, column=0, sticky=W, pady=4)
        self.work_vars["summary"] = tk.StringVar()
        ttk.Entry(work_form, textvariable=self.work_vars["summary"], width=70).grid(
            row=3, column=1, columnspan=3, sticky=W, pady=4)
        work_actions = ttk.Frame(work_form)
        work_actions.grid(row=4, column=0, columnspan=4, sticky=W, pady=(8, 0))
        # Two rows rather than one: four buttons whose labels each say what they do to the selected row
        # ask for more width than the tab has, and Tk squeezes whichever one comes last to whatever is
        # left - a control a person cannot read. Measured on the Linux leg of run 38814625351: on the Next
        # actions tab, a 200-pixel label was drawn in a 29-pixel button at the size the window opens with,
        # and the six-button rows there and on the Follow-ups tab were split for the same reason.
        work_row_one = ttk.Frame(work_actions)
        work_row_one.pack(anchor=W)
        work_row_two = ttk.Frame(work_actions)
        work_row_two.pack(anchor=W, pady=(4, 0))
        ttk.Button(work_row_one, text="Add this role", command=self._add_work_history).pack(side="left",
                                                                                           padx=(0, 8))
        ttk.Button(work_row_one, text="Save changes to the selected role",
                   command=self._update_work_history).pack(side="left", padx=8)
        ttk.Button(work_row_two, text="Select the selected role for editing", command=self._load_work_history
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(work_row_two, text="Delete the selected role", command=self._delete_work_history
                   ).pack(side="left", padx=8)
        self.work_tree = ttk.Treeview(work_form, columns=("employer", "title", "type", "period", "current"),
                                      show="headings", height=5)
        for column, label, width in (("employer", "Employer", 190), ("title", "Job title", 190),
                                     ("type", "Type", 110), ("period", "Period", 210),
                                     ("current", "Current", 70)):
            self.work_tree.heading(column, text=label)
            self.work_tree.column(column, width=width, anchor=W)
        self.work_tree.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.work_tree.bind("<<TreeviewSelect>>", self._select_work_history)

        study_form = ttk.LabelFrame(body, text="Education", padding=8)
        study_form.pack(fill=X)
        study_form.columnconfigure(1, weight=1)
        study_form.columnconfigure(3, weight=1)
        self.study_vars = {}
        self._history_entry(study_form, "Institution", "institution", 0, 0, self.study_vars)
        self._history_entry(study_form, "Qualification", "qualification", 0, 1, self.study_vars)
        self._history_entry(study_form, "Discipline (optional)", "discipline", 1, 0, self.study_vars)
        self._history_entry(study_form, "Start date (optional)", "start_date", 1, 1, self.study_vars)
        self._history_entry(study_form, "Completion date (optional)", "completion_date", 2, 0, self.study_vars)
        self.study_ongoing = tk.BooleanVar(value=False)
        ttk.Checkbutton(study_form, text="Still studying", variable=self.study_ongoing
                        ).grid(row=2, column=2, columnspan=2, sticky=W, padx=(12, 0), pady=4)
        study_actions = ttk.Frame(study_form)
        study_actions.grid(row=3, column=0, columnspan=4, sticky=W, pady=(8, 0))
        study_row_one = ttk.Frame(study_actions)
        study_row_one.pack(anchor=W)
        study_row_two = ttk.Frame(study_actions)
        study_row_two.pack(anchor=W, pady=(4, 0))
        ttk.Button(study_row_one, text="Add this qualification", command=self._add_education
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(study_row_one, text="Save changes to the selected qualification",
                   command=self._update_education).pack(side="left", padx=8)
        ttk.Button(study_row_two, text="Select the selected qualification for editing",
                   command=self._load_education).pack(side="left", padx=(0, 8))
        ttk.Button(study_row_two, text="Delete the selected qualification", command=self._delete_education
                   ).pack(side="left", padx=8)
        self.study_tree = ttk.Treeview(study_form, columns=("institution", "qualification", "discipline",
                                                            "period", "ongoing"),
                                       show="headings", height=5)
        for column, label, width in (("institution", "Institution", 190),
                                     ("qualification", "Qualification", 190),
                                     ("discipline", "Discipline", 130), ("period", "Period", 210),
                                     ("ongoing", "Ongoing", 70)):
            self.study_tree.heading(column, text=label)
            self.study_tree.column(column, width=width, anchor=W)
        self.study_tree.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self.study_tree.bind("<<TreeviewSelect>>", self._select_education)

        self.history_summary = tk.StringVar()
        ttk.Label(body, textvariable=self.history_summary, wraplength=_TAB_TEXT_WRAP,
                  justify="left").pack(anchor=W, pady=(8, 0))
        ttk.Label(
            body, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=("Deleting the saved profile deletes these records too, in one step, because they are the "
                  "detail behind it - the confirmation names how many. Nothing here is uploaded, and no "
                  "employer is contacted about any of it."),
        ).pack(anchor=W, pady=(4, 0))

    def _history_entry(self, parent, label, key, row, col, variables):
        """One labelled text field on the history tab, kept in the same variables dict its form uses."""
        label_padx = (0, 6) if col == 0 else (12, 6)
        field_padx = (0, 0) if col == 0 else (0, 12)
        ttk.Label(parent, text=label).grid(row=row, column=col * 2, sticky=W, padx=label_padx, pady=4)
        variable = tk.StringVar()
        variables[key] = variable
        ttk.Entry(parent, textvariable=variable, width=30).grid(
            row=row, column=col * 2 + 1, sticky=W, padx=field_padx, pady=4)
        return variable

    def _work_form_values(self) -> dict:
        return {key: variable.get() for key, variable in self.work_vars.items()}

    def _study_form_values(self) -> dict:
        return {key: variable.get() for key, variable in self.study_vars.items()}

    def _history_day(self, raw: str, *, label: str, optional: bool) -> date | None:
        """A day typed into one of these forms, or a refusal the person can act on.

        The shape is checked before parsing, like every other date field in this window: ``fromisoformat``
        also accepts basic-format and ISO week dates, and a field that promises ``YYYY-MM-DD`` should not
        quietly accept three other spellings.
        """
        text = (raw or "").strip()
        if not text:
            if optional:
                return None
            raise ValueError(f"Give the {label} as YYYY-MM-DD.")
        if ACTIVITY_DATE_PATTERN.fullmatch(text) is None:
            raise ValueError(f"Give the {label} as YYYY-MM-DD, for example {date.today().isoformat()}.")
        return date.fromisoformat(text)

    def _selected_tree_id(self, tree, *, what: str) -> int | None:
        """The integer record id behind the selected row, or ``None`` after explaining how to select one."""
        selection = tree.selection() if tree is not None else ()
        if not selection:
            messagebox.showinfo(f"Select a row first",
                               f"Select the {what} you want to work on in the list, then press the button "
                               "again.", parent=self.root)
            return None
        try:
            return int(selection[0])
        except (TypeError, ValueError):
            messagebox.showinfo("That row cannot be used",
                               "The selected row is not one of your saved records. Refresh the tab and "
                               "try again.", parent=self.root)
            return None

    def _refresh_history(self):
        """Rebuild both lists and the one-line summary. Read-only: nothing here writes."""
        if not hasattr(self, "work_tree"):
            return
        try:
            roles = self.store.list_work_history()
            study = self.store.list_education()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        for tree, rows, values in (
            (self.work_tree, roles, lambda row: (row.employer, row.job_title, row.employment_type_label,
                                                 row.period, "yes" if row.is_current else "")),
            (self.study_tree, study, lambda row: (row.institution, row.qualification, row.discipline or "",
                                                  row.period, "yes" if row.is_ongoing else "")),
        ):
            for item in tree.get_children():
                tree.delete(item)
            for row in rows:
                tree.insert("", END, iid=str(row.entry_id), values=values(row))
        self.history_summary.set(self._history_summary_line(roles, study))

    def _history_summary_line(self, roles, study) -> str:
        """What these records add up to, stated as a duration of periods rather than years of experience.

        Deliberately not a single "years of experience" number: a role can have no recorded end, and two
        roles can run at once, so a sum of job durations would produce a figure that looks authoritative
        and is not. The line reports the months *covered* by roles that are current or fully dated
        (overlaps counted once), says how many records it could not count, and is never written back into
        the profile - which keeps its own figure that the person controls.
        """
        today = datetime.now().date()
        counted = months_covered_by(roles, today=today)
        unknown = sum(1 for row in roles if row.end_date is None and not row.is_current)
        parts = []
        if not roles and not study:
            return ("No employment or education records yet. Both forms above save to this local database "
                    "only.")
        if roles:
            parts.append(f"{len(roles)} employment record(s)")
        if study:
            parts.append(f"{len(study)} education record(s)")
        line = " · ".join(parts) + ". "
        if counted:
            line += (f"Together they cover {counted} month(s) of recorded employment, counting overlaps "
                     "once each and not a claim about experience. ")
        if unknown:
            line += (f"{unknown} ended role(s) have no end date recorded, so no duration is counted for "
                     "them. ")
        line += "Your profile's own experience field is unchanged by this tab."
        return line

    def _select_work_history(self, _event=None):
        """Put the selected role's own values in the form, so an edit starts from what is stored."""
        if not self.work_tree.selection():
            return
        self._load_work_history(quiet=True)

    def _select_education(self, _event=None):
        if not self.study_tree.selection():
            return
        self._load_education(quiet=True)

    def _load_work_history(self, *, quiet: bool = False):
        """Fill the employment form from the stored row the list has selected."""
        entry_id = self._selected_tree_id(self.work_tree, what="role") if not quiet else (
            int(self.work_tree.selection()[0]) if self.work_tree.selection() else None)
        if entry_id is None:
            return
        try:
            entry = self.store.get_work_history(entry_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if entry is None:
            messagebox.showinfo("That record is gone", "Refresh the tab and try again.", parent=self.root)
            return
        values = {"employer": entry.employer, "job_title": entry.job_title,
                  "start_date": entry.start_date.isoformat(),
                  "end_date": entry.end_date.isoformat() if entry.end_date else "",
                  "summary": entry.summary or ""}
        for key, value in values.items():
            self.work_vars[key].set(value)
        self.work_type.set(entry.employment_type.value)
        self.work_current.set(entry.is_current)
        if not quiet:
            self.status.set(f"Loaded {entry.job_title} at {entry.employer} into the form. Change what you "
                            "need, then press Save changes to the selected role.")

    def _load_education(self, *, quiet: bool = False):
        """Fill the education form from the stored row the list has selected."""
        selection = self.study_tree.selection()
        if not selection:
            if not quiet:
                self._selected_tree_id(self.study_tree, what="qualification")
            return
        entry_id = int(selection[0])
        try:
            entry = self.store.get_education(entry_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if entry is None:
            messagebox.showinfo("That record is gone", "Refresh the tab and try again.", parent=self.root)
            return
        values = {"institution": entry.institution, "qualification": entry.qualification,
                  "discipline": entry.discipline or "",
                  "start_date": entry.start_date.isoformat() if entry.start_date else "",
                  "completion_date": entry.completion_date.isoformat() if entry.completion_date else ""}
        for key, value in values.items():
            self.study_vars[key].set(value)
        self.study_ongoing.set(entry.is_ongoing)
        if not quiet:
            self.status.set(f"Loaded {entry.label} at {entry.institution} into the form. Change what you "
                            "need, then press Save changes to the selected qualification.")

    def _add_work_history(self):
        """Add the role described by the form, with the domain's validation reported as typed."""
        values = self._work_form_values()
        try:
            started = self._history_day(values.get("start_date", ""), label="start date", optional=False)
            ended = self._history_day(values.get("end_date", ""), label="end date", optional=True)
            added = self.store.add_work_history(
                values.get("employer", ""), values.get("job_title", ""), started, end_date=ended,
                is_current=bool(self.work_current.get()), employment_type=self.work_type.get(),
                summary=values.get("summary") or None)
        except ValueError as exc:
            messagebox.showerror("Role not saved", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_history()
        self.status.set(f"Employment record added: {added.job_title} at {added.employer} ({added.period}).")

    def _update_work_history(self):
        """Save the form's values over the selected role, keeping the rest of the record as it was."""
        entry_id = self._selected_tree_id(self.work_tree, what="role")
        if entry_id is None:
            return
        values = self._work_form_values()
        try:
            started = self._history_day(values.get("start_date", ""), label="start date", optional=False)
            ended = self._history_day(values.get("end_date", ""), label="end date", optional=True)
            updated = self.store.update_work_history(
                entry_id, values.get("employer", ""), values.get("job_title", ""), started, end_date=ended,
                is_current=bool(self.work_current.get()), employment_type=self.work_type.get(),
                summary=values.get("summary") or None)
        except ValueError as exc:
            messagebox.showerror("Role not updated", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_history()
        self.status.set(f"Employment record {updated.entry_id} saved: {updated.job_title} at "
                        f"{updated.employer} ({updated.period}).")

    def _delete_work_history(self):
        """Delete the selected role, after asking, and say what was actually removed."""
        entry_id = self._selected_tree_id(self.work_tree, what="role")
        if entry_id is None:
            return
        if not messagebox.askyesno(
                "Delete this role?",
                "The employment record will be removed from this database and cannot be brought back. "
                "Your profile, your applications and your other records are not changed.",
                parent=self.root):
            return
        try:
            removed = self.store.delete_work_history(entry_id)
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_history()
        self.status.set("Employment record deleted." if removed
                        else "That employment record was already gone; nothing was deleted.")

    def _add_education(self):
        """Add the qualification described by the form."""
        values = self._study_form_values()
        try:
            started = self._history_day(values.get("start_date", ""), label="start date", optional=True)
            completed = self._history_day(values.get("completion_date", ""), label="completion date",
                                          optional=True)
            added = self.store.add_education(
                values.get("institution", ""), values.get("qualification", ""),
                discipline=values.get("discipline") or None, start_date=started,
                completion_date=completed, is_ongoing=bool(self.study_ongoing.get()))
        except ValueError as exc:
            messagebox.showerror("Qualification not saved", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_history()
        self.status.set(f"Education record added: {added.label} at {added.institution} ({added.period}).")

    def _update_education(self):
        """Save the form's values over the selected qualification."""
        entry_id = self._selected_tree_id(self.study_tree, what="qualification")
        if entry_id is None:
            return
        values = self._study_form_values()
        try:
            started = self._history_day(values.get("start_date", ""), label="start date", optional=True)
            completed = self._history_day(values.get("completion_date", ""), label="completion date",
                                          optional=True)
            updated = self.store.update_education(
                entry_id, values.get("institution", ""), values.get("qualification", ""),
                discipline=values.get("discipline") or None, start_date=started,
                completion_date=completed, is_ongoing=bool(self.study_ongoing.get()))
        except ValueError as exc:
            messagebox.showerror("Qualification not updated", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_history()
        self.status.set(f"Education record {updated.entry_id} saved: {updated.label} at "
                        f"{updated.institution} ({updated.period}).")

    def _delete_education(self):
        """Delete the selected qualification, after asking."""
        entry_id = self._selected_tree_id(self.study_tree, what="qualification")
        if entry_id is None:
            return
        if not messagebox.askyesno(
                "Delete this qualification?",
                "The education record will be removed from this database and cannot be brought back. Your "
                "profile, your applications and your other records are not changed.",
                parent=self.root):
            return
        try:
            removed = self.store.delete_education(entry_id)
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_history()
        self.status.set("Education record deleted." if removed
                        else "That education record was already gone; nothing was deleted.")

    def _build_actions(self):
        """The page that answers "what now?": every open item across applications, ordered.

        One list, because the three things a person can have to do - face a round, chase an answer, finish a
        preparation item - are only separable in a data model, never at a desk. The rows carry the buttons
        that apply to them: a preparation item can be ticked off, a round can be recorded, and a follow-up
        day is changed on its own tab, which the row says rather than offering a button that would not work.
        """
        controls = ttk.Frame(self.actions_tab)
        controls.pack(fill=X, pady=(0, 8))
        # Six buttons on one line do not fit: at the size this window opens with the last one was drawn
        # 29 pixels wide instead of the 200 its label asked for (run 38814625351, Linux leg), which is a
        # label nobody can read. Two rows of three, so the widest label is not the one that pays.
        controls_row_one = ttk.Frame(controls)
        controls_row_one.pack(anchor=W)
        controls_row_two = ttk.Frame(controls)
        controls_row_two.pack(anchor=W, pady=(4, 0))
        ttk.Button(controls_row_one, text="Refresh", command=self._refresh_actions).pack(side="left",
                                                                                         padx=(0, 8))
        ttk.Button(controls_row_one, text="Add a preparation item", command=self._add_preparation
                   ).pack(side="left", padx=8)
        ttk.Button(controls_row_one, text="Record an interview round", command=self._record_interview_round
                   ).pack(side="left", padx=8)
        ttk.Button(controls_row_two, text="Mark the selected item done", command=self._complete_preparation
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(controls_row_two, text="Record the selected round's outcome", command=self._set_round_outcome
                   ).pack(side="left", padx=8)
        ttk.Button(controls_row_two, text="Delete the selected record", command=self._delete_action_record
                   ).pack(side="left", padx=8)
        ttk.Label(
            self.actions_tab, wraplength=_TAB_TEXT_WRAP, justify=LEFT,
            text=("Everything here is a plan you wrote: a preparation item, a round you recorded, or a "
                  "follow-up day. None of it changes an application's status, and no record here is an "
                  "employer's decision - only you move an application on, and only with your own evidence."),
        ).pack(anchor=W, pady=(0, 8))
        self.actions_summary = tk.StringVar()
        ttk.Label(self.actions_tab, textvariable=self.actions_summary, wraplength=_TAB_TEXT_WRAP,
                  justify="left").pack(anchor=W, pady=(0, 8))
        columns = ("when", "what", "application", "detail")
        self.actions_tree = ttk.Treeview(self.actions_tab, columns=columns, show="headings", height=12)
        for column, label, width in (("when", "When", 190), ("what", "What", 320),
                                     ("application", "Application", 260), ("detail", "Your note", 320)):
            self.actions_tree.heading(column, text=label)
            self.actions_tree.column(column, width=width, anchor=W)
        self.actions_tree.pack(fill=BOTH, expand=True)
        self.actions_tab.columnconfigure(0, weight=1)

    def _action_rows(self):
        """Read the three record kinds and return the rows this tab shows, or ``None`` on a read failure."""
        try:
            jobs = {job.listing_id: job for job in self.store.list_jobs()}
            preparation_items = self.store.list_preparation()
            rounds = self.store.list_interviews()
            pairs = [(tracker, jobs.get(tracker.listing_id))
                     for tracker in self.store.list_follow_up_trackers()]
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return None
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return None
        today = datetime.now().date()
        reminders_found = reminders([(tracker, job) for tracker, job in pairs if job is not None], today)
        shown = next_actions(preparation_items, rounds, reminders_found, jobs, today,
                             include_later=False, include_undated=True)
        everything = next_actions(preparation_items, rounds, reminders_found, jobs, today,
                                  include_later=True, include_undated=True)
        return jobs, preparation_items, rounds, shown, everything, today

    def _refresh_actions(self):
        """Rebuild the list. Read-only: nothing here writes, moves a status, or records anything."""
        if not hasattr(self, "actions_tree"):
            return
        rows = self._action_rows()
        if rows is None:
            return
        jobs, preparation_items, rounds, shown, everything, today = rows
        self.actions_summary.set(
            actions_summary(shown, today) + f"  {preparation_summary(preparation_items, today)}"
            f"  {interview_summary(rounds, today)}"
        )
        for item in self.actions_tree.get_children():
            self.actions_tree.delete(item)
        for index, action in enumerate(shown):
            identifier = self._action_row_id(action, today)
            self.actions_tree.insert(
                "", END, iid=identifier,
                values=(self._action_when(action), action.what,
                        f"{action.role_title} at {action.employer_name}", action.detail or ""),
            )
        self._shown_action_count = len(shown)
        later = len(everything) - len(shown)
        self._later_action_count = later

    @staticmethod
    def _action_when(action) -> str:
        """The day as the person reads it: a date, and how far away it is."""
        if action.on is None:
            return "No day set"
        if action.days_away is None:
            return action.on.isoformat()
        if action.days_away == 0:
            return f"{action.on.isoformat()} (today)"
        if action.days_away < 0:
            return f"{action.on.isoformat()} ({abs(action.days_away)} day(s) overdue)"
        return f"{action.on.isoformat()} (in {action.days_away} day(s))"

    @staticmethod
    def _action_row_id(action, today) -> str:
        """A row id that names *which record* the row is about, so a button knows what it acts on.

        A preparation item and an interview round are identified by their own ids; a follow-up row is
        identified by its listing, because that is the record it belongs to.
        """
        if action.record_id is None:
            return f"follow-up:{action.listing_id}"
        prefix = "preparation" if action.kind is ActionKind.PREPARATION else "interview"
        return f"{prefix}:{action.record_id}"

    def _selected_action(self) -> tuple[str, int | str] | None:
        """The selected row as ``(kind, identifier)``, or ``None`` when nothing usable is selected."""
        if not hasattr(self, "actions_tree"):
            return None
        selection = self.actions_tree.selection()
        if not selection:
            messagebox.showinfo("Select something first",
                               "Select the row you want to act on.", parent=self.root)
            return None
        raw = str(selection[0])
        kind, _, identifier = raw.partition(":")
        if not identifier:
            return None
        return kind, identifier

    def _selected_job_id(self) -> str | None:
        """The listing a new record should belong to: the selected job or tracker row, if any."""
        for tree_name in ("jobs_tree", "tracker_tree"):
            tree = getattr(self, tree_name, None)
            if tree is None:
                continue
            try:
                selection = tree.selection()
            except Exception:  # noqa: BLE001 - a stub tree in a test may not implement selection()
                continue
            if selection:
                return str(selection[0])
        return None

    def _require_selected_job(self, title: str) -> str | None:
        """The listing to attach a new record to, or ``None`` after explaining how to choose one."""
        listing_id = self._selected_job_id()
        if listing_id is None:
            messagebox.showinfo(
                title,
                "Select the application this belongs to first: choose its row on the Jobs or "
                "Application tracker tab, then press this button again.",
                parent=self.root,
            )
            return None
        try:
            job = self.store.get_job(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return None
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return None
        if job is None:
            messagebox.showinfo(title, "That listing is no longer saved. Refresh the window.",
                                parent=self.root)
            return None
        return listing_id

    def _add_preparation(self):
        """Add one preparation item to the selected application, with an optional day."""
        listing_id = self._require_selected_job("Add a preparation item")
        if listing_id is None:
            return
        try:
            job = self.store.get_job(listing_id)
        except (StoredRecordError, sqlite3.Error):
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Add a preparation item")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        assert job is not None
        ttk.Label(dialog, text=f"{job.employer_name} — {job.role_title}", wraplength=460).pack(
            anchor=W, padx=12, pady=(12, 6))
        ttk.Label(dialog, text="What needs doing").pack(anchor=W, padx=12)
        title_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=title_var, width=48).pack(fill=X, padx=12, pady=4)
        ttk.Label(dialog, text="What kind of work it is").pack(anchor=W, padx=12, pady=(8, 0))
        kind_var = tk.StringVar(value=PreparationKind.TAILORING.value)
        ttk.Combobox(dialog, textvariable=kind_var, state="readonly", width=30,
                     values=[kind.value for kind in PreparationKind]).pack(anchor=W, padx=12, pady=4)
        ttk.Label(dialog, text="Day to do it (YYYY-MM-DD, optional)").pack(anchor=W, padx=12, pady=(8, 0))
        day_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=day_var, width=20).pack(anchor=W, padx=12, pady=4)
        ttk.Label(
            dialog, wraplength=440, justify=LEFT,
            text=("A checklist item is a plan. Ticking it off records that you did the work; it never "
                  "changes the application's status and it is not evidence that anything was sent."),
        ).pack(anchor=W, padx=12, pady=(6, 0))

        def apply():
            raw_day = day_var.get().strip()
            try:
                due_on = None
                if raw_day:
                    if ACTIVITY_DATE_PATTERN.fullmatch(raw_day) is None:
                        raise ValueError(f"Give the day as YYYY-MM-DD, for example "
                                         f"{datetime.now().date().isoformat()}, or leave it empty.")
                    due_on = date.fromisoformat(raw_day)
                added = self.store.add_preparation(listing_id, title_var.get(), kind=kind_var.get(),
                                                   due_on=due_on)
            except ValueError as exc:
                messagebox.showerror("Preparation item not saved", str(exc), parent=dialog)
                return
            except StoredRecordError as exc:
                self._report_unreadable_record(exc)
                return
            except sqlite3.Error as exc:
                self._report_database_unavailable(exc)
                return
            dialog.destroy()
            self._refresh_actions()
            when = f" for {added.due_on.isoformat()}" if added.due_on else " with no day set"
            self.status.set(f"Preparation item added{when}: {added.title}. No status was changed.")

        dialog.bind("<Return>", lambda _event: apply())
        ttk.Button(dialog, text="Add it", command=apply).pack(anchor="e", padx=12, pady=12)

    def _record_interview_round(self):
        """Record one round of an employer's process for the selected application."""
        listing_id = self._require_selected_job("Record an interview round")
        if listing_id is None:
            return
        try:
            job = self.store.get_job(listing_id)
        except (StoredRecordError, sqlite3.Error):
            return
        assert job is not None
        dialog = tk.Toplevel(self.root)
        dialog.title("Record an interview round")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        ttk.Label(dialog, text=f"{job.employer_name} — {job.role_title}", wraplength=460).pack(
            anchor=W, padx=12, pady=(12, 6))
        ttk.Label(dialog, text="Which round").pack(anchor=W, padx=12)
        stage_var = tk.StringVar(value=InterviewStage.SCREENING.value)
        ttk.Combobox(dialog, textvariable=stage_var, state="readonly", width=30,
                     values=[stage.value for stage in InterviewStage]).pack(anchor=W, padx=12, pady=4)
        ttk.Label(dialog, text="Day it is planned for (YYYY-MM-DD)").pack(anchor=W, padx=12, pady=(8, 0))
        day_var = tk.StringVar(value=datetime.now().date().isoformat())
        ttk.Entry(dialog, textvariable=day_var, width=20).pack(anchor=W, padx=12, pady=4)
        ttk.Label(dialog, text="How it is being held").pack(anchor=W, padx=12, pady=(8, 0))
        mode_var = tk.StringVar(value=InterviewMode.UNKNOWN.value)
        ttk.Combobox(dialog, textvariable=mode_var, state="readonly", width=30,
                     values=[mode.value for mode in InterviewMode]).pack(anchor=W, padx=12, pady=4)
        ttk.Label(dialog, text="Notes for the next round (optional)").pack(anchor=W, padx=12, pady=(8, 0))
        notes_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=notes_var, width=48).pack(fill=X, padx=12, pady=4)
        ttk.Label(
            dialog, wraplength=440, justify=LEFT,
            text=("This is your own record: a round you have been invited to, and what you want to "
                  "remember. It does not confirm anything with the employer, and the application's "
                  "status stays where you put it."),
        ).pack(anchor=W, padx=12, pady=(6, 0))

        def apply():
            raw_day = day_var.get().strip()
            try:
                if ACTIVITY_DATE_PATTERN.fullmatch(raw_day) is None:
                    raise ValueError("Give the day the round is planned for as YYYY-MM-DD.")
                recorded = self.store.record_interview(
                    listing_id, stage_var.get(), date.fromisoformat(raw_day), mode=mode_var.get(),
                    notes=notes_var.get() or None)
            except ValueError as exc:
                messagebox.showerror("Interview round not saved", str(exc), parent=dialog)
                return
            except StoredRecordError as exc:
                self._report_unreadable_record(exc)
                return
            except sqlite3.Error as exc:
                self._report_database_unavailable(exc)
                return
            dialog.destroy()
            self._refresh_actions()
            self.status.set(f"Recorded: {recorded.stage_label} on {recorded.scheduled_on.isoformat()}. "
                            "How it went is yours to fill in afterwards; no status was changed.")

        dialog.bind("<Return>", lambda _event: apply())
        ttk.Button(dialog, text="Record it", command=apply).pack(anchor="e", padx=12, pady=12)

    def _complete_preparation(self):
        """Tick off the selected preparation item."""
        selection = self._selected_action()
        if selection is None:
            return
        kind, identifier = selection
        if kind != "preparation":
            messagebox.showinfo(
                "That row is not a preparation item",
                "Only a preparation item can be ticked off. For a round, record how it went; for a "
                "follow-up day, use the Follow-ups tab.",
                parent=self.root,
            )
            return
        try:
            updated = self.store.complete_preparation(int(identifier))
        except ValueError as exc:
            messagebox.showinfo("Nothing was changed", str(exc), parent=self.root)
            return
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_actions()
        self.status.set(f"Done: {updated.title}. The application's status was not changed.")

    def _set_round_outcome(self):
        """Record how a round went, in the person's own words."""
        selection = self._selected_action()
        if selection is None:
            return
        kind, identifier = selection
        if kind != "interview":
            messagebox.showinfo(
                "That row is not an interview round",
                "Only a recorded round has an outcome to fill in. Use the Follow-ups tab for a "
                "follow-up day, or tick off a preparation item.",
                parent=self.root,
            )
            return
        try:
            current = self.store.get_interview(int(identifier))
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if current is None:
            messagebox.showinfo("That record is gone", "Refresh the window and try again.", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("How did the round go?")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        ttk.Label(dialog, text=f"{current.stage_label} on {current.scheduled_on.isoformat()}",
                  wraplength=460).pack(anchor=W, padx=12, pady=(12, 6))
        ttk.Label(dialog, text="Your reading of it").pack(anchor=W, padx=12)
        outcome_var = tk.StringVar(value=current.outcome.value)
        ttk.Combobox(dialog, textvariable=outcome_var, state="readonly", width=40,
                     values=[outcome.value for outcome in InterviewOutcome]).pack(anchor=W, padx=12, pady=4)
        ttk.Label(dialog, text="Notes for next time (leave empty to keep what is there)").pack(
            anchor=W, padx=12, pady=(8, 0))
        notes_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=notes_var, width=48).pack(fill=X, padx=12, pady=4)
        ttk.Label(
            dialog, wraplength=440, justify=LEFT,
            text=("These words are yours. There is deliberately no value for 'passed' or 'rejected': "
                  "the application cannot know an employer's decision, and an offer or a rejection is "
                  "recorded as an activity entry and a status change you make yourself."),
        ).pack(anchor=W, padx=12, pady=(6, 0))

        def apply():
            try:
                updated = self.store.set_interview_outcome(
                    int(identifier), outcome_var.get(), notes=notes_var.get() or None)
            except ValueError as exc:
                messagebox.showerror("Outcome not saved", str(exc), parent=dialog)
                return
            except StoredRecordError as exc:
                self._report_unreadable_record(exc)
                return
            except sqlite3.Error as exc:
                self._report_database_unavailable(exc)
                return
            dialog.destroy()
            self._refresh_actions()
            self.status.set(f"Recorded for {updated.stage_label} on "
                            f"{updated.scheduled_on.isoformat()}: {updated.outcome_label}. "
                            "No status was changed.")

        dialog.bind("<Return>", lambda _event: apply())
        ttk.Button(dialog, text="Save it", command=apply).pack(anchor="e", padx=12, pady=12)

    def _delete_action_record(self):
        """Delete the selected preparation item or interview round, after asking."""
        selection = self._selected_action()
        if selection is None:
            return
        kind, identifier = selection
        if kind == "follow-up":
            messagebox.showinfo(
                "Follow-up days are cleared, not deleted",
                "A follow-up day belongs to the application record. Clear it on the Follow-ups tab, "
                "which leaves the application, its status and its history untouched.",
                parent=self.root,
            )
            return
        label = "preparation item" if kind == "preparation" else "interview round"
        if not messagebox.askyesno(
                f"Delete this {label}?",
                f"The {label} will be removed and cannot be brought back. The application, its status, "
                "its history and the other records stay exactly as they are.",
                parent=self.root):
            return
        try:
            if kind == "preparation":
                removed = self.store.delete_preparation(int(identifier))
            else:
                removed = self.store.delete_interview(int(identifier))
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_actions()
        if removed:
            self.status.set(f"The {label} was deleted; the application itself was not changed.")
        else:
            # Saying it was deleted when the row was already gone would be a claim the database
            # contradicts, so the message says what actually happened.
            self.status.set(f"That {label} was already gone; nothing was deleted.")

    def _build_follow_ups(self):
        """The reminders tab: the days already recorded, and the two actions that change them.

        Kept deliberately small. A follow-up is one day and one line of note, so the tab shows the list,
        the day picker and the note field, and nothing else pretends to be a project-management tool.
        """
        actions = ttk.Frame(self.follow_up_tab)
        actions.pack(fill=X, pady=(0, 8))
        # Same reason as the Next actions tab: six labels on one line ask for more than the window has,
        # and the measurement showed "Export to a calendar file" squeezed to 13 pixels at the opening size.
        actions_row_one = ttk.Frame(actions)
        actions_row_one.pack(anchor=W)
        actions_row_two = ttk.Frame(actions)
        actions_row_two.pack(anchor=W, pady=(4, 0))
        ttk.Button(actions_row_one, text="Refresh", command=self._refresh_follow_ups).pack(side="left",
                                                                                           padx=(0, 8))
        ttk.Button(actions_row_one, text="Set the day for the selected application",
                   command=self._set_follow_up).pack(side="left", padx=8)
        ttk.Button(actions_row_one, text="Clear the selected follow-up",
                   command=self._clear_follow_up).pack(side="left", padx=8)
        ttk.Button(actions_row_two, text="Preview the calendar export",
                   command=self._preview_calendar_export).pack(side="left", padx=(0, 8))
        ttk.Button(actions_row_two, text="Draft a follow-up email",
                   command=self._draft_follow_up_email).pack(side="left", padx=8)
        ttk.Button(actions_row_two, text="Export to a calendar file",
                   command=self._export_follow_ups).pack(side="left", padx=8)
        ttk.Label(
            self.follow_up_tab, wraplength=_TAB_TEXT_WRAP,
            text=("A follow-up is a day you plan to act on, not a status: setting one never moves the "
                  "application, and nothing here contacts anybody. The daily reminder task reads this "
                  "list and reports it in the run history; the calendar export writes a file on this "
                  "machine for your own calendar. A draft written here is text in this window - it "
                  "cannot be sent, because no email account is connected and none can be enabled in "
                  "this build."),
        ).pack(anchor=W, pady=(0, 8))
        entry = ttk.Frame(self.follow_up_tab)
        entry.pack(fill=X, pady=(0, 8))
        ttk.Label(entry, text="Day (YYYY-MM-DD)").pack(side="left")
        self.follow_up_day = tk.StringVar()
        ttk.Entry(entry, textvariable=self.follow_up_day, width=14).pack(side="left", padx=(4, 12))
        ttk.Label(entry, text="Note (optional)").pack(side="left")
        self.follow_up_note = tk.StringVar()
        ttk.Entry(entry, textvariable=self.follow_up_note, width=48).pack(side="left", padx=4)
        self.follow_up_summary = tk.StringVar()
        ttk.Label(self.follow_up_tab, textvariable=self.follow_up_summary, wraplength=_TAB_TEXT_WRAP,
                  justify="left").pack(anchor=W, pady=(0, 8))
        columns = ("employer", "role", "status", "day", "when", "note")
        self.follow_up_tree = ttk.Treeview(self.follow_up_tab, columns=columns, show="headings", height=10)
        for column, label, width in (("employer", "Employer", 170), ("role", "Role", 200),
                                     ("status", "Application status", 170), ("day", "Follow-up day", 120),
                                     ("when", "When", 120), ("note", "Your note", 320)):
            self.follow_up_tree.heading(column, text=label)
            self.follow_up_tree.column(column, width=width, anchor=W)
        self.follow_up_tree.pack(fill=BOTH, expand=True)
        self.follow_up_tree.bind("<<TreeviewSelect>>", self._select_follow_up)
        self.follow_up_tab.columnconfigure(0, weight=1)

    def _selected_reminder_id(self) -> str | None:
        """The listing id of the row selected on this tab, or ``None`` when no row is selected."""
        if not hasattr(self, "follow_up_tree"):
            return None
        selection = self.follow_up_tree.selection()
        return str(selection[0]) if selection else None

    def _selected_follow_up_id(self) -> str | None:
        """The listing id the day and note fields act on, or ``None`` when nothing is selected.

        A reminder row comes first, because a row on this tab is what the tab is about. Failing that,
        the application selected on the Application tracker or Jobs tab is used, and that fallback is
        what makes the first reminder recordable at all: this list is built from the applications that
        already hold a day, so before the fallback existed the tab could only ever change a reminder
        that some other means had recorded - and no other means exists in this application, which left
        the first follow-up day unsettable from anywhere in the product.
        """
        return self._selected_reminder_id() or self._selected_job_id()

    def _fill_follow_up_fields(self, listing_id: str | None) -> None:
        """Put one application's recorded day and note in the fields, so editing starts from the truth.

        A record with no day, or no record at all, empties both fields: leaving the previous
        application's day standing would let a note written for one application be saved onto another.
        """
        if not hasattr(self, "follow_up_day"):
            return
        tracker = None
        if listing_id is not None:
            try:
                tracker = self.store.get_tracker(listing_id)
            except StoredRecordError as exc:
                self._report_unreadable_record(exc)
                return
            except sqlite3.Error as exc:
                self._report_database_unavailable(exc)
                return
        if tracker is None or tracker.follow_up_on is None:
            self.follow_up_day.set("")
            self.follow_up_note.set("")
            return
        self.follow_up_day.set(tracker.follow_up_on.isoformat())
        self.follow_up_note.set(tracker.follow_up_note or "")

    def _select_follow_up(self, _event=None):
        """Put the selected reminder's own day and note in the fields, so editing starts from the truth.

        Only a row on this tab fills the fields. This runs whenever the list is rebuilt as well as when a
        row is chosen, and a rebuild leaves no row selected: filling the fields from the application
        selected on another tab then would put an unrelated application's day on screen - and, after a
        reminder is cleared, would read as though the clear had not happened.
        """
        listing_id = self._selected_reminder_id()
        if listing_id is None:
            return
        self._fill_follow_up_fields(listing_id)

    def _refresh_follow_ups(self):
        """Re-read the reminders; change nothing.

        The rows come from the store's own follow-up read, so a record whose day cannot be read is
        reported rather than silently missing from a list whose whole purpose is not to forget things.
        """
        if not hasattr(self, "follow_up_tree"):
            return
        try:
            trackers = self.store.list_follow_up_trackers()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        try:
            pairs = [(tracker, self.store.get_job(tracker.listing_id)) for tracker in trackers]
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        today = datetime.now().date()
        complete = [(tracker, job) for tracker, job in pairs if job is not None]
        found = reminders(complete, today)
        self.follow_up_summary.set(summary(found))
        for item in self.follow_up_tree.get_children():
            self.follow_up_tree.delete(item)
        for reminder in found:
            self.follow_up_tree.insert(
                "", END, iid=reminder.listing_id,
                values=(reminder.employer_name, reminder.role_title,
                        reminder.status.value if reminder.status else "unknown",
                        reminder.on.isoformat(),
                        self._follow_up_when(reminder), reminder.note or ""),
            )
        missing = len(trackers) - len(complete)
        if missing:
            self.follow_up_summary.set(
                f"{summary(found)} {missing} record(s) have a day but no stored listing any more; "
                "they are not listed here.")

    def _follow_up_when(self, reminder) -> str:
        """How far away a reminder's day is, in words, from the day this window is being used."""
        return {
            FollowUpState.OVERDUE: f"{abs(reminder.days_away)} day(s) overdue",
            FollowUpState.DUE_TODAY: "due today",
            FollowUpState.UPCOMING: f"in {reminder.days_away} day(s)",
            FollowUpState.LATER: f"in {reminder.days_away} day(s)",
            FollowUpState.NONE: "no day recorded",
        }[reminder.state]

    def _set_follow_up(self):
        """Record the day and note in the fields against the selected application."""
        listing_id = self._selected_follow_up_id()
        if not listing_id:
            messagebox.showinfo(
                "Select an application",
                "Select the application this follow-up belongs to first: a row on the Application "
                "tracker tab, a saved job on the Jobs tab, or a reminder row on this tab.",
                parent=self.root)
            return
        try:
            day = date.fromisoformat(self.follow_up_day.get().strip())
        except ValueError:
            messagebox.showinfo("Give the day",
                               "Write the day as YYYY-MM-DD, for example 2026-10-20.", parent=self.root)
            return
        try:
            tracker = self.store.get_tracker(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if tracker is None:
            self._report_stale_selection(listing_id)
            return
        try:
            # One call sets the day and the note on the stored row; the status is not part of this write
            # at all, so a reminder can never be mistaken for a status change.
            updated = self.store.set_follow_up(listing_id, day, note=self.follow_up_note.get())
        except ValueError as exc:
            messagebox.showinfo("Follow-up not saved", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_follow_ups()
        self.status.set(f"Follow-up set for {updated.follow_up_on.isoformat()}; "
                        f"the application's status was not changed ({updated.status.value}).")

    def _clear_follow_up(self):
        """Remove the selected application's follow-up, after asking, keeping the application itself."""
        listing_id = self._selected_follow_up_id()
        if not listing_id:
            messagebox.showinfo(
                "Select an application",
                "Select the follow-up you want to clear first: a reminder row here, or the application "
                "on the Application tracker tab.", parent=self.root)
            return
        if not messagebox.askyesno(
                "Clear this follow-up?",
                "The day and the note will be removed. The application, its status and its history stay "
                "exactly as they are.", parent=self.root):
            return
        try:
            tracker = self.store.get_tracker(listing_id)
            if tracker is None:
                self._report_stale_selection(listing_id)
                return
            self.store.clear_follow_up(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self.follow_up_day.set("")
        self.follow_up_note.set("")
        self._refresh_follow_ups()
        self.status.set("Follow-up cleared; the application itself was not changed.")

    def _export_follow_ups(self):
        """Write the recorded follow-ups to a calendar file the person chooses."""
        try:
            trackers = self.store.list_follow_up_trackers()
            pairs = [(tracker, self.store.get_job(tracker.listing_id)) for tracker in trackers]
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        today = datetime.now().date()
        found = reminders([(tracker, job) for tracker, job in pairs if job is not None], today)
        if not found:
            messagebox.showinfo("Nothing to export",
                               "No follow-up days are recorded yet, so there is nothing to put in a "
                               "calendar.", parent=self.root)
            return
        chosen = filedialog.asksaveasfilename(
            parent=self.root, title="Save follow-up reminders", defaultextension=".ics",
            initialfile=calendar_file_name(today), filetypes=[("Calendar file", "*.ics"), ("All files", "*.*")])
        if not chosen:
            return
        target = Path(chosen)
        if target.exists() and not messagebox.askyesno(
                "Replace this file?",
                f"{target.name} already exists. Replace it with the reminders from this window?",
                parent=self.root):
            return
        try:
            written = write_private_text_file(target, to_calendar(found, now=datetime.now(timezone.utc)))
        except (PrivateWriteError, OSError) as exc:
            messagebox.showerror("Calendar file not written",
                                 f"{exc}\n\nNothing was written, and no reminder was changed.",
                                 parent=self.root)
            return
        self.status.set(f"Wrote {len(found)} reminder(s) to {written}; nothing was sent anywhere.")

    def _preview_calendar_export(self):
        """Show which events the calendar export would write, without writing anything.

        The working calendar path in this application is a local ``.ics`` file, so this is the preview of
        something that already exists rather than of an integration that does not. It uses the same reminder
        list and the same follow-up functions the export uses, so it cannot describe a different event from
        the one the file would hold.
        """
        try:
            trackers = self.store.list_follow_up_trackers()
            pairs = [(tracker, self.store.get_job(tracker.listing_id)) for tracker in trackers]
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        today = datetime.now().date()
        found = reminders([(tracker, job) for tracker, job in pairs if job is not None], today)
        if not found:
            messagebox.showinfo(
                "Nothing to preview",
                "No follow-up days are recorded, so there would be nothing to put in a calendar.",
                parent=self.root)
            return
        plan = integrations.calendar_export_plan(found)
        scrolled = self._open_read_only_dialog(
            title="Calendar export preview (read-only)",
            heading=f"What the calendar file would contain, for {today.isoformat()} (this machine's day)",
            intro=("This is the local export, not an account: it is a file on this machine that you import "
                   "into whatever calendar you already use. Nothing has been written yet, and no invitation "
                   "is involved."),
        )
        self._add_read_only_lines(scrolled, plan.describe())
        self._add_read_only_lines(scrolled, (
            "",
            "To write it: 'Export to a calendar file' on this tab.",
            "Each event is an all-day entry on the day you recorded, with your own note and no attendee.",
        ))
        self.status.set(f"Calendar export previewed: {len(plan.events)} event(s) would be written; "
                        "nothing has been written yet.")

    def _draft_follow_up_email(self):
        """Write a follow-up email draft for the selected reminder, in this window, for reading only.

        The draft comes from what is already recorded - employer, role, the day you chose, your note - and
        from nothing else. It carries no recipient, because no address is stored anywhere in this
        application and guessing one would send a private message to a stranger; there is also nothing that
        could send it, since no email integration is enabled in this build.
        """
        listing_id = self._selected_follow_up_id()
        if not listing_id:
            messagebox.showinfo("Select an application",
                               "Select the reminder this draft is about first.", parent=self.root)
            return
        try:
            tracker = self.store.get_tracker(listing_id)
            job = self.store.get_job(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if tracker is None:
            self._report_stale_selection(listing_id)
            return
        if job is None or tracker.follow_up_on is None:
            messagebox.showinfo(
                "Nothing to draft from",
                "This application has no follow-up day recorded, so there is no follow-up to write about. "
                "Set the day on this tab first.",
                parent=self.root)
            return
        today = datetime.now().date()
        draft = integrations.draft_for_follow_up(reminder_for(tracker, job, today))
        integration = integrations.default_integration()
        preview = integrations.preview_email(draft, integration=integration, listing=job)
        scrolled = self._open_read_only_dialog(
            title="Follow-up email draft (read-only, nothing is sent)",
            heading=f"Draft for {job.role_title} at {job.employer_name}",
            intro=("This is text in a window. No email account is connected, no integration is enabled, and "
                   "nothing here can send anything - the draft is yours to read, copy out, or ignore."),
        )
        self._add_read_only_lines(scrolled, preview.describe())
        self._add_read_only_lines(scrolled, ("", "The draft in full:"))
        for line in integrations.draft_as_text(draft).rstrip("\n").splitlines():
            ttk.Label(scrolled, text=line, wraplength=830, justify="left").pack(anchor=W)
        self.status.set("Draft written in this window only: nothing was sent, and no email account is "
                        "connected.")

    def _refresh_scheduler(self):
        """Re-read the schedule and the run history; change nothing.

        The same reads the worker uses, so this view cannot show a schedule that the worker would not
        act on. A row whose stored text this version cannot read is reported as that record rather than
        dropped from the list, and a database this process cannot read at all is reported by the shared
        handler, which leaves the lists as they are.
        """
        if not hasattr(self, "tasks_tree"):
            return
        try:
            status = worker_status(self.store)
            tasks = self.store.list_scheduled_tasks()
            runs = self.store.list_task_runs(limit=25)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self.scheduler_summary.set("\n".join(status.describe()))
        for tree in (self.tasks_tree, self.task_runs_tree):
            for item in tree.get_children():
                tree.delete(item)
        for task in tasks:
            self.tasks_tree.insert(
                "", END, iid=task.task_id,
                values=(
                    task.task_id, task.name, task.kind, ", ".join(task.times), task.timezone,
                    self._local_instant(task.next_run_at) if task.enabled else "paused",
                    task.last_outcome.value if task.last_outcome else "never run",
                ),
            )
        for run in runs:
            self.task_runs_tree.insert(
                "", END, iid=run.run_id,
                values=(
                    run.task_id, str(run.attempt), run.state.value,
                    self._local_instant(run.slot_at),
                    f"{run.duration_seconds:.1f}s" if run.duration_seconds is not None else "-",
                    run.error or run.detail or "-",
                ),
            )

    def _local_instant(self, moment):
        """A stored instant in this machine's local time, because that is when the person sees it run.

        The schedule is stored in UTC with the task's own zone kept beside it; showing local time is a
        display choice, and the zone column says which clock the task was configured in.
        """
        if moment is None:
            return "-"
        return moment.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _add_default_tasks(self):
        """Add the default schedule, reporting exactly what was created and what was left alone."""
        try:
            outcome = seed_default_tasks(self.store)
            self._refresh_scheduler()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        except ValueError as exc:
            # A task definition this build refuses (an unavailable timezone, for example) is a message,
            # not a traceback from a button.
            messagebox.showerror("Default tasks not added", str(exc), parent=self.root)
            self.status.set("The default tasks were not added; nothing was changed.")
            return
        created = ", ".join(outcome.created) if outcome.created else "nothing"
        kept = ", ".join(outcome.kept) if outcome.kept else "nothing"
        self.status.set(f"Default tasks: created {created}; left {kept} as they were.")
        messagebox.showinfo(
            "Default tasks",
            f"Created: {created}.\nLeft exactly as they were: {kept}.\n\n"
            "A task that already existed is never rewritten, so times you chose and tasks you paused "
            "stay as you set them.\n\nThe schedule runs while the worker is running:\n"
            "python -m career_agent --worker",
            parent=self.root,
        )

    def _selected_scheduled_task_id(self):
        """The task id selected in the list, or ``None`` when nothing is selected.

        Deliberately does no database lookup: whether the selected task still exists is the caller's
        question, and it needs a different message. Folding the two cases together here is what made the
        first version report "select a task first" to somebody who had selected one that had been
        removed from the schedule - a message about the wrong problem.
        """
        if not hasattr(self, "tasks_tree"):
            return None
        selection = self.tasks_tree.selection()
        return selection[0] if selection else None

    def _toggle_scheduled_task(self):
        """Pause or resume the selected task, with a confirmation, then show the result.

        Pausing is not deleting: the definition, the run history and the time it runs at all stay in the
        database, and choosing to resume it schedules the next occurrence from now rather than replaying
        the ones that were missed while it was paused.
        """
        task_id = self._selected_scheduled_task_id()
        if task_id is None:
            self.status.set("Select a task in the list first; nothing was changed.")
            return
        task = self.store.get_scheduled_task(task_id)
        if task is None:  # re-checked: the list may have changed since the selection was read
            self.status.set("That task is no longer in the schedule; nothing was changed.")
            self._refresh_scheduler()
            return
        if task.enabled:
            if not messagebox.askyesno(
                "Pause this task",
                f"Pause {task.task_id} ({task.name})?\n\nIt stays in the schedule with its history; "
                "no occurrence will run until you resume it.",
                parent=self.root,
            ):
                self.status.set("Pause cancelled; nothing was changed.")
                return
        try:
            stored = self.store.save_scheduled_task(task.with_definition(enabled=not task.enabled))
            self._refresh_scheduler()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        except ValueError as exc:
            messagebox.showerror("Task not changed", str(exc), parent=self.root)
            self.status.set("The task was not changed.")
            return
        if stored.enabled:
            when = self._local_instant(stored.next_run_at)
            self.status.set(f"{stored.task_id} is enabled; its next run is {when} local time.")
        else:
            self.status.set(f"{stored.task_id} is paused; no occurrence will run until it is resumed.")

    def _backup_database(self):
        destination = filedialog.asksaveasfilename(
            parent=self.root, title="Back up local database", initialfile=suggested_backup_name(),
            defaultextension=BACKUP_SUFFIX,
            filetypes=[("SQLite database", "*.sqlite3"), ("All files", "*.*")],
        )
        if not destination:
            self.status.set("Backup cancelled; nothing was written.")
            return
        try:
            info = create_backup(self.db_path, destination)
        except BackupError as exc:
            messagebox.showerror(
                "Backup not created",
                f"{exc}\n\nThe destination was left as it was.",
                parent=self.root,
            )
            self.status.set("Backup not created; nothing was written.")
            return
        self.status.set(f"Backup verified: {info.summary()} · {destination}")
        messagebox.showinfo(
            "Backup verified",
            f"Backup written and read back successfully:\n{destination}\n\n{info.summary()}.\n\n"
            "The file is owner-only where the file system supports POSIX permissions. It is not "
            "encrypted: keep it private and store it somewhere only you can reach.",
            parent=self.root,
        )

    def _restore_database(self):
        source = filedialog.askopenfilename(
            parent=self.root, title="Choose a backup to restore",
            filetypes=[("SQLite database", "*.sqlite3"), ("All files", "*.*")],
        )
        if not source:
            self.status.set("Restore cancelled; the current database was not changed.")
            return
        try:
            info = validate_app_database(source)
        except BackupError as exc:
            messagebox.showerror(
                "Backup cannot be used",
                f"{exc}\n\nThe current database was not changed.",
                parent=self.root,
            )
            self.status.set("Restore refused; the current database was not changed.")
            return
        warning = ""
        if info.foreign_key_violations:
            warning = (
                f"\n\nNote: {info.foreign_key_violations} tracker record(s) in this backup refer to listings "
                "it does not contain, so they will not appear in the app."
            )
        if not messagebox.askyesno(
            "Replace the local database?",
            f"Restore from:\n{source}\n\nThis backup holds: {info.summary()}.{warning}\n\n"
            "Your current database is copied aside before anything is replaced, and the restore is "
            "refused if that copy cannot be made. The app then reopens and verifies the restored "
            "database. Continue?",
            parent=self.root,
        ):
            self.status.set("Restore cancelled; the current database was not changed.")
            return
        # Replacing the file cannot be coordinated with an open connection, so the app's own
        # connection is closed for the swap and reopened afterwards whatever the outcome.
        self.store.close()
        try:
            result = restore_backup(source, self.db_path)
        except BackupError as exc:
            reopened = self._reopen_store()
            messagebox.showerror(
                "Restore failed",
                f"{exc}\n\n" + ("The app has reopened the local database; the message above says what "
                                 "it holds." if reopened else
                                 "The app could not reopen the local database, so this window cannot use "
                                 "it. Restart the app once the problem is resolved."),
                parent=self.root,
            )
            self.status.set("Restore failed; see the message for what the database holds now."
                            if reopened else
                            "Restore failed and the local database could not be reopened. Restart the app.")
            return
        if not self._reopen_store():
            # The file was replaced but cannot be used. Reporting "Restore complete" here would tell
            # the person the opposite of what happened, so the success dialog is not shown at all.
            previous = (f"The database that was replaced is preserved at:\n{result.pre_restore_backup}"
                        if result.pre_restore_backup is not None
                        else "There was no previous database to preserve.")
            messagebox.showerror(
                "Restore finished, but the restored database cannot be opened",
                f"The file at {self.db_path} was replaced with a copy of:\n{source}\n\n"
                f"The app could not reopen it, so nothing in this window can read or write candidate "
                f"data. Restart the app once the problem is resolved.\n\n{previous}",
                parent=self.root,
            )
            self.status.set("Restore finished, but the restored database could not be opened. Restart the app.")
            return
        detail = f"Restored from:\n{result.restored_from}\n\nNow in use: {result.info.summary()}."
        if result.needs_schema_update:
            # The summary describes the file that was installed; the update below is what happened to
            # it when this window reopened the database, so both version numbers are accounted for.
            detail += (f"\n\nThe restored file was written by an older schema (version "
                       f"{result.info.schema_version}) and was updated to schema version "
                       f"{SCHEMA_VERSION} when it was reopened; that is recorded in the file.")
        if result.pre_restore_backup is not None:
            quality = "verified copy" if result.pre_restore_verified else "raw copy (it could not be read as a database)"
            detail += f"\n\nPrevious database kept as a {quality}:\n{result.pre_restore_backup}"
        self.status.set(f"Restored from {Path(source).name}: {result.info.summary()}.")
        messagebox.showinfo(
            "Restore complete",
            f"{detail}\n\nThe restored database was reopened and verified. Keep the previous-database "
            "copy until you have confirmed everything you need is present.",
            parent=self.root,
        )

    def _reopen_store(self) -> bool:
        """Reopen the database after a restore and resynchronise the views.

        Returns whether the database is usable. On failure the closed connection is replaced by
        :class:`~career_agent.store.UnavailableStore` rather than being left in place: leaving it made
        the next action raise ``ProgrammingError: Cannot operate on a closed database`` from a Tk
        callback (a raw traceback) or report a write failure where the real problem was that nothing
        had been opened at all.
        """
        try:
            self.store = CareerStore(self.db_path)
        except Exception as exc:  # reported, never hidden: the app cannot work without the store
            self.store = UnavailableStore(self.db_path, f"{type(exc).__name__}: {exc}")
            messagebox.showerror(
                "Database unavailable",
                f"The local database could not be reopened ({exc}). Restart the app once the problem "
                "is resolved; do not keep working in this window.",
                parent=self.root,
            )
            self.status.set("The local database could not be reopened. Restart the app.")
            return False
        self.selected_job_id = None
        self._load_profile()
        self._refresh_jobs()
        self._refresh_tracker()
        return True

    def _load_profile(self):
        try:
            profile = self.store.get_profile()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if profile:
            for key, value in profile_form_values(profile).items():
                self.profile_vars[key].set(value)
        # Read even when no profile is stored: the table's empty state is what tells a first-time person
        # there is nothing saved yet, and a table left from an earlier read would say the opposite.
        self._refresh_fact_review()

    # ---------------------------------------------------------------- the saved facts and their origins
    #
    # The profile form above says what the person entered; this table says what the database holds, **who
    # supplied each value** and whether the person has checked it. It exists because the application could
    # otherwise show a value it read out of a document exactly as it shows a value somebody typed, and
    # because a confirmation made anywhere else - by a save, an import, or a screen that merely opened -
    # would be a claim about the person that the person never made. Three rules hold this section together:
    #
    # * **The table is read from storage, never from what a handler believed it wrote.** Every write path
    #   ends in ``_refresh_fact_review``, and the confirmation below re-reads the row it acted on before it
    #   says anything succeeded.
    # * **A confirmation goes through the store's own call.** ``CareerStore.confirm_profile_fact`` is the
    #   only writer of a verification state in the whole application, and this window passes it a fact name
    #   and nothing else; no SQL is written here and no value is ever read back to decide what to confirm.
    # * **A fact with no value cannot be confirmed.** The table lists only stated facts, and the store
    #   refuses the rest, so there is no path to a confirmed fact that is not there.

    def _empty_fact_review(self, summary: str) -> None:
        """Leave the facts table empty and say why it is empty - a failed read is not an empty profile."""
        self._clear_tree(self.facts_tree)
        self.facts_summary.set(summary)
        self._sync_fact_actions()

    def _refresh_fact_review(self):
        """Redraw the facts table from storage: value, origin and confirmation state, fact by fact."""
        try:
            profile = self.store.get_profile()
            provenance = self.store.get_profile_fact_provenance()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            self._empty_fact_review("The saved profile could not be read, so it is not shown here.")
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            self._empty_fact_review("The local database could not be read, so it is not shown here.")
            return
        previously_selected = self._selected_fact_key()
        rows = profile_fact_review(profile, provenance)
        self._clear_tree(self.facts_tree)
        for row in rows:
            # The row id is the fact's canonical name, which is what the store's confirmation call takes.
            self.facts_tree.insert("", END, iid=row.fact,
                                   values=(row.label, row.value, row.origin, row.confirmation))
        self.facts_summary.set(fact_review_summary(profile, provenance))
        if previously_selected is not None and any(row.fact == previously_selected for row in rows):
            # The row the person had chosen stays chosen. Confirming a fact redraws this table, and a
            # table that drops the row under the cursor the moment it is used makes the person click the
            # same thing again to see what happened - the stored-contact list keeps its row selected for
            # the same reason.
            self.facts_tree.selection_set(previously_selected)
        self._sync_fact_actions()

    def _on_fact_selection(self, _event=None):
        """The selection changed: what the confirm control may act on is decided again from the table."""
        self._sync_fact_actions()

    def _selected_fact_key(self) -> str | None:
        """The one fact the selected row stands for, or ``None`` when the selection is not exactly one fact.

        Read from the row's own item id, which is the fact's canonical name, and returned only when that
        name is one of the profile's facts. A row id that is not a fact is never passed to the store: the
        store would refuse it, and offering a refusal as if it were a confirmation is not what this window
        is for.
        """
        selection = self.facts_tree.selection()
        if len(selection) != 1:
            return None
        fact = str(selection[0])
        return fact if fact in PROFILE_FACTS else None

    def _sync_fact_actions(self):
        """Enable the confirm control only while exactly one stored fact is selected. Writes nothing."""
        self.confirm_fact_button.configure(state="normal" if self._selected_fact_key() else "disabled")

    def _confirm_selected_fact(self):
        """Record that the person has checked one saved fact; the only confirmation path in this window.

        The control acts on the fact the selected row stands for and on nothing else. It hands the work to
        the store, then reads the row back and compares what is stored with what it was: what the window
        says afterwards is the database's answer, not the handler's intention, so a confirmation that did
        not take effect - a damaged row, a full disk, a value that is no longer stated - is reported as
        not recorded. Confirming a fact that is already confirmed says exactly that and changes nothing,
        including the time of the first confirmation.
        """
        fact = self._selected_fact_key()
        if fact is None:
            messagebox.showinfo(
                "No fact selected",
                "Select the fact you have checked in the table first. Nothing was confirmed.",
                parent=self.root)
            self.status.set("No fact was selected, so nothing was confirmed.")
            return
        label = fact_label(fact)
        try:
            before = {entry.fact: entry for entry in self.store.get_profile_fact_provenance()}
            profile = self.store.get_profile()
        except StoredRecordError as exc:
            # Nothing has been attempted yet: even the state to act on could not be read, so there is
            # nothing to report about a confirmation and nothing was written.
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            self.status.set("Nothing was confirmed; the saved facts could not be read.")
            return
        already = fact in before and before[fact].is_confirmed
        value = "" if profile is None else profile_fact_values(profile)[fact]
        try:
            self.store.confirm_profile_fact(fact)
            after = {entry.fact: entry for entry in self.store.get_profile_fact_provenance()}
            stored = self.store.get_profile()
        except ValueError as exc:
            if isinstance(exc, StoredRecordError):
                # The store reads the profile before its one transaction and again after it, and the row is
                # committed before the last of those reads - so this may be a failure *after* the person's
                # confirmation was written. The window therefore does not say nothing changed; it reads the
                # stored state and reports the database's own answer.
                self._resolve_confirmation_after_failure(fact, label, already, str(exc))
                return
            # The store's own refusal: a fact the profile does not state, or a file held at a schema older
            # than the table that keeps confirmations. Every refusal is decided before a row is written, so
            # this is the one failure that can say nothing was recorded.
            messagebox.showerror(
                "Nothing was confirmed",
                f"{exc}\n\nNothing in your saved profile was changed.", parent=self.root)
            self.status.set("Nothing was confirmed; your saved profile is unchanged.")
            self._refresh_fact_review()
            return
        except sqlite3.Error as exc:
            # A database error is not distinguishable from here either: it may have come from the read that
            # follows a committed row. Reported by reading the state back, not by claiming nothing changed.
            self._resolve_confirmation_after_failure(fact, label, already, str(exc))
            return
        self._refresh_fact_review()
        stored_value = "" if stored is None else profile_fact_values(stored)[fact]
        entry = after.get(fact)
        if entry is None or not entry.is_confirmed or stored_value != value:
            # The write did not produce the state this window would otherwise be describing, so it is
            # reported as what it is: not recorded.
            messagebox.showerror(
                "Confirmation not recorded",
                f"The database does not report {label} as confirmed after the write, so this is reported as "
                "not recorded rather than as done. Refresh the table and check what is stored before relying "
                "on it.", parent=self.root)
            self.status.set(f"The confirmation of {label} could not be confirmed; check the saved facts table.")
            return
        if already:
            self.status.set(f"{label} was already confirmed by you; nothing changed, including the time.")
        else:
            self.status.set(
                f"Confirmed: you checked {label}. Its value and where it came from are unchanged.")

    def _resolve_confirmation_after_failure(self, fact: str, label: str, already: bool,
                                            detail: str) -> None:
        """Report what the database holds after a confirmation whose own write call failed.

        ``CareerStore.confirm_profile_fact`` reads the stored profile before its one transaction and again
        after it, and the row is committed before the last of those reads. A failure raised out of that call
        may therefore have happened *before* the confirmation was written or *after* it, and the two cannot
        be told apart from here. What this window must never do is call a write that may have happened
        "nothing was changed", so it reads the stored state and reports the database's own answer: confirmed,
        not confirmed, or not known because even that read failed. The recovery is safe and the same either
        way, which is said out loud: confirming a fact that is already confirmed changes nothing, including
        the time of the first confirmation.
        """
        try:
            after = {entry.fact: entry for entry in self.store.get_profile_fact_provenance()}
        except (StoredRecordError, sqlite3.Error):
            after = None
        self._refresh_fact_review()
        if after is None:
            messagebox.showerror(
                "Confirmation not verified",
                f"The saved facts could not be read again after this attempt, so it is not known whether "
                f"{label} was recorded as confirmed. The value you confirmed is untouched either way, and "
                "confirming a fact that is already confirmed changes nothing - so confirm it again from the "
                f"table once the saved facts can be read.\n\n{detail}", parent=self.root)
            self.status.set(
                f"Not known whether {label} was confirmed: the saved facts could not be read back.")
            return
        entry = after.get(fact)
        if entry is not None and entry.is_confirmed:
            # The store raised while reading its state back, after the row had already been committed.
            if already:
                self.status.set(
                    f"{label} was already confirmed by you; nothing changed, including the time.")
            else:
                self.status.set(
                    f"Confirmed: you checked {label}. Its value and where it came from are unchanged.")
            return
        messagebox.showerror(
            "Nothing was confirmed",
            f"{label} is not confirmed in the saved profile, so nothing was confirmed: no value and no "
            "origin was changed. Try again once the saved facts can be read.\n\n" + detail,
            parent=self.root)
        self.status.set(f"Nothing was confirmed for {label}; your saved profile is unchanged.")

    # ---------------------------------------------------------------- the missing-information setup

    def _open_profile_setup(self):
        """Open the setup window: only the required facts the saved profile does not state.

        The window is filled from storage every time it is opened and after every successful save, so it
        asks for what the database does not state rather than for what the last handler believed. Nothing
        is written until its save button is pressed and its one confirmation is answered; closing it,
        pressing Cancel or pressing Escape writes nothing at all, which is why a partly answered window can
        be closed and reopened without losing what is already stored.
        """
        if self.profile_setup is not None:
            # One at a time: a second window would hold answers to questions the first one has already
            # changed, and a person would have no way to tell which of the two the database followed.
            self.profile_setup.dialog.lift()
            self.status.set("The profile setup window is already open.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Required facts your profile does not state")
        dialog.transient(self.root)
        dialog.geometry("820x640")
        dialog.minsize(560, 420)
        dialog.grab_set()
        footer = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        footer.pack(fill=X, side="bottom")
        header = ttk.Frame(dialog, padding=(12, 12, 12, 6))
        header.pack(fill=X)
        ttk.Label(header, text="Fill in only what is missing — nothing is guessed",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor=W)
        ttk.Label(
            header, wraplength=760, justify=LEFT,
            text=(
                "This window asks for the facts a listing can require and your saved profile does not "
                "state, and puts the required facts it already holds in front of you to check. Nothing is "
                "guessed from your other answers, nothing is uploaded, and a blank stays unknown."
            ),
        ).pack(anchor=W, pady=(4, 0))
        body = ttk.Frame(dialog)
        body.pack(fill=BOTH, expand=True, padx=12, pady=(0, 4))
        save_button = ttk.Button(footer, text="Save and confirm these answers",
                                 command=self._save_profile_setup)
        save_button.pack(side="right")
        ttk.Button(footer, text="Cancel", command=self._cancel_profile_setup).pack(side="right", padx=(0, 8))
        self.profile_setup = ProfileSetupWindow(
            dialog=dialog, body=self._scrollable_body(body),
            summary=tk.StringVar(value="Reading the saved profile..."), save_button=save_button)
        # The window's own close button and Escape are the same path as Cancel: nothing written, and a
        # status line that says so.
        dialog.protocol("WM_DELETE_WINDOW", self._cancel_profile_setup)
        dialog.bind("<Escape>", lambda _event: self._cancel_profile_setup())
        self._render_profile_setup()
        self.status.set("Profile setup opened: it asks only for required facts your profile does not state.")

    def _render_profile_setup(self, note: str | None = None) -> bool:
        """Fill the setup window from storage, and say whether it could be read.

        Every rebuild re-reads the profile and its origins, so the questions after a save are the facts the
        database still does not state. ``note`` is the sentence about what just happened, put in front of
        the state so the person sees both the result and what is left to do.
        """
        setup = self.profile_setup
        if setup is None:
            return False
        for child in setup.body.winfo_children():
            child.destroy()
        setup.questions = ()
        setup.awaiting = ()
        setup.answer_vars = {}
        setup.confirm_vars = {}
        try:
            profile = self.store.get_profile()
            provenance = self.store.get_profile_fact_provenance()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            self._empty_profile_setup("The saved profile could not be read, so nothing can be asked here.")
            return False
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            self._empty_profile_setup("The local database could not be read, so nothing can be asked here.")
            return False

        questions = required_fact_questions(profile)
        awaiting = required_facts_to_confirm(profile, provenance)
        setup.questions = questions
        setup.awaiting = awaiting
        if questions:
            asked = ", ".join(question.label for question in questions)
            state = (f"{len(questions)} required fact(s) are not in your saved profile: {asked}. Answer what "
                     "you know and press the button below; anything left blank stays unknown.")
        elif awaiting:
            state = ("Your saved profile states every fact a listing can require, so none of them is asked "
                     "for again. The values below are saved but not confirmed yet.")
        else:
            state = ("There is nothing to fill in here: every fact a listing can require is stated and "
                     "confirmed by you.")
        setup.summary.set((note + " " if note else "") + state)
        ttk.Label(setup.body, textvariable=setup.summary, wraplength=760,
                  justify=LEFT).pack(anchor=W, pady=(0, 8))

        for question in questions:
            row = ttk.Frame(setup.body)
            row.pack(fill=X, anchor=W, pady=(6, 0))
            ttk.Label(row, text=question.question, wraplength=740, justify=LEFT).pack(anchor=W)
            variable = tk.StringVar()
            setup.answer_vars[question.fact] = variable
            answer_row = ttk.Frame(row)
            answer_row.pack(fill=X, anchor=W, padx=(16, 0))
            chooser = (ttk.Combobox(answer_row, textvariable=variable, values=list(question.choices),
                                    width=32, state="readonly") if question.choices
                       else ttk.Entry(answer_row, textvariable=variable, width=34))
            chooser.pack(side="left")
            ttk.Label(row, text=question.hint, wraplength=740, justify=LEFT).pack(anchor=W, padx=(16, 0))

        if awaiting:
            ttk.Label(
                setup.body, wraplength=760, justify=LEFT,
                text=("Saved already, not confirmed yet. These are not asked for again — the value is "
                      "there; tick the ones you have checked, or leave them and confirm them later on the "
                      "profile tab:"),
            ).pack(anchor=W, pady=(12, 2))
        for review in awaiting:
            holder = ttk.Frame(setup.body)
            holder.pack(fill=X, anchor=W, pady=(2, 0))
            variable = tk.BooleanVar(value=False)
            setup.confirm_vars[review.fact] = variable
            ttk.Checkbutton(holder, text=f"{review.label} — {review.value}",
                            variable=variable).pack(anchor=W)
            ttk.Label(holder, text=f"{review.origin} · {review.confirmation}", wraplength=740,
                      justify=LEFT).pack(anchor=W, padx=(20, 0))

        ttk.Label(
            setup.body, wraplength=760, justify=LEFT,
            text=("Nothing here leaves this device: the answers are stored in your local database, no file "
                  "is uploaded and nothing is sent. An answer you type and save is recorded as your own "
                  "words and as confirmed by you, because you typed it and pressed the button; no document "
                  "and no import can do that."),
        ).pack(anchor=W, pady=(12, 0))
        # A window with nothing to save is greyed rather than offering a write it would refuse. The
        # existing control is reconfigured instead of rebuilt, so nothing here can stack a second button.
        setup.save_button.configure(state="normal" if (questions or awaiting) else "disabled")
        return True

    def _empty_profile_setup(self, summary: str) -> None:
        """Say in the setup window that the database could not be read, and offer nothing to save."""
        setup = self.profile_setup
        if setup is None:
            return
        setup.summary.set(summary)
        ttk.Label(setup.body, textvariable=setup.summary, wraplength=760,
                  justify=LEFT).pack(anchor=W)
        setup.save_button.configure(state="disabled")

    def _cancel_profile_setup(self):
        """Close the setup window. Nothing was written, so there is nothing to undo or report as saved."""
        setup = self.profile_setup
        self.profile_setup = None
        if setup is not None:
            setup.dialog.destroy()
        self.status.set("Profile setup closed; nothing was saved.")

    def _save_profile_setup(self):
        """Save the answers typed here, confirm what the person checked, and re-read what is still missing.

        The answers go through the same ``build_candidate_profile`` validation and the same
        ``CareerStore.save_profile`` write as the form above, so there is no second, weaker route into the
        stored profile. A save that fails changes nothing and says so; a save that succeeds is read back and
        compared before anything is claimed, and only then is a confirmation recorded - one store call per
        fact, which is idempotent, keeps each fact's original origin, and refuses a fact with no value. The
        window is rebuilt from storage afterwards, so what it asks for next is what the database still does
        not state, and a setup that is still incomplete says so instead of reporting completion.
        """
        setup = self.profile_setup
        if setup is None:
            return
        answers = {
            fact: variable.get().strip()
            for fact, variable in setup.answer_vars.items() if variable.get().strip()
        }
        checked = [fact for fact, variable in setup.confirm_vars.items() if variable.get()]
        if not answers and not checked:
            messagebox.showinfo(
                "Nothing to save",
                "No answer was typed and no saved fact was ticked, so nothing was written.",
                parent=setup.dialog)
            return
        merged = form_values(self.profile_vars)
        merged.update(answers)
        try:
            profile = build_candidate_profile(merged)
        except ValueError as exc:
            # The field that cannot be read is named; the typed answers stay on screen so nothing the person
            # wrote is lost by a refusal.
            messagebox.showerror(
                "Check these answers",
                f"{exc}\n\nNothing was saved, and the answers on this screen are as you left them.",
                parent=setup.dialog)
            return
        if answers:
            detail = "\n".join(f"• {fact_label(fact)}: {value}" for fact, value in answers.items())
            if not messagebox.askyesno(
                    "Save and confirm these answers?",
                    f"{detail}\n\nThese answers are saved as the facts they name and recorded as confirmed "
                    "by you, because you typed them here and pressed this button - no document, no import "
                    "and no other action in this app can confirm a fact. The values already in the form on "
                    "the profile tab are saved with them, as yours and left unconfirmed, so an edit made "
                    "there is not lost by saving here. A question you leave blank stays unknown. Save now?",
                    parent=setup.dialog):
                self.status.set("Profile setup: nothing was saved.")
                return
        try:
            # The facts this write recorded an origin for: the answers typed here, and any value the form
            # above held that the stored profile did not. The second set is named rather than passed over,
            # because the confirmation above has just said what this press saves.
            recorded = self.store.save_profile(profile)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except ValueError as exc:
            messagebox.showerror(
                "Not saved", f"{exc}\n\nNothing was saved; your saved profile is unchanged.",
                parent=setup.dialog)
            self.status.set("Profile setup: nothing was saved.")
            return
        except sqlite3.Error as exc:
            messagebox.showerror(
                "Profile not saved",
                "The answers could not be written to the local database. Nothing was saved; your previously "
                f"saved profile is unchanged.\n\n{exc}", parent=setup.dialog)
            self.status.set("Profile setup: nothing was saved (local database error).")
            return
        # Written, so it is read back before anything is confirmed: confirming a value that is not stored
        # would be a confirmation of nothing, and a write that cannot be read is not a save.
        try:
            stored = self.store.get_profile()
        except StoredRecordError as exc:
            self._setup_written_but_unverified(str(exc))
            return
        except sqlite3.Error as exc:
            self._setup_written_but_unverified(str(exc))
            return
        if stored is None:
            messagebox.showerror(
                "Saved, but not verified",
                "The answers were written but the saved profile could not be read back, so this is reported "
                "as unconfirmed rather than saved. Open the profile tab and check what is stored before "
                "relying on it.", parent=setup.dialog)
            self.status.set("Profile setup: written but not verified.")
            return
        # Everything this write was asked to store is verified, not only the answers typed here: the form's
        # own values go into the same `save_profile` call, and verifying a subset would let a value the
        # person never saw named be written under a "saved" that was only checked for the rest.
        mismatched = profile_fields_not_matching(stored, merged)
        if mismatched:
            labels = ", ".join(fact_label(fact) for fact in mismatched)
            messagebox.showerror(
                "Profile not saved",
                f"The stored profile does not match what this window was about to save ({labels}), so this is "
                "reported as failed rather than saved. Nothing was confirmed.", parent=setup.dialog)
            self.status.set("Profile setup: the stored profile did not match the answers.")
            self._refresh_fact_review()
            return
        written_from_the_form = [fact for fact in recorded if fact not in answers]
        confirmed, already_confirmed, failed = [], [], []
        for fact in dict.fromkeys([*answers, *checked]):
            try:
                before = next(
                    (entry for entry in self.store.get_profile_fact_provenance() if entry.fact == fact), None)
                self.store.confirm_profile_fact(fact)
            except ValueError as exc:
                if isinstance(exc, StoredRecordError):
                    # This loop runs *after* the profile has been written and read back, and the store's
                    # confirmation call reads the state again. So the shared read-failure sentence - "nothing
                    # was changed" - would be false here: the answers are saved and some checks may already
                    # be recorded. Reported as what it is instead.
                    self._setup_saved_but_unchecked(confirmed, already_confirmed, fact, str(exc),
                                                    answers_saved=bool(answers),
                                                    form_values_saved=bool(written_from_the_form))
                    return
                # The store's own refusal - a fact the profile does not state, a file held at an older
                # schema - is decided before anything is written, so this fact is simply not confirmed and
                # the value it names is still saved.
                failed.append((fact, str(exc)))
                continue
            except sqlite3.Error as exc:
                # Not distinguishable from a refusal here either: the failure may have come from the read
                # that follows a committed row. Nearly always a dead connection, so the loop stops rather
                # than reporting a list of failures that might each be untrue.
                self._setup_saved_but_unchecked(confirmed, already_confirmed, fact, str(exc),
                                                answers_saved=bool(answers),
                                                form_values_saved=bool(written_from_the_form))
                return
            (already_confirmed if before is not None and before.is_confirmed else confirmed).append(fact)
        state_read_failed = False
        try:
            current = self.store.get_profile()
        except (StoredRecordError, sqlite3.Error) as exc:
            # The answers were written and read back, but the state *after* the checks could not be read.
            # Nothing is inferred from a failed read: what is still missing is not known here, and saying
            # "all six are missing" because the profile came back as ``None`` would be a claim about a
            # database this handler could not read.
            current = None
            state_read_failed = True
            self._report(str(exc))
        if current is not None:
            for key, value in profile_form_values(current).items():
                self.profile_vars[key].set(value)
        still_missing = () if state_read_failed else missing_required_profile_facts(current)
        self._refresh_fact_review()

        note_parts = []
        if confirmed:
            note_parts.append("Saved and confirmed by you: "
                              + ", ".join(fact_label(fact) for fact in confirmed) + ".")
        if written_from_the_form:
            # Named, not passed over: this same press stored them, so a report that listed only the typed
            # answers would leave a change to the saved profile unmentioned.
            note_parts.append(
                "Saved with them from the form on the profile tab, left unconfirmed: "
                + ", ".join(fact_label(fact) for fact in written_from_the_form) + ".")
        if already_confirmed:
            note_parts.append("Already confirmed, so unchanged: "
                              + ", ".join(fact_label(fact) for fact in already_confirmed) + ".")
        if failed:
            note_parts.append("Could not be confirmed (the local database refused the write): "
                              + ", ".join(fact_label(fact) for fact, _reason in failed)
                              + ". Their values are saved; confirm them again from the table above.")
        if state_read_failed:
            note_parts.append(
                "One read of your saved facts failed after this save, so what is below was read from the "
                "database again.")
        elif still_missing:
            note_parts.append(
                "Still not stated: " + ", ".join(fact_label(fact) for fact in still_missing)
                + ". Answer them above, or leave them unknown — a listing that requires one cannot be "
                "checked until you answer it.")
        else:
            note_parts.append("Your saved profile now states every fact a listing can require.")
        rendered = self._render_profile_setup(note=" ".join(note_parts))
        if not rendered:
            # The rebuild could not read the database, so what it holds is the read failure; the result of
            # the save is still reported where a person can see it.
            self.status.set(
                f"Profile setup: saved {len(answers)} answer(s) and confirmed {len(confirmed)} fact(s), but "
                "the profile could not be read back for display.")
            return
        if state_read_failed:
            self.status.set(
                f"Profile setup: saved {len(answers)} answer(s) and confirmed {len(confirmed)} fact(s); the "
                "saved facts had to be read again to say what is still missing.")
            return
        self.status.set(
            f"Profile setup: saved {len(answers)} answer(s) and confirmed {len(confirmed)} fact(s); "
            + (f"{len(still_missing)} required fact(s) still not stated." if still_missing
               else "every fact a listing can require is stated."))

    def _setup_saved_but_unchecked(self, confirmed, already_confirmed, fact: str, detail: str,
                                  *, answers_saved: bool, form_values_saved: bool = False) -> None:
        """Report a setup save whose checks could not be finished, without claiming nothing happened.

        By the time this is reached the values have been written to the database **and** read back, so the
        save is a fact; what failed is the read that decides whether the remaining checks can be recorded.
        Which values those were is passed in rather than assumed: one press writes the answers *and* whatever
        the profile form already held, so "no answer was typed" is not the same as "nothing was written", and
        each case gets its own sentence. The person is told what was recorded, that the rest is unknown, and
        where to look - and the window is filled again from storage, which is truthful whenever the database
        answers this time.
        """
        setup = self.profile_setup
        done = []
        if confirmed:
            done.append("recorded as confirmed by you: "
                        + ", ".join(fact_label(item) for item in confirmed))
        if already_confirmed:
            done.append("already confirmed, so unchanged: "
                        + ", ".join(fact_label(item) for item in already_confirmed))
        if answers_saved and form_values_saved:
            written = ("Your answers, and the values the form on the profile tab already held, were written to "
                       "the local database and read back, so they are saved. ")
        elif answers_saved:
            written = "Your answers were written to the local database and read back, so they are saved. "
        elif form_values_saved:
            written = ("The values the form on the profile tab already held were written to the local "
                       "database and read back, so they are saved. ")
        else:
            written = "No value was typed or changed, so this press changed nothing in your profile. "
        messagebox.showerror(
            "Saved, but the rest could not be checked",
            written
            + ("; ".join(done) + ". " if done else "")
            + f"The saved facts could not be read again while recording the check for {fact_label(fact)}, so "
            "it is not known whether that check was recorded, and this window cannot say which facts are "
            "still missing. Open the profile tab and press \"Refresh the saved facts\" to see what the "
            f"database holds before relying on it.\n\n{detail}",
            parent=setup.dialog if setup is not None else self.root)
        saved_something = answers_saved or form_values_saved
        self._refresh_fact_review()
        re_rendered = self._render_profile_setup(note=(
            "The last save was written and read back; the checks after it could not all be recorded, so "
            "what is below was read from the database again." if saved_something else
            "The checks below could not all be recorded, so what is below was read from the database "
            "again."))
        if not re_rendered:
            self.status.set("Profile setup: saved, but the rest could not be checked." if saved_something
                            else "Profile setup: nothing was changed; the checks could not all be recorded.")
            return
        self.status.set("Profile setup: saved; the checks after it could not all be recorded."
                        if saved_something else
                        "Profile setup: nothing was changed; the checks could not all be recorded.")


    def _setup_written_but_unverified(self, detail: str) -> None:
        """Report a setup save that reached the database but could not be read back to verify.

        Deliberately not routed through ``_report_unreadable_record``, whose sentence is "nothing was
        changed": by the time this is reached something *was* changed, and telling the person otherwise is
        exactly the kind of claim this application does not make.
        """
        setup = self.profile_setup
        messagebox.showerror(
            "Saved, but not verified",
            "The answers were written to the local database, but the saved profile could not be read back "
            "to check them, so this is reported as unconfirmed rather than saved. Nothing was confirmed on "
            f"this screen, and the facts you answered are recorded as unconfirmed.\n\n{detail}",
            parent=setup.dialog if setup is not None else self.root)
        self.status.set("Profile setup: written but not verified.")

    def _save_profile(self):
        try:
            self.store.save_profile(build_candidate_profile(form_values(self.profile_vars)))
        except StoredRecordError as exc:
            # The profile cannot even be read back to compare against, so there is nothing this write can
            # honestly record an origin for. Reported as the unreadable record it is, like every other
            # read path on this tab, rather than as an invalid form.
            self._report_unreadable_record(exc)
            return
        except ValueError as exc:
            messagebox.showerror("Invalid profile", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            messagebox.showerror(
                "Profile not saved",
                "The profile could not be written to the local database. Nothing was changed; "
                f"your previously saved profile is unchanged.\n\n{exc}",
                parent=self.root,
            )
            self.status.set("Profile not saved (local database error).")
            return
        # The table is redrawn from storage: the facts this save changed are recorded as the person's own
        # words and **unverified**, and a screen that still showed them as they were would be the one thing
        # this tab exists to prevent.
        self._refresh_fact_review()
        self.status.set("Candidate profile saved locally.")

    def _delete_profile(self):
        """Delete the profile *and* the history records that are its detail, naming how many first.

        The counts come from the store rather than from the lists on screen, so the dialog is asking about
        what the next statement will actually delete. A person who has spent an evening entering their jobs
        deserves to be told that eleven records are going, not "the profile".
        """
        try:
            counts = self.store.profile_record_counts()
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        detail = ""
        if counts["work_history"] or counts["education"]:
            detail = (f"\n\nThis also deletes the {counts['work_history']} employment record(s) and "
                      f"{counts['education']} education record(s) on the Work history & study tab, because "
                      "they are the detail behind the profile.")
        if not messagebox.askyesno("Delete profile",
                                   "Permanently delete the saved profile on this device?"
                                   + detail + "\n\nYour job listings and applications are not deleted.",
                                   parent=self.root):
            return
        try:
            deleted = self.store.delete_profile()
        except sqlite3.Error as exc:
            messagebox.showerror("Profile not deleted", f"The saved profile could not be deleted.\n\n{exc}", parent=self.root)
            self.status.set("Profile not deleted (local database error).")
            return
        if not deleted:
            self.status.set("No saved profile was found; nothing was deleted.")
            return
        for variable in self.profile_vars.values():
            variable.set("")
        self._refresh_history()
        # Deleting the profile deletes its origins in the same transaction, so the table must be redrawn:
        # rows left behind would describe facts that no longer exist.
        self._refresh_fact_review()
        self.status.set("Saved profile deleted, along with its employment and education records.")

    def _import_resume(self):
        """Read a chosen resume locally and open the review screen. Nothing is saved here.

        The file is parsed in this process by :mod:`career_agent.resume`; no value reaches the profile
        until the person reviews the proposals and confirms, and the extracted text is discarded as
        soon as the proposals are built.
        """
        chosen = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a resume to read locally (PDF or DOCX)",
            filetypes=[("Resume (PDF or DOCX)", "*.pdf *.docx"), ("PDF", "*.pdf"), ("Word document", "*.docx")],
        )
        if not chosen:
            self.status.set("Resume import cancelled; the profile was not changed.")
            return
        try:
            result = resume.parse_resume(chosen)
        except resume.ResumeImportError as exc:
            # The message names the file and the problem, never document text or a folder on disk.
            messagebox.showerror(
                "Resume not imported",
                f"{exc}\n\nYour saved profile was not changed.",
                parent=self.root,
            )
            self.status.set("Resume not imported; the profile was not changed.")
            self._record("resume.failed", f"type={type(exc).__name__}")
            return
        except Exception as exc:  # noqa: BLE001 - defensive: a Tk callback has no handler above it
            # The reader is written to refuse every unreadable file with a ResumeImportError, so this
            # is the last line of defence against a failure shape this build does not know about. Only
            # the exception's *type* is shown: an unexpected message could quote document text, and an
            # unhandled exception here would otherwise print a traceback and leave the window silent.
            messagebox.showerror(
                "Resume not imported",
                "This file could not be read, so nothing was proposed. Your saved profile was not "
                f"changed.\n\nThe reader reported {type(exc).__name__}; the file itself was not modified.",
                parent=self.root,
            )
            self.status.set("Resume not imported; the profile was not changed.")
            self._record("resume.failed", f"type={type(exc).__name__}")
            return
        # Counts only: the document's text and the values it proposed are not events.
        self._record(
            "resume.proposed",
            f"format={result.source_format.value} proposals={len(result.proposals)} "
            f"unmapped={len(result.unmapped)} characters={result.text_characters}",
        )
        self._review_resume(result)

    def _review_resume(self, result):
        """Show what was found and let the person choose; writes nothing until they confirm.

        The window is a fixed-size dialog: the header and the action buttons stay where they are while
        the proposals scroll, so a long document cannot push Save or Cancel out of reach. Each proposal
        is a plain ``ttk.Checkbutton`` — which takes ``-text``/``-variable`` and has no wrapping option
        — beside ``ttk.Label`` widgets that carry the wrapping, the value and the evidence.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Review resume import (nothing saved yet)")
        dialog.transient(self.root)
        dialog.geometry("900x640")
        dialog.minsize(620, 400)
        dialog.grab_set()

        # Packed before the scrolling body, so the actions always keep their place at the bottom.
        footer = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        footer.pack(fill=X, side="bottom")

        header = ttk.Frame(dialog, padding=(12, 12, 12, 6))
        header.pack(fill=X)
        ttk.Label(
            header,
            text=f"{result.file_name} · {result.source_format.value} · {result.text_characters:,} characters read",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(anchor=W)
        ttk.Label(
            header,
            text=(
                "Nothing has been saved. Select the values you want, then press Save selected values. "
                "Unselected values, and anything this document did not mention, keep your current "
                "profile. The resume text itself is not stored."
            ),
            wraplength=820, justify=LEFT,
        ).pack(anchor=W, pady=(4, 0))

        body = ttk.Frame(dialog)
        body.pack(fill=BOTH, expand=True, padx=12, pady=(0, 4))
        canvas = tk.Canvas(body, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill=BOTH, expand=True)
        scrolled = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=scrolled, anchor="nw")

        def fit_scrollregion(_event=None):
            """Let the canvas know how tall its content is; an empty canvas has no region."""
            box = canvas.bbox("all")
            if box:
                canvas.configure(scrollregion=box)

        def fit_width(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        def scroll_units(event):
            """Mouse wheel: one text line per event (macOS sends small deltas, Windows larger ones)."""
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        scrolled.bind("<Configure>", fit_scrollregion)
        canvas.bind("<Configure>", fit_width)
        canvas.bind("<MouseWheel>", scroll_units)
        scrolled.bind("<MouseWheel>", scroll_units)

        selections = {}
        for proposal in result.proposals:
            row = ttk.Frame(scrolled)
            row.pack(fill=X, anchor=W, pady=(4, 0))
            variable = tk.BooleanVar(value=proposal.confidence is resume.ProposalConfidence.CONFIDENT)
            selections[proposal.key] = variable
            # ttk.Checkbutton has no wrapping option; the wrapping lives on the labels beside it, which
            # is where the value and the evidence belong anyway.
            ttk.Checkbutton(row, text=proposal.label, variable=variable).pack(anchor=W)
            ttk.Label(
                row, text=f"{proposal.label}: {proposal.value}", wraplength=820, justify=LEFT,
            ).pack(anchor=W, padx=(20, 0))
            ttk.Label(
                row, text=f"{proposal.confidence.value} · from: {proposal.evidence}", wraplength=820,
                justify=LEFT,
            ).pack(anchor=W, padx=(20, 0))
        if not result.proposals:
            ttk.Label(scrolled, text="No supported profile value was found in this document.").pack(anchor=W)

        missing = resume.missing_field_labels(result.proposals)
        if missing:
            ttk.Label(
                scrolled,
                text="Not found in this document (your saved values are kept): " + ", ".join(missing),
                wraplength=820, justify=LEFT,
            ).pack(anchor=W, pady=(10, 0))
        if result.unmapped:
            ttk.Label(
                scrolled,
                text=(
                    "Present in the document but not stored (the profile has no field for it): "
                    + "; ".join(f"{item.label}: {item.value}" for item in result.unmapped)
                ),
                wraplength=820, justify=LEFT,
            ).pack(anchor=W, pady=(6, 0))
        if result.notes:
            ttk.Label(
                scrolled, text="Notes: " + " ".join(result.notes), wraplength=820, justify=LEFT,
            ).pack(anchor=W, pady=(6, 0))

        def cancel():
            dialog.destroy()
            self.status.set("Resume import cancelled; the profile was not changed.")

        def apply_selected():
            accepted = resume.accepted_values(
                result.proposals, {key: variable.get() for key, variable in selections.items()}
            )
            if not accepted:
                messagebox.showinfo(
                    "Nothing selected",
                    "No value is selected, so there is nothing to save. Select at least one value, or "
                    "close this window.",
                    parent=dialog,
                )
                return
            chosen_labels = [
                label for key, label in resume.PROFILE_FIELD_LABELS if key in accepted
            ]
            detail = "\n".join(f"• {label}: {accepted[key]}" for key, label in resume.PROFILE_FIELD_LABELS if key in accepted)
            if not messagebox.askyesno(
                "Save these values?",
                f"Selected value(s):\n{detail}\n\nThis saves the profile with these values. Other "
                "fields keep the values shown in the form, and the database is written in one "
                "transaction. Save now?",
                parent=dialog,
            ):
                return
            saved, message = self._apply_accepted_profile_values(
                accepted, document_name=result.file_name)
            if not saved:
                messagebox.showerror("Profile not saved", message, parent=dialog)
                self.status.set("Resume import: nothing was saved.")
                return
            dialog.destroy()
            skipped = [label for key, label in resume.PROFILE_FIELD_LABELS if key in resume.RESUMABLE_FIELD_KEYS
                       and key not in accepted and resume.proposal_by_key(result, key) is not None]
            messagebox.showinfo(
                "Resume import result",
                message
                + ("\n\nNot saved (not selected): " + ", ".join(skipped) if skipped else "")
                + ("\n\nNot found in this document (kept as they were): " + ", ".join(missing) if missing else "")
                + "\n\nThe resume text was not stored."
            )
            self.status.set(
                f"Resume import saved {len(accepted)} value(s) ({', '.join(chosen_labels)}); "
                f"{len(skipped)} selected proposal(s) left unsaved."
            )

        # The window close button, Escape and Cancel all leave the same state: nothing written, and a
        # status line that says so. Return asks to save, and still needs the confirmation.
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<Escape>", lambda _event: cancel())
        dialog.bind("<Return>", lambda _event: apply_selected())
        ttk.Button(footer, text="Save selected values", command=apply_selected).pack(side="right")
        ttk.Button(footer, text="Cancel", command=cancel).pack(side="right", padx=(0, 8))

    def _apply_accepted_profile_values(self, accepted, document_name: str | None = None):
        """Validate and save reviewed resume values, and confirm what the database actually holds.

        The accepted values go through the same ``build_candidate_profile`` pathway as the Save
        button, so a proposed value cannot reach the database by a second, weaker route. A failure
        before the write leaves the stored profile as it was and reports failure; success is only
        reported after the stored profile has been read back and compared field by field. A failure
        to verify after the write is reported as unconfirmed rather than as "nothing was saved",
        because by then the row has been written.

        The facts this save changes are recorded as coming **from that document and unverified** -
        accepting a proposal is not the same claim as confirming a fact, and this application is not
        entitled to assume the person read every value before clicking. The message says which of the
        two happened, in those words, rather than letting "saved" read as "confirmed".
        """
        merged = form_values(self.profile_vars)
        merged.update(accepted)
        try:
            profile = build_candidate_profile(merged)
        except ValueError as exc:
            return False, f"{exc} Nothing was saved."
        try:
            self.store.save_profile(
                profile, source=FactSource.EXTRACTED_FROM_DOCUMENT, document_name=document_name,
            )
        except StoredRecordError as exc:
            # Raised while reading the stored profile the write compares against: nothing has been
            # written at that point, and the record that could not be read is what to report.
            return False, f"{exc} Nothing was saved."
        except ValueError as exc:
            # A refusal from the storage boundary itself - an unusable document name, for example - is
            # reported like any other failure to save, and nothing is written.
            return False, f"{exc} Nothing was saved."
        except sqlite3.Error as exc:
            return False, (
                "The profile could not be written to the local database. Nothing was saved; your "
                f"previously saved profile is unchanged.\n\n{exc}"
            )
        # The write and the verification are reported separately on purpose: once the row has been
        # written, a failure to read it back must not tell the person that nothing was saved.
        try:
            stored = self.store.get_profile()
        except StoredRecordError as exc:
            return False, (
                "The reviewed values were written to the local database, but the saved profile could "
                "not be read back to verify them, so this import is reported as unconfirmed. Open the "
                f"Profile tab and check what is stored before relying on it. {exc}"
            )
        except sqlite3.Error as exc:
            return False, (
                "The reviewed values were written to the local database, but the saved profile could "
                "not be read back to verify them, so this import is reported as unconfirmed. Open the "
                f"Profile tab and check what is stored before relying on it.\n\n{exc}"
            )
        if stored is None:
            return False, (
                "The profile could not be read back after saving, so this import is reported as "
                "unconfirmed rather than saved."
            )
        mismatched = profile_fields_not_matching(stored, accepted)
        if mismatched:
            labels = ", ".join(
                label for key, label in resume.PROFILE_FIELD_LABELS if key in mismatched
            )
            return False, (
                f"The stored profile does not match the value(s) you selected ({labels}), so this "
                "import is reported as failed rather than saved."
            )
        for key, value in profile_form_values(stored).items():
            self.profile_vars[key].set(value)
        # Redrawn from storage, so the values this import changed appear in the table as what they are:
        # read out of that document, and not confirmed by anybody.
        self._refresh_fact_review()
        saved_labels = ", ".join(label for key, label in resume.PROFILE_FIELD_LABELS if key in accepted)
        origin = f" {document_name}" if document_name else " the document"
        return True, (
            f"Saved {len(accepted)} profile value(s): {saved_labels}. They were written to the local "
            f"database and read back to check them. The app recorded them as values read out of{origin}, "
            "and as not confirmed by you: a sentence in a document is not your own statement about "
            "yourself, and this app does not treat it as one. The Profile tab's saved-facts table now "
            "shows which facts are confirmed; \"This is correct — confirm it\" records your own check of "
            "one of them, and \"Set up missing required facts...\" asks for what a listing can require "
            "and your profile does not state."
        )

    def _job_from_form(self):
        """Map the current form to the listing to save and the explicit save plan.

        In ``NEW`` mode a fresh listing id is always used, so an unsaved form can never
        overwrite the selected listing. In ``EDIT`` mode the selected listing keeps its
        identity and the plan reports which eligibility-relevant fields changed.
        """
        return plan_job_save(
            form_values(self.job_vars),
            mode=self.job_save_mode,
            selected_job_id=self.selected_job_id,
            baseline=self.job_edit_baseline,
            new_listing_id=str(uuid.uuid4()),
        )

    def _set_job_mode_display(self):
        if not hasattr(self, "job_mode"):
            return
        if self.job_save_mode is JobSaveMode.EDIT and self.selected_job_id:
            self.job_mode.set("Editing the selected saved listing: saving updates it in place and preserves its identity.")
        else:
            self.job_mode.set("New listing: saving creates a separate record and never overwrites a saved listing.")

    def _begin_new_job(self):
        self.selected_job_id = None
        self.job_save_mode = JobSaveMode.NEW
        self.job_edit_baseline = None
        for key, var in self.job_vars.items():
            var.set("unknown" if key in {"availability", "scope"} else "")
        self.jobs_tree.selection_remove(self.jobs_tree.selection())
        self._set_job_mode_display()

    def _save_job(self):
        try:
            job, plan = self._job_from_form()
            if plan.needs_update_confirmation and not messagebox.askyesno(
                "Update saved listing", plan.update_confirmation_message(), parent=self.root
            ):
                return
            if not plan.is_edit:
                duplicates = tuple(
                    item for item in self.store.find_duplicate_group(job)
                    if item.listing_id != job.listing_id
                )
                if duplicates:
                    summary = "\n".join(f"- {item.employer_name}: {item.role_title} ({item.source_name})" for item in duplicates[:5])
                    if not messagebox.askyesno("Possible duplicate", "This job matches an existing canonical URL/requisition. Existing source observations are kept separately. Save another observation anyway?\n\n" + summary, parent=self.root):
                        return
            self.store.save_job(job)
            # Only create the initial tracker row; an existing row keeps its status — including a
            # status this version does not recognise, which is never rewritten by an unrelated save.
            if self.store.get_tracker_raw(job.listing_id) is None:
                self.store.save_tracker(ApplicationTracker(job.listing_id))
        except ValueError as exc:
            messagebox.showerror("Cannot save job", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            messagebox.showerror(
                "Job not saved",
                "The job could not be written to the local database. Nothing was changed; "
                f"previously saved listings are unchanged.\n\n{exc}",
                parent=self.root,
            )
            self.status.set("Job not saved (local database error).")
            return
        self.selected_job_id = job.listing_id
        self.job_save_mode = JobSaveMode.EDIT
        self.job_edit_baseline = job_form_values(job)
        self._set_job_mode_display()
        self._refresh_jobs()
        self.status.set(f"Saved {job.role_title} locally. Nothing was submitted.")

    def _refresh_jobs(self):
        if not hasattr(self, "jobs_tree"):
            return
        try:
            jobs = self.store.list_jobs()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        for item in self.jobs_tree.get_children():
            self.jobs_tree.delete(item)
        for job in jobs:
            times = self.store.get_record_times(job.listing_id) or {}
            self.jobs_tree.insert("", END, iid=job.listing_id, values=(
                job.employer_name, job.role_title, job.availability_status.value,
                stored_status_text(self.store.get_tracker_raw(job.listing_id)), job.source_name,
                format_stored_timestamp(times.get("last_seen_at")),
            ))
        self._refresh_tracker()

    def _select_job(self, _event=None):
        selection = self.jobs_tree.selection()
        if not selection:
            return
        try:
            job = self.store.get_job(selection[0])
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if not job:
            return
        self.selected_job_id = job.listing_id
        self.job_save_mode = JobSaveMode.EDIT
        self.job_edit_baseline = job_form_values(job)
        for key, value in self.job_edit_baseline.items():
            self.job_vars[key].set(value)
        self._set_job_mode_display()
        # Redaction is for the report pane only. Records saved before URL validation existed may hold
        # credential-bearing links; they are shown safely but never rewritten, and the edit form keeps the
        # stored value so the user can see and correct it themselves.
        times = self.store.get_record_times(job.listing_id) or {}
        self._report(redact_url_credentials(
            f"Selected {job.role_title} at {job.employer_name}\n"
            f"Source listing: {job.source_listing_url}\n"
            f"Employer application URL: {job.employer_apply_url or 'Not verified / not supplied'}\n"
            f"Availability evidence: {job.provenance_note or 'Not supplied'}\n"
            f"Local record times (this device only, never the source's dates): "
            f"first noted {format_stored_timestamp(times.get('first_seen_at'))}, "
            f"last saved {format_stored_timestamp(times.get('last_seen_at'))}\n"
            f"Source publication or update date: not provided by the source here, and never inferred "
            f"from the local record time"
        ))

    def _selected_listing_id(self):
        """Return the listing id the user is acting on, or None when nothing is selected."""
        return self.selected_job_id or (self.jobs_tree.selection()[0] if self.jobs_tree.selection() else None)

    def _loaded_selected_job(self, listing_id):
        """Return the stored listing for ``listing_id``, or None when it is no longer stored.

        A selection can go stale when the database changes outside the current view (an external
        tool, a restored backup, another window). The stored row is the authority, so a selection
        that no longer resolves must be reported instead of being used as if it existed.
        """
        return self.store.get_job(listing_id)

    def _drop_stale_selection(self, listing_id):
        """Reset the view after a selection no longer resolves, changing no persisted data."""
        if self.selected_job_id == listing_id:
            self.selected_job_id = None
            if hasattr(self, "jobs_tree"):
                self.jobs_tree.selection_remove(self.jobs_tree.selection())
        self._refresh_jobs()

    def _report_stale_selection(self, listing_id):
        """Explain a vanished selection and resynchronise the lists. Never raises."""
        self._drop_stale_selection(listing_id)
        messagebox.showinfo(
            "Listing not found",
            "The selected job is no longer in the local database, so nothing was changed. "
            "The lists have been refreshed; select a saved job and try again.",
            parent=self.root,
        )

    def _report_database_unavailable(self, error):
        """Report a failure that is about the connection itself, not about one saved record.

        Reached when the database cannot be read at all: after a restore that replaced the file but
        could not be reopened, or when SQLite refuses a connection for any other reason. The lists are
        left as they are and the message says nothing was changed, so a dead connection never looks
        like an empty database (which would read as "your data is gone").
        """
        self._report(str(error))
        self.status.set("The local database could not be read; nothing was changed.")
        messagebox.showerror("Local database unavailable", str(error), parent=self.root)

    def _report_unreadable_record(self, error):
        """Explain a saved record this version cannot read, and change nothing.

        A damaged or hand-edited record must never surface as a raw traceback from a Tk callback: the
        read is refused, the lists are left in a defined state, and the message says what the record is
        and that nothing was changed. Nothing is repaired, rewritten, or deleted here.
        """
        self._report(str(error))
        self.status.set("A saved record could not be read; nothing was changed.")
        messagebox.showerror("Saved record could not be read", str(error), parent=self.root)

    def _evaluate(self):
        listing_id = self._selected_listing_id()
        if not listing_id:
            messagebox.showinfo("Select a job", "Save or select a job first.", parent=self.root)
            return
        try:
            job = self._loaded_selected_job(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if job is None:
            # Stale selection: report and resync rather than evaluating a listing that is gone.
            self._report_stale_selection(listing_id)
            return
        try:
            profile = self.store.get_profile()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if not profile:
            messagebox.showinfo("Profile required", "Save your candidate profile first. Missing facts are never inferred.", parent=self.root)
            self.tabs.select(self.profile_tab)
            return
        report = evaluate_eligibility(profile, job)
        relevance = score_relevance(profile, job)
        # The eligibility report is evaluated once and handed to the matching engine, so the two answers
        # in this dialog come from the same report rather than from two evaluations that could disagree.
        assessment = assess(profile, job, eligibility=report)
        lines = [f"ELIGIBILITY: {report.decision.value.upper()}", "Only explicit PASS is eligible. UNKNOWN is not eligible.", ""]
        lines += [f"[{item.decision.value.upper()}] {item.requirement}: {item.explanation}" for item in report.requirements]
        lines += ["", f"Skill overlap: {relevance.get('skill_overlap', 'n/a')} (not a hiring probability)",
                  "Matched skills: " + (", ".join(relevance.get("matched_skills", [])) or "None recorded"),
                  "Missing required skills: " + (", ".join(relevance.get("missing_required_skills", [])) or "None recorded")]
        lines += ["", "MATCHING (explainable, and never a prediction)", ""]
        lines += [f"  {factor.line()}" for factor in assessment.factors
                  if factor.status is not FactorStatus.NOT_APPLICABLE]
        lines += [
            "",
            f"  Overlap score: {assessment.score:.0%} of the recorded preference weight"
            if assessment.score is not None else "  Overlap score: nothing could be compared yet",
            f"  How much was known: {assessment.coverage:.0%} of the applicable weight",
            f"  Reading: {assessment.band.value.replace('_', ' ')}",
            f"  Suggested next step: {assessment.recommendation.value.replace('_', ' ')}",
        ]
        lines += [f"  {note}" for note in assessment.notes]
        lines += ["", "  " + MATCHING_DISCLAIMER]
        self._report("\n".join(lines))
        self.status.set(
            f"Eligibility for {job.role_title}: {report.decision.value}; "
            f"{assessment.band.value.replace('_', ' ')}")

    def _shortlist(self):
        listing_id = self._selected_listing_id()
        if not listing_id:
            messagebox.showinfo("Select a job", "Select a saved job first.", parent=self.root)
            return
        try:
            job = self._loaded_selected_job(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if job is None:
            # Same guard as _evaluate: a vanished selection must never reach the eligibility
            # check, and must never create a tracker record.
            self._report_stale_selection(listing_id)
            return
        try:
            profile = self.store.get_profile()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if not profile:
            messagebox.showinfo("Profile required", "Save your candidate profile first.", parent=self.root)
            return
        report = evaluate_eligibility(profile, job)
        if report.decision is not Decision.PASS:
            messagebox.showwarning("Not eligible to shortlist", f"Eligibility is {report.decision.value.upper()}. Resolve unknown/failed requirements first.", parent=self.root)
            self._evaluate()
            return
        try:
            tracker = self.store.get_tracker(listing_id)
            if tracker is None:
                # A tracker record only ever starts at the permitted initial status.
                tracker = ApplicationTracker(listing_id)
                self.store.save_tracker(tracker)
            self.store.save_tracker(tracker.transition(ApplicationStatus.SHORTLISTED))
        except ValueError as exc:
            messagebox.showerror("Cannot shortlist", str(exc), parent=self.root)
            return
        except sqlite3.Error as exc:
            messagebox.showerror(
                "Shortlist not saved",
                "The tracker could not be updated in the local database. Nothing was changed.\n\n"
                f"{exc}",
                parent=self.root,
            )
            self.status.set("Shortlist not saved (local database error).")
            return
        self._refresh_jobs()
        self.status.set("Job shortlisted locally. No external action was taken.")

    def _delete_job(self):
        listing_id = self.selected_job_id or (self.jobs_tree.selection()[0] if self.jobs_tree.selection() else None)
        if not listing_id:
            messagebox.showinfo("Select a job", "Select a job to delete.", parent=self.root)
            return
        if not messagebox.askyesno("Delete job", "Permanently delete this job and its tracker history?", parent=self.root):
            return
        try:
            deleted = self.store.delete_job(listing_id)
        except sqlite3.Error as exc:
            messagebox.showerror(
                "Job not deleted",
                f"The saved job could not be deleted from the local database.\n\n{exc}",
                parent=self.root,
            )
            self.status.set("Job not deleted (local database error).")
            return
        self.selected_job_id = None
        self._begin_new_job()
        self._refresh_jobs()
        if deleted:
            self.status.set("Job and associated tracker record deleted locally.")
            self._report("Job and associated tracker record deleted locally.")
        else:
            self.status.set("No matching saved job was found; nothing was deleted.")
            self._report("No matching saved job was found; nothing was deleted.")

    def _refresh_tracker(self):
        if not hasattr(self, "tracker_tree"):
            return
        try:
            jobs = self.store.list_jobs()
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        for item in self.tracker_tree.get_children():
            self.tracker_tree.delete(item)
        for job in jobs:
            stored = self.store.get_tracker_raw(job.listing_id)
            # The note is the person's own record: shown as stored in both cases, including when the
            # status itself is a value this version does not recognise. The time column is when this
            # app last wrote the record locally, never a claim about the employer or the source.
            self.tracker_tree.insert("", END, iid=job.listing_id, values=(
                job.employer_name, job.role_title, stored_status_text(stored),
                format_stored_timestamp((stored or {}).get("updated_at")),
                (stored or {}).get("status_evidence") or "",
            ))
        self._refresh_activity()

    def _select_tracker(self, _event=None):
        selection = self.tracker_tree.selection()
        if selection:
            self.selected_job_id = selection[0]
            if selection[0] in self.jobs_tree.get_children():
                self.jobs_tree.selection_set(selection[0])
            self._refresh_activity()
            # The Follow-ups tab acts on whichever application is selected, so its day and note
            # fields follow this selection: what is on screen there always describes the application
            # the buttons will write to.
            self._fill_follow_up_fields(selection[0])

    def _selected_application(self, dialog_title: str) -> str | None:
        """The selected tracker row, or ``None`` after telling the person to select one.

        The tree selection is the source of truth rather than a remembered id: a listing can be
        deleted in another tab while its history is still on screen.
        """
        selection = self.tracker_tree.selection()
        if not selection:
            messagebox.showinfo(dialog_title, "Select an application row first.", parent=self.root)
            return None
        return selection[0]

    def _refresh_activity(self):
        """Show the selected application's history, oldest first, exactly as stored."""
        if not hasattr(self, "activity_tree"):
            return
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)
        selection = self.tracker_tree.selection()
        if not selection:
            return
        try:
            entries = self.store.list_activity(selection[0])
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        for entry in entries:
            self.activity_tree.insert("", END, iid=str(entry.activity_id), values=(
                entry.occurred_on.isoformat(), entry.label, entry.detail,
                format_stored_timestamp(entry.recorded_at),
            ))

    def _add_activity(self):
        listing_id = self._selected_application("Select application")
        if listing_id is None:
            return
        # The listing is read first: an entry for a record that no longer exists must be refused
        # before a dialog is opened, not after the person has typed something.
        try:
            job = self.store.get_job(listing_id)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        if job is None:
            messagebox.showinfo(
                "Application not saved",
                "That listing is no longer saved, so there is nothing to attach the entry to. "
                "Refresh the window.",
                parent=self.root,
            )
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Add activity entry")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        ttk.Label(dialog, text=f"{job.employer_name} — {job.role_title}", wraplength=460).pack(
            anchor=W, padx=12, pady=(12, 6))
        defaults = activity_form_values(today=datetime.now(timezone.utc).date())
        kind_var, date_var, detail_var = tk.StringVar(value=defaults["kind"]), \
            tk.StringVar(value=defaults["occurred_on"]), tk.StringVar(value=defaults["detail"])
        ttk.Label(dialog, text="What the entry records").pack(anchor=W, padx=12)
        ttk.Combobox(dialog, textvariable=kind_var, values=list(ACTIVITY_KIND_CHOICES), state="readonly",
                     width=30).pack(fill=X, padx=12, pady=4)
        ttk.Label(dialog, text="Date it happened (YYYY-MM-DD)").pack(anchor=W, padx=12, pady=(8, 0))
        ttk.Entry(dialog, textvariable=date_var, width=20).pack(anchor=W, padx=12, pady=4)
        ttk.Label(dialog, text="What happened").pack(anchor=W, padx=12, pady=(8, 0))
        ttk.Entry(dialog, textvariable=detail_var, width=48).pack(fill=X, padx=12, pady=4)
        ttk.Label(
            dialog,
            text=("Your own note, saved with this date. It does not change the application status and "
                  "is not evidence that an employer did anything."),
            wraplength=440, justify=LEFT,
        ).pack(anchor=W, padx=12)

        def apply():
            try:
                entry = build_activity({
                    "kind": kind_var.get(), "occurred_on": date_var.get(), "detail": detail_var.get(),
                })
            except ValueError as exc:
                messagebox.showerror("Activity entry not saved", str(exc), parent=dialog)
                return
            try:
                self.store.add_activity(listing_id, entry)
            except ValueError as exc:
                messagebox.showerror("Activity entry not saved", str(exc), parent=dialog)
                return
            except StoredRecordError as exc:
                self._report_unreadable_record(exc)
                return
            except sqlite3.Error as exc:
                self._report_database_unavailable(exc)
                return
            dialog.destroy()
            self._refresh_activity()
            self.status.set(f"Activity entry saved for {job.employer_name}: {entry.label} on "
                            f"{entry.occurred_on.isoformat()}. The application status was not changed.")

        dialog.bind("<Return>", lambda _event: apply())
        ttk.Button(dialog, text="Save entry", command=apply).pack(anchor="e", padx=12, pady=12)

    def _delete_activity(self):
        listing_id = self._selected_application("Select application")
        if listing_id is None:
            return
        selection = self.activity_tree.selection()
        if not selection:
            messagebox.showinfo("Select activity entry", "Select an activity entry to delete.",
                                parent=self.root)
            return
        activity_id = int(selection[0])
        values = self.activity_tree.item(activity_id, "values")
        summary = f"{values[0]} — {values[1]}: {values[2]}"
        if not messagebox.askyesno(
            "Delete activity entry?",
            f"Delete this entry from the history?\n\n{summary}\n\n"
            "Deleting an entry removes it from the database. Nothing else changes: the application "
            "status stays as it is.",
            parent=self.root,
        ):
            self.status.set("Deletion cancelled; the entry was kept.")
            return
        try:
            deleted = self.store.delete_activity(activity_id)
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        self._refresh_activity()
        if deleted:
            self.status.set(f"Activity entry deleted: {summary}")
        else:
            # Nothing was removed, so reporting a deletion would be a claim about the database that the
            # database just contradicted.
            self.status.set("That activity entry was already gone; nothing was deleted.")

    def _update_status(self):
        selection = self.tracker_tree.selection()
        if not selection:
            messagebox.showinfo("Select application", "Select an application row first.", parent=self.root)
            return
        listing_id = selection[0]
        # One read of the stored row, interpreted in one place: the dialog is never built from a second
        # read that could disagree with the first. No transition can be validated from a status this
        # build does not know, so such a record is left exactly as it is and the situation is
        # explained, rather than guessed at.
        try:
            stored = self.store.get_tracker_raw(listing_id)
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        try:
            # The parsed read, not the raw one: it carries the recorded follow-up day as well, so the
            # tracker this dialog works from is the whole stored record and a status change through it
            # cannot look like a tracker that never had a reminder.
            current_tracker = self.store.get_tracker(listing_id) or ApplicationTracker(listing_id)
        except TrackerStatusError as exc:
            messagebox.showerror(
                "Status not recognised",
                f"The saved status for this application is {exc.raw_value!r}, which this version of "
                "the application does not know. Nothing was changed and no new status is offered, "
                "because the application cannot tell which changes would be valid from an unknown "
                "state.\n\nThe value is still in your database; if you know what it should be, correct "
                "it there or restore a verified backup.",
                parent=self.root,
            )
            return
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        options = selectable_tracker_statuses(current_tracker.status)
        if len(options) == 1:
            # A terminal status has no permitted next step. Offering a chooser whose every option
            # would be refused would imply an action that does not exist.
            messagebox.showinfo(
                "No further status",
                f"This application is {current_tracker.status.value}, which is a final state: no "
                "further status change is permitted. Nothing was changed.\n\nIf the record is wrong, "
                "delete the entry or keep it as the honest record of what happened.",
                parent=self.root,
            )
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Update application status")
        dialog.transient(self.root)
        dialog.grab_set()
        # Keyboard cancellation, so the dialog does not require a mouse.
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        ttk.Label(dialog, text=f"Current status: {current_tracker.status.value}").pack(anchor=W, padx=12, pady=(12, 5))
        status_var, evidence_var = tk.StringVar(), tk.StringVar()
        ttk.Label(dialog, text="New status").pack(anchor=W, padx=12)
        # Only statuses this record may actually move to (plus its current one), so the chooser
        # cannot suggest a change the domain will refuse.
        ttk.Combobox(dialog, textvariable=status_var, values=[x.value for x in options], state="readonly", width=30).pack(fill=X, padx=12, pady=4)
        ttk.Label(dialog, text="Evidence / note (required to confirm)").pack(anchor=W, padx=12, pady=(8, 0))
        ttk.Entry(dialog, textvariable=evidence_var, width=48).pack(fill=X, padx=12, pady=4)
        ttk.Label(
            dialog,
            text="Describe what the employer actually showed you. Instruction text, placeholders, "
                 "and \"test\" are not evidence.",
            wraplength=420, justify=LEFT,
        ).pack(anchor=W, padx=12)
        # A confirmation is a claim about the employer, so the person must assert it. The dialog
        # never sets candidate_confirmed on the candidate's behalf.
        confirmed_assertion = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            dialog,
            text="I am recording a real employer confirmation for a real application "
                 "(not a test or a simulated submission)",
            variable=confirmed_assertion,
        ).pack(anchor=W, padx=12, pady=(8, 0))
        if current_tracker.status is ApplicationStatus.CONFIRMED:
            ttk.Label(
                dialog,
                text="This record is already confirmed. If that confirmation was a mistake or a test, "
                     "the honest correction is 'withdrawn' with a note saying no application was "
                     "submitted; confirmation cannot be undone backwards.",
                wraplength=420, justify=LEFT,
            ).pack(anchor=W, padx=12)
        def apply():
            message = ""
            try:
                try:
                    new_status = ApplicationStatus(status_var.get())
                except ValueError as exc:
                    raise ValueError("Select the status you want to apply.") from exc
                stored = self.store.get_tracker(listing_id)
                current = stored if stored is not None else ApplicationTracker(listing_id)
                asserted = bool(confirmed_assertion.get())
                if new_status is ApplicationStatus.CONFIRMED and not asserted:
                    raise ValueError(
                        "Recording a confirmation requires you to assert that it reflects a real "
                        "employer confirmation. A test, a demo, or a simulated submission must stay "
                        "unconfirmed. Nothing was saved."
                    )
                if new_status is not ApplicationStatus.CONFIRMED and asserted:
                    raise ValueError(
                        "The confirmation assertion applies only when the new status is "
                        f"'{ApplicationStatus.CONFIRMED.value}'. An existing confirmation is kept "
                        "automatically by later status changes, so leave it unticked. Nothing was saved."
                    )
                # Validate the requested action before any persistent write, so a refused
                # change cannot create or modify a tracker record. The confirmation flag is set
                # only from the explicit assertion above.
                updated = current.transition(
                    new_status,
                    evidence=evidence_var.get().strip() or None,
                    candidate_confirmed=True if new_status is ApplicationStatus.CONFIRMED else None,
                )
                if updated == current and stored is not None:
                    dialog.destroy()
                    self.status.set(f"No change: the application is already {current.status.value}. Nothing was saved.")
                    messagebox.showinfo(
                        "No change",
                        f"This application is already {current.status.value}. Nothing was saved; "
                        "supplied notes are not stored on a no-op.\n\nTo revise the evidence, move the "
                        "status forward with a meaningful note, or keep the existing record as it is.",
                        parent=self.root,
                    )
                    return
                if stored is None:
                    # The action is valid, so create the record at the permitted initial status.
                    self.store.save_tracker(current)
                if updated != current:
                    self.store.save_tracker(updated)
                message = (
                    f"Application record created at {current.status.value}."
                    if updated == current
                    else f"Application status updated to {new_status.value}."
                )
            except ValueError as exc:
                messagebox.showerror("Invalid status change", str(exc), parent=dialog)
                return
            except sqlite3.Error as exc:
                messagebox.showerror(
                    "Status not saved",
                    "The status change could not be written to the local database. The saved status is "
                    f"unchanged.\n\n{exc}",
                    parent=dialog,
                )
                self.status.set("Status not saved (local database error).")
                return
            except Exception as exc:  # noqa: BLE001 - unexpected failures are reported, never hidden
                # A last boundary: an unforeseen error must not close the dialog as if the change had
                # been saved. Nothing is claimed and the saved record is untouched.
                messagebox.showerror(
                    "Status not saved",
                    "The status change could not be completed and nothing was saved. The saved status "
                    f"is unchanged.\n\nUnexpected problem: {type(exc).__name__}: {exc}",
                    parent=dialog,
                )
                self.status.set("Status not saved (unexpected problem).")
                return
            dialog.destroy()
            self._refresh_jobs()
            self.status.set(message)
        dialog.bind("<Return>", lambda _event: apply())
        ttk.Button(dialog, text="Save status", command=apply).pack(anchor="e", padx=12, pady=12)

    def _export(self):
        destination = filedialog.asksaveasfilename(parent=self.root, title="Export local data", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not destination:
            return
        try:
            # The document is built by the importer module, which is also what reads a file back: one
            # definition of the format, so the two directions cannot drift apart.
            payload = import_export.export_document(self.store)
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        try:
            # Owner-only from the first byte, and never through a symbolic link: the export holds
            # profile facts and application history, so it must not inherit a permissive umask or
            # land in whatever file a link points at.
            write_private_text_file(destination, json.dumps(payload, indent=2, ensure_ascii=False))
        except PrivateWriteError as exc:
            messagebox.showerror(
                "Export not saved",
                f"{exc}\n\nNothing was written. Choose a regular file in a folder you control.",
                parent=self.root,
            )
            self.status.set("Export not saved (the file could not be protected).")
            self._record("export.failed", "reason=the file could not be kept owner-only")
            return
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)
            self.status.set("Export failed (local file error).")
            self._record("export.failed", f"reason={exc}")
            return
        self._record("export.written", f"jobs={len(payload['jobs'])}")
        self.status.set(f"Exported {len(payload['jobs'])} jobs to a user-selected local file.")
        messagebox.showinfo(
            "Export complete",
            "JSON export created with owner-only permissions where the file system supports them. "
            "Keep it private; it may contain personal data. A synced or shared folder can still "
            "expose it, so export to a folder only you can access.",
            parent=self.root,
        )

    def _import_data(self):
        """Read a JSON export back in, showing what it would do before anything is written.

        Two steps on purpose. The plan is computed first, shown in full, and only applied after the
        person agrees - so an import into a database that already holds their applications is a decision
        they make with the consequences in front of them rather than a surprise.
        """
        chosen = filedialog.askopenfilename(
            parent=self.root, title="Choose an export to import",
            filetypes=[("JSON export", "*.json"), ("All files", "*.*")])
        if not chosen:
            return
        try:
            document = import_export.read_export(chosen)
            plan = import_export.plan_import(self.store, document, source=chosen)
        except import_export.ImportRefused as exc:
            messagebox.showerror("Nothing was imported", str(exc), parent=self.root)
            self.status.set("Import refused; nothing was read into the database.")
            self._record("import.refused", f"reason={type(exc).__name__}")
            return
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        summary = "\n".join(plan.describe())
        if not messagebox.askyesno(
                "Import this file?",
                f"{summary}\n\nApply it now?", parent=self.root):
            self.status.set("Import cancelled; nothing was written.")
            return
        try:
            outcome = import_export.apply_import(
                self.store, document, source=chosen, document_name=Path(chosen).name,
            )
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        except ValueError as exc:
            messagebox.showerror("Import stopped", f"{exc}\n\nWhat was listed above was applied; "
                                                  "nothing else was.", parent=self.root)
            self._record("import.failed", "reason=a stored record was refused")
            return
        self._refresh_jobs()
        self._refresh_tracker()
        self._refresh_follow_ups()
        self._record("import.written", f"jobs={outcome.added_jobs} linked={outcome.linked_jobs} "
                                       f"rejected={outcome.rejected}")
        self.status.set(f"Import complete: {outcome.describe()}.")
        messagebox.showinfo(
            "Import complete",
            f"{outcome.describe()}.\n\nA stored listing or profile was never replaced: your records "
            "win over the file's. Records that could not be read are reported in the plan above and "
            "were skipped.",
            parent=self.root,
        )

    def _report(self, text):
        if not hasattr(self, "report"):
            return
        self.report.configure(state="normal")
        self.report.delete("1.0", END)
        self.report.insert("1.0", text)
        self.report.configure(state="disabled")

    def _record(self, event: str, detail: str | None = None) -> None:
        """Record one event about this run; never let logging fail an action the person asked for."""
        record_event(event, detail=detail, database_path=str(self.db_path))

    def close(self):
        self._record("app.stopped")
        # An open setup window is destroyed with the root. It holds answers nobody saved - that is exactly
        # what Cancel and Escape do - so there is nothing to undo and nothing to report as written.
        self.profile_setup = None
        self.store.close()
        self.root.destroy()


def main(database_path=None):
    root = tk.Tk()
    try:
        CareerAgentApp(root, database_path=database_path)
    except Exception as exc:
        # The window cannot be shown, so this message carries the whole explanation. It is built by
        # ``diagnostics`` so it names a next step without exposing candidate data, database contents,
        # credentials or filesystem locations, and the same sanitised text is kept in one bounded
        # note beside the local data folder for later diagnosis.
        explanation = describe_startup_failure(exc, database_path=database_path)
        note = record_startup_failure(exc, database_path=database_path)
        if note is not None:
            explanation += (
                f"\n\nA short, sanitised note was saved as {note.name} in the application's logs "
                "folder. It holds no candidate data."
            )
        messagebox.showerror("AI Career Agent could not start", explanation, parent=root)
        root.destroy()
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
