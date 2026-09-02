from dotenv import load_dotenv

import json
import re

from typing import Literal

from pydantic import BaseModel, Field

from groq import Groq

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage
)

from langchain_community.chat_message_histories import (
    SQLChatMessageHistory
)

from sqlalchemy import create_engine, inspect, text


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

DATABASE_URL = "sqlite:///chat_history.db"

DEFAULT_SESSION = "default_session"

MODEL_NAME = "openai/gpt-oss-20b"


# ============================================================
# DATABASE
# ============================================================

engine = create_engine(DATABASE_URL)


# ============================================================
# GROQ CLIENT
# ============================================================

groq_client = Groq()


# ============================================================
# PYDANTIC RESPONSE MODEL
# ============================================================

class AIResponse(BaseModel):
    """
    Defines the structure we expect from the LLM.
    """

    answer: str = Field(
        description="The complete answer to the user's question"
    )

    topic: str = Field(
        description="The main topic of the user's question"
    )

    difficulty: Literal[
        "beginner",
        "intermediate",
        "advanced"
    ] = Field(
        description="The estimated difficulty of the user's question"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="The model's confidence in the answer from 0.0 to 1.0"
    )


# ============================================================
# JSON SCHEMA FOR GROQ
# ============================================================

AI_RESPONSE_SCHEMA = {
    "type": "object",

    "properties": {

        "answer": {
            "type": "string",
            "description": (
                "The complete answer to the user's question"
            )
        },

        "topic": {
            "type": "string",
            "description": (
                "The main topic of the user's question"
            )
        },

        "difficulty": {
            "type": "string",
            "enum": [
                "beginner",
                "intermediate",
                "advanced"
            ],
            "description": (
                "The estimated difficulty of the user's question"
            )
        },

        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": (
                "The model's confidence in the answer "
                "from 0.0 to 1.0"
            )
        }
    },

    "required": [
        "answer",
        "topic",
        "difficulty",
        "confidence"
    ],

    "additionalProperties": False
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a helpful, accurate, and professional AI assistant.

Your job is to answer the user's questions clearly and accurately.

In addition to answering the question, classify the user's question
according to the following fields:

1. topic
   - Identify the primary subject of the user's question.

2. difficulty
   - beginner
   - intermediate
   - advanced

3. confidence
   - A value between 0.0 and 1.0 representing your confidence
     in the accuracy of your answer.

The answer should be useful, practical, and appropriately detailed
for the user's question.

