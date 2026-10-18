from __future__ import annotations

import json

import pytest
from langchain_core.messages import HumanMessage

from memory.sqlite_store import (
    DEFAULT_SESSION_NAME,
    ConversationStore,
    SQLiteConversationStore,
    decode_message,
)


@pytest.fixture
def store(tmp_path):
    return SQLiteConversationStore(
        database_url=(
            "sqlite:///"
            + str(
                tmp_path / "chat_history.db"
            ).replace("\\", "/")
        )
    )


# ========================================================
# INTERFACE
# ========================================================


def test_store_implements_the_interface(store):
    assert isinstance(
        store,
        ConversationStore,
    )


def test_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ConversationStore()


# ========================================================
# EMPTY DATABASE
# ========================================================


def test_empty_database_lists_nothing(store):
    assert store.list_sessions() == []


def test_empty_database_says_no_sessions(store):
    assert store.session_exists("nope") is False


def test_turns_for_unknown_session_are_empty(store):
    assert store.get_turns("nope") == []


def test_messages_for_unknown_session_are_empty(store):
    assert store.get_messages("nope") == []


# ========================================================
# WRITING AND READING
# ========================================================


def test_add_turn_stores_both_messages(store):
    store.add_turn(
        "s1",
        "What was total revenue?",
        "R274,000.",
    )

    turns = store.get_turns("s1")

    assert len(turns) == 2
    assert turns[0].role == "user"
    assert turns[0].content == (
        "What was total revenue?"
    )
    assert turns[1].role == "assistant"
    assert turns[1].content == "R274,000."


def test_turns_are_returned_in_order(store):
    store.add_turn("s1", "first question", "first")
    store.add_turn("s1", "second question", "second")

    contents = [
        turn.content
        for turn in store.get_turns("s1")
    ]

    assert contents == [
        "first question",
        "first",
        "second question",
        "second",
    ]


def test_messages_are_langchain_objects(store):
    store.add_turn("s1", "question", "answer")

    messages = store.get_messages("s1")

    assert isinstance(messages[0], HumanMessage)


def test_session_exists_after_a_turn(store):
    store.add_turn("s1", "q", "a")

    assert store.session_exists("s1") is True


def test_list_reports_message_count(store):
    store.add_turn("s1", "q", "a")

    summary = store.list_sessions()[0]

    assert summary.session_id == "s1"
    assert summary.message_count == 2


def test_list_previews_the_last_answer(store):
    store.add_turn("s1", "q", "final answer")

    summary = store.list_sessions()[0]

    assert summary.preview == "final answer"


def test_preview_is_truncated(store):
    store.add_turn(
        "s1",
        "q",
        "x" * 500,
    )

    summary = store.list_sessions()[0]

    assert len(summary.preview) == 120


def test_list_is_sorted_most_recent_first(store):
    """
    The conversation list must show the most recently used
    conversation first, not alphabetically by id.
    """

    store.add_turn("alpha", "q", "a")
    store.add_turn("zebra", "q", "a")

    ids = [
        summary.session_id
        for summary in store.list_sessions()
    ]

    # "zebra" was written last, so it is the most recent.
    # Alphabetically this would be ["alpha", "zebra"].
    assert ids == ["zebra", "alpha"]


# ========================================================
# SESSION LIFECYCLE
# ========================================================


def test_create_returns_a_summary(store):
    summary = store.create_session("fresh")

    assert summary.session_id == "fresh"
    assert summary.message_count == 0


def test_create_is_idempotent(store):
    store.add_turn("s1", "q", "a")

    store.create_session("s1")

    assert store.get_turns("s1")


def test_create_never_wipes_history(store):
    store.add_turn("s1", "original", "kept")

    store.create_session("s1")

    contents = [
        turn.content
        for turn in store.get_turns("s1")
    ]

    assert "original" in contents
    assert "kept" in contents


