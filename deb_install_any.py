#!/usr/bin/env python3
"""Robust installer for locally built .deb artifacts."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

os.environ.setdefault("DEBIAN_FRONTEND", "noninteractive")
REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_HELPER_SCRIPT = (REPO_ROOT / "build-helpers.sh").resolve()
BROKEN_BUILD_DEPS_PACKAGE = "agiros-pixiu-canopen-core-build-deps"
AUTO_KILL_LOCK_HOLDERS = os.environ.get("AGIROS_AUTO_KILL_LOCK_HOLDERS", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}
APT_LOCK_PATH = Path(os.environ.get("AGIROS_APT_LOCKFILE", "/mnt/lfb_ws/.locks/apt.lock"))
APT_LOCK_TIMEOUT = int(os.environ.get("AGIROS_APT_LOCK_TIMEOUT", "3600"))
APT_WAIT_FOR_LOCK = os.environ.get("AGIROS_APT_WAIT_FOR_LOCK", "1").strip().lower() not in {"0", "false", "no"}
APT_LOCK_WAIT_TIMEOUT = int(os.environ.get("AGIROS_APT_LOCK_WAIT_TIMEOUT", "600"))
APT_LOCK_WAIT_INTERVAL = float(os.environ.get("AGIROS_APT_LOCK_WAIT_INTERVAL", "5"))
APT_MAX_RETRIES = int(os.environ.get("AGIROS_APT_MAX_RETRIES", "3"))
LOCK_FILES = (Path("/var/lib/dpkg/lock-frontend"), Path("/var/lib/dpkg/lock"))
APT_LOCK_PATH = Path(os.environ.get("AGIROS_APT_LOCKFILE", "/mnt/lfb_ws/.locks/apt.lock"))
APT_LOCK_TIMEOUT = int(os.environ.get("AGIROS_APT_LOCK_TIMEOUT", "3600"))


def print_info(message: str) -> None:
    print(f"[INFO] {message}")


def print_warn(message: str) -> None:
    print(f"[WARN] {message}", file=sys.stderr)


def run_cmd(cmd: Sequence[str], *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
    print_info(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)


_APT_GUARD_MISSING_WARNED = False


def get_helper_script() -> Path:
    override = os.environ.get("AGIROS_BUILD_HELPERS")
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_HELPER_SCRIPT


def run_apt_guard() -> None:
    global _APT_GUARD_MISSING_WARNED
    helper = get_helper_script()
    if not helper.exists():
        if not _APT_GUARD_MISSING_WARNED:
            print_warn(f"Apt guard script not found at {helper}, skipping dpkg state cleanup.")
            _APT_GUARD_MISSING_WARNED = True
        return
    run_with_lock_retries(
        ["bash", "-c", f"source '{helper}' && fix_and_clean_broken_agiros"],
        check=False,
        use_apt_lock=True,
    )


def wrap_with_apt_lock(cmd: Sequence[str], *, enable: bool = True) -> List[str]:
    if not enable:
        return list(cmd)
    if not APT_LOCK_PATH:
        return list(cmd)
    try:
        APT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print_warn(f"Failed to ensure apt lock directory: {exc}")
        return list(cmd)
    if cmd and cmd[0] == "flock":
        return list(cmd)
    return ["flock", "-w", str(APT_LOCK_TIMEOUT), str(APT_LOCK_PATH), *cmd]


def _print_process_output(proc: subprocess.CompletedProcess) -> None:
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    sys.stdout.flush()
    sys.stderr.flush()


def _extract_lock_pids(output: str) -> Set[int]:
    pids: Set[int] = set()
    for match in re.findall(r"process(?:\\D+)?(\\d+)", output, flags=re.IGNORECASE):
        try:
            pids.add(int(match))
        except ValueError:
            continue
    return pids


def _maybe_print_process_details(pids: Set[int]) -> None:
    if not pids:
        return
    try:
        proc = subprocess.run(
            ["ps", "-p", ",".join(str(pid) for pid in sorted(pids)), "-o", "pid,ppid,etimes,cmd"],
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.stdout:
            print_info("Lock holders:")
            sys.stdout.write(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        print_warn(f"Unable to describe lock holders: {exc}")


def _print_related_package_processes() -> None:
    patterns = ("apt-get", " apt ", "dpkg", "mk-build-deps", "dpkg-buildpackage", "debuild_runner")
    try:
        proc = subprocess.run(
            ["ps", "axo", "pid,ppid,etimes,cmd"],
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        print_warn(f"Unable to list related processes: {exc}")
        return
    if not proc.stdout:
        return
    lines = proc.stdout.splitlines()
    header, *rows = lines
    matches = [line for line in rows if any(pattern in line for pattern in patterns)]
    if matches:
        print_info("Related package processes (ps axo pid,ppid,etimes,cmd):")
        print(header)
        for line in matches:
            print(line)


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_processes(pids: Iterable[int]) -> None:
    victims = {pid for pid in pids if pid not in {os.getpid(), os.getppid()}}
    if not victims:
        return
    print_warn(f"Attempting to terminate lock holders: {', '.join(str(pid) for pid in sorted(victims))}")
    for sig, desc in ((signal.SIGTERM, "TERM"), (signal.SIGKILL, "KILL")):
        try:
            for pid in list(victims):
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    continue
                except PermissionError:
                    print_warn(f"No permission to send {desc} to PID {pid}")
            if sig == signal.SIGTERM:
                time.sleep(5)
        finally:
            victims = {pid for pid in victims if _is_process_alive(pid)}
            if not victims:
                break


def _wait_for_lock_release() -> bool:
    if not APT_WAIT_FOR_LOCK or APT_LOCK_WAIT_TIMEOUT <= 0:
        return False
    print_info(f"Waiting up to {APT_LOCK_WAIT_TIMEOUT}s for dpkg/apt lock to clear...")
    start = time.time()
    while time.time() - start < APT_LOCK_WAIT_TIMEOUT:
        busy = False
        for lock in LOCK_FILES:
            if not lock.exists():
                continue
            try:
                proc = subprocess.run(
                    ["fuser", str(lock)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if proc.returncode == 0:
                    busy = True
                    break
            except FileNotFoundError:
                if not lock.exists():
                    continue
            except Exception as exc:  # noqa: BLE001
                print_warn(f"Unable to probe lock {lock}: {exc}")
        if not busy:
            return True
        time.sleep(APT_LOCK_WAIT_INTERVAL)
    print_warn(f"Lock still held after waiting {APT_LOCK_WAIT_TIMEOUT}s.")
    return False


def _fix_dpkg_state() -> None:
    for cmd in (["dpkg", "--configure", "-a"], ["apt-get", "-f", "install", "-y"]):
        effective_cmd = wrap_with_apt_lock(cmd, enable=True)
        proc = subprocess.run(effective_cmd, text=True, capture_output=True, check=False)
        _print_process_output(proc)
        if proc.returncode != 0:
            print_warn(f"{' '.join(cmd)} returned {proc.returncode}")


def _purge_broken_build_deps() -> None:
    if not BROKEN_BUILD_DEPS_PACKAGE:
        return
    cmd = ["apt-get", "remove", "--purge", "-y", BROKEN_BUILD_DEPS_PACKAGE]
    effective_cmd = wrap_with_apt_lock(cmd, enable=True)
    proc = subprocess.run(effective_cmd, text=True, capture_output=True, check=False)
    _print_process_output(proc)
    if proc.returncode != 0:
        print_warn(f"Failed to purge {BROKEN_BUILD_DEPS_PACKAGE}, continuing.")


def _handle_lock_and_recover(cmd: Sequence[str], combined_output: str) -> tuple[bool, bool]:
    lock_keywords = (
        "could not get lock",
        "unable to acquire the dpkg frontend lock",
        "is another process using it?",
        "is locked by another process",
        "dpkg was interrupted",
    )
    lower_output = combined_output.lower()
    pids = _extract_lock_pids(combined_output)
    has_lock = bool(pids) or any(keyword in lower_output for keyword in lock_keywords)
    if not has_lock:
        return (False, False)

    print_warn(f"Detected apt/dpkg lock while running: {' '.join(cmd)}")
    if pids:
        _maybe_print_process_details(pids)
    _print_related_package_processes()

    waited = False
    if _wait_for_lock_release():
        print_info("Lock released after waiting, will retry command.")
        return (True, False)
    if APT_WAIT_FOR_LOCK:
        waited = True

    if not AUTO_KILL_LOCK_HOLDERS:
        if waited:
            print_warn("Auto-kill disabled (AGIROS_AUTO_KILL_LOCK_HOLDERS=0); waited but lock persists, skipping recovery.")
        else:
            print_warn("Auto-kill disabled (AGIROS_AUTO_KILL_LOCK_HOLDERS=0), skipping recovery.")
        return (False, False)

    _terminate_processes(pids or [])
    _fix_dpkg_state()
    _purge_broken_build_deps()
    _fix_dpkg_state()
    return (True, True)


def run_with_lock_retries(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    max_retries: int | None = None,
    use_apt_lock: bool = False,
) -> subprocess.CompletedProcess:
    attempts = 0
    effective_max = APT_MAX_RETRIES if max_retries is None else max_retries
    last_proc: Optional[subprocess.CompletedProcess] = None
    while attempts <= effective_max:
        effective_cmd = wrap_with_apt_lock(cmd, enable=use_apt_lock)
        print_info(f"$ {' '.join(effective_cmd)}")
        proc = subprocess.run(
            effective_cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            check=False,
        )
        _print_process_output(proc)
        if proc.returncode == 0:
            return proc

        combined = (proc.stdout or "") + "\\n" + (proc.stderr or "")
        should_retry, consume_attempt = _handle_lock_and_recover(cmd, combined)
        if attempts < effective_max and should_retry:
            if consume_attempt:
                attempts += 1
            print_info("Retrying command after handling apt/dpkg lock...")
            continue

        last_proc = proc
        break

    if check and last_proc is not None:
        raise subprocess.CalledProcessError(
            last_proc.returncode,
            cmd,
            output=last_proc.stdout,
            stderr=last_proc.stderr,
        )
    return last_proc if last_proc is not None else proc


def parse_changelog_name(pkg_dir: Path) -> Optional[str]:
    changelog = pkg_dir / "debian" / "changelog"
    if not changelog.exists():
        return None
    try:
        first_line = changelog.read_text(encoding="utf-8").splitlines()[0]
    except Exception:
        return None
    parts = first_line.split()
    return parts[0] if parts else None


def find_deb_candidates(pkg_dir: Path, pkg_name: Optional[str]) -> List[Path]:
    parent = pkg_dir.parent
    pattern = f"{pkg_name}_*.deb" if pkg_name else "*.deb"
    candidates = [path for path in parent.glob(pattern) if path.is_file()]
    filtered = [path for path in candidates if "-dbgsym_" not in path.name]
    if filtered:
        candidates = filtered
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def package_name_from_deb(deb_path: Path) -> str:
    proc = subprocess.run(
        ["dpkg-deb", "-f", str(deb_path), "Package"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0:
        name = proc.stdout.strip()
        if name:
            return name
    return deb_path.name.split("_", 1)[0]


def query_dpkg_status(pkg_name: str) -> str:
    proc = subprocess.run(
        ["dpkg-query", "-W", "-f", "${db:Status-Abbrev}", pkg_name],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def purge_broken_package(pkg_name: str, assume_yes: bool) -> None:
    if not pkg_name:
        return
    status = query_dpkg_status(pkg_name)
    if not status:
        print_info(f"[CLEAN] Package {pkg_name} not installed, no purge needed.")
        return
    if status.startswith("ii"):
        print_info(f"[CLEAN] Package {pkg_name} already installed cleanly.")
        return
    print_warn(f"[CLEAN] Purging half-installed package {pkg_name} (status={status})")
    cmd = ["apt-get", "remove", "--purge"]
    if assume_yes:
        cmd.append("-y")
    cmd.append(pkg_name)
    run_cmd(cmd, check=False)


def apt_update() -> None:
    run_apt_guard()
    proc = run_with_lock_retries(["apt-get", "update"], check=False, use_apt_lock=True)
    if proc.returncode != 0:
        print_warn("apt-get update returned non-zero, continuing.")


def apt_fix(assume_yes: bool) -> None:
    cmd = ["apt-get", "-o", "Debug::pkgProblemResolver=yes", "-f", "install"]
    if assume_yes:
        cmd.append("-y")
    run_with_lock_retries(cmd, check=False, use_apt_lock=True)


def try_install_deb(path: Path) -> bool:
    proc = run_with_lock_retries(["dpkg", "-i", str(path)], check=False, use_apt_lock=True)
    return proc.returncode == 0


def install_deb_with_recovery(path: Path, assume_yes: bool, allow_warning: bool) -> bool:
    pkg_name = package_name_from_deb(path)
    print_info(f"Installing {path}")
    run_apt_guard()
    if try_install_deb(path):
        print_info(f"Installed {path.name}")
        return True

    print_warn("dpkg -i failed, attempting apt-get -f install.")
    apt_fix(assume_yes)
    if try_install_deb(path):
        print_info(f"Installed {path.name}")
        return True

    print_warn(f"Failed to install {path.name} after dependency fix attempts.")
    purge_broken_package(pkg_name, assume_yes)
    run_apt_guard()
    if allow_warning:
        print_warn(
            f"Treating install failure of {pkg_name or path.name} as warning. "
            "Deb has been purged to avoid blocking later installs."
        )
        return True
    return False


def gather_directory_debs(directory: Path) -> List[Path]:
    files = sorted(
        path for path in directory.glob("*.deb") if path.is_file()
    )
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install local .deb files with dependency fixups.")
    parser.add_argument(
        "target",
        nargs="?",
        help=".deb file or directory containing .deb files to install.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Package directory to auto-detect latest artifact (default: WORK_DIR env or current directory).",
    )
    parser.add_argument("--no-assume-yes", action="store_true", help="Do not pass -y to apt-get -f install.")
    parser.add_argument(
        "--allow-install-fail-as-warning",
        action="store_true",
        help="Purge broken packages and continue with warning when installation fails.",
    )
    return parser.parse_args()


def resolve_targets(args: argparse.Namespace) -> List[Path]:
    if args.target:
        target = Path(args.target).resolve()
        if target.is_file():
            if target.suffix != ".deb":
                raise SystemExit(f"[ERR ] Not a .deb file: {target}")
            return [target]
        if target.is_dir():
            files = gather_directory_debs(target)
            if not files:
                raise SystemExit(f"[ERR ] Directory does not contain .deb files: {target}")
            return files
        raise SystemExit(f"[ERR ] Target path not found: {target}")

    work_dir = args.work_dir or Path(os.environ.get("WORK_DIR", Path.cwd()))
    work_dir = work_dir.resolve()
    if not work_dir.exists():
        raise SystemExit(f"[ERR ] work_dir does not exist: {work_dir}")
    pkg_name = parse_changelog_name(work_dir)
    candidates = find_deb_candidates(work_dir, pkg_name)
    if not candidates:
        raise SystemExit("[ERR ] No .deb artifacts were found near the work directory.")
    print_info(f"Selected {candidates[0].name} from {work_dir.parent}")
    return [candidates[0]]


def main() -> None:
    args = parse_args()
    assume_yes = not args.no_assume_yes
    targets = resolve_targets(args)
    apt_update()
    failed: List[str] = []
    for deb in targets:
        if not install_deb_with_recovery(deb, assume_yes, args.allow_install_fail_as_warning):
            failed.append(deb.name)
    if failed:
        raise SystemExit(f"[ERR ] Installation failed for: {', '.join(failed)}")
    print_info("All packages installed.")


if __name__ == "__main__":
    main()
