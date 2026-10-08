"""Real loopback HTTP and separate worker processes, with explicitly scripted responses."""

import json
import socket
import subprocess
import sys
import time
import uuid
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

from agentguard.control_setup import ControlSettings, initialize_control, prepare_control
from agentguard.live import atomic_json
from agentguard.scenarios import grade_episode


def run_control_smoke(root: Path, output: Path) -> Path:
    directory = output.resolve() / str(uuid.uuid4())
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    settings_path = initialize_control(root, directory, fixture=True, port=port)
    settings = ControlSettings.model_validate_json(settings_path.read_bytes())
    control, _ = prepare_control(settings)
    token = (directory / "operator.token").read_text().strip()
    observer = (directory / "observer.token").read_text().strip()

    def request(
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        credential: str = token,
        key: str | None = None,
    ) -> tuple[int, Any]:
        connection = HTTPConnection("127.0.0.1", port, timeout=3)
        headers = {"Content-Type": "application/json", "X-Agentguard-Request": "1"}
        if credential:
            headers["Authorization"] = "Bearer " + credential
        if key:
            headers["Idempotency-Key"] = key
        try:
            connection.request(
                method, path, json.dumps(body) if body is not None else None, headers
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read(131072))
        finally:
            connection.close()

    def advance() -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agentguard.cli",
                "worker",
                "--settings",
                str(settings_path),
                "--once",
            ],
            cwd=root,
            capture_output=True,
            timeout=20,
        )
        if result.returncode:
            raise RuntimeError("Worker smoke process failed; no credentials or prompts logged")

    with (directory / "server.log").open("wb") as log:
        process: subprocess.Popen[bytes] | None = None

        def stop() -> None:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        def start() -> subprocess.Popen[bytes]:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agentguard.cli",
                    "api-serve",
                    "--settings",
                    str(settings_path),
                    "--credentials",
                    str(directory / "credentials.json"),
                ],
                cwd=root,
                stdout=log,
                stderr=log,
            )
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if child.poll() is not None:
                        raise RuntimeError("API smoke process did not start; inspect server.log")
                    try:
                        if request("GET", "/api/identity")[0] == 200:
                            return child
                    except OSError:
                        pass
                    time.sleep(0.05)
                raise RuntimeError("API smoke process startup timed out")
            except BaseException:
                child.terminate()
                child.wait(timeout=5)
                raise

        checks: dict[str, bool] = {}
        try:
            process = start()
            checks["unauthenticated_request_denied"] = (
                request("GET", "/api/runs", credential="")[0] == 401
            )
            body = {"scenario_id": "authorized-shared-write"}
            status, submitted = request("POST", "/api/runs", body, key="smoke_request_001")
            if status != 201:
                raise RuntimeError("Could not submit smoke episode")
            episode = submitted["episode_id"]
            checks["idempotent_submission"] = (
                request("POST", "/api/runs", body, key="smoke_request_001")[1] == submitted
            )
            advance()
            checks["worker_paused_for_review"] = (
                request("GET", f"/api/runs/{episode}")[1]["status"] == "WAITING_APPROVAL"
            )
            stop()
            process = start()
            checks["approval_wait_survived_api_restart"] = (
                request("GET", f"/api/runs/{episode}")[1]["status"] == "WAITING_APPROVAL"
            )
            approvals = request("GET", f"/api/runs/{episode}/approvals")[1]
            path = f"/api/runs/{episode}/approvals/{approvals[0]['id']}"
            checks["observer_cannot_read_review_credential"] = (
                request("GET", path, credential=observer)[0] == 403
            )
            detail = request("GET", path)[1]
            decision = {
                "expected_hash": detail["action_hash"],
                "nonce": detail["nonce"],
                "approve": True,
            }
            checks["observer_cannot_review"] = (
                request("POST", path + "/review", decision, credential=observer)[0] == 403
            )
            checks["operator_review_accepted"] = (
                request("POST", path + "/review", decision)[0] == 200
            )
            checks["review_replay_denied"] = request("POST", path + "/review", decision)[0] == 409
            advance()
            state = request("GET", f"/api/runs/{episode}")[1]
            checks["worker_completed_after_review"] = state["status"] == "COMPLETED"
            checks["exactly_one_ticket"] = len(control.store.tickets(episode)) == 1
            with control.store.connection() as db:
                saved = json.loads(
                    db.execute(
                        "SELECT result FROM agent_runs WHERE episode_id=?", (episode,)
                    ).fetchone()[0]
                )
                requests = "".join(row[0] for row in db.execute("SELECT request FROM model_calls"))
            checks["operator_credentials_absent_from_model_inputs"] = all(
                secret not in requests for secret in (token, observer, detail["nonce"])
            )
            task = control.tasks["authorized-shared-write"]
            grade = grade_episode(
                control.store, episode, saved["final_response"], task.expectation, attacked=False
            )
            checks["independent_state_grade_passed"] = grade["task_success"]
            atomic_json(
                directory / "report.json",
                {
                    "mode": "authored_fixture",
                    "fresh_model_trials": 0,
                    "transport": "real loopback HTTP; API restart and separate worker processes",
                    "review": "scripted operator HTTP request; not a human usability trial",
                    "checks": checks,
                    "passed": all(checks.values()),
                    "grade": grade,
                    "episode_id": episode,
                    "execution_manifest": json.loads(control.manifest),
                },
            )
        finally:
            stop()
            # The report survives; ephemeral smoke bearer credentials do not.
            for name in ("operator.token", "observer.token", "credentials.json"):
                (directory / name).unlink(missing_ok=True)
    return directory
