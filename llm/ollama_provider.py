from langchain_ollama import ChatOllama

from models.response_models import AIResponse


OLLAMA_MODEL = "llama3.2:3b"


def get_ollama_llm():

    return ChatOllama(
        model=OLLAMA_MODEL,
        temperature=0
    )


def get_ollama_response(messages):

    llm = get_ollama_llm()

    structured_llm = llm.with_structured_output(
        AIResponse
    )

    response = structured_llm.invoke(
        messages
    )

    return response.model_dump()

def get_ollama_model():
    return OLLAMA_MODEL