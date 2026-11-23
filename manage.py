#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MIN_DJANGO = (5, 2)


def _venv_python() -> Path | None:
    for candidate in (BASE_DIR / "venv" / "Scripts" / "python.exe", BASE_DIR / "venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return None


def _ensure_project_venv() -> None:
    """Re-run this command with the project's venv if started by another Python.

    A global Python may carry an older Django (e.g. 5.1, which crashes on
    Python 3.14), so `python manage.py ...` must always use venv/.
    """
    venv_python = _venv_python()
    if venv_python is None or os.environ.get("FKF_NO_VENV_REEXEC"):
        return
    if Path(sys.prefix).resolve() == venv_python.parent.parent.resolve():
        return
    env = {**os.environ, "FKF_NO_VENV_REEXEC": "1"}
    try:
        sys.exit(subprocess.call([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]], env=env))
    except KeyboardInterrupt:
        sys.exit(130)


def main():
    """Run administrative tasks."""
    _ensure_project_venv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fkf_league.settings")
    try:
        import django
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Create the virtual environment and install "
            "dependencies: python -m venv venv && venv/Scripts/python -m pip install -r requirements.txt"
        ) from exc
    if django.VERSION[:2] < MIN_DJANGO:
        sys.exit(
            f"Django {django.get_version()} found, but this project needs "
            f"{MIN_DJANGO[0]}.{MIN_DJANGO[1]}+ (see requirements.txt). "
            "Run: venv/Scripts/python -m pip install -r requirements.txt"
        )
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