def test_create_on_empty_store_adds_no_message(store):
    """
    Creating a session must not invent conversation
    content, but the session must still be listable.
    """

    store.create_session("fresh")

    assert store.get_turns("fresh") == []


# ========================================================
# CONVERSATION NAMES
# ========================================================


def test_unnamed_session_gets_a_default_name(store):
    """
    A conversation created without a name must still show
    something readable. A raw id such as "web-lz4k2p" is not
    a label a reader should have to parse.
    """

    summary = store.create_session("fresh")

    assert summary.as_dict()["name"] == DEFAULT_SESSION_NAME


def test_named_session_keeps_its_name(store):
    summary = store.create_session(
        "fresh",
        name="Q3 revenue review",
    )

    assert summary.as_dict()["name"] == "Q3 revenue review"

    listed = {
        entry.session_id: entry.as_dict()["name"]
        for entry in store.list_sessions()
    }

    assert listed["fresh"] == "Q3 revenue review"


def test_renaming_an_existing_session(store):
    """
    The rename path. A named create of a session that
    already exists applies the new name - that is what makes
    the one endpoint serve both create and rename.
    """

    store.create_session("s1", name="First name")

    renamed = store.create_session("s1", name="Second name")

    assert renamed.as_dict()["name"] == "Second name"

    listed = {
        entry.session_id: entry.as_dict()["name"]
        for entry in store.list_sessions()
    }

    assert listed["s1"] == "Second name"


def test_renaming_preserves_the_conversation(store):
    """
    A rename must never touch history. Losing messages to a
    rename would be far worse than a stale name.
    """

    store.create_session("s1", name="Before")
    store.add_turn("s1", "q", "a")

    store.create_session("s1", name="After")

    turns = store.get_turns("s1")

    assert len(turns) == 2
    assert turns[0].content == "q"
    assert turns[1].content == "a"


def test_renaming_an_unnamed_session(store):
    """A conversation using the default label can be named."""

    store.create_session("s1")

    assert (
        store.create_session("s1").as_dict()["name"]
        == DEFAULT_SESSION_NAME
    )

    renamed = store.create_session(
        "s1", name="Now named"
    )

    assert renamed.as_dict()["name"] == "Now named"


def test_unnamed_recreate_leaves_the_name_alone(store):
    """
    A blank or absent name must not clear a stored name.

    The rename dialog sends null when its field is empty, so
    if that cleared the name a cancelled-looking edit would
    silently rename the conversation to the default label.
    """

    store.create_session("s1", name="Kept")

    store.create_session("s1")

    assert (
        store.create_session("s1").as_dict()["name"]
        == "Kept"
    )


def test_rename_trims_whitespace(store):
    store.create_session("s1", name="Original")

    renamed = store.create_session(
        "s1", name="   Padded name   "
    )

    assert renamed.as_dict()["name"] == "Padded name"


def test_name_is_trimmed(store):
    summary = store.create_session(
        "fresh",
        name="  Sales by region  ",
    )

    assert summary.as_dict()["name"] == "Sales by region"


def test_whitespace_name_counts_as_unnamed(store):
    summary = store.create_session(
        "fresh",
        name="   ",
    )

    assert summary.as_dict()["name"] == DEFAULT_SESSION_NAME


def test_creating_an_existing_session_can_rename_it(store):
    store.create_session("fresh")

    summary = store.create_session(
        "fresh",
        name="Renamed later",
    )

    assert summary.as_dict()["name"] == "Renamed later"


def test_recreating_without_a_name_preserves_the_stored_name(
    store,
):
    """
    Re-creating a session is how a chat is auto-created on
    first use, so an unnamed re-create must not wipe a name
    the user already chose.
    """

    store.create_session("fresh", name="Kept")

    summary = store.create_session("fresh")

    assert summary.as_dict()["name"] == "Kept"


