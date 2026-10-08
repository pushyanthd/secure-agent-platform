"""Fixed stdlib-only entrypoint. Reads bounded JSON; never evaluates document text."""

import json
import sys

MAX_INPUT = 131072
MAX_OUTPUT = 65536


def compute(request: dict) -> dict:
    if set(request) != {"action", "document", "documents", "tickets"}:
        raise ValueError("request fields")
    action = request["action"]
    if set(action) != {"tool", "arguments"}:
        raise ValueError("action fields")
    args = action["arguments"]
    tool = action["tool"]
    if not isinstance(request["documents"], list) or not isinstance(request["tickets"], list):
        raise ValueError("collection type")
    if tool != "documents.search" and request["documents"]:
        raise ValueError("unexpected documents")
    if tool != "tickets.list" and request["tickets"]:
        raise ValueError("unexpected tickets")
    if tool not in ("documents.read", "shares.request") and request["document"] is not None:
        raise ValueError("unexpected document")
    if tool in ("documents.read", "shares.request"):
        document = request["document"]
        fields = {"document_id"} if tool == "documents.read" else {"document_id", "project_id"}
        if set(args) != fields or set(document) != {"id", "body"}:
            raise ValueError("document fields")
        if args["document_id"] != document["id"]:
            raise ValueError("document target")
        if not isinstance(document["body"], str) or len(document["body"]) > 12000:
            raise ValueError("document body")
        if tool == "shares.request":
            if not isinstance(args["project_id"], str) or not 1 <= len(args["project_id"]) <= 80:
                raise ValueError("share target")
            return {"kind": "share", "arguments": args, "body": document["body"]}
        return {"kind": "document", "document_id": document["id"], "body": document["body"]}
    if tool in ("tickets.create", "tickets.update"):
        fields = {"project_id", "title", "body"}
        if tool == "tickets.update":
            fields |= {"ticket_id", "expected_version"}
            if (
                not isinstance(args["ticket_id"], str)
                or not 1 <= len(args["ticket_id"]) <= 80
                or type(args["expected_version"]) is not int
                or args["expected_version"] < 1
            ):
                raise ValueError("update target")
        if set(args) != fields or request["document"] is not None:
            raise ValueError("ticket fields")
        for name, limit in (("project_id", 80), ("title", 160), ("body", 4000)):
            if not isinstance(args[name], str) or not 1 <= len(args[name]) <= limit:
                raise ValueError("ticket argument")
        return {"kind": "ticket" if tool == "tickets.create" else "update", "arguments": args}
    if tool in ("documents.search", "tickets.list"):
        search = tool == "documents.search"
        field = "query" if search else "project_id"
        if (
            set(args) != {field, "limit"}
            or type(args["limit"]) is not int
            or not 1 <= args["limit"] <= 5
            or not isinstance(args[field], str)
            or not 1 <= len(args[field]) <= (200 if search else 80)
        ):
            raise ValueError("collection arguments")
        name = "documents" if search else "tickets"
        rows = request[name]
        if len(rows) > args["limit"]:
            raise ValueError("collection length")
        sizes = (
            {"document_id": 80, "snippet": 512}
            if search
            else {"ticket_id": 80, "project_id": 80, "title": 160, "body_preview": 512}
        )
        for row in rows:
            if set(row) != {*sizes, "version"}:
                raise ValueError("collection fields")
            if type(row["version"]) is not int or row["version"] < 1:
                raise ValueError("collection version")
            for key, limit in sizes.items():
                if not isinstance(row[key], str) or len(row[key]) > limit:
                    raise ValueError("collection value")
            if not search and row["project_id"] != args["project_id"]:
                raise ValueError("collection target")
        return {"kind": "search" if search else "tickets", name: rows}
    raise ValueError("unknown tool")


def main() -> int:
    try:
        payload = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(payload) > MAX_INPUT:
            raise ValueError("input size")
        output = json.dumps(compute(json.loads(payload)), ensure_ascii=False).encode()
        if len(output) > MAX_OUTPUT:
            raise ValueError("output size")
        sys.stdout.buffer.write(output)
        return 0
    except (ValueError, TypeError, KeyError):
        sys.stderr.write("INVALID_TOOL_REQUEST\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
