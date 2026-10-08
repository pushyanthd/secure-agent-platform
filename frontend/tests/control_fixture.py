"""Out-of-band browser-test driver. Adds no test routes to the application API."""

import json
import sys
from pathlib import Path

from agentguard.control_setup import ControlSettings, initialize_control, prepare_control

root, directory, operation = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
if operation == "init":
    initialize_control(root, directory, fixture=True, port=int(sys.argv[4]))
else:
    settings = ControlSettings.model_validate_json((directory / "settings.json").read_bytes())
    control, worker = prepare_control(settings)
    if operation == "advance":
        result = worker.run_once()
        print(json.dumps({"status": result.get("status") if result else None}))
    elif operation == "change_resource":
        with control.store.connection() as db:
            db.execute(
                "UPDATE resources SET payload=json_set(payload,'$.version',2) "
                "WHERE episode_id=? AND id='shared'",
                (sys.argv[4],),
            )
    elif operation == "expire":
        with control.store.connection() as db:
            db.execute("UPDATE approvals SET expires_at=0 WHERE episode_id=?", (sys.argv[4],))
    elif operation == "hostile":
        # Preserve malicious strings in the returned scope snapshot to exercise DOM escaping.
        with control.store.connection() as db:
            row = db.execute(
                "SELECT id,snapshot FROM approvals WHERE episode_id=?", (sys.argv[4],)
            ).fetchone()
            snapshot = json.loads(row["snapshot"])
            snapshot["action"]["arguments"]["body"] = sys.argv[5]
            db.execute(
                "UPDATE approvals SET snapshot=? WHERE id=?",
                (json.dumps(snapshot), row["id"]),
            )
    elif operation == "count_shares":
        print(json.dumps({"count": len(control.store.shares(sys.argv[4]))}))
    elif operation == "tickets":
        print(json.dumps(control.store.tickets(sys.argv[4])))
    elif operation == "count_tickets":
        with control.store.connection() as db:
            count = db.execute(
                "SELECT count(*) FROM tickets WHERE episode_id=?", (sys.argv[4],)
            ).fetchone()[0]
        print(json.dumps({"count": count}))
    else:
        raise ValueError("Unknown fixture operation")
