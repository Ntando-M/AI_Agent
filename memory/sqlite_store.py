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

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "preview": self.preview,
        }


@dataclass
class Turn:
    """
    One exchange: a question and the answer given to it.
    """

    role: str
    content: str
    created_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
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
    ) -> SessionSummary:
        """
        Create a session.

        Returns the existing summary when the session
        already exists, so creating twice is safe and
        never destroys history.
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
    ) -> None:
        """Append one exchange."""

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
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    MESSAGE_STORE_TABLE.c.session_id,
                    func.count(
                        MESSAGE_STORE_TABLE.c.id
                    ).label("message_count"),
                    func.min(
                        MESSAGE_STORE_TABLE.c.id
                    ).label("first_id"),
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
                .order_by(
                    MESSAGE_STORE_TABLE.c.session_id
                )
            ).fetchall()

        summaries = []

        for row in rows:
            summaries.append(
                SessionSummary(
                    session_id=row.session_id,
                    message_count=int(
                        row.message_count
                    ),
                    preview=self._preview(row.last_id),
                )
            )

        return summaries

    def session_exists(
        self,
        session_id: str,
    ) -> bool:
        with self.engine.connect() as connection:
            result = connection.execute(
                select(MESSAGE_STORE_TABLE.c.id)
                .where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
                .limit(1)
            ).fetchone()

        return result is not None

    def create_session(
        self,
        session_id: str,
    ) -> SessionSummary:
        """
        A session exists once it holds a message.

        A fresh session is represented by its id alone, so
        creating one twice is a no-op rather than an error,
        and creating an existing session never touches its
        history.
        """

        for summary in self.list_sessions():
            if summary.session_id == session_id:
                return summary

        return SessionSummary(
            session_id=session_id,
            message_count=0,
            created_at=self._now(),
            last_activity_at=self._now(),
        )

    def delete_session(
        self,
        session_id: str,
    ) -> bool:
        with self.engine.begin() as connection:
            result = connection.execute(
                delete(MESSAGE_STORE_TABLE).where(
                    MESSAGE_STORE_TABLE.c.session_id
                    == session_id
                )
            )

            return result.rowcount > 0

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
                select(MESSAGE_STORE_TABLE.c.message)
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

            turns.append(
                Turn(
                    role=(
                        "user"
                        if message.type == "human"
                        else "assistant"
                    ),
                    content=str(message.content),
                )
            )

        return turns

    def add_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        history = self._history(session_id)

        history.add_user_message(question)
        history.add_ai_message(answer)