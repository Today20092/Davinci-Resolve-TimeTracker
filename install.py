"""Cross-platform installer for Resolve Time Tracker."""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_URL = "https://github.com/Today20092/Davinci-Resolve-TimeTracker.git"
PYTHON_VERSION = "3.13"
STARTUP_SCRIPT_NAME = "ResolveTimeTrackerBackground.cmd"


def is_source_checkout(path: Path) -> bool:
    return (
        (path / "pyproject.toml").is_file()
        and (path / "scripts" / "ResolveTimeTracker.py").is_file()
        and (path / "scripts" / "install_resolve_menu.py").is_file()
    )


def default_source_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "ResolveTimeTracker" / "source"


def source_dir_for(installer_path: Path, requested: Path | None) -> Path:
    if requested is not None:
        return requested.expanduser().resolve()
    here = installer_path.resolve().parent
    if is_source_checkout(here):
        return here
    return default_source_dir()


def prerequisite_errors(source_dir: Path) -> list[str]:
    errors = []
    if not is_source_checkout(source_dir) and shutil.which("git") is None:
        errors.append("Git is required to download the project source.")
    pnpm = "pnpm.cmd" if os.name == "nt" else "pnpm"
    if shutil.which(pnpm) is None:
        errors.append("Node.js with pnpm is required to build the desktop app.")
    return errors


def ensure_source(source_dir: Path, repo_url: str, update: bool) -> None:
    if is_source_checkout(source_dir):
        print(f"[3/7] Using existing source checkout: {source_dir}", flush=True)
        git = shutil.which("git")
        if update and git is not None and (source_dir / ".git").is_dir():
            print("[3/7] Updating source checkout...", flush=True)
            run([git, "pull", "--ff-only"], cwd=source_dir)
        return
    if source_dir.exists():
        raise RuntimeError(
            f"{source_dir} exists but is not a Resolve Time Tracker checkout"
        )
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to clone Resolve Time Tracker source")
    source_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"[3/7] Cloning source to {source_dir}", flush=True)
    run([git, "clone", repo_url, str(source_dir)])


def uv_command() -> list[str] | None:
    configured = os.environ.get("RESOLVE_TIME_TRACKER_UV")
    if configured:
        return [configured]
    uv = shutil.which("uv")
    if uv is not None:
        return [uv]
    try:
        run([sys.executable, "-m", "uv", "--version"])
    except (subprocess.CalledProcessError, OSError):
        return None
    return [sys.executable, "-m", "uv"]


@contextmanager
def preserve_source(source_dir: Path, repo_url: str, update: bool):
    target = source_dir.resolve()
    existed = target.exists()
    previous_head = None
    git = shutil.which("git")
    if update and existed and git and (target / ".git").exists():
        if run([git, "status", "--porcelain"], cwd=target).strip():
            raise RuntimeError(
                "The source checkout has local changes. Save them before upgrading."
            )
        previous_head = run([git, "rev-parse", "HEAD"], cwd=target).strip()
    try:
        ensure_source(target, repo_url, update)
        yield
    except BaseException:
        if previous_head and git:
            # --keep refuses to overwrite local changes made during the attempt.
            run([git, "reset", "--keep", previous_head], cwd=target)
        elif not existed and target.is_dir():
            if target.is_symlink() or target.resolve() != source_dir.resolve():
                raise RuntimeError(
                    f"Refusing to remove changed installation path: {target}"
                )
            shutil.rmtree(target)
        raise


def ensure_uv() -> list[str]:
    command = uv_command()
    if command is not None:
        print(f"[4/7] Using uv: {' '.join(command)}", flush=True)
        return command
    raise RuntimeError(
        "uv is required. Run install.ps1 on Windows or install.sh on macOS/Linux."
    )


