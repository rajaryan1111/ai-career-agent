"""Scripted Tk flow tests against temporary databases.

They exercise the real widget tree with stubbed dialogs, so they need a usable
display. Where no display or Tkinter is available the module skips rather than
hiding a failure; CI without a virtual display will report the skips.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import tkinter as tk

    from career_agent import desktop
except Exception:  # Tkinter is missing or cannot initialise on this interpreter.
    tk = None
    desktop = None


def display_available() -> bool:
    """Return True only when a Tk window can actually be created.

    The probe runs in a child interpreter: some Tk builds abort the process
    instead of raising when no display is reachable, which would kill test
    collection before any skip could be reported.
    """
    if tk is None or desktop is None:
        return False
    if os.environ.get("CAREER_AGENT_SKIP_GUI_TESTS"):
        return False
    try:
        probe = subprocess.run(
            [sys.executable, "-c", "import tkinter; root = tkinter.Tk(); root.destroy()"],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


DISPLAY_AVAILABLE = display_available()


def find_button(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, tk.ttk.Button) and str(child.cget("text")) == text:
            return child
        found = find_button(child, text)
        if found is not None:
            return found
    return None


@unittest.skipUnless(DISPLAY_AVAILABLE, "a Tk display is required for GUI flow tests")
class GuiFlowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dialogs = []
        self.answers = {"yes": True, "file": ""}

        self.root = tk.Tk()
        self.root.withdraw()
        self.originals = {
            name: getattr(desktop.messagebox, name)
            for name in ("askyesno", "showinfo", "showwarning", "showerror")
        }
        self.original_open = desktop.filedialog.askopenfilename
        desktop.messagebox.askyesno = self._ask_yes_no
        for name in ("showinfo", "showwarning", "showerror"):
            setattr(desktop.messagebox, name, self._record(name))
        desktop.filedialog.askopenfilename = lambda **kwargs: self.answers["file"]
        self.addCleanup(self._teardown_dialogs)

        self.app = desktop.CareerAgentApp(self.root, Path(self.folder.name) / "gui.sqlite3")
        self.addCleanup(self._close_app)

    def _teardown_dialogs(self):
        for name, original in self.originals.items():
            setattr(desktop.messagebox, name, original)
        desktop.filedialog.askopenfilename = self.original_open

    def _close_app(self):
        try:
            self.app.store.close()
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _ask_yes_no(self, title="", message="", **kwargs):
        self.dialogs.append(("askyesno", str(title), str(message)))
        return self.answers["yes"]

    def _record(self, kind):
        def handler(title="", message="", **kwargs):
            self.dialogs.append((kind, str(title), str(message)))
        return handler

    def seed(self):
        from career_agent import ApplicationStatus, Availability, CandidateProfile, JobListing
        from career_agent import store as store_module

        self.app.store.save_profile(CandidateProfile(
            candidate_country="India", degree_discipline="ECE", study_status="undergraduate",
            graduation_year=2027, experience_years=0.5, skills=frozenset({"Python", "RAG"}),
        ))
        self.app.store.save_job(JobListing(
            listing_id="j1", source_id="manual", source_name="Manual entry",
            source_listing_url="https://jobs.example/role/1", employer_name="Example",
            role_title="AI Intern", availability_status=Availability.OPEN,
            employer_apply_url="https://employer.example/apply/1", location_text="Remote",
            work_mode="remote", role_type="internship", eligibility_scope="restricted",
            eligible_countries=("India",), allowed_degree_disciplines=("ECE",),
            allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027,),
            minimum_experience_years=0.0, maximum_experience_years=2.0,
            required_skills=frozenset({"Python"}), provenance_note="Checked the listing.",
        ))
        self.app.store.start_application("j1")
        self.app.store.save_tracker(
            self.app.store.get_tracker("j1").transition(ApplicationStatus.SHORTLISTED)
        )
        self.app._refresh_jobs()
        self.jobs_tree_select("j1")

    def jobs_tree_select(self, listing_id):
        self.app.jobs_tree.selection_set(listing_id)

    def test_prepare_records_prepared_state_and_history(self):
        from career_agent import ApplicationStatus

        self.seed()
        self.dialogs.clear()
        find_button(self.app.jobs_tab, "Prepare application").invoke()
        self.assertIs(self.app.store.get_tracker("j1").status, ApplicationStatus.PREPARED)
        self.assertIn("READINESS: READY", self.app.report.get("1.0", "end"))
        self.assertIs(self.app.store.list_events("j1")[-1].to_status, ApplicationStatus.PREPARED)

    def test_declined_preparation_changes_nothing(self):
        from career_agent import ApplicationStatus

        self.seed()
        self.dialogs.clear()
        self.answers["yes"] = False
        find_button(self.app.jobs_tab, "Prepare application").invoke()
        self.assertIs(self.app.store.get_tracker("j1").status, ApplicationStatus.SHORTLISTED)
        self.assertIn("cancelled", self.app.status.get())

    def test_declined_restore_keeps_existing_data(self):
        from copy import deepcopy

        from career_agent import build_export_payload
        from career_agent.export import write_export
        from career_agent.store import CareerStore

        source = CareerStore(Path(self.folder.name) / "source.sqlite3")
        self.addCleanup(source.close)
        source.save_profile(self.app.store.get_profile() or __import__("career_agent").CandidateProfile(candidate_country="India"))
        backup = Path(self.folder.name) / "backup.json"
        write_export(source, backup)

        self.seed()
        before = tuple(self.app.store.list_jobs())
        self.dialogs.clear()
        self.answers["yes"] = False
        self.answers["file"] = str(backup)
        find_button(self.app.tracker_tab, "Restore from backup…").invoke()
        self.assertEqual(tuple(self.app.store.list_jobs()), before)
        self.assertIn("cancelled", self.app.status.get())
        self.assertFalse([call for call in self.dialogs if call[0] == "showinfo"])

    def test_cancelled_file_chooser_touches_nothing(self):
        self.seed()
        self.dialogs.clear()
        self.answers["file"] = ""
        find_button(self.app.tracker_tab, "Restore from backup…").invoke()
        self.assertEqual(self.dialogs, [])
        self.assertIsNotNone(self.app.store.get_tracker("j1"))

    def test_resume_import_proposals_stay_unsaved_until_save_is_clicked(self):
        resume_file = Path(self.folder.name) / "resume.txt"
        resume_file.write_text(
            "Country: India\nSkills: Python, SQL\nGraduation year: 2027\n", encoding="utf-8"
        )
        self.answers["file"] = str(resume_file)
        self.answers["yes"] = True
        self.assertIsNone(self.app.store.get_profile())
        find_button(self.app.profile_tab, "Import resume (review)…").invoke()
        self.assertEqual(self.app.profile_vars["country"].get(), "India")
        self.assertEqual(self.app.profile_vars["skills"].get(), "Python, SQL")
        self.assertEqual(self.app.profile_vars["graduation_year"].get(), "2027")
        self.assertIsNone(self.app.store.get_profile(), "import must not save the profile")
        self.assertIn("Nothing was saved yet", self.app.status.get())

        find_button(self.app.profile_tab, "Save profile locally").invoke()
        self.assertEqual(self.app.store.get_profile().candidate_country, "India")

    def test_declined_resume_import_changes_nothing(self):
        resume_file = Path(self.folder.name) / "resume.txt"
        resume_file.write_text("Country: India\n", encoding="utf-8")
        self.answers["file"] = str(resume_file)
        self.answers["yes"] = False
        find_button(self.app.profile_tab, "Import resume (review)…").invoke()
        self.assertEqual(self.app.profile_vars["country"].get(), "")
        self.assertIn("cancelled", self.app.status.get())

    def test_sources_tab_reports_the_closed_gate(self):
        rows = {item: self.app.sources_tree.item(item, "values")
                for item in self.app.sources_tree.get_children()}
        self.assertEqual(set(rows), {"manual", "himalayas", "smartrecruiters"})
        self.assertEqual(rows["manual"][1], "supported")
        self.assertEqual(rows["himalayas"][1], "blocked")
        labels = [widget.cget("text") for widget in self.app.sources_tab.winfo_children()
                  if widget.winfo_class() == "TLabel"]
        self.assertTrue(any("discovery is disabled" in text for text in labels))
        self.assertTrue(any("gate: closed" in text for text in labels))

    def test_delete_all_local_data_clears_records_only_when_confirmed(self):
        self.seed()
        button = find_button(self.app.sources_tab, "Delete all local data…")
        self.dialogs.clear()
        self.answers["yes"] = False
        button.invoke()
        self.assertTrue(self.app.store.has_data())

        self.answers["yes"] = True
        button.invoke()
        self.assertFalse(self.app.store.has_data())
        self.assertEqual(self.app.profile_vars["country"].get(), "")
        self.assertIn("Deleted 1 profile, 1 job(s), 1 attempt(s)", self.app.status.get())

    def test_unsaved_profile_changes_are_confirmed_before_close(self):
        self.dialogs.clear()
        self.app.profile_vars["country"].set("India")
        self.answers["yes"] = False
        self.app.close()
        self.assertTrue(
            any(kind == "askyesno" and "Unsaved" in title for kind, title, _ in self.dialogs)
        )
        self.assertIn("Close cancelled", self.app.status.get())
        self.assertEqual(self.app.profile_vars["country"].get(), "India")

        self.answers["yes"] = True
        self.app.close()

    def test_clean_close_needs_no_confirmation(self):
        self.seed()
        self.dialogs.clear()
        self.app.close()
        self.assertEqual(self.dialogs, [])

    def test_no_error_dialog_is_raised_by_ordinary_flows(self):
        self.seed()
        self.dialogs.clear()
        find_button(self.app.jobs_tab, "Evaluate selected").invoke()
        self.assertFalse([call for call in self.dialogs if call[0] == "showerror"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
