from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import BaseMessage
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    delete,
    func,
    select,
)


DEFAULT_SESSION = "default_session"
SCHEMA_PROBE_SESSION = "__schema_probe__"

# Shown for any conversation the user did not name. A session
# can be created without a name (the CLI does, and so does an
# auto-created chat session), and a raw id such as
# "web-lz4k2p" is not something a reader should have to parse.
DEFAULT_SESSION_NAME = "Untitled conversation"


# LangChain's SQLChatMessageHistory owns this table and its
# exact shape. The API must be able to list and create
# sessions before anything has been written, but LangChain
# creates the table lazily on first write. Declaring the
# same schema here with CREATE IF NOT EXISTS lets the store
# exist standalone, without a throwaway probe row.

MESSAGE_STORE_METADATA = MetaData()

MESSAGE_STORE_TABLE = Table(
    "message_store",
    MESSAGE_STORE_METADATA,
    Column("id", Integer, primary_key=True),
    Column("session_id", Text),
    Column("message", Text),
    # The answer's supporting metadata, as JSON, on the
    # assistant row only. LangChain owns the writes to this
    # table and does not know about this column, so it is
    # declared nullable and populated by a follow-up UPDATE
    # rather than being part of the INSERT.
    Column("evidence", Text, nullable=True),
)

# A session created through the API has no messages yet, so
# it would not appear in a listing derived from
# message_store. The catalog records that a session was
# deliberately created, which is what lets an API client
# create a session and then see it in GET /sessions.
SESSION_CATALOG_TABLE = Table(
    "conversation_session",
    MESSAGE_STORE_METADATA,
    Column("session_id", Text, primary_key=True),
    Column("created_at", Text),
    Column("name", Text, nullable=True),
)


@dataclass
class SessionSummary:
    """
    Metadata about a stored conversation.

    The API needs this to render a session list without
    loading every message of every conversation, so it
    carries only what a list view needs.
    """

    session_id: str
    message_count: int = 0
    created_at: str | None = None
    last_activity_at: str | None = None
    preview: str | None = None
    name: str | None = None

    @property
    def display_name(self) -> str:
        """
        The name to show, never empty.

        A conversation the user did not name falls back to a
        readable label rather than its raw id, so a list
        entry always says something. Whitespace-only names
        count as unnamed.
        """

        if self.name and self.name.strip():
            return self.name.strip()

        return DEFAULT_SESSION_NAME

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "preview": self.preview,
            "name": self.display_name,
        }


@dataclass
class Turn:
    """
    One exchange: a question and the answer given to it.

    `evidence` carries the answer's supporting metadata
    (analysis type, confidence, sources, and the rest) when
    it was recorded. It is optional and defaults to None so
    a turn stored before this existed reads back as
    answer-only rather than as a turn with empty evidence,
    which would misrepresent a known-unknown as a finding of
    zero confidence.
    """

    role: str
    content: str
    created_at: str | None = None
    evidence: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "evidence": self.evidence,
        }


class ConversationStore(ABC):
    """
    The memory interface every surface depends on.

    The CLI and the HTTP API both talk to this, which is
    what makes the engine genuinely shared: adding a
    client does not add a second way to store a
    conversation.

    An abstract base rather than a concrete type, so the
    backend can change without touching callers.
    """

    @abstractmethod
    def list_sessions(self) -> list[SessionSummary]:
        """Every known session, with a short preview."""

    @abstractmethod
    def session_exists(
        self,
        session_id: str,
    ) -> bool:
        """Whether a session has any stored messages."""

    @abstractmethod
    def create_session(
        self,
        session_id: str,
        name: str | None = None,
    ) -> SessionSummary:
        """
        Create a session.

        Returns the existing summary when the session
        already exists, so creating twice is safe and
        never destroys history. A name supplied for an
        existing session updates it, so a conversation can
        be named after it was created.
        """

    @abstractmethod
    def delete_session(
        self,
        session_id: str,
    ) -> bool:
        """
        Remove a session entirely.

        Returns False when the session did not exist, so
        a caller can tell a no-op delete from a real one.
        """

    @abstractmethod
    def get_messages(
        self,
        session_id: str,
    ) -> list[BaseMessage]:
        """
        LangChain messages for a session, in order.

        Returned as message objects because the
        orchestrator consumes them directly.
        """

    @abstractmethod
    def get_turns(
        self,
        session_id: str,
    ) -> list[Turn]:
        """The same conversation as plain Turns."""

    @abstractmethod
    def add_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """
        Append one exchange.

        `evidence` is the answer's supporting metadata. It is
        optional so a caller that has none - the CLI's
        transcript path, a plain answer - can record the
        exchange without inventing evidence for it.
        """

    @abstractmethod
    def clear_session(
        self,
        session_id: str,
    ) -> None:
        """Delete the messages but keep the session."""


