from sqlalchemy import create_engine
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
)

from config import LLM_PROVIDER
from data_analysis.agent import DataAnalysisAgent
from llm.groq_provider import (
    get_groq_model,
    get_groq_response,
    get_groq_raw_response,
)

from llm.ollama_provider import (
    get_ollama_model,
    get_ollama_response,
    get_ollama_raw_response,
)

from llm.router import get_llm_response
from models.response_models import AIResponse
from rag.retriever import (
    retrieve_relevant_chunks,
    format_context_for_prompt,
)

DATABASE_URL = "sqlite:///chat_history.db"
DEFAULT_SESSION = "default_session"
DATASET_PATH = "data/sample_sales.xlsx"


SYSTEM_PROMPT = """
You are a helpful and professional AI assistant.

Answer the user's question accurately and clearly.

When retrieved document context is provided, use it when relevant.
Do not invent information that is not supported by the available
context or conversation.

Your response must contain:
- answer
- topic
- difficulty
- confidence

Difficulty must be one of:
- beginner
- intermediate
- advanced

Confidence must be a value between 0 and 1.
""".strip()


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


def get_existing_sessions() -> list[str]:
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as connection:
            result = connection.exec_driver_sql(
                """
                SELECT DISTINCT session_id
                FROM message_store
                ORDER BY session_id
                """
            )

            return [
                row[0]
                for row in result.fetchall()
            ]

    except Exception:
        return []

    finally:
        engine.dispose()


def create_new_session() -> str:
    print()
    session_id = input(
        "Enter a name for the new session: "
    ).strip()

    if not session_id:
        return DEFAULT_SESSION

    return session_id


def select_session() -> str:
    sessions = get_existing_sessions()

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


def get_ai_response(
    provider: str,
    messages: list,
) -> dict:
    response = get_llm_response(
        provider,
        messages,
    )

    validated_response = AIResponse.model_validate(
        response
    )

    return validated_response.model_dump()


def display_response(response: dict) -> None:
    print()
    print("AI:")
    print(response["answer"])
    print()
    print(f"Topic: {response['topic']}")
    print(f"Difficulty: {response['difficulty']}")
    print(f"Confidence: {response['confidence']}")
    print()


def display_history(history) -> None:
    messages = history.messages

    if not messages:
        print()
        print("No conversation history.")
        print()
        return

    print()
    print("Conversation history:")
    print()

    for message in messages:
        message_type = message.__class__.__name__

        if message_type == "HumanMessage":
            print(f"You: {message.content}")

        elif message_type == "AIMessage":
            print(f"AI: {message.content}")

        else:
            print(f"{message_type}: {message.content}")

    print()


def get_data_analysis_response(
    provider: str,
    agent: DataAnalysisAgent,
    question: str,
) -> dict:
    def planning_llm_function(messages):
        if provider == "groq":
            return get_groq_raw_response(messages)

        return get_ollama_raw_response(messages)

    def final_llm_function(messages):
        return get_ai_response(
            provider,
            messages,
        )

    return agent.analyse(
        question,
        planning_llm_function,
        final_llm_function,
    )


def is_data_analysis_question(
    question: str,
) -> bool:
    analytical_keywords = [
        "dataset",
        "data",
        "rows",
        "columns",
        "revenue",
        "average",
        "mean",
        "median",
        "maximum",
        "minimum",
        "highest",
        "lowest",
        "top",
        "region",
        "product",
        "monthly",
        "month",
        "missing",
        "percentage",
        "statistics",
        "group",
        "sort",
        "filter",
    ]

    question_lower = question.lower()

    return any(
        keyword in question_lower
        for keyword in analytical_keywords
    )


def main() -> None:
    print("=" * 60)
    print("AI Data Analyst Chatbot")
    print("=" * 60)

    provider = select_llm_provider()

    session_id = select_session()

    history = SQLChatMessageHistory(
        session_id=session_id,
        connection=DATABASE_URL,
    )

    try:
        data_analysis_agent = DataAnalysisAgent(
            DATASET_PATH
        )

        print(
            f"Dataset loaded: {DATASET_PATH}"
        )

    except Exception as exc:
        data_analysis_agent = None

        print(
            f"Warning: Data-analysis agent could not "
            f"load the dataset: {exc}"
        )

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
            display_history(history)
            continue

        if user_input.lower() == "/clear":
            history.clear()
            print("Conversation history cleared.")
            continue

        if (
            data_analysis_agent is not None
            and is_data_analysis_question(user_input)
        ):
            try:
                analysis = get_data_analysis_response(
                    provider,
                    data_analysis_agent,
                    user_input,
                )

                response = analysis["response"]

                display_response(response)

                history.add_user_message(
                    user_input
                )

                history.add_ai_message(
                    response["answer"]
                )

                continue

            except Exception as exc:
                print()
                print(
                    f"Data analysis error: {exc}"
                )
                print()

                continue

        try:
            retrieved_chunks = retrieve_relevant_chunks(
                user_input
            )

            context = format_context_for_prompt(
                retrieved_chunks
            )

        except Exception as exc:
            print()
            print(
                f"RAG retrieval warning: {exc}"
            )
            print()

            context = ""

        history_messages = history.messages

        augmented_question = f"""
Use the following retrieved document context when relevant.

Retrieved context:
{context}

User question:
{user_input}
""".strip()

        messages = [
            SystemMessage(
                content=SYSTEM_PROMPT
            ),
            *history_messages,
            HumanMessage(
                content=augmented_question
            ),
        ]

        try:
            response = get_ai_response(
                provider,
                messages,
            )

            display_response(response)

            history.add_user_message(
                user_input
            )

            history.add_ai_message(
                response["answer"]
            )

        except Exception as exc:
            print()
            print(
                f"LLM error: {exc}"
            )
            print()


if __name__ == "__main__":
    main()