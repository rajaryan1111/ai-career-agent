import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "smoke_check.py"
SPEC = importlib.util.spec_from_file_location("smoke_check", SCRIPT)
smoke_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke_check)


def completed(returncode):
    return mock.Mock(returncode=returncode, stdout="output", stderr="error")


class SmokeCheckTests(unittest.TestCase):
    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return smoke_check.main()

    def test_all_checks_passing_returns_zero(self):
        with mock.patch.object(smoke_check.subprocess, "run", return_value=completed(0)) as run:
            self.assertEqual(self.run_main(), 0)
        self.assertEqual(run.call_count, len(smoke_check.COMMANDS))

    def test_any_failure_returns_one(self):
        with mock.patch.object(
            smoke_check.subprocess, "run", side_effect=[completed(0), completed(3), completed(0), completed(0)]
        ):
            self.assertEqual(self.run_main(), 1)

    def test_check_list_covers_every_required_step(self):
        names = [name for name, _ in smoke_check.COMMANDS]
        self.assertEqual(
            names, ["unit tests", "tracker smoke test", "compileall", "CSV audit"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
