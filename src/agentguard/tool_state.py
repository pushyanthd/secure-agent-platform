"""Resolve authoritative resources within a transaction, before tool computation."""

import sqlite3
from dataclasses import dataclass

from agentguard.computation import DocumentSnapshot, SearchHit, TicketPreview, ToolRequest
from agentguard.contracts import (
    Action,
    Decision,
    Document,
    ListAction,
    Profile,
    Project,
    ReadAction,
    SearchAction,
    ShareAction,
    TaskContract,
    Ticket,
    UpdateAction,
)
from agentguard.policy import evaluate


def preview(text: str) -> str:
    return text.encode("utf-8")[:512].decode("utf-8", errors="ignore")


@dataclass(frozen=True)
class ToolState:
    resource: Document | Project | None = None
    ticket: Ticket | None = None
    source: Document | None = None
    collection: tuple[Document | Ticket, ...] = ()
    hits: tuple[SearchHit, ...] = ()

    def decision(
        self,
        *,
        episode_id: str,
        contract: TaskContract,
        profile: Profile,
        action: Action,
        confidential: bool,
    ) -> Decision:
        return evaluate(
            episode_id=episode_id,
            contract=contract,
            profile=profile,
            action=action,
            confidential=confidential,
            resource=self.resource,
            ticket=self.ticket,
            source=self.source,
            collection=self.collection,
        )

    def request(self, action: Action) -> ToolRequest:
        document = self.resource if isinstance(action, ReadAction) else self.source
        return ToolRequest(
            action=action,
            document=DocumentSnapshot(id=document.id, body=document.body)
            if isinstance(document, Document)
            else None,
            documents=self.hits,
            tickets=tuple(
                TicketPreview(
                    ticket_id=t.id,
                    project_id=t.project_id,
                    title=t.title,
                    body_preview=preview(t.body),
                    version=t.version,
                )
                for t in self.collection
                if isinstance(t, Ticket)
            ),
        )

    @property
    def sensitive(self) -> bool:
        resources = (self.resource, self.source, self.ticket, *self.collection)
        return any(
            isinstance(r, (Document, Ticket)) and r.classification == "confidential"
            for r in resources
        )


def resolve(
    db: sqlite3.Connection, episode: str, contract: TaskContract, profile: Profile, action: Action
) -> ToolState:
    def document(identifier: str) -> Document | None:
        row = db.execute(
            "SELECT payload FROM resources WHERE episode_id=? AND kind='document' AND id=?",
            (episode, identifier),
        ).fetchone()
        return Document.model_validate_json(row[0]) if row else None

    if isinstance(action, SearchAction):
        # Quote the complete user query as an FTS phrase: no operators, column selectors,
        # or SQL syntax are accepted. Stable ID ordering never exposes global FTS ranks.
        query = '"' + action.arguments.query.replace('"', '""') + '"'
        rows = db.execute(
            "SELECT r.payload, snippet(documents_fts, 2, '', '', ' … ', 24) AS excerpt "
            "FROM documents_fts JOIN resources r ON r.rowid=documents_fts.rowid "
            "WHERE documents_fts MATCH ? AND r.episode_id=? AND r.kind='document' "
            "ORDER BY r.id",
            (query, episode),
        )
        documents, hits = [], []
        for row in rows:
            doc = Document.model_validate_json(row["payload"])
            if doc.workspace != contract.workspace or (
                profile == "defended"
                and (doc.id not in contract.document_ids or contract.actor not in doc.readers)
            ):
                continue
            documents.append(doc)
            hits.append(
                SearchHit(document_id=doc.id, snippet=preview(row["excerpt"]), version=doc.version)
            )
            if len(hits) == action.arguments.limit:
                break
        return ToolState(collection=tuple(documents), hits=tuple(hits))
    if isinstance(action, ReadAction):
        return ToolState(resource=document(action.arguments.document_id))
    row = db.execute(
        "SELECT payload FROM resources WHERE episode_id=? AND kind='project' AND id=?",
        (episode, action.arguments.project_id),
    ).fetchone()
    project = Project.model_validate_json(row[0]) if row else None
    if isinstance(action, ShareAction):
        return ToolState(resource=project, source=document(action.arguments.document_id))
    if isinstance(action, UpdateAction):
        row = db.execute(
            "SELECT * FROM tickets WHERE episode_id=? AND id=?",
            (episode, action.arguments.ticket_id),
        ).fetchone()
        ticket = Ticket.model_validate({k: row[k] for k in Ticket.model_fields}) if row else None
        return ToolState(resource=project, ticket=ticket)
    if isinstance(action, ListAction):
        rows = db.execute(
            "SELECT * FROM tickets WHERE episode_id=? AND project_id=? "
            "AND workspace=? ORDER BY id LIMIT ?",
            (episode, action.arguments.project_id, contract.workspace, action.arguments.limit),
        )
        return ToolState(
            resource=project,
            collection=tuple(
                Ticket.model_validate({k: row[k] for k in Ticket.model_fields}) for row in rows
            ),
        )
    return ToolState(resource=project)
