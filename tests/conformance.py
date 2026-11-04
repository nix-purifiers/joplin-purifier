"""Exercise the installed integration with the native Joplin application."""

import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cli", type=Path)
    args = parser.parse_args()
    cli = args.cli.resolve()
    fixture = Path(__file__).resolve().parents[1] / "examples/minimal"
    with tempfile.TemporaryDirectory(prefix="joplin-conformance-") as temporary:
        project = Path(temporary)
        for name in [
            "build.cjs",
            "answer.json",
            "joplin-purifier.json",
            "joplin-purifier.lock.json",
        ]:
            shutil.copyfile(fixture / name, project / name)

        def run(*arguments, status=0):
            result = subprocess.run(
                [str(cli), *arguments],
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == status, result.stdout + result.stderr
            return result

        shutil.copyfile(
            Path(__file__).with_name("runtime.cjs"), project / "runtime.cjs"
        )

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ordinary HTTP works")

            def log_message(self, *_arguments):
                pass

        with http.server.HTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            previous = os.environ.get("PROBE_URL")
            os.environ["PROBE_URL"] = f"http://127.0.0.1:{server.server_port}/"
            try:
                for counter in [1, 2]:
                    (project / "counter.json").write_text(json.dumps(counter))
                    run("run", "runtime.cjs")
            finally:
                if previous is None:
                    os.environ.pop("PROBE_URL")
                else:
                    os.environ["PROBE_URL"] = previous
                server.shutdown()
                thread.join()

        hashes = []
        for answer in [42, 43, 42]:
            (project / "answer.json").write_text(json.dumps({"answer": answer}))
            run("run", "build.cjs")
            output = (project / "output/combined.md").read_bytes()
            assert (
                output == f"# First\n\n{answer}\n\n# Second\n\nSecond body\n".encode()
            )
            hashes.append(hashlib.sha256(output).hexdigest())
        assert hashes[0] != hashes[1] and hashes[0] == hashes[2]

        (project / "status.cjs").write_text("module.exports = async () => 7;\n")
        run("run", "status.cjs", status=7)
        selection = project / "joplin-purifier.json"
        selection.write_text('{"plugins": []}\n')
        result = subprocess.run(
            [str(cli), "prefetch"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert "selection changed" in result.stderr.lower(), result.stderr
        assert "lock --update" in result.stderr, result.stderr
    print(
        "Native export/source restoration, script status and stale lock checks passed"
    )


if __name__ == "__main__":
    main()
