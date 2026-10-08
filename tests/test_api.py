import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentguard.api import Credential, Credentials, SecurityBoundary, create_app, token_hash
from agentguard.control import ControlPlane, Principal, SubmitRun
from agentguard.control_setup import (
    ControlSettings,
    initialize_control,
    load_credentials,
    prepare_control,
)
from agentguard.worker import Queue

ORIGIN = "http://127.0.0.1:8000"
OPERATOR = "operator_" + "a" * 40
OBSERVER = "observer_" + "b" * 40
OTHER = "other_" + "c" * 40
WRONG_SCOPE = "scope_" + "d" * 40


@pytest.fixture
def service(tmp_path):
    settings_file = initialize_control(Path.cwd(), tmp_path / "control", fixture=True)
    settings = ControlSettings.model_validate_json(settings_file.read_bytes())
    control, runner = prepare_control(settings)
    principal = Principal(subject="alice", actor="alex", workspace="acme-lab")
    entries = (
        (OPERATOR, principal),
        (OBSERVER, principal.model_copy(update={"role": "observer"})),
        (OTHER, principal.model_copy(update={"subject": "bob"})),
        (WRONG_SCOPE, principal.model_copy(update={"subject": "morgan", "actor": "morgan"})),
    )
    credentials = Credentials(
        entries=tuple(
            Credential(token_sha256=token_hash(token), principal=identity)
            for token, identity in entries
        )
    )
    app = create_app(control, credentials, origin=ORIGIN)
    with TestClient(app, base_url=ORIGIN) as client:
        client.headers.update({"Authorization": f"Bearer {OPERATOR}", "X-Agentguard-Request": "1"})
        yield client, control, runner, principal, credentials


