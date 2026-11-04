"""Run an explicit project script through the native application lifecycle."""

import os
import sys
import tempfile
from pathlib import Path

from joplin_purifier_session import private_environment, session


def run_project(project, script, state, environment, sdk, fonts, xvfb, dbus, output):
    project = Path(project).resolve()
    state = Path(state).resolve()
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="launch-", dir=state) as temporary:
        root = Path(temporary)
        env, bus = private_environment(root, os.environ.copy(), fonts)
        status_file = root / "status"
        error_file = root / "error"
        env.update(
            JOPLIN_PURIFIER_ENVIRONMENT=str(environment),
            JOPLIN_PURIFIER_SCRIPT=str(Path(script).resolve()),
            JOPLIN_PURIFIER_STATUS=str(status_file),
            JOPLIN_PURIFIER_ERROR=str(error_file),
            JOPLIN_PURIFIER_OUTPUT=str(Path(output).resolve()),
        )
        status = session(
            [
                Path(sdk) / "bin/joplin-desktop",
                "--ozone-platform=x11",
                "--disable-gpu",
                "--profile",
                state / "profile",
            ],
            env,
            bus,
            xvfb,
            dbus,
            cwd=project,
        )
        if status:
            return status
        if not status_file.exists():
            raise RuntimeError("Joplin closed before the project script completed")
        if error_file.exists():
            print(error_file.read_text(), file=sys.stderr)
        return int(status_file.read_text())


if __name__ == "__main__":
    raise SystemExit(
        run_project(
            os.environ["JOPLIN_PURIFIER_PROJECT"],
            os.environ["JOPLIN_PURIFIER_SCRIPT"],
            os.environ["JOPLIN_PURIFIER_STATE"],
            os.environ["JOPLIN_PURIFIER_ENVIRONMENT"],
            os.environ["JOPLIN_PURIFIER_SDK_PATH"],
            os.environ["JOPLIN_PURIFIER_FONTS"],
            os.environ["JOPLIN_PURIFIER_XVFB"],
            os.environ["JOPLIN_PURIFIER_DBUS"],
            os.environ["JOPLIN_PURIFIER_OUTPUT"],
        )
    )
