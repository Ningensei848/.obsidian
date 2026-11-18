#!/usr/bin/env python3
"""Deploy this configuration and its templates using only Python's standard library."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile


SOURCE = Path(__file__).resolve().parents[1]
STATIC_CONFIGS = ("core-plugins.json", "file-recovery.json", "switcher.json", "templates.json")
PLUGIN_FILES = ("manifest.json", "main.js", "styles.css", "obsidian_askpass.sh")


class SetupError(Exception):
    def __init__(self, code, stage, scope, **details):
        super().__init__(code)
        self.record = dict(code=code, stage=stage, scope=scope, **details)


def event(code, *, error=False, **details):
    print(json.dumps(dict(code=code, **details), ensure_ascii=False),
          file=sys.stderr if error else sys.stdout)


def read(path):
    try:
        return path.read_bytes()
    except OSError as cause:
        raise SetupError("FILE_READ_FAILED", "read", str(path),
                         error_type=type(cause).__name__, errno=cause.errno) from cause


def parse_json(data, scope):
    try:
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as cause:
        raise SetupError("INVALID_JSON", "preflight", str(scope),
                         error_type=type(cause).__name__,
                         line=getattr(cause, "lineno", None),
                         column=getattr(cause, "colno", None)) from cause


def same_content(path, expected, actual):
    if expected == actual:
        return True
    if actual is None or path.suffix != ".json":
        return False
    # Obsidian の保存で変わる改行コード・ファイル末尾の空白だけは競合にしない。
    def normalize(data):
        return data.replace(b"\r\n", b"\n").rstrip(b" \t\r\n")
    return normalize(expected) == normalize(actual)


def relative_path(value, *, root=False):
    if root and value in ("", "/"):
        return Path()
    if not isinstance(value, str) or not value or "\\" in value:
        raise SetupError("INVALID_VAULT_PATH", "preflight", "settings")
    path = Path(value)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise SetupError("INVALID_VAULT_PATH", "preflight", "settings")
    if not path.parts or path.parts[0].startswith("."):
        raise SetupError("INVALID_VAULT_PATH", "preflight", "settings")
    return path


def check_target(path, vault, *, directory=False):
    if not path.is_relative_to(vault):
        raise SetupError("TARGET_OUTSIDE_VAULT", "preflight", str(path))
    current = vault
    for part in path.relative_to(vault).parts:
        current = current / part
        if current.is_symlink():
            raise SetupError("TARGET_SYMLINK", "preflight", str(current))
        if current.exists() and current != path and not current.is_dir():
            raise SetupError("PARENT_NOT_DIRECTORY", "preflight", str(current))
    if path.exists() and path.is_dir() != directory:
        raise SetupError("TARGET_TYPE_MISMATCH", "preflight", str(path))


def make_plan(source, vault):
    config = vault / ".obsidian"
    files = {}
    directories = {config}

    def add(src, dest):
        if src.is_symlink():
            raise SetupError("SOURCE_SYMLINK", "preflight", str(src))
        data = read(src)
        if src.suffix == ".json":
            parse_json(data, src)
        if dest in files:
            raise SetupError("DUPLICATE_TARGET", "preflight", str(dest))
        files[dest] = (data, src.stat().st_mode & 0o777)

    for name in STATIC_CONFIGS:
        add(source / name, config / name)
    for src in sorted(source.glob("*.default.json")):
        add(src, config / src.name.replace(".default.json", ".json"))
    bundled_plugins = set()
    for plugin in sorted((source / "plugins").iterdir()):
        if plugin.is_symlink():
            raise SetupError("SOURCE_SYMLINK", "preflight", str(plugin))
        if not plugin.is_dir():
            continue
        manifest = parse_json(read(plugin / "manifest.json"), plugin / "manifest.json")
        if not isinstance(manifest, dict) or manifest.get("id") != plugin.name:
            raise SetupError("PLUGIN_DIRECTORY_ID_MISMATCH", "preflight", str(plugin))
        if not (plugin / "main.js").is_file() or not read(plugin / "main.js"):
            raise SetupError("PLUGIN_MAIN_MISSING", "preflight", plugin.name)
        bundled_plugins.add(plugin.name)
        for name in PLUGIN_FILES:
            src = plugin / name
            if src.exists():
                add(src, config / "plugins" / plugin.name / name)
        preset = plugin / "data.default.json"
        if preset.exists():
            add(preset, config / "plugins" / plugin.name / "data.json")
        elif (plugin / "data.json").is_file():
            add(plugin / "data.json", config / "plugins" / plugin.name / "data.json")

    enabled_plugins = parse_json(files[config / "community-plugins.json"][0], "community-plugins.json")
    if not isinstance(enabled_plugins, list) or not all(isinstance(value, str) for value in enabled_plugins):
        raise SetupError("INVALID_PLUGIN_LIST", "preflight", "community-plugins.json")
    for plugin_id in enabled_plugins:
        if plugin_id not in bundled_plugins:
            raise SetupError("ENABLED_PLUGIN_NOT_BUNDLED", "preflight", plugin_id)

    def settings(name):
        return parse_json(files[config / name][0], name)

    templater = settings("plugins/templater-obsidian/data.json")
    template_dir = relative_path(templater["templates_folder"])
    if relative_path(templater["user_scripts_folder"]) != template_dir:
        raise SetupError("SCRIPT_FOLDER_MISMATCH", "preflight", "templater")
    if relative_path(settings("templates.json")["folder"]) != template_dir:
        raise SetupError("TEMPLATE_FOLDER_MISMATCH", "preflight", "templates")
    template_source = source / "__Template"
    if template_source.is_symlink():
        raise SetupError("SOURCE_SYMLINK", "preflight", str(template_source))
    for src in sorted(template_source.rglob("*")):
        if src.is_symlink():
            raise SetupError("SOURCE_SYMLINK", "preflight", str(src))
        if src.is_file():
            add(src, vault / template_dir / src.relative_to(template_source))

    daily = settings("daily-notes.json")
    for reference in [daily["template"], *(rule["template"] for rule in templater["folder_templates"])]:
        path = relative_path(reference)
        if not path.suffix:
            path = path.with_suffix(".md")
        if vault / path not in files:
            raise SetupError("TEMPLATE_NOT_BUNDLED", "preflight", str(path))

    app_settings = settings("app.json")
    folders = [str(template_dir), daily["folder"],
               *(rule["folder"] for rule in templater["folder_templates"])]
    if app_settings.get("newFileLocation") == "folder":
        folders.append(app_settings["newFileFolderPath"])
    attachment = app_settings.get("attachmentFolderPath", "")
    if attachment not in ("", "/", ".", "./") and not attachment.startswith("./"):
        folders.append(attachment)
    for folder in folders:
        directories.add(vault / relative_path(folder, root=True))
    for dest in files:
        directories.add(dest.parent)
        check_target(dest, vault)
    for dest in directories:
        check_target(dest, vault, directory=True)
    return files, directories


def write_atomic(path, data, mode):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".obsidian-setup-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError as cause:
                event("TEMP_CLEANUP_FAILED", error=True, stage="cleanup", scope=str(path),
                      error_type=type(cause).__name__, errno=cause.errno, attempts=1,
                      retry="not_attempted")


def activate(args, vault):
    executable = args.obsidian_cli or shutil.which("obsidian")
    if not executable and os.name == "nt":
        executable = shutil.which("Obsidian.com")
    if not executable:
        raise SetupError("OBSIDIAN_CLI_NOT_FOUND", "activate", "templater-local-settings")
    script = read(SOURCE / "scripts" / "enable-templater.js").decode("utf-8")
    code = "(async()=>{const module={exports:null};\n" + script
    code += "\nreturn await module.exports(" + json.dumps(str(vault)) + ");})()"
    try:
        result = subprocess.run([executable, f"vault={args.obsidian_vault or vault.name}",
                                 "eval", f"code={code}"], cwd=vault,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as cause:
        raise SetupError("OBSIDIAN_CLI_FAILED", "activate", "templater-local-settings",
                         error_type=type(cause).__name__, errno=getattr(cause, "errno", None)) from cause
    output = result.stdout + result.stderr
    causes = ("VAULT_MISMATCH", "CONFIG_DIR_MISMATCH", "TEMPLATER_NOT_LOADED", "ACTIVATION_NOT_SAVED")
    known = next((code for code in causes if f"DOT_OBSIDIAN_{code}" in output), None)
    marker = "DOT_OBSIDIAN_TEMPLATER_ENABLED"
    def is_confirmation(line):
        value = line.strip()
        if value.startswith("=> "):
            value = value[3:].strip()
        return value in (marker, json.dumps(marker), repr(marker))
    confirmed = any(is_confirmation(line) for line in result.stdout.splitlines())
    if result.returncode or known or not confirmed:
        # CLI の生出力には文書やプラグインのログが含まれ得るため記録しない。
        raise SetupError(known or "OBSIDIAN_CLI_RESULT_UNCONFIRMED", "activate",
                         "templater-local-settings", exit_code=result.returncode)
    event("TEMPLATER_AUTO_CREATE_ENABLED", stage="activate")


def main(argv=None):
    # Windows のリダイレクト時も、JSONL は常に UTF-8 とする。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, help="Vault root; optional when this repository is .obsidian")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without writing or activating")
    parser.add_argument("--overwrite", action="store_true", help="Back up differing files outside the Vault, then replace them")
    parser.add_argument("--activate", action="store_true", help="Enable automatic templates using a running Obsidian CLI")
    parser.add_argument("--obsidian-cli", help="Obsidian CLI executable, including a Windows .com path")
    parser.add_argument("--obsidian-vault", help="Registered Vault name or ID for CLI activation")
    args = parser.parse_args(argv)
    completed = 0
    backup = None
    stage = "preflight"
    scope = "setup"
    try:
        if args.vault is None and SOURCE.name != ".obsidian":
            raise SetupError("VAULT_REQUIRED", stage, "--vault")
        vault = (args.vault or SOURCE.parent).expanduser().resolve()
        config = vault / ".obsidian"
        if vault.exists() and not vault.is_dir():
            raise SetupError("VAULT_NOT_DIRECTORY", stage, str(vault))
        if SOURCE != config and (vault.is_relative_to(SOURCE) or SOURCE.is_relative_to(vault)):
            raise SetupError("SOURCE_TARGET_OVERLAP", stage, str(vault))
        files, directories = make_plan(SOURCE, vault)
        changes = []
        conflicts = []
        for path, (data, mode) in files.items():
            old = read(path) if path.exists() else None
            if same_content(path, data, old):
                continue
            changes.append((path, data, mode, old))
            if old is not None:
                conflicts.append((path, old))
            event("WOULD_REPLACE" if old is not None else "WOULD_CREATE", scope=str(path.relative_to(vault)))
        missing_dirs = [path for path in directories if not path.exists()]
        if args.dry_run:
            event("DRY_RUN", files=len(changes), folders=len(missing_dirs), conflicts=len(conflicts),
                  activation=args.activate, overwrite_required=bool(conflicts and not args.overwrite))
            return 0
        if conflicts and not args.overwrite:
            raise SetupError("EXISTING_CONTENT_DIFFERS", stage, "files", affected=len(conflicts))
        if conflicts:
            stage = "backup"
            temp = Path(tempfile.gettempdir()).resolve()
            if temp.is_relative_to(vault) or temp.is_relative_to(SOURCE):
                raise SetupError("BACKUP_LOCATION_UNSAFE", stage, "temporary-directory")
            backup = Path(tempfile.mkdtemp(prefix="dot-obsidian-backup-"))
            event("BACKUP_CREATED", scope=str(backup))
            for path, old in conflicts:
                scope = str(path.relative_to(vault))
                if read(path) != old:
                    raise SetupError("FILE_CHANGED_DURING_SETUP", stage, scope)
                dest = backup / path.relative_to(vault)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(old)
                shutil.copystat(path, dest)
        stage = "write"
        for directory in sorted(directories, key=lambda path: len(path.parts)):
            scope = str(directory.relative_to(vault))
            check_target(directory, vault, directory=True)
            directory.mkdir(parents=True, exist_ok=True)
        for path, data, mode, old in changes:
            scope = str(path.relative_to(vault))
            check_target(path, vault)
            now = read(path) if path.exists() else None
            if now != old:
                raise SetupError("FILE_CHANGED_DURING_SETUP", stage, scope)
            write_atomic(path, data, mode)
            completed += 1
        event("FILES_READY", changed=completed, unchanged=len(files) - completed,
              backup=str(backup) if backup else None)
        if args.activate:
            stage, scope = "activate", "templater-local-settings"
            activate(args, vault)
        else:
            event("ACTIVATION_NOT_REQUESTED", scope="templater-local-settings",
                  next_step="--activate or enable Trigger Templater on new file creation in this Vault")
        return 0
    except Exception as cause:
        details = cause.record if isinstance(cause, SetupError) else dict(
            code="OS_ERROR" if isinstance(cause, OSError) else "UNKNOWN_FAILURE",
            stage=stage, scope=scope, error_type=type(cause).__name__,
            errno=getattr(cause, "errno", None))
        event(error=True, **details, completed_files=completed,
              backup=str(backup) if backup else None, attempts=1, retry="not_attempted")
        return 1


if __name__ == "__main__":
    sys.exit(main())