def decode_message(
    message_json: str,
) -> BaseMessage | None:
    """
    Rebuild a LangChain message from its stored JSON.

    A row that cannot be decoded returns None rather than
    raising: one unreadable message must not make an
    entire conversation unavailable to the caller.
    """

    try:
        payload = json.loads(message_json)
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    data = payload.get("data") or {}

    content = data.get("content", "")

    if not isinstance(content, str):
        content = str(content)

    message_type = payload.get("type")

    if message_type == "human":
        from langchain_core.messages import (
            HumanMessage,
        )

        return HumanMessage(content=content)

    if message_type == "ai":
        from langchain_core.messages import (
            AIMessage,
        )

        return AIMessage(content=content)

    return None


def decode_evidence(
    evidence_json: str | None,
) -> dict[str, Any] | None:
    """
    Rebuild an answer's evidence from its stored JSON.

    A row written before evidence was recorded has NULL and
    returns None, which is what tells a reader the metadata
    was never captured rather than captured empty.

    Unreadable JSON also returns None: a single corrupt
    evidence value must not make an entire conversation
    unreadable, the same rule decode_message follows.
    """

    if not evidence_json:
        return None

    try:
        payload = json.loads(evidence_json)
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


class SQLiteConversationStore(ConversationStore):
    """
    Conversation memory in SQLite.

    Reads and session management go through SQLAlchemy
    against the same table LangChain's SQLChatMessageHistory
    writes. Writes go through LangChain, so the stored
    format stays exactly what it would have been - this
    store must never be the reason a message becomes
    unreadable to the CLI.

    Methods return or raise cleanly rather than leaking
    SQLAlchemy errors, because the API turns these
    outcomes into HTTP status codes.
    """

    def __init__(
        self,
        database_url: str = "sqlite:///chat_history.db",
    ):
        self.database_url = database_url

        self.engine = create_engine(
            database_url
        )

        MESSAGE_STORE_METADATA.create_all(
            self.engine,
            checkfirst=True,
        )

        self._ensure_name_column()
        self._ensure_evidence_column()

    def _ensure_name_column(self) -> None:
        """
        Add the name column to an existing catalog table.

        create_all only creates missing tables, so a
        chat_history.db written before conversations could be
        named keeps its old three-column catalog. A session
        list must still work against it, so the column is
        added in place. SQLite has no "ADD COLUMN IF NOT
        EXISTS", hence the inspection first.
        """

        self._add_column_if_missing(
            SESSION_CATALOG_TABLE.name,
            "name",
            "TEXT",
        )

    def _ensure_evidence_column(self) -> None:
        """
        Add the evidence column to an existing message table.

        The same problem as the catalog's name column, and
        the same fix: a chat_history.db written before
        answers carried evidence keeps its three-column
        message_store, and every turn in it must still read
        back. Those rows get NULL and restore as answer-only,
        which is the truth about them - they were recorded
        before the evidence existed.

        The column is added to the table LangChain writes,
        which never sets it. That is safe because it is
        nullable and LangChain's INSERT names its columns
        explicitly rather than relying on positional order.
        """

        self._add_column_if_missing(
            MESSAGE_STORE_TABLE.name,
            "evidence",
            "TEXT",
        )

    def _add_column_if_missing(
        self,
        table: str,
        column: str,
        column_type: str,
    ) -> None:
        """
        Add one nullable column to an existing table, once.

        SQLite has no "ADD COLUMN IF NOT EXISTS", so the
        current columns are inspected first. A missing table
        is left alone: create_all owns creating it, and this
        only ever widens a table that is already there.
        """

        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)

        if table not in inspector.get_table_names():
            return

        existing = {
            found["name"]
            for found in inspector.get_columns(table)
        }

        if column in existing:
            return

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN {column} {column_type}"
                )
            )

    # ====================================================
    # INTERNAL
    # ====================================================

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _history(self, session_id: str):
        from langchain_community.chat_message_histories import (
            SQLChatMessageHistory,
        )

        return SQLChatMessageHistory(
            session_id=session_id,
            connection=self.database_url,
        )

    def _preview(
        self,
        last_id: int | None,
    ) -> str | None:
        if last_id is None:
            return None

        with self.engine.connect() as connection:
            row = connection.execute(
                select(MESSAGE_STORE_TABLE.c.message)
                .where(MESSAGE_STORE_TABLE.c.id == last_id)
            ).fetchone()

        if row is None:
            return None

        message = decode_message(row.message)

        if message is None:
            return None

        return str(message.content)[:120]

    # ====================================================
    # SESSIONS
    # ====================================================

    def list_sessions(self) -> list[SessionSummary]:
        """
        Every known session, including empty ones.

        The catalog and the message table are unioned: a
        session created through the API but never used has a
        catalog row and no messages, and dropping it would
        make POST /sessions look like it had failed.
        """

        with self.engine.connect() as connection:
            counted = connection.execute(
                select(
                    MESSAGE_STORE_TABLE.c.session_id,
                    func.count(
                        MESSAGE_STORE_TABLE.c.id
                    ).label("message_count"),
                    func.max(
                        MESSAGE_STORE_TABLE.c.id
                    ).label("last_id"),
                )
                .where(
                    MESSAGE_STORE_TABLE.c.session_id
                    != SCHEMA_PROBE_SESSION
                )
                .group_by(
                    MESSAGE_STORE_TABLE.c.session_id
                )
            ).fetchall()

            catalogued = connection.execute(
                select(SESSION_CATALOG_TABLE.c)
            ).fetchall()

        by_id = {
            row.session_id: {
                "message_count": int(
                    row.message_count
                ),
                "last_id": row.last_id,
                "created_at": None,
                "name": None,
            }
            for row in counted
        }

        for row in catalogued:
            entry = by_id.setdefault(
                row.session_id,
                {
                    "message_count": 0,
                    "last_id": None,
                    "created_at": None,
                    "name": None,
                },
            )

            entry["created_at"] = row.created_at
            entry["name"] = row.name

        # Most recent first. Sessions with messages are
        # ordered by their last message id (higher = more
        # recent), and sessions without messages fall back to
        # their creation time. This puts the conversation you
        # just used at the top of the list.
        def _recency_key(session_id: str) -> tuple:
            entry = by_id[session_id]
            # last_id is the max message id; higher means more
            # recent. Sessions without messages have last_id=None
            # and sort to the end.
            last_id = entry["last_id"] or 0
            created = entry["created_at"] or ""
            return (last_id, created)

        ordered_ids = sorted(
            by_id,
            key=_recency_key,
            reverse=True,
        )

        summaries = []

        for session_id in ordered_ids:
            entry = by_id[session_id]

            summaries.append(
                SessionSummary(
                    session_id=session_id,
                    message_count=entry[
                        "message_count"
                    ],
                    created_at=entry["created_at"],
                    last_activity_at=(
                        self._now()
                        if entry["message_count"]
                        else entry["created_at"]
                    ),
                    preview=self._preview(
                        entry["last_id"]
                    ),
                    name=entry["name"],
                )
            )

        return summaries

    def session_exists(
        self,
        session_id: str,
    ) -> bool:
        """
        Whether the session was created or holds messages.

        Deliberately true for an empty created session: a
        client that was told "created" must be able to read
        it back.
        """

        with self.engine.connect() as connection:
            catalogued = connection.execute(
                select(SESSION_CATALOG_TABLE.c.session_id)
                .where(
                    SESSION_CATALOG_TABLE.c.session_id
                    == session_id
                )
                .limit(1)
            ).fetchone()

            if catalogued is not None:
                return True

            messaged = connection.execute(
                select(MESSAGE_STORE_TABLE.c.id)
                .where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
                .limit(1)
            ).fetchone()

        return messaged is not None

    def create_session(
        self,
        session_id: str,
        name: str | None = None,
    ) -> SessionSummary:
        """
        A session exists once it holds a message.

        A fresh session is represented by its id alone, so
        creating one twice is a no-op rather than an error,
        and creating an existing session never touches its
        history. A name given for an existing session is
        applied, so a conversation can be named after the
        fact; an unnamed re-create leaves the stored name
        alone rather than clearing it.
        """

        cleaned = (
            name.strip()
            if name and name.strip()
            else None
        )

        for summary in self.list_sessions():
            if summary.session_id != session_id:
                continue

            if cleaned is None or cleaned == summary.name:
                return summary

            with self.engine.begin() as connection:
                connection.execute(
                    SESSION_CATALOG_TABLE.update()
                    .where(
                        SESSION_CATALOG_TABLE.c.session_id
                        == session_id
                    )
                    .values(name=cleaned)
                )

            summary.name = cleaned

            return summary

        created_at = self._now()

        with self.engine.begin() as connection:
            connection.execute(
                SESSION_CATALOG_TABLE.insert().values(
                    session_id=session_id,
                    created_at=created_at,
                    name=cleaned,
                )
            )

        return SessionSummary(
            session_id=session_id,
            message_count=0,
            created_at=created_at,
            last_activity_at=created_at,
            name=cleaned,
        )

    def delete_session(
        self,
        session_id: str,
    ) -> bool:
        with self.engine.begin() as connection:
            catalogued = connection.execute(
                delete(SESSION_CATALOG_TABLE).where(
                    SESSION_CATALOG_TABLE.c.session_id
                    == session_id
                )
            )

            messaged = connection.execute(
                delete(MESSAGE_STORE_TABLE).where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
            )

            # An empty created session is still a session, so
            # removing its catalog row counts as a delete.
            return (
                catalogued.rowcount > 0
                or messaged.rowcount > 0
            )

    def clear_session(
        self,
        session_id: str,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                delete(MESSAGE_STORE_TABLE).where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
            )

    # ====================================================
    # MESSAGES
    # ====================================================

    def get_messages(
        self,
        session_id: str,
    ) -> list[BaseMessage]:
        return self._history(
            session_id
        ).messages

    def get_turns(
        self,
        session_id: str,
    ) -> list[Turn]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    MESSAGE_STORE_TABLE.c.message,
                    MESSAGE_STORE_TABLE.c.evidence,
                )
                .where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
                .order_by(MESSAGE_STORE_TABLE.c.id)
            ).fetchall()

        turns = []

        for row in rows:
            message = decode_message(row.message)

            if message is None:
                continue

            is_user = message.type == "human"

            turns.append(
                Turn(
                    role=(
                        "user"
                        if is_user
                        else "assistant"
                    ),
                    content=str(message.content),
                    evidence=(
                        None
                        if is_user
                        else decode_evidence(row.evidence)
                    ),
                )
            )

        return turns

    def add_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """
        Append one exchange, then attach the answer's
        evidence to the row just written.

        The messages go in through LangChain so the stored
        format stays exactly what SQLChatMessageHistory
        would have produced. LangChain cannot set the
        evidence column - it does not know it exists - so
        the value is applied by a follow-up UPDATE against
        the row LangChain just inserted. The write is
        therefore two steps, and the second is why this
        method must not be made concurrent on one session
        without care: it targets the newest assistant row.
        """

        history = self._history(session_id)

        history.add_user_message(question)
        history.add_ai_message(answer)

        if evidence is not None:
            self._attach_evidence(
                session_id,
                evidence,
            )

    def _attach_evidence(
        self,
        session_id: str,
        evidence: dict[str, Any],
    ) -> None:
        """
        Record evidence on the newest assistant row.

        Only the newest: the question and answer were added
        in this call, so the last assistant row is the one
        this exchange produced. Targeting it rather than
        every assistant row keeps an earlier turn's evidence
        intact.
        """

        with self.engine.begin() as connection:
            newest = connection.execute(
                select(func.max(MESSAGE_STORE_TABLE.c.id))
                .where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
            ).scalar()

            if newest is None:
                return

            connection.execute(
                MESSAGE_STORE_TABLE.update()
                .where(
                    MESSAGE_STORE_TABLE.c.id == newest
                )
                .values(
                    evidence=json.dumps(evidence)
                )
            )