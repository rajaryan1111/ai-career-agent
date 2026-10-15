"""Offline-first Tkinter desktop workflow for AI Career Agent.

Launch with python -m career_agent. No network calls or external service dependencies.
Domain rules, validation, and form mapping live in ``core.py``, ``store.py``,
``validation.py``, and ``desktop_logic.py``; this module only wires them to widgets.
"""
from __future__ import annotations
import json
import sqlite3
import uuid
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
    Decision, EducationEntry, EmploymentType, InterviewMode, InterviewOutcome, InterviewStage,
    PreparationKind, WorkHistoryEntry, evaluate_eligibility, months_covered_by, score_relevance,
    selectable_tracker_statuses,
)
from . import __version__
from . import analytics
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
    format_stored_timestamp, form_values, job_form_values, plan_job_save,
    profile_fields_not_matching, profile_form_values,
)
from . import resume
from .diagnostics import describe_startup_failure, record_startup_failure
from .store import (
    SCHEMA_VERSION,
    CareerStore,
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
        self.tabs.add(self.profile_tab, text="Candidate profile")
        self.tabs.add(self.jobs_tab, text="Jobs & eligibility")
        self.tabs.add(self.tracker_tab, text="Application tracker")
        self.tabs.add(self.history_tab, text="Work history & study")
        self.tabs.add(self.actions_tab, text="Next actions")
        self.tabs.add(self.follow_up_tab, text="Follow-ups")
        self.tabs.add(self.data_tab, text="Data safety")
        self.tabs.add(self.scheduler_tab, text="Background tasks")
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

    def _entry(self, parent, label, key, row, col, variables, *, choices=None, width=26):
        ttk.Label(parent, text=label).grid(row=row, column=col * 2, sticky=W, padx=(0, 5), pady=4)
        var = tk.StringVar()
        variables[key] = var
        widget = ttk.Combobox(parent, textvariable=var, values=choices, width=width, state="readonly") if choices else ttk.Entry(parent, textvariable=var, width=width)
        widget.grid(row=row, column=col * 2 + 1, sticky="ew", padx=(0, 12), pady=4)
        return widget

    def _build_profile(self):
        for col in (1, 3):
            self.profile_tab.columnconfigure(col, weight=1)
        ttk.Label(self.profile_tab, text="Only enter verifiable facts. Blank fields remain unknown.").grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 8))
        fields = [
            ("Country", "country", 1, 0, None), ("Degree / discipline", "degree", 1, 1, None),
            ("Study status", "study_status", 2, 0, ["undergraduate", "graduate", "postgraduate", "doctoral", "graduated", "other"]),
            ("Graduation year", "graduation_year", 2, 1, None), ("Experience years", "experience", 3, 0, None),
            ("Work authorization value (exact when required)", "work_authorization", 3, 1, None), ("Skills (comma-separated)", "skills", 4, 0, None),
            ("Preferred locations", "locations", 4, 1, None), ("Preferred work modes", "work_modes", 5, 0, None),
            ("Preferred role types", "role_types", 5, 1, None),
        ]
        for label, key, row, col, choices in fields:
            self._entry(self.profile_tab, label, key, row, col, self.profile_vars, choices=choices)
        actions = ttk.Frame(self.profile_tab)
        actions.grid(row=6, column=0, columnspan=4, sticky=W, pady=12)
        ttk.Button(actions, text="Save profile locally", command=self._save_profile).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Import resume (PDF/DOCX)", command=self._import_resume).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete saved profile", command=self._delete_profile).pack(side="left")
        ttk.Label(
            self.profile_tab,
            text=(
                "Resume import reads the chosen file on this device and proposes values for you to "
                "review: nothing is uploaded, nothing is saved until you confirm, and the extracted "
                "text is not kept. Privacy: no cloud sync, external AI API, or data transfer is "
                "performed. Data stays in the local application-data folder."
            ),
            wraplength=850,
        ).grid(row=7, column=0, columnspan=4, sticky=W, pady=8)
        ttk.Label(
            self.profile_tab,
            text=(
                "A resume is untrusted input: the import reads text only, never runs macros, and refuses "
                "an encrypted or over-sized file. It is not a malware scanner."
            ),
            wraplength=850,
        ).grid(row=8, column=0, columnspan=4, sticky=W)

    def _build_jobs(self):
        for col in (1, 3, 5):
            self.jobs_tab.columnconfigure(col, weight=1)
        ttk.Label(self.jobs_tab, text="Manual entry only. Leave unknown requirements blank; do not guess country eligibility or apply URLs.", wraplength=900).grid(row=0, column=0, columnspan=6, sticky=W, pady=(0, 8))
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
            wraplength=900,
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
            self.tracker_tab, textvariable=self.progress_summary, wraplength=1000, justify="left",
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
        canvas = tk.Canvas(body, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
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


    def _build_data_safety(self):
        ttk.Label(
            self.data_tab,
            text="Local only: no account, no cloud service, and no network access. Keep backups on storage you control.",
            wraplength=900,
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
            wraplength=900,
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
            wraplength=900,
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
        ttk.Label(
            self.scheduler_tab,
            text=(
                "Scheduled tasks run while the worker is running: python -m career_agent --worker "
                "(Ctrl-C stops it). Nothing here runs while the worker is stopped, and nothing runs "
                "while the computer is off or asleep. Every task runs locally; the source-quality gate "
                "is closed, so a scheduled discovery run is recorded as a refusal and fetches nothing."
            ),
            wraplength=900, justify=LEFT,
        ).grid(row=0, column=0, columnspan=4, sticky=W, pady=(0, 8))
        self.scheduler_summary = tk.StringVar(value="Checking the schedule...")
        ttk.Label(self.scheduler_tab, textvariable=self.scheduler_summary, wraplength=900,
                  justify=LEFT).grid(row=1, column=0, columnspan=4, sticky=W, pady=(0, 8))
        ttk.Button(self.scheduler_tab, text="Add the default tasks",
                   command=self._add_default_tasks).grid(row=2, column=0, sticky=W, pady=4)
        ttk.Button(self.scheduler_tab, text="Enable or disable the selected task",
                   command=self._toggle_scheduled_task).grid(row=2, column=1, sticky=W, padx=(8, 0), pady=4)
        ttk.Button(self.scheduler_tab, text="Refresh",
                   command=self._refresh_scheduler).grid(row=2, column=2, sticky=W, padx=(8, 0), pady=4)
        ttk.Label(self.scheduler_tab, text="Tasks").grid(row=3, column=0, columnspan=4, sticky=W, pady=(10, 2))
        task_columns = ("task", "name", "kind", "times", "zone", "next", "last")
        self.tasks_tree = ttk.Treeview(self.scheduler_tab, columns=task_columns, show="headings", height=6)
        for column, heading, width in (
            ("task", "Task", 150), ("name", "What it is", 190), ("kind", "Kind", 140),
            ("times", "Runs at", 110), ("zone", "Zone", 120), ("next", "Next run (local)", 190),
            ("last", "Last result", 200),
        ):
            self.tasks_tree.heading(column, text=heading)
            self.tasks_tree.column(column, width=width, anchor=W)
        self.tasks_tree.grid(row=4, column=0, columnspan=4, sticky="nsew")
        ttk.Label(self.scheduler_tab, text="Recent attempts").grid(row=5, column=0, columnspan=4,
                                                                  sticky=W, pady=(10, 2))
        run_columns = ("task", "attempt", "outcome", "when", "took", "note")
        self.task_runs_tree = ttk.Treeview(self.scheduler_tab, columns=run_columns, show="headings",
                                          height=6)
        for column, heading, width in (
            ("task", "Task", 150), ("attempt", "Attempt", 70), ("outcome", "Outcome", 110),
            ("when", "Scheduled for (local)", 190), ("took", "Took", 80), ("note", "What happened", 400),
        ):
            self.task_runs_tree.heading(column, text=heading)
            self.task_runs_tree.column(column, width=width, anchor=W)
        self.task_runs_tree.grid(row=6, column=0, columnspan=4, sticky="nsew")
        self.scheduler_tab.columnconfigure(0, weight=1)

    def _build_history(self):
        """The employment and study records behind the profile's summary fields.

        Two forms, two lists, on their own tab rather than inside the profile form: these are the records a
        person edits and reorders over years, and the profile form's ten fields are the summary they keep in
        mind. The buttons say what they do to the *selected row*, and a row has to be selected before an edit
        or a deletion can happen at all.
        """
        ttk.Label(
            self.history_tab, wraplength=960, justify=LEFT,
            text=("Your own record, in the order a CV reads: the current role first, then the most recent. "
                  "These are notes you keep, not verified facts, and nothing here is checked against any "
                  "employer or document. Blank fields stay unknown rather than being guessed."),
        ).pack(anchor=W, pady=(0, 8))

        work_form = ttk.LabelFrame(self.history_tab, text="Employment", padding=8)
        work_form.pack(fill=X, pady=(0, 8))
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
        ttk.Button(work_actions, text="Add this role", command=self._add_work_history).pack(side="left", padx=(0, 8))
        ttk.Button(work_actions, text="Save changes to the selected role",
                   command=self._update_work_history).pack(side="left", padx=8)
        ttk.Button(work_actions, text="Select the selected role for editing", command=self._load_work_history
                   ).pack(side="left", padx=8)
        ttk.Button(work_actions, text="Delete the selected role", command=self._delete_work_history
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

        study_form = ttk.LabelFrame(self.history_tab, text="Education", padding=8)
        study_form.pack(fill=X)
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
        ttk.Button(study_actions, text="Add this qualification", command=self._add_education
                   ).pack(side="left", padx=(0, 8))
        ttk.Button(study_actions, text="Save changes to the selected qualification",
                   command=self._update_education).pack(side="left", padx=8)
        ttk.Button(study_actions, text="Select the selected qualification for editing",
                   command=self._load_education).pack(side="left", padx=8)
        ttk.Button(study_actions, text="Delete the selected qualification", command=self._delete_education
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
        ttk.Label(self.history_tab, textvariable=self.history_summary, wraplength=960,
                  justify="left").pack(anchor=W, pady=(8, 0))
        ttk.Label(
            self.history_tab, wraplength=960, justify=LEFT,
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
        ttk.Button(controls, text="Refresh", command=self._refresh_actions).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Add a preparation item", command=self._add_preparation
                   ).pack(side="left", padx=8)
        ttk.Button(controls, text="Record an interview round", command=self._record_interview_round
                   ).pack(side="left", padx=8)
        ttk.Button(controls, text="Mark the selected item done", command=self._complete_preparation
                   ).pack(side="left", padx=8)
        ttk.Button(controls, text="Record the selected round's outcome", command=self._set_round_outcome
                   ).pack(side="left", padx=8)
        ttk.Button(controls, text="Delete the selected record", command=self._delete_action_record
                   ).pack(side="left", padx=8)
        ttk.Label(
            self.actions_tab, wraplength=900, justify=LEFT,
            text=("Everything here is a plan you wrote: a preparation item, a round you recorded, or a "
                  "follow-up day. None of it changes an application's status, and no record here is an "
                  "employer's decision - only you move an application on, and only with your own evidence."),
        ).pack(anchor=W, pady=(0, 8))
        self.actions_summary = tk.StringVar()
        ttk.Label(self.actions_tab, textvariable=self.actions_summary, wraplength=900,
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
        ttk.Button(actions, text="Refresh", command=self._refresh_follow_ups).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Set the day for the selected application",
                   command=self._set_follow_up).pack(side="left", padx=8)
        ttk.Button(actions, text="Clear the selected follow-up",
                   command=self._clear_follow_up).pack(side="left", padx=8)
        ttk.Button(actions, text="Preview the calendar export",
                   command=self._preview_calendar_export).pack(side="left", padx=8)
        ttk.Button(actions, text="Draft a follow-up email",
                   command=self._draft_follow_up_email).pack(side="left", padx=8)
        ttk.Button(actions, text="Export to a calendar file",
                   command=self._export_follow_ups).pack(side="left", padx=8)
        ttk.Label(
            self.follow_up_tab, wraplength=900,
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
        ttk.Label(self.follow_up_tab, textvariable=self.follow_up_summary, wraplength=900,
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
        if not profile:
            return
        for key, value in profile_form_values(profile).items():
            self.profile_vars[key].set(value)

    def _save_profile(self):
        try:
            self.store.save_profile(build_candidate_profile(form_values(self.profile_vars)))
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
            saved, message = self._apply_accepted_profile_values(accepted)
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

    def _apply_accepted_profile_values(self, accepted):
        """Validate and save reviewed resume values, and confirm what the database actually holds.

        The accepted values go through the same ``build_candidate_profile`` pathway as the Save
        button, so a proposed value cannot reach the database by a second, weaker route. A failure
        before the write leaves the stored profile as it was and reports failure; success is only
        reported after the stored profile has been read back and compared field by field. A failure
        to verify after the write is reported as unconfirmed rather than as "nothing was saved",
        because by then the row has been written.
        """
        merged = form_values(self.profile_vars)
        merged.update(accepted)
        try:
            profile = build_candidate_profile(merged)
        except ValueError as exc:
            return False, f"{exc} Nothing was saved."
        try:
            self.store.save_profile(profile)
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
        saved_labels = ", ".join(label for key, label in resume.PROFILE_FIELD_LABELS if key in accepted)
        return True, f"Saved {len(accepted)} profile value(s): {saved_labels}. Verified in the local database."

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
            outcome = import_export.apply_import(self.store, document, source=chosen)
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
