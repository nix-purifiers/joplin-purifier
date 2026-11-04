"""JOPLIN's normal application workflow with a frozen native extension profile."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def public_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("JOPLIN addon repositories must use public HTTPS URLs")
    return url


def selection(project):
    import re

    value = json.loads((project / "joplin-purifier.json").read_text())
    if set(value) != {"plugins"} or not isinstance(value["plugins"], list):
        raise ValueError("joplin-purifier.json needs a plugins list of native IDs")
    if any(
        not isinstance(id, str) or not re.fullmatch("[A-Za-z0-9][A-Za-z0-9._-]*", id)
        for id in value["plugins"]
    ):
        raise ValueError("invalid native plugin ID")
    if len(value["plugins"]) != len(set(value["plugins"])):
        raise ValueError("duplicate plugin IDs")
    return value


def project_path(explicit):
    if explicit:
        return Path(explicit).resolve()
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "joplin-purifier.json").exists() or (
            parent / "joplin-purifier.lock.json"
        ).exists():
            return parent
    return current


def validate(project, lock):
    data = json.loads(lock.read_text())
    if data.get("version") != 1 or data.get("purifier") != "joplin":
        raise ValueError("unsupported JOPLIN lock")
    if data.get("sdk") != os.environ["JOPLIN_PURIFIER_SDK"]:
        raise ValueError("JOPLIN SDK changed; run joplin-purifier lock --update")
    if data.get("selection") != selection(project):
        raise ValueError(
            "extension selection changed; run joplin-purifier lock --update"
        )
    return data


def realize(project, lock, target="environment", out_link=None):
    args = [
        "nix",
        "build",
        "--impure",
        "--file",
        os.environ["JOPLIN_PURIFIER_REALIZE"],
        "--argstr",
        "projectPath",
        str(project),
        "--argstr",
        "lockPath",
        str(lock),
        "--argstr",
        "target",
        target,
        "--json",
    ]
    args += ["--out-link", str(out_link)] if out_link else ["--no-link"]
    result = run(args, stdout=subprocess.PIPE, text=True)
    return Path(json.loads(result.stdout)[0]["outputs"]["out"])


def native_operation(root, request):
    request_file = root / "request.json"
    response = root / "response.json"
    request_file.write_text(json.dumps(request))
    run(
        [
            os.environ["JOPLIN_PURIFIER_PYTHON"],
            os.environ["JOPLIN_PURIFIER_NATIVE"] + "/joplin_purifier_helper.py",
            str(root / "session"),
            str(request_file),
            str(response),
        ],
        stdout=sys.stderr,
    )
    return json.loads(response.read_text())


def prefetch(url, name):
    return json.loads(
        run(
            [
                "nix",
                "store",
                "prefetch-file",
                "--json",
                "--name",
                name,
                public_url(url),
            ],
            stdout=subprocess.PIPE,
            text=True,
        ).stdout
    )


def capture(project, lock):
    requested = selection(project)
    with tempfile.TemporaryDirectory(prefix="joplin-purifier-") as temporary:
        root = Path(temporary)
        native = native_operation(
            root,
            {
                "action": "capture",
                "plugins": requested["plugins"],
                "root": str(root / "capture"),
            },
        )
        entries = []
        for entry in native["entries"]:
            fetched = prefetch(entry["url"], entry["path"])

            if (
                hashlib.sha256(Path(fetched["storePath"]).read_bytes()).hexdigest()
                != entry["bytesSha256"]
            ):
                raise ValueError(
                    "Nix archive differs from the original Joplin download"
                )
            entries.append(
                {key: value for key, value in entry.items() if key != "bytesSha256"}
                | {"hash": fetched["hash"], "mirrors": []}
            )
        data = {
            "version": 1,
            "purifier": "joplin",
            "sdk": os.environ["JOPLIN_PURIFIER_SDK"],
            "selection": requested,
            "entries": entries,
            "native": {
                "metadata": native["metadata"],
                "repository": native["repository"],
            },
        }
        candidate = root / "joplin-purifier.lock.json"
        candidate.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        realize(project, candidate)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=lock.parent, delete=False
        ) as output:
            output.write(candidate.read_text())
            pending = Path(output.name)
        try:
            os.replace(pending, lock)
        finally:
            pending.unlink(missing_ok=True)


def prepared_environment(project, lock):
    data = validate(project, lock)
    state = project / ".joplin-purifier"
    identity = hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    roots = state / "environments"
    roots.mkdir(parents=True, exist_ok=True)
    environment = realize(project, lock, out_link=roots / identity)
    alias = state / "environment"
    if alias.exists() and not alias.is_symlink():
        raise ValueError("unexpected file at the managed Joplin environment link")
    with tempfile.TemporaryDirectory(dir=state) as temporary:
        link = Path(temporary) / "environment"
        link.symlink_to(environment)
        os.replace(link, alias)
    return state, environment


def native_exec(project, lock, arguments, command="joplin-desktop"):
    original = Path(os.environ["JOPLIN_PURIFIER_ORIGINAL"]) / "bin/joplin-desktop"
    if not lock.exists():
        print(
            "warning: no Joplin purifier lock; using ordinary, impure plugin resolution",
            file=sys.stderr,
        )
        os.execve(original, [str(original), *arguments], os.environ.copy())
    _state, environment = prepared_environment(project, lock)
    env = os.environ.copy()
    for key in [
        "NODE_OPTIONS",
        "NODE_PATH",
        "ELECTRON_RUN_AS_NODE",
        "JOPLIN_PURIFIER_SCRIPT",
        "JOPLIN_PURIFIER_STATUS",
        "JOPLIN_PURIFIER_ERROR",
    ]:
        env.pop(key, None)
    env["JOPLIN_PURIFIER_ENVIRONMENT"] = str(environment)
    executable = Path(os.environ["JOPLIN_PURIFIER_SDK_PATH"]) / "bin/joplin-desktop"
    os.execve(executable, [str(executable), *arguments], env)


def main():
    if os.environ.get("JOPLIN_PURIFIER_COMMAND") not in {None, "joplin-purifier"}:
        project = project_path(os.environ.get("JOPLIN_PURIFIER_PROJECT"))
        lock = Path(
            os.environ.get(
                "JOPLIN_PURIFIER_LOCK", project / "joplin-purifier.lock.json"
            )
        ).resolve()
        native_exec(project, lock, sys.argv[1:], os.environ["JOPLIN_PURIFIER_COMMAND"])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--lock")
    sub = parser.add_subparsers(dest="action", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("--update", action="store_true")
    sub.add_parser("prefetch")
    scripted = sub.add_parser("run")
    scripted.add_argument("script")
    for name in ["build", "bundle"]:
        sub.add_parser(name)
    publish = sub.add_parser("publish")
    publish.add_argument("--tag", required=True)
    execute = sub.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    project = project_path(args.project or os.environ.get("JOPLIN_PURIFIER_PROJECT"))
    lock = Path(
        args.lock
        or os.environ.get("JOPLIN_PURIFIER_LOCK", project / "joplin-purifier.lock.json")
    ).resolve()
    if args.action == "run":
        state, environment = prepared_environment(project, lock)
        sys.path.insert(0, os.environ["JOPLIN_PURIFIER_NATIVE"])
        from joplin_purifier_run_project import run_project

        raise SystemExit(
            run_project(
                project,
                (project / args.script).resolve(),
                state / "run",
                environment,
                os.environ["JOPLIN_PURIFIER_SDK_PATH"],
                os.environ["JOPLIN_PURIFIER_FONTS"],
                os.environ["JOPLIN_PURIFIER_XVFB"],
                os.environ["JOPLIN_PURIFIER_DBUS"],
                project / "output",
            )
        )
    if args.action == "lock" and args.update:
        capture(project, lock)
        return
    if args.action == "exec":
        arguments = (
            args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        )
        native_exec(project, lock, arguments)
        return
    validate(project, lock)
    if args.action == "lock":
        realize(project, lock)
    elif args.action == "prefetch":
        print(realize(project, lock))
    elif args.action in {"build", "bundle"}:
        print(
            realize(project, lock, "project" if args.action == "build" else "release")
        )
    elif args.action == "publish":
        release = realize(project, lock, "release")
        run(
            [
                os.environ.get("JOPLIN_PURIFIER_GH", "gh"),
                "release",
                "upload",
                args.tag,
                str(release / "joplin-project.tar.gz"),
                "--clobber",
            ]
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"joplin-purifier: {error}", file=sys.stderr)
        sys.exit(1)