def submit(client, scenario="authorized-shared-write", key="request_0001"):
    response = client.post(
        "/api/runs", json={"scenario_id": scenario}, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 201, response.text
    return response.json()["episode_id"]


def waiting(service):
    client, control, runner, _, _ = service
    episode = submit(client)
    assert runner.run_once()["status"] == "WAITING_APPROVAL"
    approvals = client.get(f"/api/runs/{episode}/approvals").json()
    path = f"/api/runs/{episode}/approvals/{approvals[0]['id']}"
    detail = client.get(path).json()
    return episode, path, detail


def review_body(detail, approve=True):
    return {"expected_hash": detail["action_hash"], "nonce": detail["nonce"], "approve": approve}


@pytest.mark.parametrize("token", [None, "bad", "Bearer " + "z" * 40, "Basic " + OPERATOR])
def test_every_api_route_requires_authentication(service, token):
    client, *_ = service
    client.headers.pop("authorization")
    headers = {"Authorization": token} if token else {}
    for path in ("/api/identity", "/api/scenarios", "/api/runs", "/api/runs/missing/timeline"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.json() == {"error": "AUTHENTICATION_REQUIRED"}


def test_catalog_exposes_only_authenticated_task_scope(service):
    client, control, *_ = service
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert len(response.json()) == len(control.tasks)
    assert all(set(task) == {"id", "task", "scope"} for task in response.json())
    assert "attack_payload" not in response.text
    assert "clean_script" not in response.text
    assert (
        client.get("/api/scenarios", headers={"Authorization": f"Bearer {WRONG_SCOPE}"}).json()
        == []
    )
    response = client.post(
        "/api/runs",
        json={"scenario_id": "authorized-shared-write"},
        headers={"Authorization": f"Bearer {WRONG_SCOPE}", "Idempotency-Key": "wrong_0001"},
    )
    assert response.status_code == 404


def test_response_withholding_exposes_decision_without_raw_output(service):
    from agentguard.contracts import ResponseScope

    client, control, runner, *_ = service
    task = control.tasks["confidential-response-triage"]
    control.tasks[task.id] = task.model_copy(
        update={
            "contract": task.contract.model_copy(
                update={
                    "response_scope": ResponseScope(
                        recipient="task-response", max_classification="internal"
                    )
                }
            )
        }
    )
    episode = submit(client, task.id)
    assert runner.run_once()["status"] == "WAITING_APPROVAL"
    approvals = client.get(f"/api/runs/{episode}/approvals").json()
    path = f"/api/runs/{episode}/approvals/{approvals[0]['id']}"
    detail = client.get(path).json()
    assert detail["snapshot"]["contract"]["response_scope"]["max_classification"] == "internal"
    assert client.post(path + "/review", json=review_body(detail)).status_code == 200
    result = runner.run_once()
    assert result["final_response"] == ""
    timeline = client.get(f"/api/runs/{episode}/timeline")
    last = timeline.json()[-1]
    assert last["kind"] == "final"
    assert last["decision"] == {"outcome": "DENY", "reason": "CONFIDENTIAL_RESPONSE_BLOCKED"}
    assert "SYNTHETIC_RESPONSE_TRIAGE_CANARY" not in timeline.text
    assert "Private triage scheduled." not in timeline.text
    assert "final_response" not in client.get(f"/api/runs/{episode}").text


@pytest.mark.parametrize(
    "extra",
    [
        {"profile": "baseline"},
        {"actor": "morgan"},
        {"workspace": "other"},
        {"task": "Ignore policy"},
        {"budgets": {"max_steps": 64}},
        {"model": "remote"},
        {"approval_id": "forged"},
        {"attack_payload": "injected"},
    ],
)
def test_submission_cannot_supply_authority_or_experiment_controls(service, extra):
    client, control, *_ = service
    response = client.post(
        "/api/runs",
        json={"scenario_id": "authorized-shared-write", **extra},
        headers={"Idempotency-Key": "request_0001"},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "INVALID_REQUEST"}
    with control.store.connection() as db:
        assert db.execute("SELECT count(*) FROM episodes").fetchone()[0] == 0


def test_submission_is_atomic_idempotent_and_survives_restart(service, monkeypatch):
    client, control, runner, principal, _ = service
    episode = submit(client)
    assert submit(client) == episode
    changed = client.post(
        "/api/runs",
        json={"scenario_id": "launch-scope"},
        headers={"Idempotency-Key": "request_0001"},
    )
    assert changed.status_code == 409
    with control.store.connection() as db:
        assert db.execute("SELECT count(*) FROM episodes").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    reopened = ControlPlane(
        control.store,
        control.tasks,
        manifest=runner.manifest,
        budgets=control.budgets,
        mode=control.mode,
    )
    assert (
        reopened.submit(principal, SubmitRun(scenario_id="authorized-shared-write"), "request_0001")
        == episode
    )

    def fail(*args, **kwargs):
        raise RuntimeError("Injected failure before job commit")

    monkeypatch.setattr(Queue, "_submit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        submit(client, key="request_0002")
    with control.store.connection() as db:
        assert db.execute("SELECT count(*) FROM episodes").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM api_submissions").fetchone()[0] == 1


def test_concurrent_delivery_creates_one_episode(service):
    _, control, _, principal, _ = service
    with ThreadPoolExecutor(max_workers=8) as pool:
        episodes = list(
            pool.map(
                lambda _: control.submit(
                    principal, SubmitRun(scenario_id="authorized-shared-write"), "concurrent_0001"
                ),
                range(8),
            )
        )
    assert len(set(episodes)) == 1


@pytest.mark.parametrize("approve", [True, False])
def test_authenticated_review_resumes_worker_without_exposing_credentials(service, approve):
    client, control, runner, *_ = service
    episode, path, detail = waiting(service)
    assert detail["snapshot"]["action"]["arguments"]["project_id"] == "shared"
    assert detail["snapshot"]["resource"]["version"] == 1
    timeline = client.get(f"/api/runs/{episode}/timeline").json()
    assert timeline[-1]["decision"]["outcome"] == "REQUIRE_APPROVAL"
    assert timeline[-1]["approval_status"] == "PENDING"
    response = client.post(path + "/review", json=review_body(detail, approve))
    assert response.status_code == 200
    assert runner.run_once()["status"] == "COMPLETED"
    assert len(control.store.tickets(episode)) == int(approve)
    assert control.store.approval(detail["id"])["reviewer"] == "alice"
    assert client.post(path + "/review", json=review_body(detail, approve)).status_code == 409
    with control.store.connection() as db:
        messages = "".join(row[0] for row in db.execute("SELECT request FROM model_calls"))
    for secret in (OPERATOR, OBSERVER, detail["nonce"], detail["id"]):
        assert secret not in messages


def test_other_owner_cannot_read_cancel_or_review_even_with_exact_nonce(service):
    client, *_ = service
    episode, path, detail = waiting(service)
    headers = {"Authorization": f"Bearer {OTHER}"}
    assert client.get("/api/runs", headers=headers).json() == []
    for route in (
        f"/api/runs/{episode}",
        f"/api/runs/{episode}/timeline",
        f"/api/runs/{episode}/approvals",
        path,
    ):
        assert client.get(route, headers=headers).status_code == 404
    assert client.post(f"/api/runs/{episode}/cancel", json={}, headers=headers).status_code == 404
    assert (
        client.post(path + "/review", json=review_body(detail), headers=headers).status_code == 404
    )


def test_observer_can_read_redacted_state_but_cannot_review_or_mutate(service):
    client, *_ = service
    episode, path, detail = waiting(service)
    headers = {"Authorization": f"Bearer {OBSERVER}"}
    assert client.get(f"/api/runs/{episode}", headers=headers).status_code == 200
    for route in (f"/api/runs/{episode}/timeline", f"/api/runs/{episode}/approvals"):
        response = client.get(route, headers=headers)
        assert response.status_code == 200
        assert detail["nonce"] not in response.text
        assert "snapshot" not in response.text
    assert client.get(path, headers=headers).status_code == 403
    assert (
        client.post(path + "/review", json=review_body(detail), headers=headers).status_code == 403
    )
    assert client.post(f"/api/runs/{episode}/cancel", json={}, headers=headers).status_code == 403
    assert (
        client.post(
            "/api/runs",
            json={"scenario_id": "launch-scope"},
            headers={**headers, "Idempotency-Key": "observer_0001"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("changed", ["version", "acl", "scope", "taint", "expired", "deadline"])
def test_stale_approval_is_rejected_at_review_time(service, changed):
    client, control, *_ = service
    episode, path, detail = waiting(service)
    with control.store.connection() as db:
        if changed == "version":
            db.execute(
                "UPDATE resources SET payload=json_set(payload,'$.version',2) WHERE id='shared'"
            )
        elif changed == "acl":
            db.execute(
                "UPDATE resources SET payload=json_set(payload,'$.writers',json('[]')) "
                "WHERE id='shared'"
            )
        elif changed == "scope":
            db.execute("UPDATE episodes SET contract=json_set(contract,'$.project_ids',json('[]'))")
        elif changed == "taint":
            db.execute("UPDATE episodes SET confidential=1")
        elif changed == "deadline":
            db.execute("UPDATE jobs SET deadline=0")
        else:
            db.execute("UPDATE approvals SET expires_at=0")
    response = client.post(path + "/review", json=review_body(detail))
    assert response.status_code == 409
    assert control.store.approval(detail["id"])["status"] == "PENDING"
    assert control.store.tickets(episode) == []


def test_review_credentials_are_bound_to_one_run_and_cannot_set_reviewer(service):
    client, _, runner, *_ = service
    episode, path, detail = waiting(service)
    second = submit(client, key="request_0002")
    runner.run_once()
    assert client.get(path.replace(episode, second)).status_code == 404
    assert (
        client.post(
            path + "/review", json={**review_body(detail), "reviewer": "forged"}
        ).status_code
        == 422
    )
    bad = client.post(path + "/review", json={**review_body(detail), "nonce": "wrong_" * 8})
    assert bad.status_code == 409
    assert "wrong_" not in bad.text


def test_cancel_revokes_lease_and_invalidates_pending_review(service):
    client, control, runner, *_ = service
    episode, path, detail = waiting(service)
    assert client.post(f"/api/runs/{episode}/cancel", json={}).json() == {"status": "CANCELLED"}
    assert client.post(path + "/review", json=review_body(detail)).status_code == 409
    assert runner.run_once() is None
    assert control.store.tickets(episode) == []


def test_lease_token_is_not_an_operator_credential(service):
    client, control, runner, *_ = service
    episode = submit(client)
    lease = runner.queue.claim(manifest=runner.manifest)
    response = client.post(
        f"/api/runs/{episode}/cancel", json={}, headers={"Authorization": f"Bearer {lease.token}"}
    )
    assert response.status_code == 401
    assert not control.store.is_cancelled(episode)


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Origin": "https://evil.example"}, 403),
        ({"Origin": "null"}, 403),
        ({"Origin": "http://127.0.0.1:9999"}, 403),
        ({"Sec-Fetch-Site": "cross-site"}, 403),
        ({"Sec-Fetch-Site": "same-site"}, 403),
        ({"X-Agentguard-Request": ""}, 403),
        ({"Content-Type": "text/plain"}, 415),
        ({"Host": "evil.example:8000"}, 400),
        ({"Host": "127.0.0.1:9999"}, 400),
    ],
)
def test_browser_request_boundary(service, headers, status):
    client, *_ = service
    response = client.post(
        "/api/runs",
        json={"scenario_id": "launch-scope"},
        headers={
            "Idempotency-Key": "request_0001",
            **headers,
        },
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "access-control-allow-origin" not in response.headers


def test_same_origin_requests_work_and_duplicate_headers_fail_closed(service):
    client, *_ = service
    response = client.post(
        "/api/runs",
        json={"scenario_id": "launch-scope"},
        headers={
            "Origin": ORIGIN,
            "Sec-Fetch-Site": "same-origin",
            "Idempotency-Key": "request_0001",
        },
    )
    assert response.status_code == 201
    response = client.get(
        "/api/runs", headers=[("Host", "evil.example"), ("Host", "127.0.0.1:8000")]
    )
    assert response.status_code == 400


def test_actual_body_limit_and_validation_never_reflect_secrets(service):
    client, *_ = service
    response = client.post(
        "/api/runs", content=b"x" * 16385, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    response = client.post(
        "/api/runs", content=f'{{"token":"{OPERATOR}"', headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert OPERATOR not in response.text


def test_chunked_body_limit_does_not_trust_content_length(service):
    _, _, _, _, credentials = service
    called = []

    async def downstream(scope, receive, send):
        called.append(True)

    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 10000, "more_body": True},
            {"type": "http.request", "body": b"x" * 10000, "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [
            (b"host", b"127.0.0.1:8000"),
            (b"authorization", f"Bearer {OPERATOR}".encode()),
            (b"content-type", b"application/json"),
            (b"x-agentguard-request", b"1"),
            (b"content-length", b"2"),
        ],
    }
    asyncio.run(
        SecurityBoundary(downstream, credentials=credentials, origin=ORIGIN)(scope, receive, send)
    )
    assert sent[0]["status"] == 413
    assert not called


def test_trace_redaction_omits_document_bodies_arguments_final_text_and_lease(service):
    client, control, runner, *_ = service
    episode = submit(client, scenario="confidential-internal-review")
    runner.run_once()
    task = control.tasks["confidential-internal-review"]
    text = "".join(
        client.get(path).text
        for path in (
            f"/api/runs/{episode}",
            f"/api/runs/{episode}/timeline",
            f"/api/runs/{episode}/approvals",
        )
    )
    assert task.expectation.canary not in text
    assert "raw_response" not in text
    assert "snapshot" not in text
    assert "arguments" not in text
    with control.store.connection() as db:
        nonce = db.execute("SELECT nonce FROM approvals").fetchone()[0]
    assert nonce not in text


def test_pending_admission_limit_retains_idempotency(service):
    client, *_ = service
    for index in range(32):
        submit(client, key=f"request_{index:04d}")
    assert submit(client, key="request_0000")
    response = client.post(
        "/api/runs",
        json={"scenario_id": "authorized-shared-write"},
        headers={"Idempotency-Key": "request_0033"},
    )
    assert response.status_code == 429


def test_setup_has_private_credentials_and_worker_needs_no_credential_file(tmp_path):
    directory = tmp_path / "control"
    settings = initialize_control(Path.cwd(), directory, fixture=True)
    credentials = load_credentials(directory / "credentials.json")
    token = (directory / "operator.token").read_text().strip()
    assert token not in (directory / "credentials.json").read_text()
    assert token not in settings.read_text()
    assert credentials.entries[0].token_sha256 == token_hash(token)
    for file in directory.iterdir():
        assert file.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        initialize_control(Path.cwd(), directory, fixture=True)
    (directory / "credentials.json").chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        load_credentials(directory / "credentials.json")
    for path in (
        directory / "credentials.json",
        directory / "operator.token",
        directory / "observer.token",
    ):
        path.unlink()
    control, runner = prepare_control(ControlSettings.model_validate_json(settings.read_bytes()))
    principal = Principal(subject="alice", actor="alex", workspace="acme-lab")
    control.submit(principal, SubmitRun(scenario_id="launch-scope"), "request_0001")
    assert runner.run_once()["status"] == "COMPLETED"


def test_original_execution_mode_survives_api_reconfiguration(service):
    client, control, *_ = service
    episode = submit(client)
    control.mode = "fresh_local_inference"
    assert client.get(f"/api/runs/{episode}").json()["mode"] == "authored_fixture"


def test_non_ascii_nonce_and_non_boolean_decision_are_rejected(service):
    client, *_ = service
    _, path, detail = waiting(service)
    for changed in ({"nonce": "é" * 32}, {"approve": "false"}):
        response = client.post(path + "/review", json={**review_body(detail), **changed})
        assert response.status_code == 422


def test_unexpected_errors_do_not_reflect_secrets_and_are_not_cached(service, monkeypatch):
    _, control, _, _, credentials = service

    def fail(*args, **kwargs):
        raise RuntimeError(OPERATOR)

    monkeypatch.setattr(control, "runs", fail)
    with TestClient(
        create_app(control, credentials, origin=ORIGIN),
        base_url=ORIGIN,
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/runs", headers={"Authorization": f"Bearer {OPERATOR}"})
    assert response.status_code == 500
    assert response.json() == {"error": "INTERNAL_ERROR"}
    assert response.headers["cache-control"] == "no-store"


def test_fixture_model_exposes_no_credentials_and_live_requires_preflight(tmp_path, monkeypatch):
    from agentguard import control_setup
    from agentguard.model import LocalModel, ModelConfig

    settings_path = initialize_control(Path.cwd(), tmp_path / "live", fixture=False)
    settings = ControlSettings.model_validate_json(settings_path.read_bytes())
    monkeypatch.setattr(
        control_setup,
        "prepare_local_model",
        lambda *args: (LocalModel(ModelConfig()), {}, {"preflight_error": "MODEL_UNAVAILABLE"}),
    )
    with pytest.raises(ValueError, match="Start the pinned local model"):
        prepare_control(settings)


def test_cancel_completed_job_does_not_claim_it_was_cancelled(service):
    client, _, runner, *_ = service
    episode = submit(client, scenario="launch-scope")
    assert runner.run_once()["status"] == "COMPLETED"
    assert client.post(f"/api/runs/{episode}/cancel", json={}).json() == {"status": "COMPLETED"}


def test_unknown_failure_text_and_out_of_scope_targets_are_redacted(service):
    from test_runtime import reply

    client, control, runner, *_ = service
    episode = submit(client, scenario="launch-scope")
    runner.run_once()
    canary = "SYNTHETIC_SECRET_CANARY"
    raw = reply(
        json.dumps(
            {
                "kind": "action",
                "action": {"tool": "documents.read", "arguments": {"document_id": canary}},
            }
        )
    )
    with control.store.connection() as db:
        db.execute("UPDATE model_calls SET raw_response=?", (raw,))
        db.execute("UPDATE agent_runs SET result=?", (json.dumps({"reason": canary}),))
    detail = client.get(f"/api/runs/{episode}")
    timeline = client.get(f"/api/runs/{episode}/timeline")
    assert canary not in detail.text + timeline.text
    assert detail.json()["result"]["reason"] == "FAILURE_REDACTED"
    assert timeline.json()[0]["target"] == "[outside task scope]"


@pytest.fixture
def public_ui(service, tmp_path):
    _, control, _, _, credentials = service
    directory = tmp_path / "ui"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text('<div id="root"></div>')
    (directory / "assets/app.js").write_text("document.title = 'AgentGuard';")
    (directory / "assets/app.css").write_text("body { margin: 0; }")
    (directory / "assets/private.json").write_text('{"secret": "private"}')
    outside = tmp_path / "outside.js"
    outside.write_text("secret")
    (directory / "assets/link.js").symlink_to(outside)
    app = create_app(control, credentials, origin=ORIGIN, ui_directory=directory)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, directory


def test_public_ui_serves_only_compiled_shell_with_strict_csp(public_ui):
    client, _ = public_ui
    for path in ("/", "/assets/app.js", "/assets/app.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        csp = response.headers["content-security-policy"]
        assert "script-src 'self'" in csp
        assert "connect-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert client.head("/").status_code == 200
    assert client.get("/api/identity").status_code == 401
    authenticated = client.get("/api/identity", headers={"Authorization": f"Bearer {OPERATOR}"})
    assert authenticated.status_code == 200
    assert authenticated.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/assets/private.json",
        "/assets/link.js",
        "/assets/unknown.js",
        "/assets/%2e%2e/credentials.json",
        "/assets/%2fapi/identity",
        "/index.html",
        "/api/runs",
    ],
)
def test_public_allowlist_does_not_expose_other_files_or_routes(public_ui, path):
    client, _ = public_ui
    response = client.get(path)
    assert response.status_code == 401
    assert "secret" not in response.text


def test_public_ui_still_rejects_cross_origin_hosts_and_writes(public_ui):
    client, _ = public_ui
    for path in ("/", "/assets/app.js"):
        assert client.get(path, headers={"Host": "attacker.test"}).status_code == 400
        assert client.get(path, headers={"Origin": "https://attacker.test"}).status_code == 403
        assert client.get(path, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert client.post(path, json={}).status_code == 401


def test_static_symlink_swap_is_checked_at_request_time(public_ui, tmp_path):
    client, directory = public_ui
    asset = directory / "assets/app.js"
    asset.unlink()
    outside = tmp_path / "sensitive.js"
    outside.write_text("private contents")
    asset.symlink_to(outside)
    response = client.get("/assets/app.js")
    assert response.status_code == 503
    assert "private contents" not in response.text


def test_unbuilt_ui_has_setup_hint_without_disabling_api_auth(service, tmp_path):
    _, control, _, _, credentials = service
    app = create_app(control, credentials, origin=ORIGIN, ui_directory=tmp_path / "unbuilt")
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/").status_code == 503
        assert "make ui-setup ui-build" in client.get("/").text
        assert client.get("/api/runs").status_code == 401
