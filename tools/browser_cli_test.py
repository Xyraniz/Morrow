import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import browser_cli


class BrowserCliTest(unittest.TestCase):

    def test_help_is_available_without_a_source_tree(self):
        output = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(output):
            browser_cli.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("build", output.getvalue())
        self.assertIn("doctor", output.getvalue())

    def test_format_candidates_keep_only_supported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "base" / "sample.cc"
            source.parent.mkdir()
            source.write_text("int main() {}\n", encoding="utf-8")
            text = root / "README.md"
            text.write_text("sample\n", encoding="utf-8")
            with mock.patch.object(browser_cli, "ROOT", root), mock.patch.object(
                browser_cli,
                "_git_paths",
                return_value=[source, text],
            ):
                self.assertEqual(browser_cli._format_candidates([]), [source])

    def test_default_binary_uses_platform_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            binary = output / "chrome"
            binary.write_text("", encoding="utf-8")
            with mock.patch.object(browser_cli.platform, "system", return_value="Linux"):
                self.assertEqual(browser_cli._default_browser_binary(output), binary)

    def test_passthrough_separator_is_not_forwarded(self):
        self.assertEqual(browser_cli._passthrough_args(["--", "--flag"]), ["--flag"])
        self.assertEqual(browser_cli._passthrough_args(["--flag"]), ["--flag"])

    def test_virtualenv_names_are_restricted(self):
        self.assertIsNone(browser_cli._python_interpreter("bad/name"))


if __name__ == "__main__":
    unittest.main()