def venv_python(source_dir: Path) -> Path | None:
    if os.name == "nt":
        candidates = [
            source_dir / ".venv" / "Scripts" / "python.exe",
            source_dir / ".venv" / "Scripts" / "pythonw.exe",
        ]
    else:
        candidates = [
            source_dir / ".venv" / "bin" / "python",
            source_dir / ".venv" / "bin" / "pythonw",
        ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def install_menu(source_dir: Path, uv: list[str], utility_dir: Path | None) -> Path:
    print("[6/7] Installing Python dependencies...", flush=True)
    run([*uv, "sync", "--python", PYTHON_VERSION], cwd=source_dir)
    python = venv_python(source_dir)
    if python is None:
        raise RuntimeError(
            f"uv sync did not create a virtualenv Python under {source_dir / '.venv'}"
        )
    command = [
        *uv,
        "run",
        "--python",
        PYTHON_VERSION,
        "scripts/install_resolve_menu.py",
    ]
    if utility_dir is not None:
        command.extend(["--utility-dir", str(utility_dir)])
    print("[7/7] Installing DaVinci Resolve menu script...", flush=True)
    output = run(command, cwd=source_dir)
    target = Path(output.strip().splitlines()[-1])
    verify_menu_script(target, source_dir)
    return target


def windows_startup_dir() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def windows_launcher_paths() -> list[Path]:
    programs = windows_startup_dir().parent
    desktop = Path.home() / "Desktop"
    if os.name == "nt":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            desktop = Path(os.path.expandvars(winreg.QueryValueEx(key, "Desktop")[0]))
    return [
        programs / "DaVinci Resolve + Time Tracker.lnk",
        desktop / "DaVinci Resolve + Time Tracker.lnk",
        programs / "Resolve Time Tracker Dashboard.lnk",
    ]


@contextmanager
def preserve_launchers(paths: list[Path]):
    previous = {p: p.read_bytes() if p.is_file() else None for p in paths}
    try:
        yield
    except BaseException:
        for target, content in previous.items():
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        raise


def install_launchers(source_dir: Path) -> list[Path]:
    if platform.system() != "Windows":
        return []
    python = source_dir / ".venv" / "Scripts" / "pythonw.exe"
    if not python.is_file():
        python = venv_python(source_dir)
    if python is None:
        raise RuntimeError("Python environment is missing")
    targets = windows_launcher_paths()
    legacy = windows_startup_dir() / STARTUP_SCRIPT_NAME

    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    with preserve_launchers([*targets, legacy]):
        for index, target in enumerate(targets):
            target.parent.mkdir(parents=True, exist_ok=True)
            arguments = subprocess.list2cmdline(
                [
                    str(source_dir.resolve() / "scripts" / "ResolveTimeTracker.py"),
                    "--companion" if index == 2 else "--tracked-launch",
                ]
            )
            script = (
                "$ErrorActionPreference='Stop'; "
                "$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut("
                + quote(target)
                + "); "
                "$shortcut.TargetPath=" + quote(python) + "; "
                "$shortcut.Arguments=" + quote(arguments) + "; "
                "$shortcut.WorkingDirectory=" + quote(source_dir.resolve()) + "; "
                "$shortcut.Save()"
            )
            encoded = base64.b64encode(script.encode("utf-16-le")).decode()
            run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded,
                ]
            )
        legacy.unlink(missing_ok=True)
    return targets


