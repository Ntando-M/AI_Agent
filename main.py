from pathlib import Path

from config import LLM_PROVIDER
from llm.groq_provider import get_groq_model
from llm.ollama_provider import get_ollama_model
from memory.sqlite_store import (
    DEFAULT_SESSION,
    SQLiteConversationStore,
)
from orchestrator.llm_gateway import LLMGateway
from orchestrator.orchestrator import Orchestrator

DATABASE_URL = "sqlite:///chat_history.db"
DATASET_PATH = "data/sample_sales.xlsx"
ANALYTICS_DATABASE_PATH = "data/sales.db"


# The response system prompt is owned by the orchestrator, so
# every routing path speaks through one contract.


def select_llm_provider() -> str:
    print()
    print("Select LLM provider:")
    print("1. Groq")
    print("2. Ollama")
    print()

    default_provider = LLM_PROVIDER

    while True:
        choice = input(
            f"Enter choice [default: {default_provider}]: "
        ).strip().lower()

        if not choice:
            choice = default_provider

        if choice in {"1", "groq"}:
            provider = "groq"
            break

        if choice in {"2", "ollama"}:
            provider = "ollama"
            break

        print(
            "Invalid selection. Please choose 1, 2, groq, or ollama."
        )

    if provider == "groq":
        model = get_groq_model()
    else:
        model = get_ollama_model()

    print()
    print(f"Selected provider: {provider}")
    print(f"Selected model: {model}")
    print()

    return provider


def create_new_session() -> str:
    print()
    session_id = input(
        "Enter a name for the new session: "
    ).strip()

    if not session_id:
        return DEFAULT_SESSION

    return session_id


def select_session(
    store: SQLiteConversationStore,
) -> str:
    sessions = [
        summary.session_id
        for summary in store.list_sessions()
    ]

    if not sessions:
        print(
            f"No existing sessions found. "
            f"Using '{DEFAULT_SESSION}'."
        )
        return DEFAULT_SESSION

    print()
    print("Existing sessions:")

    for index, session in enumerate(
        sessions,
        start=1,
    ):
        print(f"{index}. {session}")

    print(f"{len(sessions) + 1}. Create new session")
    print()

    while True:
        choice = input(
            "Select a session: "
        ).strip()

        if not choice:
            return sessions[0]

        try:
            selection = int(choice)
        except ValueError:
            print("Please enter a valid number.")
            continue

        if 1 <= selection <= len(sessions):
            return sessions[selection - 1]

        if selection == len(sessions) + 1:
            return create_new_session()

        print("Invalid selection.")


def display_response(
    response: dict,
    visualisations: list[str] | None = None,
) -> None:
    print()
    print("AI:")
    print(response["answer"])
    print()

    if response.get("key_findings"):
        print("Key findings:")
        for finding in response["key_findings"]:
            print(f"- {finding}")
        print()

    if response.get("calculations_performed"):
        print("Calculations performed:")
        for calculation in response[
            "calculations_performed"
        ]:
            print(f"- {calculation}")
        print()

    if response.get("datasets_used"):
        print(
            "Datasets used: "
            f"{', '.join(response['datasets_used'])}"
        )

    if response.get("sources"):
        print(
            "Sources: "
            f"{', '.join(response['sources'])}"
        )

    if visualisations:
        print()
        print("Visualisations:")
        for path in visualisations:
            print(f"- {path}")

    print()
    print(f"Analysis type: {response['analysis_type']}")
    print(f"Confidence: {response['confidence']}")
    print()


def display_session(
    store: SQLiteConversationStore,
    session_id: str,
) -> None:
    turns = store.get_turns(session_id)

    if not turns:
        print()
        print("No conversation history.")
        print()
        return

    print()
    print("Conversation history:")
    print()

    for turn in turns:
        if turn.role == "user":
            print(f"You: {turn.content}")
        else:
            print(f"AI: {turn.content}")

    print()


def main() -> None:
    print("=" * 60)
    print("AI Data Analyst Chatbot")
    print("=" * 60)

    provider = select_llm_provider()

    # The conversation store is the single memory
    # implementation. The CLI and the HTTP API share it,
    # so a session means the same thing in both.
    store = SQLiteConversationStore(
        database_url=DATABASE_URL
    )

    session_id = select_session(store)

    # The CLI chooses the provider; the orchestrator only
    # receives a gateway already bound to it.
    gateway = LLMGateway.build(provider)

    analytics_database_path = None

    if Path(ANALYTICS_DATABASE_PATH).exists():
        analytics_database_path = ANALYTICS_DATABASE_PATH

    orchestrator = Orchestrator(
        gateway=gateway,
        dataset_path=DATASET_PATH,
        database_path=analytics_database_path,
    )

    print(f"Dataset loaded: {DATASET_PATH}")

    if orchestrator.has_database:
        print(
            f"Analytical database: "
            f"{ANALYTICS_DATABASE_PATH}"
        )
    else:
        print(
            f"Analytical database not found at "
            f"{ANALYTICS_DATABASE_PATH}. "
            f"Run scripts/create_sales_database.py to "
            f"create it. SQL tools are disabled."
        )

    for warning in orchestrator.load_warnings:
        print(f"Warning: {warning}")

    print()
    print(f"Session: {session_id}")
    print(f"Provider: {provider}")
    print()
    print("Commands:")
    print("/history - show conversation history")
    print("/clear   - clear current conversation")
    print("/exit    - exit the application")
    print()

    while True:
        try:
            user_input = input("You: ").strip()

        except KeyboardInterrupt:
            print()
            print("Exiting...")
            break

        except EOFError:
            print()
            print("Exiting...")
            break

        if not user_input:
            continue

        if user_input.lower() == "/exit":
            print("Goodbye.")
            break

        if user_input.lower() == "/history":
            display_session(store, session_id)
            continue

        if user_input.lower() == "/clear":
            store.clear_session(session_id)
            print("Conversation history cleared.")
            continue

        try:
            outcome = orchestrator.handle(
                user_input,
                history=store.get_messages(
                    session_id
                ),
            )

        except Exception as exc:
            print()
            print(f"Analysis error: {exc}")
            print()
            continue

        for warning in orchestrator.load_warnings[
            -1:
        ]:
            print(f"Warning: {warning}")

        display_response(
            outcome["response"],
            outcome["visualisations"],
        )

        store.add_turn(
            session_id,
            user_input,
            outcome["response"]["answer"],
        )


if __name__ == "__main__":
    main()