def test_default_name_survives_a_nameless_catalog(tmp_path):
    """
    A database written before names existed has no name
    column. The store must add it in place and still list
    every session.
    """

    import sqlite3

    path = tmp_path / "legacy.db"

    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE conversation_session ("
        "session_id TEXT PRIMARY KEY, created_at TEXT)"
    )
    connection.execute(
        "INSERT INTO conversation_session "
        "VALUES ('legacy', '2026-01-01T00:00:00+00:00')"
    )
    connection.commit()
    connection.close()

    store = SQLiteConversationStore(
        database_url=(
            "sqlite:///"
            + str(path).replace("\\", "/")
        )
    )

    listed = {
        entry.session_id: entry.as_dict()["name"]
        for entry in store.list_sessions()
    }

    assert listed["legacy"] == DEFAULT_SESSION_NAME

    columns = {
        row[1]
        for row in sqlite3.connect(path).execute(
            "PRAGMA table_info(conversation_session)"
        )
    }

    assert "name" in columns


def test_created_empty_session_is_listed(store):
    """
    An API client that creates a session and then lists
    them must see it. Without this, POST /sessions looks
    like it silently failed.
    """

    store.create_session("fresh")

    ids = [
        summary.session_id
        for summary in store.list_sessions()
    ]

    assert "fresh" in ids


def test_created_empty_session_exists(store):
    store.create_session("fresh")

    assert store.session_exists("fresh") is True


def test_created_empty_session_reports_zero_messages(
    store,
):
    store.create_session("fresh")

    summary = [
        item
        for item in store.list_sessions()
        if item.session_id == "fresh"
    ][0]

    assert summary.message_count == 0


def test_created_session_records_a_creation_time(store):
    store.create_session("fresh")

    summary = store.list_sessions()[0]

    assert summary.created_at is not None


def test_creating_twice_records_one_row(store):
    store.create_session("fresh")
    store.create_session("fresh")

    assert len(store.list_sessions()) == 1


def test_delete_removes_an_empty_session_from_the_list(
    store,
):
    store.create_session("fresh")

    store.delete_session("fresh")

    assert store.list_sessions() == []


def test_session_with_messages_only_is_still_listed(store):
    """
    A session written directly by the CLI has no catalog
    row, and must still appear.
    """

    store.add_turn("cli_session", "q", "a")

    ids = [
        summary.session_id
        for summary in store.list_sessions()
    ]

    assert "cli_session" in ids


def test_catalogued_session_with_messages_is_listed_once(
    store,
):
    store.create_session("both")
    store.add_turn("both", "q", "a")

    matching = [
        summary
        for summary in store.list_sessions()
        if summary.session_id == "both"
    ]

    assert len(matching) == 1
    assert matching[0].message_count == 2


def test_delete_removes_the_session(store):
    store.add_turn("s1", "q", "a")

    assert store.delete_session("s1") is True
    assert store.session_exists("s1") is False
    assert store.get_turns("s1") == []


def test_delete_of_a_catalogued_empty_session(store):
    """
    An empty created session is real, so deleting it is a
    success rather than a 404.
    """

    store.create_session("fresh")

    assert store.delete_session("fresh") is True
    assert store.session_exists("fresh") is False


def test_delete_of_unknown_session_returns_false(store):
    assert store.delete_session("nope") is False


def test_clear_empties_but_does_not_raise(store):
    store.add_turn("s1", "q", "a")

    store.clear_session("s1")

    assert store.get_turns("s1") == []


# ========================================================
# ISOLATION
# ========================================================


def test_sessions_do_not_leak_into_each_other(store):
    store.add_turn("alpha", "alpha question", "alpha answer")
    store.add_turn("beta", "beta question", "beta answer")

    alpha = [
        turn.content
        for turn in store.get_turns("alpha")
    ]

    beta = [
        turn.content
        for turn in store.get_turns("beta")
    ]

    assert "beta question" not in alpha
    assert "alpha question" not in beta


