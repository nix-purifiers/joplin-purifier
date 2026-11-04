"""Launch the SDK's original repository client and installer with a real DOM."""

import json
import os
import sys
from pathlib import Path

from joplin_purifier_session import private_environment, session

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
request = Path(sys.argv[2]).resolve()
response = Path(sys.argv[3]).resolve()
base = os.environ.copy()
for key in list(base):
    if key.startswith("JOPLIN_PURIFIER_") and key not in {
        "JOPLIN_PURIFIER_ORIGINAL",
        "JOPLIN_PURIFIER_PYTHON",
    }:
        base.pop(key, None)
env, bus = private_environment(root, base, os.environ["JOPLIN_PURIFIER_FONTS"])
env.update(
    JOPLIN_PURIFIER_REQUEST=str(request),
    JOPLIN_PURIFIER_RESPONSE=str(response),
    JOPLIN_PURIFIER_HELPER_STATE=str(root / "native"),
)
status = session(
    [
        Path(os.environ["JOPLIN_PURIFIER_ELECTRON"]) / "bin/electron",
        "--no-sandbox",
        "--ozone-platform=x11",
        Path(__file__).with_name("helper-main.cjs"),
    ],
    env,
    bus,
    os.environ["JOPLIN_PURIFIER_XVFB"],
    os.environ["JOPLIN_PURIFIER_DBUS"],
)
if status:
    raise SystemExit(status)
if not response.is_file():
    raise RuntimeError("Native Joplin helper closed without completing")
json.loads(response.read_text())
