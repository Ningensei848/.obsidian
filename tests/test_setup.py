"""Exercise actual deployments in OS temporary directories, without touching a Vault."""

import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("obsidian_setup", Path(__file__).resolve().parents[1] / "scripts" / "setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="dot-obsidian-test-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.source = self.root / "source with spaces"
        self.source.mkdir()
        for name in ("core-plugins.json", "file-recovery.json", "switcher.json", "templates.json"):
            shutil.copy2(ROOT / name, self.source / name)
        for path in ROOT.glob("*.default.json"):
            shutil.copy2(path, self.source / path.name)
        for name in ("scripts", "__Template"):
            shutil.copytree(ROOT / name, self.source / name, ignore=shutil.ignore_patterns("__pycache__"))
        for plugin in (ROOT / "plugins").iterdir():
            if not plugin.is_dir() or plugin.is_symlink():
                continue
            target = self.source / "plugins" / plugin.name
            target.mkdir(parents=True)
            for name in ("manifest.json", "data.default.json", "data.json"):
                if (plugin / name).is_file():
                    shutil.copy2(plugin / name, target / name)
            # The installer must copy only known payloads, not arbitrary files.
            (target / "main.js").write_text("// test plugin payload\n", encoding="utf-8")
            (target / "private.txt").write_text("PRIVATE_NOT_FOR_DEPLOYMENT", encoding="utf-8")
        self.vault = self.root / "新規 Vault with spaces"

    def run_setup(self, *args, expected=0, env=None):
        result = subprocess.run([sys.executable, str(self.source / "scripts" / "setup.py"),
                                 "--vault", str(self.vault), *args], cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def snapshot(self):
        return {str(path.relative_to(self.vault)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.vault.rglob("*") if path.is_file()}

    def test_fresh_vault_materializes_presets_templates_and_folders(self):
        self.run_setup()
        for preset in self.source.rglob("*.default.json"):
            destination = self.vault / ".obsidian" / str(preset.relative_to(self.source)).replace(".default.json", ".json")
            self.assertEqual(destination.read_bytes(), preset.read_bytes())
            self.assertTrue(preset.exists())
        self.assertFalse(list((self.vault / ".obsidian").rglob("*.default.json")))
        for template in (self.source / "__Template").iterdir():
            self.assertEqual((self.vault / "__Template" / template.name).read_bytes(), template.read_bytes())
        for name in ("MyWork/Daily", "MyWork/Misc", "__Attachment"):
            self.assertTrue((self.vault / name).is_dir())
        for name in ("docs", "tmp", "scripts", "tests"):
            self.assertFalse((self.vault / name).exists())
        self.assertFalse(list(self.vault.rglob("private.txt")))

    def test_second_run_does_not_rewrite_files(self):
        self.run_setup()
        before = self.snapshot()
        result = self.run_setup()
        self.assertEqual(before, self.snapshot())
        self.assertIn('"changed": 0', result.stdout)

    def test_dry_run_writes_nothing(self):
        self.run_setup("--dry-run", "--activate")
        self.assertFalse(self.vault.exists())

    def test_conflict_aborts_before_any_writes(self):
        self.run_setup()
        (self.vault / "__Template" / "Daily.md").write_text("My own daily template", encoding="utf-8")
        (self.vault / ".obsidian" / "app.json").unlink()
        before = self.snapshot()
        result = self.run_setup(expected=1)
        self.assertIn("EXISTING_CONTENT_DIFFERS", result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertNotIn("My own daily template", result.stdout + result.stderr)

    def test_overwrite_backs_up_outside_vault_and_preserves_notes(self):
        self.run_setup()
        target = self.vault / "__Template" / "Daily.md"
        target.write_text("Local customization", encoding="utf-8")
        note = self.vault / "MyWork" / "Daily" / "Existing.md"
        note.write_text("USER_NOTE", encoding="utf-8")
        result = self.run_setup("--overwrite")
        records = [json.loads(line) for line in result.stdout.splitlines()]
        backup = Path(next(item["scope"] for item in records if item["code"] == "BACKUP_CREATED"))
        self.addCleanup(shutil.rmtree, backup)
        self.assertFalse(backup.is_relative_to(self.vault))
        self.assertFalse(backup.is_relative_to(self.source))
        self.assertEqual((backup / "__Template" / "Daily.md").read_text(encoding="utf-8"), "Local customization")
        self.assertEqual(target.read_bytes(), (self.source / "__Template" / "Daily.md").read_bytes())
        self.assertEqual(note.read_text(encoding="utf-8"), "USER_NOTE")

    def test_invalid_json_records_location_without_content(self):
        (self.source / "daily-notes.default.json").write_text('{"SECRET_SENTINEL": invalid}', encoding="utf-8")
        result = self.run_setup(expected=1)
        self.assertIn("INVALID_JSON", result.stderr)
        self.assertIn('"line": 1', result.stderr)
        self.assertNotIn("SECRET_SENTINEL", result.stdout + result.stderr)
        self.assertFalse(self.vault.exists())

    def test_unsafe_linux_and_windows_paths_are_rejected(self):
        preset = self.source / "daily-notes.default.json"
        data = json.loads(preset.read_text(encoding="utf-8"))
        for folder in ("../escape", "/absolute", "C:/Windows", "C:\\Windows", "//server/share"):
            with self.subTest(folder=folder):
                data["folder"] = folder
                preset.write_text(json.dumps(data), encoding="utf-8")
                result = self.run_setup(expected=1)
                self.assertIn("INVALID_VAULT_PATH", result.stderr)
                self.assertFalse(self.vault.exists())

    def test_symlinked_destination_does_not_modify_target(self):
        self.vault.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "Daily.md"
        sentinel.write_text("DO_NOT_OVERWRITE", encoding="utf-8")
        try:
            (self.vault / "__Template").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {type(error).__name__}")
        result = self.run_setup("--overwrite", expected=1)
        self.assertIn("TARGET_SYMLINK", result.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "DO_NOT_OVERWRITE")
        self.assertFalse((self.vault / ".obsidian").exists())

    def test_missing_template_fails_before_writing(self):
        (self.source / "__Template" / "Daily.md").unlink()
        result = self.run_setup(expected=1)
        self.assertIn("TEMPLATE_NOT_BUNDLED", result.stderr)
        self.assertFalse(self.vault.exists())

    def test_missing_cli_reports_activation_failure_after_files_ready(self):
        env = dict(os.environ, PATH="")
        result = self.run_setup("--activate", expected=1, env=env)
        self.assertIn("FILES_READY", result.stdout)
        self.assertIn("OBSIDIAN_CLI_NOT_FOUND", result.stderr)
        self.assertIn('"stage": "activate"', result.stderr)
        self.assertTrue((self.vault / "__Template" / "Daily.md").is_file())

    def test_clone_as_dot_obsidian_needs_no_vault_argument(self):
        self.vault.mkdir()
        config = self.vault / ".obsidian"
        shutil.move(self.source, config)
        result = subprocess.run([sys.executable, str(config / "scripts" / "setup.py"), "--overwrite"],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        records = [json.loads(line) for line in result.stdout.splitlines()]
        backup_record = next((item for item in records if item["code"] == "BACKUP_CREATED"), None)
        if backup_record:
            self.addCleanup(shutil.rmtree, backup_record["scope"])
        self.assertTrue((self.vault / "__Template" / "Daily.md").is_file())
        self.assertTrue((config / "daily-notes.default.json").is_file())
        self.assertTrue((config / "daily-notes.json").is_file())

    def test_activation_passes_executable_and_vault_as_separate_arguments(self):
        args = SimpleNamespace(obsidian_cli="C:\\Program Files\\Obsidian\\Obsidian.com",
                               obsidian_vault="registered-vault-id")
        result = subprocess.CompletedProcess([], 0, '"DOT_OBSIDIAN_TEMPLATER_ENABLED"\n', "")
        with patch.object(setup.subprocess, "run", return_value=result) as run:
            with patch("sys.stdout", new_callable=io.StringIO):
                setup.activate(args, self.vault)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [args.obsidian_cli, "vault=registered-vault-id", "eval"])
        self.assertTrue(command[3].startswith("code="))
        self.assertEqual(run.call_args.kwargs["cwd"], self.vault)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_activation_does_not_accept_marker_inside_an_error_dump(self):
        args = SimpleNamespace(obsidian_cli="obsidian", obsidian_vault=None)
        output = "Script failed: return 'DOT_OBSIDIAN_TEMPLATER_ENABLED'; DOCUMENT_SECRET"
        result = subprocess.CompletedProcess([], 0, output, "")
        with patch.object(setup.subprocess, "run", return_value=result):
            with self.assertRaises(setup.SetupError) as raised:
                setup.activate(args, self.vault)
        self.assertEqual(raised.exception.record["code"], "OBSIDIAN_CLI_RESULT_UNCONFIRMED")
        self.assertNotIn("DOCUMENT_SECRET", str(raised.exception.record))

    def test_activation_keeps_confirmed_cause_without_logging_raw_cli_output(self):
        args = SimpleNamespace(obsidian_cli="obsidian", obsidian_vault=None)
        result = subprocess.CompletedProcess([], 1, "", "DOT_OBSIDIAN_VAULT_MISMATCH DOCUMENT_SECRET")
        with patch.object(setup.subprocess, "run", return_value=result):
            with self.assertRaises(setup.SetupError) as raised:
                setup.activate(args, self.vault)
        self.assertEqual(raised.exception.record["code"], "VAULT_MISMATCH")
        self.assertEqual(raised.exception.record["exit_code"], 1)
        self.assertNotIn("DOCUMENT_SECRET", str(raised.exception.record))


if __name__ == "__main__":
    unittest.main()