def test_deleting_one_session_keeps_the_other(store):
    store.add_turn("alpha", "q", "a")
    store.add_turn("beta", "q", "a")

    store.delete_session("alpha")

    assert store.session_exists("beta") is True


def test_clearing_one_session_keeps_the_other(store):
    store.add_turn("alpha", "q", "a")
    store.add_turn("beta", "q", "a")

    store.clear_session("alpha")

    assert store.get_turns("beta")


# ========================================================
# LANGCHAIN COMPATIBILITY
# ========================================================


def test_langchain_can_read_what_the_store_wrote(store):
    """
    Writes go through LangChain so the CLI keeps working.
    This proves the two agree on the format.
    """

    store.add_turn("s1", "question", "answer")

    messages = store.get_messages("s1")

    assert len(messages) == 2
    assert messages[0].content == "question"
    assert messages[1].content == "answer"


def test_store_reads_what_langchain_wrote(store):
    from langchain_community.chat_message_histories import (
        SQLChatMessageHistory,
    )

    SQLChatMessageHistory(
        session_id="shared",
        connection=store.database_url,
    ).add_user_message("written by langchain")

    turns = store.get_turns("shared")

    assert turns[0].content == (
        "written by langchain"
    )


# ========================================================
# DECODING
# ========================================================


def test_decode_hand_message():
    payload = json.dumps(
        {
            "type": "human",
            "data": {"content": "hello"},
        }
    )

    message = decode_message(payload)

    assert message.content == "hello"


def test_decode_ai_message():
    payload = json.dumps(
        {
            "type": "ai",
            "data": {"content": "reply"},
        }
    )

    message = decode_message(payload)

    assert message.content == "reply"


def test_decode_rejects_garbage():
    assert decode_message("not json") is None


def test_decode_rejects_unknown_type():
    payload = json.dumps(
        {
            "type": "system",
            "data": {"content": "x"},
        }
    )

    assert decode_message(payload) is None


def test_corrupt_row_does_not_break_the_turns(store):
    """
    One unreadable row must not make the whole
    conversation unavailable.
    """

    store.add_turn("s1", "good question", "good answer")

    with store.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO message_store "
            "(session_id, message) VALUES (?, ?)",
            ("s1", "{corrupt"),
        )

    contents = [
        turn.content
        for turn in store.get_turns("s1")
    ]

    assert "good question" in contents
    assert "good answer" in contents


# ========================================================
# SERIALISATION FOR THE API
# ========================================================


def test_summary_serialises(store):
    store.add_turn("s1", "q", "a")

    payload = store.list_sessions()[0].as_dict()

    assert payload["session_id"] == "s1"
    assert payload["message_count"] == 2


def test_turn_serialises(store):
    store.add_turn("s1", "q", "a")

    payload = store.get_turns("s1")[0].as_dict()

    assert payload["role"] == "user"
    assert payload["content"] == "q"


# ========================================================
# EVIDENCE
# ========================================================


def test_evidence_round_trips_on_the_answer(store):
    """
    The reason evidence is stored at all: a restored turn
    must show the confidence and sources the live turn
    showed, and neither is recoverable from the answer text.
    """

    evidence = {
        "analysis_type": "document",
        "confidence": 0.87,
        "sources": ["strategy.docx"],
    }

    store.add_turn("s1", "q", "a", evidence=evidence)

    turns = store.get_turns("s1")

    assert turns[0].role == "user"
    assert turns[0].evidence is None

    assert turns[1].role == "assistant"
    assert turns[1].evidence == evidence


def test_turn_without_evidence_reads_back_as_none(store):
    """
    A turn recorded before evidence existed - or by a
    caller that had none - must read back as None rather
    than as empty evidence. The two mean different things:
    "not recorded" versus "recorded and empty", and only the
    first should render as answer-only.
    """

    store.add_turn("s1", "q", "a")

    assert store.get_turns("s1")[1].evidence is None