def confirm_install(*, default: bool = True) -> bool:
    if not sys.stdin.isatty():
        return default
    answer = input("Do you want to continue? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def install_frontend(source_dir: Path) -> None:
    frontend_dir = source_dir / "frontend"
    if not (frontend_dir / "package.json").is_file():
        print(
            "[5/7] No frontend package found; skipping Electron companion.", flush=True
        )
        return
    pnpm = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is required to install the Electron companion")
    print("[5/7] Installing and building Electron companion...", flush=True)
    run([pnpm, "install", "--frozen-lockfile"], cwd=frontend_dir)
    run([pnpm, "exec", "electron", "--version"], cwd=frontend_dir)
    run([pnpm, "run", "build"], cwd=frontend_dir)


@contextmanager
def preserve_build(source_dir: Path):
    """Build replacements separately; restore the working environment on failure."""
    root = source_dir.resolve()
    targets = [
        root / ".venv",
        root / "frontend" / "node_modules",
        root / "frontend" / "dist",
    ]
    for target in targets:
        if target.is_symlink() or (
            target.exists() and not target.resolve().is_relative_to(root)
        ):
            raise RuntimeError(
                f"Cannot replace linked installation directory: {target}"
            )
    backup_root = Path(tempfile.mkdtemp(prefix=".install-backup-", dir=root))
    backups = []
    prepared = False
    try:
        for index, target in enumerate(targets):
            backup = backup_root / str(index)
            if target.exists():
                target.rename(backup)
                backups.append((target, backup))
        prepared = True
        yield
    except BaseException:
        # If setup itself failed, untouched originals must remain untouched.
        for target in targets if prepared else [item[0] for item in backups]:
            if target.exists():
                if target.is_symlink() or not target.resolve().is_relative_to(root):
                    raise RuntimeError(
                        f"Refusing to remove linked build directory: {target}"
                    )
                shutil.rmtree(target)
        for target, backup in backups:
            backup.rename(target)
        # A restore failure leaves the backup directory for recovery.
        shutil.rmtree(backup_root)
        raise
    else:
        shutil.rmtree(backup_root)


def verify_menu_script(target: Path, source_dir: Path) -> None:
    if not target.is_file():
        raise RuntimeError(f"Resolve menu script was not created: {target}")
    text = target.read_text(encoding="utf-8")
    if str(source_dir.resolve()) not in text or "--tracked-launch" not in text:
        raise RuntimeError(
            f"Resolve menu script does not point at this checkout: {target}"
        )


def run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Resolve Time Tracker for DaVinci Resolve"
    )
    parser.add_argument(
        "--source-dir", type=Path, help="Existing or new Resolve Time Tracker checkout"
    )
    parser.add_argument("--repo-url", default=REPO_URL)
    parser.add_argument(
        "--utility-dir", type=Path, help="Override Resolve Scripts/Utility folder"
    )
    parser.add_argument(
        "--startup",
        choices=["ask", "manual", "auto"],
        default="ask",
        help="Legacy option, ignored: tracking now starts only with Tracked Launch",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    installer_path = Path(__file__)
    source_dir = source_dir_for(installer_path, args.source_dir)
    print("Plan:", flush=True)
    print(f"  - Source checkout: {source_dir}", flush=True)
    print(
        "  - Install/update frontend dependencies if the companion app is present.",
        flush=True,
    )
    print("  - Install the DaVinci Resolve Scripts menu entry.", flush=True)
    print("  - Close Resolve and the dashboard before replacing the build.", flush=True)
    print(
        "  - Create Tracked Launch and dashboard shortcuts; remove legacy startup.",
        flush=True,
    )
    print("", flush=True)
    errors = prerequisite_errors(source_dir)
    if errors:
        raise RuntimeError("\n".join(errors))
    if not confirm_install():
        print("Install cancelled.")
        return 0
    update_source = args.source_dir is None and not is_source_checkout(
        installer_path.resolve().parent
    )
    with preserve_source(source_dir, args.repo_url, update_source):
        uv = ensure_uv()
        sys.path.insert(0, str(source_dir))
        from scripts.install_resolve_menu import (
            default_utility_dir,
            MENU_SCRIPT_NAME,
            DEV_MENU_SCRIPT_NAME,
        )

        utility = args.utility_dir or default_utility_dir()
        artifacts = [utility / MENU_SCRIPT_NAME, utility / DEV_MENU_SCRIPT_NAME]
        if platform.system() == "Windows":
            artifacts += [
                *windows_launcher_paths(),
                windows_startup_dir() / STARTUP_SCRIPT_NAME,
            ]
        with preserve_launchers(artifacts), preserve_build(source_dir):
            install_frontend(source_dir)
            target = install_menu(source_dir, uv, args.utility_dir)
            launchers = install_launchers(source_dir)
    print(f"Source: {source_dir}")
    print(f"Resolve menu script: {target}")
    for launcher in launchers:
        print(f"Shortcut: {launcher}")
    print("Use DaVinci Resolve + Time Tracker to start editing with tracking.")
    print("Open Resolve Time Tracker Dashboard for reports. Nothing starts at login.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stdout:
            print(exc.stdout, file=sys.stderr)
        raise SystemExit(1)
