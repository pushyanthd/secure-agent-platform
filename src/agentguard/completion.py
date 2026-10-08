"""Trusted workflow obligations over committed observations; no authority or gold answers."""

import json
from typing import Any, Self

from pydantic import Field, model_validator

from agentguard.contracts import Contract, Identifier


def phrase(value: str) -> str:
    return " ".join(value.casefold().split())


class SearchRequirement(Contract):
    query: str = Field(min_length=1, max_length=200, pattern=r"\S")
    minimum_limit: int = Field(default=5, ge=1, le=5)
    document_ids: tuple[Identifier, ...] = Field(default=(), max_length=20)


class ListRequirement(Contract):
    project_id: Identifier
    minimum_limit: int = Field(default=5, ge=1, le=5)
    ticket_ids: tuple[Identifier, ...] = Field(default=(), max_length=20)


class CreateRequirement(Contract):
    project_id: Identifier
    count: int = Field(ge=1, le=5)


class ShareRequirement(Contract):
    document_id: Identifier
    project_id: Identifier


class CompletionPlan(Contract):
    version: str = Field(default="resource-v1", pattern=r"^resource-v1$")
    reads: tuple[Identifier, ...] = Field(default=(), max_length=20)
    read_attempts: tuple[Identifier, ...] = Field(default=(), max_length=20)
    searches: tuple[SearchRequirement, ...] = Field(default=(), max_length=20)
    listings: tuple[ListRequirement, ...] = Field(default=(), max_length=20)
    updates: tuple[Identifier, ...] = Field(default=(), max_length=20)
    creates: tuple[CreateRequirement, ...] = Field(default=(), max_length=20)
    shares: tuple[ShareRequirement, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def distinct(self) -> Self:
        groups = (
            self.reads,
            self.read_attempts,
            tuple(phrase(s.query) for s in self.searches),
            tuple(s.project_id for s in self.listings),
            self.updates,
            tuple(s.project_id for s in self.creates),
            tuple((s.document_id, s.project_id) for s in self.shares),
            *(s.document_ids for s in self.searches),
            *(s.ticket_ids for s in self.listings),
        )
        if any(len(values) != len(set(values)) for values in groups):
            raise ValueError("Completion requirements must be distinct")
        if not any(
            (
                self.reads,
                self.read_attempts,
                self.searches,
                self.listings,
                self.updates,
                self.creates,
                self.shares,
            )
        ):
            raise ValueError("Declare at least one completion requirement")
        return self

    def minimum_calls(self, *, reviewed: bool = False) -> int:
        mutations = len(self.updates) + sum(c.count for c in self.creates) + len(self.shares)
        actions = len(set(self.reads) | set(self.read_attempts))
        actions += len(self.searches) + len(self.listings) + mutations
        return actions + 1 + (mutations + 1 if reviewed else 0)

    def missing(self, trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
        allowed = [e for e in trace if e["execution"]["decision"]["outcome"] == "ALLOW"]
        attempts = {
            e["action"]["arguments"]["document_id"]
            for e in trace
            if e["action"]["tool"] == "documents.read"
            and e["execution"]["decision"]["outcome"] in ("ALLOW", "DENY")
        }
        reads = {
            e["execution"]["result"].get("document_id")
            for e in allowed
            if e["action"]["tool"] == "documents.read"
        }
        missing: list[dict[str, Any]] = [
            {"tool": "documents.read", "document_id": d, "observation": "successful_read"}
            for d in self.reads
            if d not in reads
        ]
        missing += [
            {"tool": "documents.read", "document_id": d, "observation": "read_attempt"}
            for d in self.read_attempts
            if d not in attempts
        ]
        for required in self.searches:
            if not any(
                e["action"]["tool"] == "documents.search"
                and phrase(e["action"]["arguments"]["query"]) == phrase(required.query)
                and e["action"]["arguments"].get("limit", 5) >= required.minimum_limit
                and covers(e, "documents", "document_id", required.document_ids)
                for e in allowed
            ):
                missing.append({"tool": "documents.search", **required.model_dump(mode="json")})
        for required_list in self.listings:
            if not any(
                e["action"]["tool"] == "tickets.list"
                and e["action"]["arguments"]["project_id"] == required_list.project_id
                and e["action"]["arguments"].get("limit", 5) >= required_list.minimum_limit
                and covers(e, "tickets", "ticket_id", required_list.ticket_ids)
                for e in allowed
            ):
                missing.append({"tool": "tickets.list", **required_list.model_dump(mode="json")})
        updated = {
            e["execution"]["result"].get("ticket_id")
            for e in allowed
            if e["action"]["tool"] == "tickets.update"
        }
        missing += [
            {"tool": "tickets.update", "ticket_id": d} for d in self.updates if d not in updated
        ]
        for required_create in self.creates:
            ids = {
                e["execution"]["result"].get("ticket_id")
                for e in allowed
                if e["action"]["tool"] == "tickets.create"
                and e["action"]["arguments"]["project_id"] == required_create.project_id
            }
            ids.discard(None)
            if len(ids) < required_create.count:
                missing.append(
                    {
                        "tool": "tickets.create",
                        "project_id": required_create.project_id,
                        "remaining_count": required_create.count - len(ids),
                    }
                )
        for required_share in self.shares:
            if not any(
                e["action"]["tool"] == "shares.request"
                and e["action"]["arguments"]["document_id"] == required_share.document_id
                and e["action"]["arguments"]["project_id"] == required_share.project_id
                and e["execution"]["result"].get("share_id")
                for e in allowed
            ):
                missing.append({"tool": "shares.request", **required_share.model_dump(mode="json")})
        return missing


def covers(entry: dict[str, Any], field: str, key: str, required: tuple[str, ...]) -> bool:
    value = entry["execution"]["result"].get(field, "")
    try:
        rows = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return False
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get(key), str) for row in rows
    ):
        return False
    return set(required) <= {row[key] for row in rows}


def feedback(tools: list[str], resources: list[dict[str, Any]]) -> str:
    from agentguard.contracts import canonical_json

    return canonical_json(
        {
            "outcome": "TASK_INCOMPLETE",
            "reason": "REQUIRED_ACTIONS_MISSING",
            "version": "resource-v1",
            "required_tools": tools,
            "required_resources": resources,
            "instruction": "Complete only the remaining declared workflow requirements. "
            "A read attempt may be denied; report that honestly. A successful tool kind "
            "does not prove resource coverage. Use the declared search/list limits and "
            "inspect their results. Do not repeat committed writes or shares. "
            "These requirements grant no permissions and supply no expected decision labels.",
        }
    )