def test_evidence_lands_only_on_its_own_turn(store):
    """
    Attaching evidence targets the newest assistant row, so
    an earlier turn's evidence must survive a later turn.
    """

    store.add_turn(
        "s1", "q1", "a1", evidence={"confidence": 0.1}
    )
    store.add_turn(
        "s1", "q2", "a2", evidence={"confidence": 0.9}
    )

    answers = [
        turn
        for turn in store.get_turns("s1")
        if turn.role == "assistant"
    ]

    assert len(answers) == 2
    assert answers[0].evidence == {"confidence": 0.1}
    assert answers[1].evidence == {"confidence": 0.9}


def test_evidence_does_not_disturb_message_history(store):
    """
    Evidence is attached by a follow-up UPDATE, so the
    LangChain messages the orchestrator reads back must be
    untouched by it.
    """

    store.add_turn(
        "s1", "q", "a", evidence={"confidence": 0.5}
    )

    messages = store.get_messages("s1")

    assert [str(m.content) for m in messages] == ["q", "a"]


def test_corrupt_evidence_does_not_break_the_conversation(
    store, tmp_path
):
    """
    One unreadable evidence value must not make the whole
    conversation unreadable - the same rule decode_message
    follows for messages.
    """

    from sqlalchemy import text

    store.add_turn("s1", "q", "a")

    with store.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE message_store SET evidence = "
                "'{not valid json' WHERE session_id = 's1'"
            )
        )

    turns = store.get_turns("s1")

    assert len(turns) == 2
    assert turns[1].content == "a"
    assert turns[1].evidence is None


def test_evidence_column_is_added_to_an_existing_table(
    tmp_path,
):
    """
    The additive migration. A chat_history.db written before
    evidence existed has a three-column message_store, and
    opening it must widen the table without losing a row -
    that file holds real conversations.
    """

    import sqlite3

    path = tmp_path / "legacy.db"

    connection = sqlite3.connect(path)

    connection.execute(
        "CREATE TABLE message_store ("
        "id INTEGER PRIMARY KEY, "
        "session_id TEXT, "
        "message TEXT)"
    )

    connection.execute(
        "INSERT INTO message_store (session_id, message) "
        "VALUES ('old', ?)",
        (json.dumps({"type": "ai", "data": {"content": "hi"}}),),
    )

    connection.commit()
    connection.close()

    store = SQLiteConversationStore(
        database_url=(
            "sqlite:///" + str(path).replace("\\", "/")
        )
    )

    columns = {
        row[1]
        for row in sqlite3.connect(path).execute(
            "PRAGMA table_info(message_store)"
        )
    }

    assert "evidence" in columns

    turns = store.get_turns("old")

    assert len(turns) == 1
    assert turns[0].content == "hi"
    assert turns[0].evidence is None


def test_reopening_the_store_is_idempotent(tmp_path):
    """
    The migration runs on every construction, so opening the
    same file repeatedly must not fail on an existing column.
    """

    url = (
        "sqlite:///"
        + str(tmp_path / "twice.db").replace("\\", "/")
    )

    SQLiteConversationStore(database_url=url)
    second = SQLiteConversationStore(database_url=url)

    second.add_turn(
        "s1", "q", "a", evidence={"confidence": 1.0}
    )

    assert second.get_turns("s1")[1].evidence == {
        "confidence": 1.0
    }


# ========================================================
# SEPARATE STORE INSTANCES SEE THE SAME DATA
# ========================================================


def test_two_stores_share_one_database(tmp_path):
    url = (
        "sqlite:///"
        + str(
            tmp_path / "shared.db"
        ).replace("\\", "/")
    )

    first = SQLiteConversationStore(
        database_url=url
    )
    second = SQLiteConversationStore(
        database_url=url
    )

    first.add_turn("s1", "q", "a")

    assert second.session_exists("s1") is True
    assert second.get_turns("s1")