"""Removing the local data: what is planned, what is refused, and what is never touched.

Every test here works in a temporary folder with synthetic files. The command deletes files, so the tests
that matter most are the ones about *not* deleting: a preview must not write, a folder passed as a database
must be refused, a symbolic link must be refused rather than followed, a file the application did not write
must survive, and an incomplete delete must not report success.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from career_agent import __main__ as cli
from career_agent.erasure import DataFile, ErasureError, erase, plan_erasure


class ErasureTestCase(unittest.TestCase):
    """A temporary folder holding the files this application writes, and one file it did not."""

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.folder = Path(self._temporary.name)
        self.database = self.folder / "career_agent.sqlite3"
        self.logs = self.folder / "logs"
        self.logs.mkdir()
        self.foreign = self.folder / "holiday-photo.jpg"

    def make_data(self) -> None:
        """Create one of everything the application writes for a database, plus a foreign file."""
        self.database.write_bytes(b"synthetic database bytes")
        for suffix in ("-journal", "-wal", "-shm"):
            self.database.with_name(self.database.name + suffix).write_bytes(b"synthetic sidecar")
        (self.folder / f"{self.database.name}.backup-20260101T000000Z").write_bytes(b"synthetic snapshot")
        (self.folder / f".{self.database.name}.restore-20260101T000000Z.partial").write_bytes(b"synthetic staged restore")
        (self.folder / f".{self.database.name}.rollback.partial").write_bytes(b"synthetic rollback")
        (self.logs / "application.log").write_text("synthetic log line\\n", encoding="utf-8")
        (self.logs / "startup-diagnostics.log").write_text("synthetic diagnostic\\n", encoding="utf-8")
        self.foreign.write_bytes(b"not the application's file")
        (self.logs / "something-else.log").write_text("not written by this application\\n", encoding="utf-8")

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        """Run the command line against this test's database.

        The database argument is appended, so a test that passes its own ``--database`` must use
        ``run_cli_raw`` instead: argparse keeps the last value, and silently measuring the wrong path is
        exactly how a check like this stops meaning anything.
        """
        return self.run_cli_raw(*arguments, "--database", str(self.database))

    def run_cli_raw(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(arguments))
        return code, out.getvalue(), err.getvalue()


class ErasurePlanTests(ErasureTestCase):
    """Planning names exactly the application's own files, and creates nothing."""

    def test_the_plan_covers_everything_the_application_writes_and_nothing_else(self):
        self.make_data()
        plan = plan_erasure(self.database)
        names = {item.path.name for item in plan.data_files}

        self.assertIn(self.database.name, names)
        for suffix in ("-journal", "-wal", "-shm"):
            self.assertIn(self.database.name + suffix, names)
        self.assertIn(f"{self.database.name}.backup-20260101T000000Z", names)
        self.assertIn(f".{self.database.name}.restore-20260101T000000Z.partial", names)
        self.assertIn(f".{self.database.name}.rollback.partial", names)
        self.assertIn("application.log", names)
        self.assertIn("startup-diagnostics.log", names)
        self.assertNotIn(self.foreign.name, names, "a file the application did not write is not in the plan")
        self.assertNotIn("something-else.log", names, "only the logs this application writes are named")
        self.assertGreater(plan.total_bytes, 0)
        self.assertTrue(all(isinstance(item, DataFile) and item.description for item in plan.data_files))

    def test_planning_writes_nothing(self):
        before = sorted(path.name for path in self.folder.rglob("*"))
        plan_erasure(self.database)
        after = sorted(path.name for path in self.folder.rglob("*"))
        self.assertEqual(before, after, "planning must not create a database, a folder or a log")
        self.assertEqual(sorted(path.name for path in self.logs.iterdir()), [])

    def test_a_plan_for_a_folder_with_no_data_removes_nothing(self):
        plan = plan_erasure(self.database)
        self.assertFalse(plan.anything_to_remove)
        self.assertEqual(plan.total_bytes, 0)
        self.assertTrue(plan.left_alone, "the report always says what it is leaving alone")

    def test_a_database_path_that_is_a_folder_is_refused(self):
        """Pointing --database at a folder must not delete the logs of whatever database lives there."""
        self.make_data()
        with self.assertRaises(ErasureError):
            plan_erasure(self.logs)

    @unittest.skipIf(os.name == "nt", "creating a symbolic link needs privileges on Windows")
    def test_a_symbolic_link_is_refused_rather_than_followed(self):
        elsewhere = self.folder / "somewhere-else.sqlite3"
        elsewhere.write_bytes(b"a database somewhere else")
        link = self.folder / "linked.sqlite3"
        link.symlink_to(elsewhere)
        with self.assertRaises(ErasureError):
            plan_erasure(link)

    @unittest.skipIf(os.name == "nt", "creating a symbolic link needs privileges on Windows")
    def test_a_link_among_the_candidates_is_left_alone_and_named(self):
        self.make_data()
        target = self.folder / "outside.log"
        target.write_text("not this application's file\\n", encoding="utf-8")
        (self.logs / "application.log").unlink()
        (self.logs / "application.log").symlink_to(target)

        plan = plan_erasure(self.database)
        outcome = erase(plan)

        # A candidate that is a link is refused at planning time, so it is never in the deletion list at
        # all: it is named in the report as left alone, and the file it points at is untouched.
        self.assertTrue(target.exists(), "deleting through a link would remove somebody else's file")
        self.assertNotIn(
            self.logs / "application.log", [item.path for item in plan.data_files],
            "a link is not a file this command may delete",
        )
        self.assertTrue(
            any(str(self.logs / "application.log") in note for note in plan.left_alone),
            plan.left_alone,
        )
        self.assertTrue(outcome.complete, "what remains is not a failure: it was never a candidate")

    def test_a_logs_folder_that_is_itself_a_link_is_not_deleted_through(self):
        self.make_data()
        elsewhere = self.folder / "elsewhere"
        elsewhere.mkdir()
        same_name = elsewhere / "application.log"
        same_name.write_text("a file in another folder that happens to share the name\n", encoding="utf-8")
        shutil.rmtree(self.logs)
        self.logs.symlink_to(elsewhere, target_is_directory=True)

        plan = plan_erasure(self.database)
        outcome = erase(plan)

        # The ``logs`` folder is the one directory this module derives from the database path, so a link
        # standing in for it says the folder is not this application's: the file behind the link shares a
        # name with a log this application writes and is nothing to do with it. Refusing is the only answer
        # that cannot delete somebody else's file.
        self.assertTrue(same_name.exists(), "deleting through a linked folder removes another folder's file")
        self.assertNotIn(
            self.logs / "application.log", [item.path for item in plan.data_files],
            "a file reached through a linked folder is not a file this command may delete",
        )
        self.assertTrue(
            any(str(self.logs) in note for note in plan.left_alone),
            plan.left_alone,
        )
        self.assertTrue(outcome.complete, "what remains is not a failure: it was never a candidate")
        # The database named on the command line is still removed: the refusal is about the derived
        # folder, not about the path the person chose.
        self.assertIn(self.database, outcome.removed)

    def test_a_database_name_with_glob_characters_does_not_capture_another_files_snapshot(self):
        # A person may name a database anything the filesystem allows, and ``[1]`` is a character class to
        # a glob: with the database named ``my[1].sqlite3``, the snapshot pattern matched
        # ``my1.sqlite3.backup-…``, which belongs to a different database, and the planner listed it for
        # deletion. The same held for the staged-restore pattern.
        bracketed = self.folder / "my[1].sqlite3"
        bracketed.write_bytes(b"synthetic database bytes")
        other_snapshot = self.folder / "my1.sqlite3.backup-20260101T000000Z"
        other_snapshot.write_bytes(b"another database's snapshot")
        other_staged = self.folder / ".my1.sqlite3.restore-20260101T000000Z.partial"
        other_staged.write_bytes(b"another database's staged restore")

        plan = plan_erasure(bracketed)
        outcome = erase(plan)

        self.assertTrue(other_snapshot.exists(), "another database's snapshot was deleted")
        self.assertTrue(other_staged.exists(), "another database's staged restore was deleted")
        self.assertNotIn(other_snapshot, [item.path for item in plan.data_files])
        self.assertNotIn(other_staged, [item.path for item in plan.data_files])
        self.assertIn(bracketed, outcome.removed, "the database that was named is still removed")

    def test_a_snapshot_of_the_named_database_is_still_found(self):
        # The other half of the rule: escaping the name must not stop the module from finding the files
        # that really do belong to the database it was pointed at.
        bracketed = self.folder / "my[1].sqlite3"
        bracketed.write_bytes(b"synthetic database bytes")
        own_snapshot = self.folder / "my[1].sqlite3.backup-20260101T000000Z"
        own_snapshot.write_bytes(b"this database's snapshot")
        own_staged = self.folder / ".my[1].sqlite3.restore-20260101T000000Z.partial"
        own_staged.write_bytes(b"this database's staged restore")

        plan = plan_erasure(bracketed)
        listed = [item.path for item in plan.data_files]
        outcome = erase(plan)

        self.assertIn(own_snapshot, listed, "the database's own snapshot must still be listed")
        self.assertIn(own_staged, listed, "the database's own staged restore must still be listed")
        self.assertTrue(outcome.complete, outcome.failed)


