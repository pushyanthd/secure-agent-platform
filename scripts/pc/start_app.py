"""Start the PC's live operator API and durable worker with local log files."""

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from agentguard.control_setup import initialize_control


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    directory = root / "artifacts/control"
    profile = root / "artifacts/pc-wsl/model-profile.json"
    with socket.socket() as port:
        port.settimeout(1)
        try:
            occupied = port.connect_ex(("127.0.0.1", 8000)) == 0
        except TimeoutError:
            occupied = False
        if occupied:
            raise SystemExit("Port 8000 is already in use; existing processes were left alone")
    if not (directory / "settings.json").exists():
        initialize_control(root, directory, fixture=False, model_profile=profile)
    settings = json.loads((directory / "settings.json").read_text())
    if settings["mode"] != "fresh_local_inference" or Path(settings["model_profile"]) != profile:
        raise SystemExit("Existing control settings do not select this PC's live profile")
    children = []
    for command in ("api-serve", "worker"):
        with (directory / f"{command}.log").open("ab") as log:
            child = subprocess.Popen(
                [str(root / ".venv/bin/python"), "-m", "agentguard.cli", command],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        children.append(child)
    deadline = time.monotonic() + 60
    ready = False
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in children):
            break
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=1) as response:
                ready = response.status == 200
            if ready:
                break
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    if not ready:
        for child in children:
            if child.poll() is None:
                child.terminate()
        raise SystemExit(f"Application startup failed; inspect local logs in {directory}")
    processes = {"api_pid": children[0].pid, "worker_pid": children[1].pid}
    (directory / "processes.json").write_text(json.dumps(processes, indent=2) + "\n")
    print("Live PC operator console: http://127.0.0.1:8000/")
    print("Read artifacts/control/operator.token locally to connect; do not share the token.")
    print(json.dumps(processes))


if __name__ == "__main__":
    main()
