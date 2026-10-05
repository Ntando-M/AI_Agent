from __future__ import annotations

import json

import pytest
from langchain_core.messages import HumanMessage

from memory.sqlite_store import (
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


def test_list_is_sorted_by_session_id(store):
    store.add_turn("zebra", "q", "a")
    store.add_turn("alpha", "q", "a")

    ids = [
        summary.session_id
        for summary in store.list_sessions()
    ]

    assert ids == ["alpha", "zebra"]


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
    Creating a session must not make it appear to exist,
    because existence means "has messages".
    """

    store.create_session("fresh")

    assert store.session_exists("fresh") is False


def test_delete_removes_the_session(store):
    store.add_turn("s1", "q", "a")

    assert store.delete_session("s1") is True
    assert store.session_exists("s1") is False
    assert store.get_turns("s1") == []


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