Do not mention the internal JSON structure to the user.
"""


# ============================================================
# SESSION MANAGEMENT
# ============================================================

def get_existing_sessions():
    """
    Retrieve all existing session IDs from SQLite.

    If the message_store table does not exist yet,
    return only the default session.
    """

    inspector = inspect(engine)

    # --------------------------------------------------------
    # First application run
    # --------------------------------------------------------

    if not inspector.has_table("message_store"):
        return [DEFAULT_SESSION]

    # --------------------------------------------------------
    # Retrieve sessions
    # --------------------------------------------------------

    with engine.connect() as connection:

        result = connection.execute(
            text("""
                SELECT DISTINCT session_id
                FROM message_store
                WHERE session_id IS NOT NULL
                ORDER BY session_id
            """)
        )

        sessions = [
            row[0]
            for row in result
        ]

    # --------------------------------------------------------
    # Always include default_session
    # --------------------------------------------------------

    if DEFAULT_SESSION not in sessions:

        sessions.insert(
            0,
            DEFAULT_SESSION
        )

    return sessions


def create_new_session():
    """
    Ask the user for a new session name and convert it
    into a safe session ID.
    """

    while True:

        name = input(
            "\nEnter a name for the new session: "
        ).strip()

        if not name:

            print(
                "[ERROR] Session name cannot be empty."
            )

            continue

        # ----------------------------------------------------
        # Convert name into a safe session ID
        # ----------------------------------------------------

        session_id = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            name
        ).strip("_").lower()

        if not session_id:

            print(
                "[ERROR] Please enter a valid session name."
            )

            continue

        # ----------------------------------------------------
        # Check whether session already exists
        # ----------------------------------------------------

        existing_sessions = get_existing_sessions()

        if session_id in existing_sessions:

            print(
                f"\n[WARNING] Session '{session_id}' "
                f"already exists."
            )

            use_existing = input(
                "Use this existing session? (y/n): "
            ).strip().lower()

            if use_existing == "y":

                return session_id

            continue

        print(
            f"\n[OK] New session created: {session_id}"
        )

        return session_id


def select_session():
    """
    Display all existing sessions and allow the user to:

    1. Select an existing session
    2. Create a new session
    3. Exit
    """

    sessions = get_existing_sessions()

    while True:

        print("\n")
        print("=" * 60)
        print("AI AGENT - SELECT CONVERSATION")
        print("=" * 60)

        print("\nAvailable sessions:")

        # ----------------------------------------------------
        # Existing sessions
        # ----------------------------------------------------

        for index, session in enumerate(
            sessions,
            start=1
        ):

            if session == DEFAULT_SESSION:

                print(
                    f"{index}. {session} "
                    f"(default)"
                )

            else:

                print(
                    f"{index}. {session}"
                )

        # ----------------------------------------------------
        # Additional options
        # ----------------------------------------------------

        create_option = len(sessions) + 1
        exit_option = len(sessions) + 2

        print(
            f"{create_option}. Create new session"
        )

        print(
            f"{exit_option}. Exit"
        )

        print("=" * 60)

        choice = input(
            "Select an option: "
        ).strip()

        # ----------------------------------------------------
        # Validate numeric input
        # ----------------------------------------------------

        try:

            choice = int(choice)

        except ValueError:

            print(
                "\n[ERROR] Please enter a number."
            )

            continue

        # ----------------------------------------------------
        # Existing session
        # ----------------------------------------------------

        if 1 <= choice <= len(sessions):

            selected_session = sessions[
                choice - 1
            ]

            print("\n" + "-" * 60)

            print(
                f"Selected session: "
                f"{selected_session}"
            )

            print("-" * 60)

            return selected_session

        # ----------------------------------------------------
        # Create new session
        # ----------------------------------------------------

        elif choice == create_option:

            return create_new_session()

        # ----------------------------------------------------
        # Exit
        # ----------------------------------------------------

        elif choice == exit_option:

            print(
                "\nGoodbye!"
            )

            return None

        # ----------------------------------------------------
        # Invalid option
        # ----------------------------------------------------

        else:

            print(
                f"\n[ERROR] Please enter a number "
                f"between 1 and {exit_option}."
            )


# ============================================================
# CONVERT LANGCHAIN MESSAGES TO GROQ FORMAT
# ============================================================

def convert_messages(messages):
    """
    Convert LangChain message objects into the format
    expected by the Groq Chat Completions API.
    """

    converted_messages = []

    for message in messages:

        # ----------------------------------------------------
        # System message
        # ----------------------------------------------------

        if isinstance(
            message,
            SystemMessage
        ):

            role = "system"

        # ----------------------------------------------------
        # Human message
        # ----------------------------------------------------

        elif isinstance(
            message,
            HumanMessage
        ):

            role = "user"

        # ----------------------------------------------------
        # AI message
        # ----------------------------------------------------

        elif isinstance(
            message,
            AIMessage
        ):

            role = "assistant"

        # ----------------------------------------------------
        # Ignore unsupported message types
        # ----------------------------------------------------

        else:

            continue

        converted_messages.append(
            {
                "role": role,
                "content": message.content
            }
        )

    return converted_messages


# ============================================================
# CALL GROQ
# ============================================================

def get_ai_response(messages):
    """
    Send the conversation to Groq and return
    a validated Pydantic AIResponse object.
    """

    # --------------------------------------------------------
    # Convert LangChain messages
    # --------------------------------------------------------

    groq_messages = convert_messages(
        messages
    )

    # --------------------------------------------------------
    # Call Groq
    # --------------------------------------------------------

    response = groq_client.chat.completions.create(

        model=MODEL_NAME,

        messages=groq_messages,

        temperature=0,

        response_format={
            "type": "json_schema",

            "json_schema": {

                "name": "ai_response",

                "strict": True,

                "schema": AI_RESPONSE_SCHEMA
            }
        }
    )

    # --------------------------------------------------------
    # Extract JSON content
    # --------------------------------------------------------

    content = response.choices[
        0
    ].message.content

    if not content:

        raise ValueError(
            "Groq returned an empty response."
        )

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    response_data = json.loads(
        content
    )

    # --------------------------------------------------------
    # Validate using Pydantic
    # --------------------------------------------------------

    ai_response = AIResponse.model_validate(
        response_data
    )

    return ai_response


# ============================================================
# DISPLAY RESPONSE
# ============================================================

def display_response(response):
    """
    Display the validated Pydantic response.
    """

    print("\nAI:")
    print(response.answer)

    print("\n" + "-" * 50)

    print(
        f"Topic:       {response.topic}"
    )

    print(
        f"Difficulty:  {response.difficulty}"
    )

    print(
        f"Confidence:  {response.confidence:.2f}"
    )

    print("-" * 50)


# ============================================================
# DISPLAY HISTORY
# ============================================================

def display_history(history):
    """
    Display the current conversation history.
    """

    print("\n")
    print("=" * 60)
    print("CONVERSATION HISTORY")
    print("=" * 60)

    if not history.messages:

        print(
            "\nNo conversation history."
        )

        print("=" * 60)

        return

    for message in history.messages:

        # ----------------------------------------------------
        # User
        # ----------------------------------------------------

        if isinstance(
            message,
            HumanMessage
        ):

            print(
                f"\nYou: {message.content}"
            )

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        elif isinstance(
            message,
            AIMessage
        ):

            print(
                f"\nAI: {message.content}"
            )

    print("\n" + "=" * 60)


# ============================================================
# MAIN CHATBOT
# ============================================================

def main():

    # ========================================================
    # SELECT SESSION
    # ========================================================

    session_id = select_session()

    if session_id is None:

        return

    # ========================================================
    # LOAD SQLITE HISTORY
    # ========================================================

    history = SQLChatMessageHistory(
        session_id=session_id,
        connection=engine
    )

    # ========================================================
    # DISPLAY SESSION INFORMATION
    # ========================================================

    print("\n")
    print("=" * 60)

    print(
        f"Chatbot session: "
        f"{session_id}"
    )

    print("=" * 60)

    if history.messages:

        print(
            f"\n[INFO] Loaded "
            f"{len(history.messages)} "
            f"messages from memory."
        )

    else:

        print(
            "\n[INFO] This is a new conversation."
        )

    # ========================================================
    # COMMANDS
    # ========================================================

    print("\nCommands:")

    print(
        "  /history  - Show conversation history"
    )

    print(
        "  /clear    - Clear current conversation"
    )

    print(
        "  /exit     - Exit chatbot"
    )

    print("=" * 60)

    # ========================================================
    # CHAT LOOP
    # ========================================================

    while True:

        try:

            user_input = input(
                "\nYou: "
            ).strip()

        except KeyboardInterrupt:

            print(
                "\n\nGoodbye!"
            )

            break

        except EOFError:

            print(
                "\n\nGoodbye!"
            )

            break

        # ====================================================
        # EMPTY INPUT
        # ====================================================

        if not user_input:

            continue

        # ====================================================
        # EXIT
        # ====================================================

        if user_input.lower() == "/exit":

            print(
                "\nGoodbye!"
            )

            break

        # ====================================================
        # HISTORY
        # ====================================================

        if user_input.lower() == "/history":

            display_history(
                history
            )

            continue

        # ====================================================
        # CLEAR
        # ====================================================

        if user_input.lower() == "/clear":

            history.clear()

            print(
                "\n[OK] Conversation history cleared."
            )

            continue

        # ====================================================
        # BUILD MESSAGE HISTORY
        # ====================================================

        messages = [

            SystemMessage(
                content=SYSTEM_PROMPT
            )

        ]

        # ----------------------------------------------------
        # Add previous conversation
        # ----------------------------------------------------

        messages.extend(
            history.messages
        )

        # ----------------------------------------------------
        # Add current user message
        # ----------------------------------------------------

        messages.append(
            HumanMessage(
                content=user_input
            )
        )

        # ====================================================
        # CALL AI
        # ====================================================

        print(
            "\n[INFO] Thinking..."
        )

        try:

            ai_response = get_ai_response(
                messages
            )

        # ----------------------------------------------------
        # Groq/API errors
        # ----------------------------------------------------

        except Exception as e:

            print(
                "\n[ERROR] Error communicating "
                "with Groq:"
            )

            print(e)

            continue

        # ====================================================
        # DISPLAY RESPONSE
        # ====================================================

        display_response(
            ai_response
        )

        # ====================================================
        # SAVE USER MESSAGE
        # ====================================================

        history.add_message(
            HumanMessage(
                content=user_input
            )
        )

        # ====================================================
        # SAVE AI MESSAGE
        # ====================================================

        history.add_message(
            AIMessage(
                content=ai_response.answer
            )
        )


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()