import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_agent import paths


class DefaultDatabasePathTests(unittest.TestCase):
    def test_macos_location_is_not_created_until_requested(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.object(paths.platform, "system", return_value="Darwin"), \
                    mock.patch.dict(os.environ, {"HOME": home}):
                target = paths.default_database_path(create=False)
                self.assertEqual(
                    target,
                    Path(home) / "Library" / "Application Support" / "AI Career Agent" / "career_agent.sqlite3",
                )
                self.assertFalse(target.parent.exists())
                paths.default_database_path(create=True)
                self.assertTrue(target.parent.is_dir())

    def test_linux_uses_xdg_data_home_and_a_lowercase_folder(self):
        with tempfile.TemporaryDirectory() as xdg:
            with mock.patch.object(paths.platform, "system", return_value="Linux"), \
                    mock.patch.dict(os.environ, {"XDG_DATA_HOME": xdg}):
                target = paths.default_database_path(create=False)
                self.assertEqual(target, Path(xdg) / "ai-career-agent" / "career_agent.sqlite3")

    def test_windows_uses_localappdata(self):
        with tempfile.TemporaryDirectory() as base:
            with mock.patch.object(paths.platform, "system", return_value="Windows"), \
                    mock.patch.dict(os.environ, {"LOCALAPPDATA": base}):
                target = paths.default_database_path(create=False)
                self.assertEqual(target, Path(base) / "AI Career Agent" / "career_agent.sqlite3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