class ErasureExecutionTests(ErasureTestCase):
    """Carrying out the plan: complete, honest, and idempotent."""

    def test_it_removes_what_it_listed_and_leaves_everything_else(self):
        self.make_data()
        outcome = erase(plan_erasure(self.database))

        self.assertTrue(outcome.complete, outcome.failed)
        self.assertFalse(self.database.exists())
        for suffix in ("-journal", "-wal", "-shm"):
            self.assertFalse(self.database.with_name(self.database.name + suffix).exists())
        self.assertFalse((self.logs / "application.log").exists())
        self.assertFalse((self.logs / "startup-diagnostics.log").exists())
        self.assertTrue(self.foreign.exists(), "a foreign file survives")
        self.assertTrue((self.logs / "something-else.log").exists(), "a foreign log survives")
        self.assertTrue(self.logs.exists(), "the folder itself is not removed")

    def test_it_is_idempotent_and_does_not_create_anything(self):
        self.make_data()
        erase(plan_erasure(self.database))
        after_first = sorted(path.name for path in self.folder.rglob("*"))

        second = erase(plan_erasure(self.database))

        self.assertEqual(second.removed, ())
        self.assertTrue(second.complete)
        self.assertEqual(sorted(path.name for path in self.folder.rglob("*")), after_first)

    def test_a_path_that_changed_shape_is_not_deleted(self):
        """A plan acted on later must be re-checked; a folder in the list must not be removed."""
        self.make_data()
        plan = plan_erasure(self.database)
        replaced = plan.data_files[0].path
        replaced.unlink()
        replaced.mkdir()

        outcome = erase(plan)

        self.assertFalse(outcome.complete)
        self.assertTrue(replaced.is_dir(), "the folder is still there")
        self.assertTrue(any("no longer a regular file" in reason for _path, reason in outcome.failed))


