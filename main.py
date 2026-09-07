from dotenv import load_dotenv

from models.response_models import AIResponse

import re

from llm.router import get_llm_response

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage
)

from langchain_community.chat_message_histories import (
    SQLChatMessageHistory
)

from sqlalchemy import create_engine, inspect, text

from config import LLM_PROVIDER

from llm.groq_provider import get_groq_model

from llm.ollama_provider import get_ollama_model

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

DATABASE_URL = "sqlite:///chat_history.db"

DEFAULT_SESSION = "default_session"

# ============================================================
# DATABASE
# ============================================================

engine = create_engine(DATABASE_URL)

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
# LLM Provider MANAGEMENT
# ============================================================
def select_llm_provider():
    """
    Display the LLM provider selection menu.

    The provider configured in .env is used as the default.
    The selected provider and model are displayed before
    the session begins.
    """

    default_provider = LLM_PROVIDER

    # --------------------------------------------------------
    # Validate .env configuration
    # --------------------------------------------------------

    if default_provider not in ("groq", "ollama"):

        print(
            "\n[WARNING] Invalid LLM_PROVIDER in .env:"
            f" '{default_provider}'"
        )

        print(
            "[INFO] Falling back to Groq."
        )

        default_provider = "groq"

    # --------------------------------------------------------
    # Get model names from provider modules
    # --------------------------------------------------------

    groq_model = get_groq_model()
    ollama_model = get_ollama_model()

    default_model = (
        groq_model
        if default_provider == "groq"
        else ollama_model
    )

    # --------------------------------------------------------
    # Display menu
    # --------------------------------------------------------

    print("\n")
    print("=" * 60)
    print("AI DATA ANALYST CHATBOT - SELECT LLM PROVIDER")
    print("=" * 60)

    print(
        f"\nDefault provider: {default_provider.capitalize()}"
    )

    print(
        f"Default model:    {default_model}"
    )

    print("\nAvailable providers:")

    print(
        f"1. Groq   → {groq_model}"
    )

    print(
        f"2. Ollama → {ollama_model}"
    )

    print("3. Exit")

    print("=" * 60)

    # --------------------------------------------------------
    # User selection
    # --------------------------------------------------------

    while True:

        choice = input(
            "Select an option "
            f"[Enter = {default_provider.capitalize()}]: "
        ).strip()

        # ----------------------------------------------------
        # Use .env default
        # ----------------------------------------------------

        if not choice:

            selected_provider = default_provider

            break

        # ----------------------------------------------------
        # Groq
        # ----------------------------------------------------

        if choice == "1":

            selected_provider = "groq"

            break

        # ----------------------------------------------------
        # Ollama
        # ----------------------------------------------------

        if choice == "2":

            selected_provider = "ollama"

            break

        # ----------------------------------------------------
        # Exit
        # ----------------------------------------------------

        if choice == "3":

            print("\nGoodbye!")

            return None

        # ----------------------------------------------------
        # Invalid option
        # ----------------------------------------------------

        print(
            "\n[ERROR] Invalid selection."
        )

        print(
            "Please choose 1, 2, 3, or press Enter "
            "to use the default."
        )

    # --------------------------------------------------------
    # Determine selected model
    # --------------------------------------------------------

    selected_model = (
        groq_model
        if selected_provider == "groq"
        else ollama_model
    )

    # --------------------------------------------------------
    # Display active configuration
    # --------------------------------------------------------

    print(
        f"\n[OK] Using {selected_provider.capitalize()}"
    )

    print(
        f"[OK] Model: {selected_model}"
    )

    return selected_provider

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

# ========================================================
    # SELECT LLM PROVIDER
    # ========================================================

    selected_provider = select_llm_provider()

    if selected_provider is None:

        return

    # ========================================================
    # SELECT SESSION
    # ========================================================

    session_id = select_session()

    if session_id is None:

        return

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
# CALL LLM PROVIDER
# ============================================================
def get_ai_response(provider,messages):
    """
    Get an AI response from the configured provider
    and validate it using the application response model.
    """

    response_data = get_llm_response(
        provider,
        messages
    )

    return AIResponse.model_validate(
        response_data
    )
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
    # SELECT LLM PROVIDER
    # ========================================================

    selected_provider = select_llm_provider()

    if selected_provider is None:

        return 
    
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
                selected_provider,
                messages
            )

        # ----------------------------------------------------
        # LLM_Provider API errors
        # ----------------------------------------------------

        except Exception as e:

            print(
                "\n[ERROR] Error communicating "
                f"with {selected_provider.capitalize()}:"
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