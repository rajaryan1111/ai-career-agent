"""Offline-first Tkinter desktop workflow for AI Career Agent.

Launch with python -m career_agent. No network calls or external service dependencies.
Domain rules, validation, and form mapping live in ``core.py``, ``store.py``,
``validation.py``, and ``desktop_logic.py``; this module only wires them to widgets.
"""
from __future__ import annotations

import json
import sqlite3
import tkinter as tk
import uuid
from dataclasses import asdict
from pathlib import Path
from tkinter import BOTH, END, LEFT, W, X, filedialog, messagebox, ttk

from . import resume
from .backup import (
    BACKUP_SUFFIX,
    BackupError,
    create_backup,
    restore_backup,
    suggested_backup_name,
    validate_app_database,
)
from .core import (
    INITIAL_APPLICATION_STATUS,
    ApplicationStatus,
    ApplicationTracker,
    Availability,
    score_relevance,
    selectable_tracker_statuses,
)
from .desktop_logic import (
    JobSaveMode,
    build_candidate_profile,
    default_database_path,
    form_values,
    format_stored_timestamp,
    job_form_values,
    plan_job_save,
    profile_fields_not_matching,
    profile_form_values,
)
from .diagnostics import describe_startup_failure, record_startup_failure
from .matching import assess_strategy
from .notifications import NotificationManager
from .policy import ActionStatus, check_policy
from .reporting import (
    build_eligibility_insights,
)
from .scheduler import SchedulerEngine, SchedulerStatus
from .store import (
    CareerStore,
    PrivateWriteError,
    StoredRecordError,
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


#: Controlled interval between scheduler polls, in milliseconds. The cron
#: scheduler only schedules to minute granularity, so a one-minute poll
#: introduces at most one minute of delay after the computed due time.
SCHEDULER_POLL_MS = 60_000


class CareerAgentApp:
    """Small local UI over the tested domain logic and SQLite store."""
    def __init__(self, root: tk.Tk, database_path: str | Path | None = None):
        self.root = root
        self.root.title("AI Career Agent — Local Workspace")
        self.root.geometry("1120x760")
        self.root.minsize(900, 600)
        self.db_path = Path(database_path) if database_path else default_database_path()
        self.store = CareerStore(self.db_path)
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
        self.tabs.add(self.profile_tab, text="Candidate profile")
        self.tabs.add(self.jobs_tab, text="Jobs & eligibility")
        self.tabs.add(self.tracker_tab, text="Application tracker")
        self.tabs.add(self.data_tab, text="Data safety")
        self.profile_vars: dict[str, str] = {}
        self.job_vars: dict[str, str] = {}
        self.notification_manager = NotificationManager(self.store)
        self._build_profile()
        self._build_jobs()
        self._build_tracker()
        self._build_data_safety()
        self.status = tk.StringVar(value=f"Local database: {self.db_path}")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor=W, padding=5).pack(fill=X, side="bottom")
        self._load_profile()
        self._refresh_jobs()
        # - Scheduler runtime ------------------------------------------------
        # The persisted SQLite store is authoritative: schedules, run state
        # and notifications are all read from and written to the store, never
        # only in-memory. The Tk event loop drives the engine via a single
        # non-blocking ``after`` timer; no background thread is started.
        self._start_scheduler_runtime()

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

    def _build_data_safety(self):
        ttk.Label(
            self.data_tab,
            text="Local only: no account, no cloud service, and no network access. Keep backups on storage you control.",
            wraplength=900,
        ).grid(row=0, column=0, sticky=W, pady=(0, 8))
        ttk.Button(self.data_tab, text="Back up database", command=self._backup_database).grid(row=1, column=0, sticky=W, pady=4)
        ttk.Button(self.data_tab, text="Restore from backup", command=self._restore_database).grid(row=2, column=0, sticky=W, pady=4)
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
        ).grid(row=3, column=0, sticky=W, pady=(10, 0))

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
            self.store = UnavailableStore(self.db_path, f"{type(exc).__name__}: {exc}")  # type: ignore[assignment]
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
        if not messagebox.askyesno("Delete profile", "Permanently delete the saved profile on this device?", parent=self.root):
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
        self.status.set("Saved profile deleted.")

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
            return
        except Exception as exc:
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
            return
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
        # Use Phase 5 matching strategy for assessable results
        strategy = assess_strategy(profile, job)
        # Use Phase 5 reporting for structured insights
        summary = build_eligibility_insights(profile, job)
        # Check policy at the evaluation boundary
        policy_check = check_policy("evaluate_eligibility", strategy,
                                     user_authorized=False, has_credentials=False)
        # Compute relevance for skill overlap display
        relevance = score_relevance(profile, job)

        lines = [f"ELIGIBILITY: {strategy.overall_decision.value.upper()}",
                 f"Recommendation: {strategy.recommendation.value}",
                 f"Confidence: {strategy.confidence}",
                 f"Verification required: {strategy.verification_required}",
                 "", f"Skill overlap: {relevance.get('skill_overlap', 'n/a')} (not a hiring probability)",
                 ""]
        lines += [f"[{item.decision.value.upper()}] {item.requirement}: {item.reason}"
                  for item in summary.confirmed_facts]
        lines += ["  (provenance: {item.provenance})" for item in summary.confirmed_facts]
        lines += ["", "Inferred facts:"]
        lines += [f"  {item.requirement}: {item.reason} (provenance: {item.provenance})"
                  for item in summary.inferred_facts]
        lines += ["", "Missing requirements:"]
        lines += [f"  {r}" for r in summary.missing_requirements]
        lines += ["", f"Overall: {summary.overall_decision.value}"]
        lines += ["", "Recommendations:"]
        lines += [f"  {r}" for r in summary.recommendations]
        lines += ["", f"Policy: {policy_check.status.value}"]
        lines += [f"  {policy_check.reason}"]
        if policy_check.requires_auth:
            lines += ["  (requires explicit user authorization)"]
        lines += ["", policy_check.blocking_issue or ""]
        self._report("\n".join(lines))
        # Show follow-up reminder if eligibility is uncertain or a fail
        if hasattr(self, "notification_manager"):
            reminder = self.notification_manager.check_followup_reminder(
                f"eligibility_{job.listing_id}",
                min_interval_hours=24,
            )
            if reminder is not None:
                self._report(f"\nFollow-up reminder: {reminder.message}")
        self.status.set(f"Eligibility for {job.role_title}: {strategy.overall_decision.value} ({strategy.recommendation.value}).")

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
        # Use Phase 5 matching strategy
        strategy = assess_strategy(profile, job)
        # Check policy before shortlisting
        policy_check = check_policy("shortlist_application", strategy,
                                     user_authorized=False, has_credentials=False)

        if policy_check.status == ActionStatus.BLOCKED:
            messagebox.showwarning("Cannot shortlist", f"{policy_check.reason}\n\n{policy_check.blocking_issue}", parent=self.root)
            return
        if policy_check.status == ActionStatus.UNCERTAIN:
            messagebox.showwarning("Cannot shortlist", f"{policy_check.reason}\n\nResolve missing evidence first.", parent=self.root)
            return

        if policy_check.status == ActionStatus.CONDITIONAL:
            if not messagebox.askyesno(
                "Conditional shortlist",
                f"{policy_check.reason}\n\nProceed with shortlisting despite conditional status?",
                parent=self.root,
            ):
                return

        if policy_check.status == ActionStatus.PERMITTED:
            # Full pass - shortlist normally
            pass

        # Proceed with shortlisting
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

    def _select_tracker(self, _event=None):
        selection = self.tracker_tree.selection()
        if selection:
            self.selected_job_id = selection[0]
            if selection[0] in self.jobs_tree.get_children():
                self.jobs_tree.selection_set(selection[0])

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
        stored = self.store.get_tracker_raw(listing_id)
        try:
            current_tracker = (
                ApplicationTracker(listing_id) if stored is None
                else ApplicationTracker(
                    listing_id, ApplicationStatus(stored["status"]),
                    stored["status_evidence"], stored["candidate_confirmed"],
                )
            )
        except ValueError:
            messagebox.showerror(
                "Status not recognised",
                f"The saved status for this application is {stored['status']!r}, which this version of "
                "the application does not know. Nothing was changed and no new status is offered, "
                "because the application cannot tell which changes would be valid from an unknown "
                "state.\n\nThe value is still in your database; if you know what it should be, correct "
                "it there or restore a verified backup.",
                parent=self.root,
            )
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
            except Exception as exc:
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
            profile = self.store.get_profile()
            jobs = self.store.list_jobs()
            # Read every tracker row here, inside the same guard: a connection that dies midway through
            # the loop below would otherwise raise out of a Tk callback, and the file must not be
            # half-written either way.
            tracker_rows = {job.listing_id: self.store.get_tracker_raw(job.listing_id) for job in jobs}
        except StoredRecordError as exc:
            self._report_unreadable_record(exc)
            return
        except sqlite3.Error as exc:
            self._report_database_unavailable(exc)
            return
        payload = {"format_version": 1, "profile": asdict(profile) if profile else None, "jobs": [],
                   "privacy_note": "Export may contain personal information; store securely."}
        if payload["profile"]:
            for key, value in payload["profile"].items():
                if isinstance(value, (set, frozenset, tuple)):
                    payload["profile"][key] = sorted(value)
        for job in jobs:
            record = asdict(job)
            record["availability_status"] = job.availability_status.value
            for key, value in record.items():
                if isinstance(value, (set, frozenset, tuple)):
                    record[key] = sorted(value)
            # The stored values are exported exactly as they are, so a record whose status this
            # version does not recognise can still be taken out of the app instead of blocking the
            # whole export. ``status_recognised: false`` marks that value; it is only added when this
            # version did not understand the stored status, so the format is unchanged otherwise.
            stored_status = tracker_rows[job.listing_id]
            if stored_status is None:
                record["application_tracker"] = None
            else:
                try:
                    ApplicationStatus(stored_status["status"])
                except ValueError:
                    stored_status["status_recognised"] = False
                record["application_tracker"] = stored_status
            payload["jobs"].append(record)
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
            return
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)
            self.status.set("Export failed (local file error).")
            return
        self.status.set(f"Exported {len(payload['jobs'])} jobs to a user-selected local file.")
        messagebox.showinfo(
            "Export complete",
            "JSON export created with owner-only permissions where the file system supports them. "
            "Keep it private; it may contain personal data. A synced or shared folder can still "
            "expose it, so export to a folder only you can access.",
            parent=self.root,
        )

    def _report(self, text):
        if not hasattr(self, "report"):
            return
        self.report.configure(state="normal")
        self.report.delete("1.0", END)
        self.report.insert("1.0", text)
        self.report.configure(state="disabled")

    # ------------------------------------------------------------- scheduler runtime

    def _start_scheduler_runtime(self):
        """Bring the persisted scheduler up for this session.

        Recovery policy (safe, bounded):
        - Runs still marked RUNNING from a previous process are failed with
          an explicit reason. ``SchedulerEngine.complete_run`` then applies
          the bounded retry policy instead of leaving a zombie state, and no
          side effects of the interrupted run are re-attempted silently.
        - Due schedules are processed once at resume by the first tick; the
          engine then computes the next cron occurrence, so a long closure
          produces one catch-up execution, never a storm.
        """
        # Runtime state is owned here so the scheduler works identically
        # whether or not the full __init__ path built it first.
        self._scheduler_closing = False
        self._scheduler_after_id = None
        self._scheduler_polling_active = False
        self.scheduler_engine = SchedulerEngine(self.store)
        self._recover_interrupted_runs()
        self._scheduler_polling_active = True
        self._scheduler_schedule_tick()
        self._report_scheduler_status()

    def _recover_interrupted_runs(self):
        """Close out runs that were interrupted by a previous process."""
        recovered = 0
        for run in self.scheduler_engine.get_pending_runs():
            if run.status is SchedulerStatus.RUNNING:
                self.scheduler_engine.complete_run(
                    run.id,
                    SchedulerStatus.FAILED,
                    error_message="interrupted by application restart",
                )
                recovered += 1
        return recovered

    def _scheduler_schedule_tick(self, delay_ms=None):
        """Queue the next poll on the UI event loop (never blocking it)."""
        if self._scheduler_closing or not self._scheduler_polling_active:
            return
        after = getattr(self.root, "after", None)
        if after is None:
            # Test stubs are driven by calling _scheduler_tick directly.
            return
        self._scheduler_after_id = after(
            SCHEDULER_POLL_MS if delay_ms is None else delay_ms,
            self._scheduler_tick,
        )

    def _scheduler_tick(self):
        """One scheduler poll. Runs the engine, executes due schedules, and
        re-arms itself. Exceptions are reported; they must not crash the UI
        loop or kill the polling cycle."""
        self._scheduler_after_id = None
        try:
            due_runs = self.scheduler_engine.check_due_runs()
        except Exception as exc:  # engine or storage failure: keep polling
            self.status.set(f"Scheduler check failed: {type(exc).__name__}: {exc}")
            self._scheduler_schedule_tick()
            return
        for run in due_runs:
            try:
                self._execute_scheduled_run(run)
            except Exception as exc:
                self.scheduler_engine.complete_run(
                    run.id,
                    SchedulerStatus.FAILED,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
        self._report_scheduler_status()
        self._scheduler_schedule_tick()

    def _execute_scheduled_run(self, run):
        """Execute the action attached to a due scheduled run.

        Local-alpha actions are deliberately bounded: a run produces one
        persistent follow-up reminder notification describing the scheduled
        job listing. Nothing here sends email or submits an application;
        those boundaries live in the approval-gated flows.
        """
        schedule = self.scheduler_engine.get_schedule(run.schedule_id)
        if schedule is None:
            self.scheduler_engine.complete_run(
                run.id, SchedulerStatus.FAILED, error_message="schedule definition missing"
            )
            return
        if not schedule.enabled:
            self.scheduler_engine.complete_run(
                run.id, SchedulerStatus.CANCELLED, error_message="schedule disabled"
            )
            return
        listing = self.store.get_job(schedule.job_listing_id)
        if listing is None:
            self.scheduler_engine.complete_run(
                run.id, SchedulerStatus.FAILED, error_message="job listing no longer stored"
            )
            return
        # Dedup key: one reminder per schedule per calendar day; repeated
        # polls of the same due schedule cannot create duplicates.
        dedup_key = f"schedule:{schedule.id}:{run.started_at[:10]}"
        reminder = self.notification_manager.check_followup_reminder(dedup_key)
        if reminder is not None:
            note = f"follow-up reminder created for {listing.role_title} ({listing.employer_name})"
        else:
            note = f"follow-up reminder already pending for {listing.role_title} ({listing.employer_name})"
        self.scheduler_engine.complete_run(run.id, SchedulerStatus.COMPLETED, output=note)
        if reminder is not None:
            self._refresh_tracker()

    def _report_scheduler_status(self):
        try:
            schedules = self.scheduler_engine.list_schedules()
            enabled = sum(1 for s in schedules if s.enabled)
            self.status.set(
                f"Scheduler: active · {enabled}/{len(schedules)} schedule(s)"
                f" · poll every {SCHEDULER_POLL_MS // 1000}s"
            )
        except Exception:
            pass

    def _stop_scheduler_runtime(self):
        """Stop polling and release the pending timer (graceful shutdown)."""
        self._scheduler_closing = True
        self._scheduler_polling_active = False
        after_id = getattr(self, "_scheduler_after_id", None)
        if after_id is not None:
            after_cancel = getattr(self.root, "after_cancel", None)
            if after_cancel is not None:
                try:
                    after_cancel(after_id)
                except Exception:
                    pass
            self._scheduler_after_id = None

    def close(self):
        # Stop the scheduler loop before releasing the store it depends on.
        self._stop_scheduler_runtime()
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