class RecreationTests(ErasureTestCase):
    """A database that comes back must not be reported as gone."""

    def test_a_database_that_reappears_is_reported_rather_than_claimed_as_removed(self):
        """A worker in another terminal recreates the file it holds open; the report must say so."""
        from career_agent.erasure import ErasurePlan

        self.make_data()
        plan = ErasurePlan(database=self.database, data_files=(), left_alone=())
        # Something recreates the database between the plan and the removal: a running worker does this.
        outcome = erase(plan)

        self.assertFalse(outcome.complete)
        message = " ".join(reason for _path, reason in outcome.failed)
        self.assertIn("still there when the removal finished", message)

    def test_a_removal_that_completes_still_exits_zero(self):
        """The recreation check must not fail an ordinary, complete removal."""
        self.make_data()
        code, out, err = self.run_cli("--forget-local-data", "--yes")

        self.assertEqual(code, cli.EXIT_OK, (out, err))
        self.assertIn("Removed", out)
        self.assertNotIn("exists again", out + err)


class ForgetCommandTests(ErasureTestCase):
    """The command line: preview by default, delete only with --yes, and refuse the rest."""

    def test_without_yes_it_only_reports_what_would_be_removed(self):
        self.make_data()
        code, out, err = self.run_cli("--forget-local-data")

        self.assertEqual(code, cli.EXIT_OK, (out, err))
        self.assertIn("Would remove", out)
        self.assertIn("Nothing has been removed yet", out)
        self.assertIn("Left alone on purpose", out)
        self.assertTrue(self.database.exists(), "a preview must not delete")
        self.assertTrue((self.logs / "application.log").exists())

    def test_with_yes_it_removes_the_data_and_reports_what_it_leaves(self):
        self.make_data()
        code, out, err = self.run_cli("--forget-local-data", "--yes")

        self.assertEqual(code, cli.EXIT_OK, (out, err))
        self.assertFalse(self.database.exists())
        self.assertFalse((self.logs / "application.log").exists())
        self.assertTrue(self.foreign.exists())
        self.assertIn("Removed", out)
        self.assertIn("Left alone on purpose", out)
        self.assertIn("delete them yourself", out, "the report must not imply the whole machine is clean")

    def test_a_folder_with_nothing_in_it_is_reported_as_nothing_and_creates_nothing(self):
        before = sorted(path.name for path in self.folder.rglob("*"))
        code, out, _err = self.run_cli("--forget-local-data", "--yes")

        self.assertEqual(code, cli.EXIT_OK, out)
        self.assertIn("Nothing to remove", out)
        self.assertIn("nothing was created", out)
        self.assertEqual(sorted(path.name for path in self.folder.rglob("*")), before)

    def test_a_directory_as_the_database_is_refused_and_nothing_is_deleted(self):
        self.make_data()
        before = sorted(path.name for path in self.folder.rglob("*"))
        code, _out, err = self.run_cli_raw("--forget-local-data", "--yes", "--database", str(self.logs))

        self.assertEqual(code, cli.EXIT_REFUSED, err)
        self.assertIn("REFUSED", err)
        self.assertEqual(sorted(path.name for path in self.folder.rglob("*")), before, "nothing was deleted")

    def test_yes_on_its_own_is_refused_rather_than_ignored(self):
        code, _out, err = self.run_cli("--yes")

        self.assertEqual(code, cli.EXIT_REFUSED, err)
        self.assertIn("--yes only means something", err)

    def test_the_command_is_in_the_help_text(self):
        """The help is what a person reads before deleting anything, so the wording has to be there."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.parse_arguments(["--help"])

        help_text = out.getvalue()
        self.assertIn("--forget-local-data", help_text)
        self.assertIn("--yes", help_text)
        # argparse wraps the help text, so the check is on the words rather than on a line break
        flattened = " ".join(help_text.split())
        self.assertIn("Shows what it would remove unless --yes is given", flattened)


if __name__ == "__main__":
    unittest.main()
