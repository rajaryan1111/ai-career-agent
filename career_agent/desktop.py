"""Offline-first Tkinter desktop workflow for AI Career Agent.

Launch with python -m career_agent. No network calls or external service dependencies.
"""
from __future__ import annotations
import json
import os
import platform
import re
import uuid
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import BOTH, END, LEFT, W, X, filedialog, messagebox, ttk

from .core import ApplicationStatus, ApplicationTracker, Availability, CandidateProfile, Decision, JobListing, evaluate_eligibility, score_relevance
from .store import CareerStore
from .validation import optional_float, optional_int, split_values


def default_database_path() -> Path:
    """Choose a per-user app-data directory; never put candidate data in the repository."""
    system = platform.system()
    if system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    folder = root / ("AI Career Agent" if system in {"Darwin", "Windows"} else "ai-career-agent")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "career_agent.sqlite3"


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
        self.tabs.add(self.profile_tab, text="Candidate profile")
        self.tabs.add(self.jobs_tab, text="Jobs & eligibility")
        self.tabs.add(self.tracker_tab, text="Application tracker")
        self.profile_vars = {}
        self.job_vars = {}
        self._build_profile()
        self._build_jobs()
        self._build_tracker()
        self.status = tk.StringVar(value=f"Local database: {self.db_path}")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor=W, padding=5).pack(fill=X, side="bottom")
        self._load_profile()
        self._refresh_jobs()

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
            ("Work authorization notes", "work_authorization", 3, 1, None), ("Skills (comma-separated)", "skills", 4, 0, None),
            ("Preferred locations", "locations", 4, 1, None), ("Preferred work modes", "work_modes", 5, 0, None),
            ("Preferred role types", "role_types", 5, 1, None),
        ]
        for label, key, row, col, choices in fields:
            self._entry(self.profile_tab, label, key, row, col, self.profile_vars, choices=choices)
        actions = ttk.Frame(self.profile_tab)
        actions.grid(row=6, column=0, columnspan=4, sticky=W, pady=12)
        ttk.Button(actions, text="Save profile locally", command=self._save_profile).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete saved profile", command=self._delete_profile).pack(side="left")
        ttk.Label(self.profile_tab, text="Privacy: no cloud sync, external AI API, resume upload, or data transfer is performed. Data stays in the local application-data folder.", wraplength=850).grid(row=7, column=0, columnspan=4, sticky=W, pady=8)

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
            ("Shortlist if eligible", self._shortlist), ("Delete selected", self._delete_job), ("Clear form", self._clear_form),
        ]:
            ttk.Button(actions, text=text, command=callback).pack(side="left", padx=(0, 6))
        self.jobs_tree = ttk.Treeview(self.jobs_tab, columns=("employer", "role", "availability", "status", "source"), show="headings", height=9)
        for col, label, width in [("employer", "Employer", 140), ("role", "Role", 170), ("availability", "Availability", 100), ("status", "Tracker status", 150), ("source", "Source", 190)]:
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
        self.tracker_tree = ttk.Treeview(self.tracker_tab, columns=("employer", "role", "status", "evidence"), show="headings")
        for col, label, width in [("employer", "Employer", 170), ("role", "Role", 200), ("status", "Status", 180), ("evidence", "Evidence / note", 420)]:
            self.tracker_tree.heading(col, text=label)
            self.tracker_tree.column(col, width=width, anchor=W)
        self.tracker_tree.pack(fill=BOTH, expand=True)
        self.tracker_tree.bind("<<TreeviewSelect>>", self._select_tracker)

    def _load_profile(self):
        profile = self.store.get_profile()
        if not profile:
            return
        values = {
            "country": profile.candidate_country or "", "degree": profile.degree_discipline or "",
            "study_status": profile.study_status or "", "graduation_year": str(profile.graduation_year or ""),
            "experience": "" if profile.experience_years is None else str(profile.experience_years),
            "work_authorization": profile.work_authorization or "", "skills": ", ".join(sorted(profile.skills)),
            "locations": ", ".join(sorted(profile.preferred_locations)), "work_modes": ", ".join(sorted(profile.preferred_work_modes)),
            "role_types": ", ".join(sorted(profile.preferred_role_types)),
        }
        for key, value in values.items():
            self.profile_vars[key].set(value)

    def _save_profile(self):
        try:
            v = self.profile_vars
            self.store.save_profile(CandidateProfile(
                candidate_country=v["country"].get().strip() or None,
                degree_discipline=v["degree"].get().strip() or None,
                study_status=v["study_status"].get().strip() or None,
                graduation_year=optional_int(v["graduation_year"].get(), "Graduation year"),
                experience_years=optional_float(v["experience"].get(), "Experience"),
                work_authorization=v["work_authorization"].get().strip() or None,
                skills=frozenset(split_values(v["skills"].get())),
                preferred_locations=frozenset(split_values(v["locations"].get())),
                preferred_work_modes=frozenset(split_values(v["work_modes"].get())),
                preferred_role_types=frozenset(split_values(v["role_types"].get())),
            ))
            self.status.set("Candidate profile saved locally.")
        except ValueError as exc:
            messagebox.showerror("Invalid profile", str(exc), parent=self.root)

    def _delete_profile(self):
        if not messagebox.askyesno("Delete profile", "Permanently delete the saved profile on this device?", parent=self.root):
            return
        self.store.delete_profile()
        for variable in self.profile_vars.values():
            variable.set("")
        self.status.set("Saved profile deleted.")

    def _job_from_form(self):
        v = self.job_vars
        employer, title, url = (v[key].get().strip() for key in ("employer", "title", "source_url"))
        if not employer or not title or not url:
            raise ValueError("Employer, role title, and source listing URL are required.")
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("Source listing URL must start with http:// or https://.")
        apply_url = v["apply_url"].get().strip() or None
        if apply_url and not re.match(r"^https?://", apply_url, re.I):
            raise ValueError("Employer apply URL must start with http:// or https://.")
        def items(key):
            values = split_values(v[key].get())
            return values or None
        years = tuple(int(item) for item in split_values(v["graduation_years"].get()))
        minimum, maximum = optional_float(v["min_exp"].get(), "Minimum experience"), optional_float(v["max_exp"].get(), "Maximum experience")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("Minimum experience cannot exceed maximum experience.")
        return JobListing(
            listing_id=self.selected_job_id or str(uuid.uuid4()), source_id="manual",
            source_name=v["source_name"].get().strip() or "Manual entry", source_listing_url=url,
            employer_name=employer, role_title=title, availability_status=Availability(v["availability"].get() or "unknown"),
            employer_apply_url=apply_url, canonical_requisition_id=v["requisition"].get().strip() or None,
            location_text=v["location"].get().strip() or None, work_mode=v["work_mode"].get().strip() or None,
            role_type=v["role_type"].get().strip() or None, eligibility_scope=v["scope"].get() or "unknown",
            eligible_countries=split_values(v["countries"].get()), allowed_work_authorizations=items("allowed_work_authorizations"), allowed_degree_disciplines=items("degrees"),
            allowed_study_statuses=items("study_statuses"), allowed_graduation_years=years or None,
            minimum_experience_years=minimum, maximum_experience_years=maximum,
            required_skills=frozenset(split_values(v["required_skills"].get())),
            provenance_note=v["provenance_note"].get().strip() or None,
        )

    def _save_job(self):
        try:
            job = self._job_from_form()
            existed = self.store.get_job(job.listing_id) is not None
            self.store.save_job(job)
            if not existed:
                self.store.save_tracker(ApplicationTracker(job.listing_id))
            self.selected_job_id = job.listing_id
            self._refresh_jobs()
            self.status.set(f"Saved {job.role_title} locally. Nothing was submitted.")
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Cannot save job", str(exc), parent=self.root)

    def _clear_form(self):
        self.selected_job_id = None
        for key, var in self.job_vars.items():
            var.set("unknown" if key in {"availability", "scope"} else "")
        self.jobs_tree.selection_remove(self.jobs_tree.selection())

    def _refresh_jobs(self):
        if not hasattr(self, "jobs_tree"):
            return
        for item in self.jobs_tree.get_children():
            self.jobs_tree.delete(item)
        for job in self.store.list_jobs():
            tracker = self.store.get_tracker(job.listing_id)
            self.jobs_tree.insert("", END, iid=job.listing_id, values=(
                job.employer_name, job.role_title, job.availability_status.value,
                tracker.status.value if tracker else "discovered", job.source_name,
            ))
        self._refresh_tracker()

    def _select_job(self, _event=None):
        selection = self.jobs_tree.selection()
        if not selection:
            return
        job = self.store.get_job(selection[0])
        if not job:
            return
        self.selected_job_id = job.listing_id
        values = {
            "employer": job.employer_name, "title": job.role_title, "source_name": job.source_name,
            "source_url": job.source_listing_url, "apply_url": job.employer_apply_url or "",
            "requisition": job.canonical_requisition_id or "", "availability": job.availability_status.value,
            "scope": job.eligibility_scope, "work_mode": job.work_mode or "", "role_type": job.role_type or "",
            "location": job.location_text or "", "countries": ", ".join(job.eligible_countries),
            "degrees": ", ".join(job.allowed_degree_disciplines or []),
            "allowed_work_authorizations": ", ".join(job.allowed_work_authorizations or []),
            "study_statuses": ", ".join(job.allowed_study_statuses or []),
            "graduation_years": ", ".join(map(str, job.allowed_graduation_years or [])),
            "min_exp": "" if job.minimum_experience_years is None else str(job.minimum_experience_years),
            "max_exp": "" if job.maximum_experience_years is None else str(job.maximum_experience_years),
            "required_skills": ", ".join(sorted(job.required_skills)), "provenance_note": job.provenance_note or "",
        }
        for key, value in values.items():
            self.job_vars[key].set(value)
        self._report(f"Selected {job.role_title} at {job.employer_name}\nSource listing: {job.source_listing_url}\nEmployer application URL: {job.employer_apply_url or 'Not verified / not supplied'}\nAvailability evidence: {job.provenance_note or 'Not supplied'}")

    def _evaluate(self):
        listing_id = self.selected_job_id or (self.jobs_tree.selection()[0] if self.jobs_tree.selection() else None)
        if not listing_id:
            messagebox.showinfo("Select a job", "Save or select a job first.", parent=self.root)
            return
        job, profile = self.store.get_job(listing_id), self.store.get_profile()
        if not profile:
            messagebox.showinfo("Profile required", "Save your candidate profile first. Missing facts are never inferred.", parent=self.root)
            self.tabs.select(self.profile_tab)
            return
        report = evaluate_eligibility(profile, job)
        relevance = score_relevance(profile, job)
        lines = [f"ELIGIBILITY: {report.decision.value.upper()}", "Only explicit PASS is eligible. UNKNOWN is not eligible.", ""]
        lines += [f"[{item.decision.value.upper()}] {item.requirement}: {item.explanation}" for item in report.requirements]
        lines += ["", f"Skill overlap: {relevance.get('skill_overlap', 'n/a')} (not a hiring probability)",
                  "Matched skills: " + (", ".join(relevance.get("matched_skills", [])) or "None recorded"),
                  "Missing required skills: " + (", ".join(relevance.get("missing_required_skills", [])) or "None recorded")]
        self._report("\n".join(lines))
        self.status.set(f"Eligibility for {job.role_title}: {report.decision.value}.")

    def _shortlist(self):
        listing_id = self.selected_job_id or (self.jobs_tree.selection()[0] if self.jobs_tree.selection() else None)
        if not listing_id:
            messagebox.showinfo("Select a job", "Select a saved job first.", parent=self.root)
            return
        job, profile = self.store.get_job(listing_id), self.store.get_profile()
        if not profile:
            messagebox.showinfo("Profile required", "Save your candidate profile first.", parent=self.root)
            return
        report = evaluate_eligibility(profile, job)
        if report.decision is not Decision.PASS:
            messagebox.showwarning("Not eligible to shortlist", f"Eligibility is {report.decision.value.upper()}. Resolve unknown/failed requirements first.", parent=self.root)
            self._evaluate()
            return
        try:
            tracker = self.store.get_tracker(listing_id) or ApplicationTracker(listing_id)
            self.store.save_tracker(tracker.transition(ApplicationStatus.SHORTLISTED))
            self._refresh_jobs()
            self.status.set("Job shortlisted locally. No external action was taken.")
        except ValueError as exc:
            messagebox.showerror("Cannot shortlist", str(exc), parent=self.root)

    def _delete_job(self):
        listing_id = self.selected_job_id or (self.jobs_tree.selection()[0] if self.jobs_tree.selection() else None)
        if not listing_id:
            messagebox.showinfo("Select a job", "Select a job to delete.", parent=self.root)
            return
        if messagebox.askyesno("Delete job", "Permanently delete this job and its tracker history?", parent=self.root):
            self.store.delete_job(listing_id)
            self.selected_job_id = None
            self._clear_form()
            self._refresh_jobs()
            self._report("Job and associated tracker record deleted locally.")

    def _refresh_tracker(self):
        if not hasattr(self, "tracker_tree"):
            return
        for item in self.tracker_tree.get_children():
            self.tracker_tree.delete(item)
        for job in self.store.list_jobs():
            tracker = self.store.get_tracker(job.listing_id) or ApplicationTracker(job.listing_id)
            self.tracker_tree.insert("", END, iid=job.listing_id, values=(
                job.employer_name, job.role_title, tracker.status.value, tracker.status_evidence or "",
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
        tracker = self.store.get_tracker(listing_id) or ApplicationTracker(listing_id)
        dialog = tk.Toplevel(self.root)
        dialog.title("Update application status")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=f"Current status: {tracker.status.value}").pack(anchor=W, padx=12, pady=(12, 5))
        status_var, evidence_var = tk.StringVar(), tk.StringVar()
        ttk.Label(dialog, text="New status").pack(anchor=W, padx=12)
        ttk.Combobox(dialog, textvariable=status_var, values=[x.value for x in ApplicationStatus], state="readonly", width=30).pack(fill=X, padx=12, pady=4)
        ttk.Label(dialog, text="Evidence / note (required to confirm)").pack(anchor=W, padx=12, pady=(8, 0))
        ttk.Entry(dialog, textvariable=evidence_var, width=48).pack(fill=X, padx=12, pady=4)
        def apply():
            try:
                new_status = ApplicationStatus(status_var.get())
                updated = tracker.transition(new_status, evidence=evidence_var.get().strip() or None, candidate_confirmed=True if new_status is ApplicationStatus.CONFIRMED else None)
                self.store.save_tracker(updated)
                dialog.destroy()
                self._refresh_jobs()
                self.status.set(f"Application status updated to {new_status.value}.")
            except (ValueError, KeyError) as exc:
                messagebox.showerror("Invalid status change", str(exc), parent=dialog)
        ttk.Button(dialog, text="Save status", command=apply).pack(anchor="e", padx=12, pady=12)

    def _export(self):
        destination = filedialog.asksaveasfilename(parent=self.root, title="Export local data", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not destination:
            return
        profile = self.store.get_profile()
        payload = {"format_version": 1, "profile": asdict(profile) if profile else None, "jobs": [],
                   "privacy_note": "Export may contain personal information; store securely."}
        if payload["profile"]:
            for key, value in payload["profile"].items():
                if isinstance(value, (set, frozenset, tuple)):
                    payload["profile"][key] = sorted(value)
        for job in self.store.list_jobs():
            record = asdict(job)
            record["availability_status"] = job.availability_status.value
            for key, value in record.items():
                if isinstance(value, (set, frozenset, tuple)):
                    record[key] = sorted(value)
            tracker = self.store.get_tracker(job.listing_id)
            record["application_tracker"] = {
                "status": tracker.status.value, "status_evidence": tracker.status_evidence,
                "candidate_confirmed": tracker.candidate_confirmed,
            } if tracker else None
            payload["jobs"].append(record)
        try:
            Path(destination).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            self.status.set(f"Exported {len(payload['jobs'])} jobs to a user-selected local file.")
            messagebox.showinfo("Export complete", "JSON export created. Keep it private; it may contain personal data.", parent=self.root)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)

    def _report(self, text):
        if not hasattr(self, "report"):
            return
        self.report.configure(state="normal")
        self.report.delete("1.0", END)
        self.report.insert("1.0", text)
        self.report.configure(state="disabled")

    def close(self):
        self.store.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        CareerAgentApp(root)
    except Exception as exc:
        messagebox.showerror("AI Career Agent could not start", str(exc), parent=root)
        root.destroy()
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
